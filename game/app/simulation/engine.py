"""틱 엔진 — 7페이즈를 고정 순서로 돈다 (TDD §4.1).

UPKEEP → TELEGRAPH → PERCEPTION → DECIDE → ACT → RESOLVE → CLEANUP.

PERCEPTION 과 DECIDE 를 나누는 이유는 동시성 공정성이다. 모든 엔티티가 같은 시점의
세계를 보고 판단해야 하며, 순차 갱신하면 처리 순서가 유리/불리를 만든다. 그래서
DECIDE 는 부작용을 내지 않고 계획만 돌려주며, 실제 변경은 ACT 부터다.
"""

from dataclasses import dataclass, field
from typing import Protocol

from game.app.combat.damage import DamageRules, calculate_damage
from game.app.core.event_log import EventLog, LogEntry
from game.app.grid.geometry import get_manhattan_distance, iter_neighbors
from game.app.pathfinding.distance_field import build_distance_field, find_next_step
from game.app.simulation.perception import PerceptionSnapshot, build_snapshot
from game.app.simulation.state import FACTION_PLAYER, Entity, WorldState
from game.schemas.room import TILE_LAVA, TILE_SPRING, WALKABLE_TILES

PHASE_UPKEEP = "UPKEEP"
PHASE_TELEGRAPH = "TELEGRAPH"
PHASE_PERCEPTION = "PERCEPTION"
PHASE_DECIDE = "DECIDE"
PHASE_ACT = "ACT"
PHASE_RESOLVE = "RESOLVE"
PHASE_CLEANUP = "CLEANUP"

PHASE_ORDER = (
    PHASE_UPKEEP,
    PHASE_TELEGRAPH,
    PHASE_PERCEPTION,
    PHASE_DECIDE,
    PHASE_ACT,
    PHASE_RESOLVE,
    PHASE_CLEANUP,
)

OUTCOME_ONGOING = "ONGOING"
OUTCOME_PLAYER_WIN = "PLAYER_WIN"
OUTCOME_PLAYER_LOSS = "PLAYER_LOSS"
OUTCOME_TIMEOUT = "TIMEOUT"

LAVA_DAMAGE = 3


@dataclass(frozen=True)
class PlannedAction:
    """DECIDE 가 내놓는 계획. 아직 세계를 바꾸지 않았다."""

    entity_id: str
    action_id: str
    target_id: str | None = None
    rule_index: int | None = None
    expr: str = ""


class DecisionPolicy(Protocol):
    """행동 결정기. W2 에서 RuleVM 이 이 자리에 들어온다."""

    def plan_action(
        self, entity: Entity, snapshot: PerceptionSnapshot, state: WorldState
    ) -> PlannedAction:
        """이번 틱의 행동을 정한다. 부작용을 내지 않는다."""
        ...


@dataclass(frozen=True)
class EngineConfig:
    """엔진이 balance.json 에서 받아 쓰는 값들."""

    damage_rules: DamageRules
    kind_types: dict[str, str]
    skill_coef_pct: dict[str, int]
    floor: int = 1
    max_ticks: int = 400
    combat_regen_pct: int = 50


