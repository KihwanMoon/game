"""행동 실행 — ACT 페이즈가 계획을 실제 변경으로 옮긴다 (TDD §4.1).

**행동 14개를 전부 다룬다.** 처리하지 않는 행동을 조용히 넘기면 규칙이 발동했는데
아무 일도 일어나지 않고, 플레이어는 자기 논리가 틀렸다고 오해한다 — 그것이 P1(실패는
정보다)을 가장 직접적으로 깨뜨리는 방식이다. 아직 만들 수 없는 행동은 그 사실을
로그에 남긴다.
"""

from dataclasses import dataclass, field

from game.app.combat.damage import calculate_damage
from game.app.core.event_log import EventLog, LogEntry
from game.app.grid.geometry import get_manhattan_distance, iter_neighbors
from game.app.grid.vision import VisionGrid, check_line_of_sight, find_cover_positions
from game.app.pathfinding.distance_field import build_distance_field, find_next_step
from game.app.simulation.blast_actions import BlastActionMixin
from game.app.simulation.plan import (
    ATTACK_ACTIONS,
    GUARD_SKILL_ID,
    MELEE_REACH,
    PHASE_ACT,
    SLOW_EVERY,
    STATUS_GUARD,
    STATUS_SLOW,
    EngineConfig,
    PlannedAction,
)
from game.app.simulation.state import Entity, WorldState
from game.app.simulation.support_actions import SupportActionMixin
from game.app.simulation.telegraph import CANCEL_BY_HIT, TelegraphBoard

# **여기서 다시 내보낸다.** 두 상수의 정본은 `plan.py` 로 옮겼지만(규칙 평가와 실행이
# 같은 목록을 봐야 해서), 「행동이 사는 곳」에서 읽어 온 코드가 이미 여럿이다 — 그쪽을
# 전부 고치는 것보다 파사드를 두는 편이 낫다.
__all__ = ["ATTACK_ACTIONS", "MELEE_REACH", "ActionExecutor"]
from game.app.skills.catalog import find_skill
from game.schemas.room import TILE_DOOR, TILE_SPRING, TILE_STAIRS, WALKABLE_TILES

# 퍼센트 기준. 100 이 1.0배다.
PERCENT_BASE = 100

# 어느 방어가 걸렸는지를 상태에 함께 실어야 한다 (지금은 그럴 필요가 없다).

MOVE_ACTIONS = frozenset({"APPROACH", "RETREAT", "MOVE_TO_EXIT", "MOVE_TO_HEAL", "MOVE_TO_COVER"})

# 이 사거리까지는 시야를 묻지 않는다. 인접한 적은 벽 너머에 있을 수 없다.

# 아직 만들 수 없는 행동과 그 사유. 조용히 무시하지 않고 로그로 알린다.
# **W6 통합으로 비었다.** 목록과 record_deferred 를 남겨 두는 것은 규칙표가 부를 수는
# 있으나 실행할 수 없는 행동이 다시 생길 때를 위해서다. 도감도 이 표를 읽어 경고한다.
DEFERRED_ACTIONS: dict[str, str] = {}


# 타일을 목표로 하는 이동. 행동 id 에서 찾을 타일 갈래로.
TILE_MOVE_TARGETS: dict[str, set[int]] = {
    "MOVE_TO_EXIT": {TILE_DOOR, TILE_STAIRS},
    "MOVE_TO_HEAL": {TILE_SPRING},
}


def check_slowed_this_tick(entity: Entity, tick: int) -> bool:
    """둔화 때문에 이번 틱에 못 움직이는가.

    **둔화는 두 틱에 한 칸이다** (GDD §211 의 「이동 2틱 소모」). 없으면 `SLOW` 는 인지
    변수에만 있고 걸어도 아무 일이 없다 — 상태를 거는 스킬이 빈 껍데기가 되는 자리다.

    **틱의 홀짝으로 가른다.** 걸린 시점을 따로 들고 있으면 그것이 세계 상태가 되고 두
    코어가 그 값을 함께 얼려야 한다. 홀짝은 이미 있는 값이라 그럴 필요가 없다 (R5).

    Args:
        entity: 움직이려는 엔티티.
        tick: 지금 틱.

    Returns:
        못 움직이면 True.
    """
    return entity.statuses.get(STATUS_SLOW, 0) > 0 and tick % SLOW_EVERY != 0


