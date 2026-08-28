"""행동 실행 — ACT 페이즈가 계획을 실제 변경으로 옮긴다 (TDD §4.1).

**동결된 행동 12개를 전부 다룬다.** 처리하지 않는 행동을 조용히 넘기면 규칙이 발동했는데
아무 일도 일어나지 않고, 플레이어는 자기 논리가 틀렸다고 오해한다 — 그것이 P1(실패는
정보다)을 가장 직접적으로 깨뜨리는 방식이다. 아직 만들 수 없는 행동은 그 사실을
로그에 남긴다.
"""

from dataclasses import dataclass

from game.app.combat.damage import calculate_damage
from game.app.core.event_log import EventLog, LogEntry
from game.app.grid.geometry import get_manhattan_distance, iter_neighbors
from game.app.pathfinding.distance_field import build_distance_field, find_next_step
from game.app.simulation.plan import PHASE_ACT, EngineConfig, PlannedAction
from game.app.simulation.state import Entity, WorldState
from game.schemas.room import TILE_DOOR, TILE_SPRING, TILE_STAIRS, WALKABLE_TILES

MOVE_ACTIONS = frozenset({"APPROACH", "RETREAT", "MOVE_TO_EXIT", "MOVE_TO_HEAL", "MOVE_TO_COVER"})
ATTACK_ACTIONS = frozenset({"ATTACK", "SKILL_1", "SKILL_2"})
AREA_ATTACK_RADIUS = 2

# 아직 만들 수 없는 행동과 그 사유. 조용히 무시하지 않고 로그로 알린다.
DEFERRED_ACTIONS = {"MOVE_TO_COVER": "Phase 2 W6 — 엄폐·LOS 미구현"}