@dataclass
class TickEngine:
    """한 방의 전투를 틱 단위로 진행한다."""

    state: WorldState
    policy: DecisionPolicy
    config: EngineConfig
    log: EventLog = field(default_factory=EventLog)

    def run_upkeep(self) -> None:
        """쿨타임·상태이상 감소, 회복, 타일 피해를 처리한다 (페이즈 1)."""
        in_combat = bool([e for e in self.state.list_actors() if e.faction != FACTION_PLAYER])
        for entity in self.state.list_actors():
            for skill, remaining in entity.cooldowns.items():
                entity.cooldowns[skill] = max(0, remaining - 1)
            for status, remaining in entity.statuses.items():
                entity.statuses[status] = max(0, remaining - 1)
            if self.state.get_tile(*entity.position) == TILE_LAVA:
                self._apply_damage(
                    entity, LAVA_DAMAGE, PHASE_UPKEEP, "용암 위", actor_id=entity.entity_id
                )
            self._apply_regen(entity, in_combat=in_combat)

    def run_telegraph(self) -> None:
        """예고 공격을 진행한다 (페이즈 2).

        Phase 2 W6 산출물이다. 지금은 아무것도 하지 않지만 페이즈 자리는 비워 둔다 —
        나중에 끼워 넣으면 그 앞뒤 페이즈의 순서 전제가 바뀐다.
        """

    def build_perceptions(self) -> dict[str, PerceptionSnapshot]:
        """전 엔티티의 인지 변수를 이 시점에 고정한다 (페이즈 3).

        Returns:
            entity_id 에서 스냅샷으로의 대응표.
        """
        return {
            entity.entity_id: build_snapshot(self.state, entity, self.config.kind_types)
            for entity in self.state.list_actors()
        }

    def plan_actions(self, snapshots: dict[str, PerceptionSnapshot]) -> tuple[PlannedAction, ...]:
        """각 엔티티의 행동을 결정한다 (페이즈 4). 세계를 바꾸지 않는다.

        Args:
            snapshots: PERCEPTION 이 고정한 스냅샷들.

        Returns:
            엔티티별 계획.
        """
        plans = tuple(
            self.policy.plan_action(entity, snapshots[entity.entity_id], self.state)
            for entity in self.state.list_actors()
        )
        # 결정을 매 틱 남긴다. 피해가 난 틱만 기록하면 "왜 그 규칙이 안 떴는지"를
        # 되짚을 수 없고, 그것이 P1(실패는 정보다)의 실현을 막는다. GDD §8.2 가
        # 요구하는 것은 발동 결과가 아니라 평가된 조건의 실제 값이다.
        for plan in plans:
            target = f" @{plan.target_id}" if plan.target_id else ""
            self.log.record(
                LogEntry(
                    tick=self.state.tick,
                    entity_id=plan.entity_id,
                    phase=PHASE_DECIDE,
                    expr=plan.expr,
                    outcome=f"{plan.action_id}{target}",
                    rule=plan.rule_index,
                    fired=True,
                )
            )
        return plans

    def apply_actions(self, plans: tuple[PlannedAction, ...]) -> None:
        """계획을 실제로 실행한다 (페이즈 5). 이동을 먼저, 공격을 나중에 한다.

        Args:
            plans: DECIDE 가 내놓은 계획들.
        """
        order = self._sort_by_initiative(plans)
        for plan in order:
            entity = self.state.entities.get(plan.entity_id)
            if entity is None or not entity.is_alive:
                continue
            if plan.action_id in {"APPROACH", "RETREAT"}:
                self._apply_move(entity, plan)
        for plan in order:
            entity = self.state.entities.get(plan.entity_id)
            if entity is None or not entity.is_alive:
                continue
            if plan.action_id in {"ATTACK", "SKILL_1", "SKILL_2"}:
                self._apply_attack(entity, plan)
            elif plan.action_id == "USE_POTION":
                self._apply_potion(entity, plan)

    def resolve_effects(self) -> None:
        """사망 처리와 타일 상태 갱신 (페이즈 6)."""
        for entity in list(self.state.entities.values()):
            if entity.hp <= 0 and entity.hp != 0:
                entity.hp = 0
        for position, pool in list(self.state.spring_pools.items()):
            if pool <= 0:
                self.state.tile_overrides[position] = 0

    def run_cleanup(self) -> str:
        """승패를 판정한다 (페이즈 7).

        Returns:
            OUTCOME_* 중 하나.
        """
        actors = self.state.list_actors()
        players = [e for e in actors if e.faction == FACTION_PLAYER]
        enemies = [e for e in actors if e.faction != FACTION_PLAYER]
        if not players:
            return OUTCOME_PLAYER_LOSS
        if not enemies:
            return OUTCOME_PLAYER_WIN
        if self.state.tick >= self.config.max_ticks:
            return OUTCOME_TIMEOUT
        return OUTCOME_ONGOING

    def run_tick(self) -> str:
        """7페이즈를 한 바퀴 돈다.

        Returns:
            이번 틱 종료 시점의 승패 판정.
        """
        self.state.tick += 1
        self.run_upkeep()
        self.run_telegraph()
        snapshots = self.build_perceptions()
        plans = self.plan_actions(snapshots)
        self.apply_actions(plans)
        self.resolve_effects()
        return self.run_cleanup()

    # ── 내부 ────────────────────────────────────────────────────────────────

    def _sort_by_initiative(self, plans: tuple[PlannedAction, ...]) -> tuple[PlannedAction, ...]:
        """이동 충돌을 가를 순서를 정한다 (TDD §4.2).

        entity_id 사전순으로 가르면 이름이 앞선 엔티티가 영구히 유리해진다. 그래서
        이니셔티브를 먼저 보고, 동률은 시드 PRNG 로 가른다 — 시드가 같으면 같은 순서다.

        Args:
            plans: 정렬할 계획들.

        Returns:
            실행 순서대로 정렬된 계획들.
        """
        keyed = []
        for plan in plans:
            entity = self.state.entities[plan.entity_id]
            keyed.append((-entity.initiative, self.state.rng.get_uint64(), plan))
        keyed.sort(key=lambda item: (item[0], item[1]))
        return tuple(item[2] for item in keyed)

    def _apply_regen(self, entity: Entity, *, in_combat: bool) -> None:
        """회복을 적용한다. 전투 중에는 감쇠하고 샘은 잔여량을 깎는다 (GDD §7).

        Args:
            entity: 대상.
            in_combat: 전투 중인가.
        """
        tile_regen = 0
        position = entity.position
        if self.state.get_tile(*position) == TILE_SPRING:
            pool = self.state.spring_pools.get(position, 0)
            tile_regen = min(2, pool)
            self.state.spring_pools[position] = pool - tile_regen
        # 전투 중 감쇠는 GDD §7 의 어뷰징 차단이다. 정수 연산이라 regen_base 1 은
        # 전투 중 0 이 된다 — 문서의 0.5 를 내림한 값이며 의도된 결과다.
        regen_pct = self.config.combat_regen_pct if in_combat else 100
        base = entity.regen_base * regen_pct // 100
        healed = min(entity.hp_max - entity.hp, base + tile_regen)
        if healed > 0:
            entity.hp += healed

    def _apply_move(self, entity: Entity, plan: PlannedAction) -> None:
        """한 칸 이동한다. 막히면 제자리이며 그 틱의 행동은 낭비된다 (TDD §4.2).

        Args:
            entity: 이동할 엔티티.
            plan: 이동 계획.
        """
        target = self.state.entities.get(plan.target_id or "")
        if target is None or not target.is_alive:
            return
        occupied = frozenset(
            other.position for other in self.state.list_actors() if other is not entity
        )
        goals: tuple[tuple[int, int], ...] = (target.position,)
        if plan.action_id == "RETREAT":
            goals = tuple(
                pos
                for pos in iter_neighbors(entity.position)
                if self.state.get_tile(*pos) in WALKABLE_TILES
                and pos not in occupied
                and get_manhattan_distance(pos, target.position)
                > get_manhattan_distance(entity.position, target.position)
            )
            if not goals:
                return
        field_map = build_distance_field(self.state, goals, blocked=occupied)
        step = find_next_step(field_map, entity.position)
        if step is not None:
            entity.position = step

    def _apply_attack(self, entity: Entity, plan: PlannedAction) -> None:
        """공격을 적용한다.

        Args:
            entity: 공격자.
            plan: 공격 계획.
        """
        target = self.state.entities.get(plan.target_id or "")
        if target is None or not target.is_alive:
            return
        if get_manhattan_distance(entity.position, target.position) > entity.attack_range:
            self.log.record(
                LogEntry(
                    tick=self.state.tick,
                    entity_id=entity.entity_id,
                    phase=PHASE_ACT,
                    expr=f"{plan.action_id} @{target.entity_id}",
                    outcome="사거리 밖 — 틱 낭비",
                    rule=plan.rule_index,
                    fired=True,
                )
            )
            return
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
        self._apply_damage(
            target,
            amount,
            PHASE_ACT,
            f"{plan.action_id} @{target.entity_id}",
            actor_id=entity.entity_id,
        )

    def _apply_potion(self, entity: Entity, plan: PlannedAction) -> None:
        """포션을 쓴다.

        Args:
            entity: 사용자.
            plan: 사용 계획.
        """
        if entity.potions <= 0:
            return
        entity.potions -= 1
        healed = min(entity.hp_max - entity.hp, entity.hp_max // 2)
        entity.hp += healed
        self.log.record(
            LogEntry(
                tick=self.state.tick,
                entity_id=entity.entity_id,
                phase=PHASE_ACT,
                expr="USE_POTION",
                outcome=f"{entity.entity_id} HP {entity.hp}/{entity.hp_max}",
                rule=plan.rule_index,
                delta=healed,
                fired=True,
            )
        )

    def _apply_damage(
        self, target: Entity, amount: int, phase: str, expr: str, actor_id: str
    ) -> None:
        """피해를 입히고 로그를 남긴다.

        Args:
            target: 피격자.
            amount: 피해량.
            phase: 발생한 페이즈.
            expr: 로그에 남길 조건·행동 문자열.
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