@dataclass
class ActionExecutor(SupportActionMixin, BlastActionMixin):
    """계획을 실행하고 결과를 로그에 남긴다."""

    state: WorldState
    log: EventLog
    config: EngineConfig
    # 예고를 등록할 판. 없으면 예고형 광역기가 즉발로 떨어진다 (단독 테스트용).
    telegraphs: TelegraphBoard = field(default_factory=TelegraphBoard)

    def record_missing_executor(self, entity: Entity, plan: PlannedAction) -> None:
        """부를 줄 모르는 스킬을 로그에 남긴다.

        **조용히 사라지는 것이 제일 나쁜 실패다.** `USE_SKILL[X]` 는 `resolve_skill_plan`
        이 `action_id = X` 로 풀어 주는데, X 가 실행기의 어느 갈래에도 안 걸리면 그냥
        끝난다 — 문법 검증도 통과하고(`validator` 는 대상 진영만 본다) 「불가」로도 안
        잡힌다(`check_has_skill` 은 장착만 본다). 오류도 로그도 안 남는다.

        **`USE_SKILL` 로 온 것만 여기 온다.** `_apply_settled` 는 이동 계획에도 불리므로
        (엔진이 루프를 두 번 돈다), 안 가리면 이동마다 이 줄이 붙는다.

        Args:
            entity: 행위자.
            plan: 실행할 수 없던 계획.
        """
        self._record(entity.entity_id, plan, "쓸 줄 모른다 — 실행기가 없다", None)

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

    def _build_grid(self) -> VisionGrid:
        """시야 판정용 격자를 만든다.

        WorldState 를 감싸는 이유는 파괴된 벽(tile_overrides)을 반영하기 위해서다.
        RoomTemplate 을 넘기면 부수기 전 지형으로 판정한다.

        Returns:
            이번 순간의 지형을 읽는 격자.
        """
        return VisionGrid(self.state, self.state.room.width, self.state.room.height)

    def _apply_cooldown(self, entity: Entity, action_id: str) -> None:
        """성공한 행동에 쿨타임을 건다.

        실패한 틱(사거리 밖·대상 없음)에는 걸지 않는다. 헛친 것까지 세면 규칙표를
        고쳐도 발동 간격이 그대로여서 원인을 특정할 수 없다 (P1).

        Args:
            entity: 행위자.
            action_id: 사용한 행동 id.
        """
        ticks = find_skill(self.config.skills, action_id).cooldown
        if ticks > 0:
            entity.cooldowns[action_id] = ticks

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
        if step in occupied:
            # 거리장은 목표 칸을 점유 여부와 무관하게 0 으로 깐다(APPROACH 의 목표가
            # 곧 적이 선 칸이므로 그래야 길이 이어진다). 그 마지막 한 걸음까지 허용하면
            # 두 개체가 한 칸에 겹쳐 적거리 0 이 나오고 RETREAT 이 영영 막힌다.
            self._record(entity.entity_id, plan, f"다음 칸 점유 {step} — 제자리", None)
            return
        entity.position = step
        self._record(entity.entity_id, plan, f"이동 {step}", None)

    def record_deferred(self, entity: Entity, plan: PlannedAction) -> None:
        """아직 실행할 수 없는 행동이라는 사실을 로그에 남긴다.

        Args:
            entity: 행위자.
            plan: 실행하려던 계획.
        """
        reason = DEFERRED_ACTIONS.get(plan.action_id, "사유 미상")
        self._record(entity.entity_id, plan, f"미구현 — {reason}", None)

    def apply_move(self, entity: Entity, plan: PlannedAction) -> None:
        """이동 계열 행동을 실행한다.

        Args:
            entity: 이동할 엔티티.
            plan: 실행할 계획.
        """
        if plan.action_id in DEFERRED_ACTIONS:
            self.record_deferred(entity, plan)
            return
        if check_slowed_this_tick(entity, self.state.tick):
            self._record(entity.entity_id, plan, "둔화 — 이번 틱은 못 움직인다", None)
            return
        # 타일을 목표로 하는 이동들. 표로 두는 이유는 가지가 늘 때마다 return 이 하나씩
        # 늘어 함수가 상한에 닿기 때문이고, 무엇보다 **셋이 같은 모양**이라 그렇다.
        wanted = TILE_MOVE_TARGETS.get(plan.action_id)
        if wanted is not None:
            self._apply_step(entity, self._find_tiles(wanted), plan)
            return
        if plan.action_id == "MOVE_TO_COVER":
            self._apply_cover_move(entity, plan)
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

    def _apply_cover_move(self, entity: Entity, plan: PlannedAction) -> None:
        """모든 적의 시야에서 벗어나는 칸으로 한 칸 간다 (GDD §4.4).

        목표는 벽 자체가 아니라 **그 뒤에 서면 시야가 끊기는 칸**이다. 벽으로 가면
        등을 붙인 채 그대로 노출된다.

        Args:
            entity: 이동할 엔티티.
            plan: 실행 중인 계획.
        """
        # list_hostiles 는 list_actors 순서라 이미 결정론적이다. 집합으로 만들지 않는다 (R5).
        threats = tuple(other.position for other in self.state.list_hostiles(entity))
        goals = find_cover_positions(self._build_grid(), threats, self._list_occupied(entity))
        if entity.position in goals:
            # 목표 거리가 0 이면 find_next_step 이 None 을 돌려줘 "길 막힘" 으로 찍힌다.
            # 이미 숨어 있는 것과 갈 수 없는 것은 다른 사실이다 (P1).
            self._record(entity.entity_id, plan, "이미 엄폐 중", None)
            return
        self._apply_step(entity, goals, plan)

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
        reach = find_skill(self.config.skills, plan.action_id).reach or entity.attack_range
        distance = get_manhattan_distance(entity.position, target.position)
        if distance > reach:
            self._record(entity.entity_id, plan, f"사거리 밖({distance} > {reach}) — 틱 낭비", None)
            return
        # GDD §4.1 — 원거리 공격은 직선 시야가 통할 때만 닿는다. 이것이 없으면
        # 엄폐가 아무것도 막지 못해 MOVE_TO_COVER 가 순손실이 된다.
        if reach > MELEE_REACH and not check_line_of_sight(
            self._build_grid(), entity.position, target.position
        ):
            self._record(entity.entity_id, plan, "시야 없음 — 틱 낭비", None)
            return
        self._apply_strike(entity, target, plan)
        self._apply_cooldown(entity, plan.action_id)

    def apply_damage(
        self,
        target: Entity,
        amount: int,
        phase: str,
        expr: str,
        actor_id: str,
        rule: int | None = None,
    ) -> None:
        """피해를 입히고 로그를 남긴다.

        Args:
            target: 피격자.
            amount: 피해량.
            phase: 발생한 페이즈.
            expr: 로그에 남길 문자열.
            actor_id: 피해를 일으킨 주체. 지형 피해면 피격자 자신이다.
            rule: 이 피해를 일으킨 규칙의 우선순위. 지형 피해처럼 규칙이 없으면 None.
                이것을 빠뜨리면 규칙이 죽인 적이 DEFAULT 의 공으로 집계되어,
                사후 분석이 "어느 규칙이 통했는가" 를 거짓으로 말한다 (P1).
        """
        # 방어 태세는 여기서 본다. 정수 나눗셈이며 내림이다 (R5) — 부동소수를 쓰면
        # 두 코어가 같은 피해에서 갈린다.
        if target.statuses.get(STATUS_GUARD, 0) > 0:
            reduction = find_skill(self.config.skills, GUARD_SKILL_ID).guard_pct
            amount = amount * (PERCENT_BASE - reduction) // PERCENT_BASE
        target.hp = max(0, target.hp - amount)
        # **맞으면 시전이 끊긴다** — 켜 둔 예고만 (설계/5_스킬 §10.2). 「안전한 자리에서
        # 쏘는가」를 규칙표에 묻는 자리이고, 카이팅과 그대로 결합한다. 0 이 아니라 실제로
        # 깎였을 때만 본다 — 방어 태세가 전부 막아 낸 피해로 끊기면 방어가 벌이 된다.
        if amount > 0:
            self.telegraphs.apply_cancel(self.state, self.log, target.entity_id, CANCEL_BY_HIT)
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
                target_id=target.entity_id,
                rule=rule,
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
            if get_manhattan_distance(other.position, target.position) <= MELEE_REACH
        )
        # 스킬 계수(스킬이 정한다)와 스킬위력(개체가 정한다)은 다른 것이다. 곱해서
        # 넘기는 이유는 수식이 계수 하나만 받기 때문이며, 정수 곱 뒤 내림 나눗셈이라
        # 기본값 100 에서는 결과가 한 톨도 바뀌지 않는다 (결정 #51).
        coef_pct = find_skill(self.config.skills, plan.action_id).coef_pct
        amount = calculate_damage(
            attack=entity.attack,
            skill_coef_pct=coef_pct * entity.skill_power_pct // PERCENT_BASE,
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
            rule=plan.rule_index,
        )