@dataclass
class ActionExecutor:
    """계획을 실행하고 결과를 로그에 남긴다."""

    state: WorldState
    log: EventLog
    config: EngineConfig

    def _record(self, actor_id: str, plan: PlannedAction, outcome: str, delta: int | None) -> None:
        """실행 결과를 남긴다.

        Args:
            actor_id: 행위자 id.
            plan: 실행한 계획.
            outcome: 결과 설명.
            delta: 수치 변화. 없으면 None.
        """
        target = f" @{plan.target_id}" if plan.target_id else ""
        self.log.record(
            LogEntry(
                tick=self.state.tick,
                entity_id=actor_id,
                phase=PHASE_ACT,
                expr=f"{plan.action_id}{target}",
                outcome=outcome,
                rule=plan.rule_index,
                delta=delta,
                fired=True,
            )
        )

    def _list_occupied(self, entity: Entity) -> frozenset[tuple[int, int]]:
        """자기 자신을 뺀 다른 엔티티들이 서 있는 칸.

        Args:
            entity: 기준 엔티티.

        Returns:
            점유된 좌표 집합.
        """
        return frozenset(
            other.position for other in self.state.list_actors() if other is not entity
        )

    def _find_tiles(self, kinds: set[int]) -> tuple[tuple[int, int], ...]:
        """방에서 해당 종류의 타일 좌표를 모은다.

        Args:
            kinds: 찾을 타일 ID 집합.

        Returns:
            좌표들. 없으면 빈 튜플.
        """
        return tuple(
            (x, y)
            for y in range(self.state.room.height)
            for x in range(self.state.room.width)
            if self.state.get_tile(x, y) in kinds
        )

    def _apply_step(
        self, entity: Entity, goals: tuple[tuple[int, int], ...], plan: PlannedAction
    ) -> None:
        """목표들 쪽으로 한 칸 간다. 막히면 제자리이며 그 틱은 낭비된다 (TDD §4.2).

        Args:
            entity: 이동할 엔티티.
            goals: 목표 좌표들.
            plan: 실행 중인 계획.
        """
        if not goals:
            self._record(entity.entity_id, plan, "목표 없음 — 틱 낭비", None)
            return
        occupied = self._list_occupied(entity)
        field_map = build_distance_field(self.state, goals, blocked=occupied)
        step = find_next_step(field_map, entity.position)
        if step is None:
            self._record(entity.entity_id, plan, "길 막힘 — 틱 낭비", None)
            return
        entity.position = step
        self._record(entity.entity_id, plan, f"이동 {step}", None)

    def apply_move(self, entity: Entity, plan: PlannedAction) -> None:
        """이동 계열 행동을 실행한다.

        Args:
            entity: 이동할 엔티티.
            plan: 실행할 계획.
        """
        reason = DEFERRED_ACTIONS.get(plan.action_id)
        if reason is not None:
            self._record(entity.entity_id, plan, f"미구현 — {reason}", None)
            return
        if plan.action_id == "MOVE_TO_EXIT":
            self._apply_step(entity, self._find_tiles({TILE_DOOR, TILE_STAIRS}), plan)
            return
        if plan.action_id == "MOVE_TO_HEAL":
            self._apply_step(entity, self._find_tiles({TILE_SPRING}), plan)
            return

        target = self.state.entities.get(plan.target_id or "")
        if target is None or not target.is_alive:
            self._record(entity.entity_id, plan, "대상 없음 — 틱 낭비", None)
            return
        if plan.action_id == "APPROACH":
            self._apply_step(entity, (target.position,), plan)
            return
        occupied = self._list_occupied(entity)
        here = get_manhattan_distance(entity.position, target.position)
        away = tuple(
            pos
            for pos in iter_neighbors(entity.position)
            if self.state.get_tile(*pos) in WALKABLE_TILES
            and pos not in occupied
            and get_manhattan_distance(pos, target.position) > here
        )
        self._apply_step(entity, away, plan)

    def apply_attack(self, entity: Entity, plan: PlannedAction) -> None:
        """단일 대상 공격을 실행한다.

        Args:
            entity: 공격자.
            plan: 실행할 계획.
        """
        target = self.state.entities.get(plan.target_id or "")
        if target is None or not target.is_alive:
            self._record(entity.entity_id, plan, "대상 없음 — 틱 낭비", None)
            return
        reach = self.config.skill_range.get(plan.action_id) or entity.attack_range
        distance = get_manhattan_distance(entity.position, target.position)
        if distance > reach:
            self._record(entity.entity_id, plan, f"사거리 밖({distance} > {reach}) — 틱 낭비", None)
            return
        self._apply_strike(entity, target, plan)

    def apply_area_attack(self, entity: Entity, plan: PlannedAction) -> None:
        """반경 안의 적 전체를 친다.

        Args:
            entity: 공격자.
            plan: 실행할 계획.
        """
        victims = [
            other
            for other in self.state.list_hostiles(entity)
            if get_manhattan_distance(entity.position, other.position) <= AREA_ATTACK_RADIUS
        ]
        if not victims:
            self._record(entity.entity_id, plan, "반경 안에 적 없음 — 틱 낭비", None)
            return
        for victim in victims:
            self._apply_strike(entity, victim, plan)

    def apply_potion(self, entity: Entity, plan: PlannedAction) -> None:
        """포션을 쓴다.

        Args:
            entity: 사용자.
            plan: 실행할 계획.
        """
        if entity.potions <= 0:
            self._record(entity.entity_id, plan, "포션 없음 — 틱 낭비", None)
            return
        entity.potions -= 1
        healed = min(entity.hp_max - entity.hp, entity.hp_max // 2)
        entity.hp += healed
        self._record(entity.entity_id, plan, f"HP {entity.hp}/{entity.hp_max}", healed)

    def apply_hold(self, entity: Entity, plan: PlannedAction) -> None:
        """의도적으로 아무것도 하지 않는다. 무시와 구분하기 위해 로그는 남긴다.

        Args:
            entity: 대상.
            plan: 실행할 계획.
        """
        self._record(entity.entity_id, plan, "대기", None)

    def apply_flag(self, entity: Entity, plan: PlannedAction) -> None:
        """규칙이 지정한 플래그를 세우거나 내린다 (GDD §3.5).

        Args:
            entity: 대상 엔티티.
            plan: 실행 중인 계획.
        """
        if plan.set_flag is None:
            return
        name, _, raw = plan.set_flag.partition("=")
        entity.flags[name.strip()] = raw.strip().lower() != "false"

    def apply_damage(
        self, target: Entity, amount: int, phase: str, expr: str, actor_id: str
    ) -> None:
        """피해를 입히고 로그를 남긴다.

        Args:
            target: 피격자.
            amount: 피해량.
            phase: 발생한 페이즈.
            expr: 로그에 남길 문자열.
            actor_id: 피해를 일으킨 주체. 지형 피해면 피격자 자신이다.
        """
        target.hp = max(0, target.hp - amount)
        self.log.record(
            LogEntry(
                tick=self.state.tick,
                entity_id=actor_id,
                phase=phase,
                expr=expr,
                outcome=(
                    f"{target.entity_id} HP {target.hp}/{target.hp_max}"
                    + ("" if target.is_alive else " 사망")
                ),
                delta=-amount,
                fired=True,
            )
        )

    def _apply_strike(self, entity: Entity, target: Entity, plan: PlannedAction) -> None:
        """한 대상에게 피해를 계산해 넣는다.

        Args:
            entity: 공격자.
            target: 피격자.
            plan: 실행 중인 계획.
        """
        adjacent = sum(
            1
            for other in self.state.list_hostiles(target)
            if get_manhattan_distance(other.position, target.position) <= 1
        )
        amount = calculate_damage(
            attack=entity.attack,
            skill_coef_pct=self.config.skill_coef_pct.get(plan.action_id, 100),
            defense=target.defense,
            floor=self.config.floor,
            adjacent_enemies=adjacent,
            rules=self.config.damage_rules,
        )
        self.apply_damage(
            target,
            amount,
            PHASE_ACT,
            f"{plan.action_id} @{target.entity_id}",
            actor_id=entity.entity_id,
        )
