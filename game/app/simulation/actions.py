"""행동 실행 — ACT 페이즈가 계획을 실제 변경으로 옮긴다 (TDD §4.1).

**행동 14개를 전부 다룬다.** 처리하지 않는 행동을 조용히 넘기면 규칙이 발동했는데
아무 일도 일어나지 않고, 플레이어는 자기 논리가 틀렸다고 오해한다 — 그것이 P1(실패는
정보다)을 가장 직접적으로 깨뜨리는 방식이다. 아직 만들 수 없는 행동은 그 사실을
로그에 남긴다.
"""

from dataclasses import dataclass, field

from game.app.combat.damage import calculate_damage
from game.app.core.event_log import EventLog, LogEntry
from game.app.grid.geometry import get_manhattan_distance
from game.app.grid.vision import VisionGrid, check_line_of_sight
from game.app.simulation.blast_actions import BlastActionMixin
from game.app.simulation.movement import MoveActionMixin
from game.app.simulation.plan import (
    ATTACK_ACTIONS,
    GUARD_SKILL_ID,
    MELEE_REACH,
    PHASE_ACT,
    STATUS_GUARD,
    EngineConfig,
    PlannedAction,
)
from game.app.simulation.scrolls import read_reach
from game.app.simulation.slow import check_slowed_this_tick
from game.app.simulation.state import Entity, WorldState
from game.app.simulation.support_actions import SupportActionMixin
from game.app.simulation.telegraph import CANCEL_BY_HIT, TelegraphBoard

# **여기서 다시 내보낸다.** 두 상수의 정본은 `plan.py` 로 옮겼지만(규칙 평가와 실행이
# 같은 목록을 봐야 해서), 「행동이 사는 곳」에서 읽어 온 코드가 이미 여럿이다 — 그쪽을
# 전부 고치는 것보다 파사드를 두는 편이 낫다.
__all__ = ["ATTACK_ACTIONS", "MELEE_REACH", "ActionExecutor"]
from game.app.skills.catalog import find_skill

# 퍼센트 기준. 100 이 1.0배다.
PERCENT_BASE = 100

# 어느 방어가 걸렸는지를 상태에 함께 실어야 한다 (지금은 그럴 필요가 없다).

MOVE_ACTIONS = frozenset({"APPROACH", "RETREAT", "MOVE_TO_EXIT", "MOVE_TO_HEAL", "MOVE_TO_COVER"})

# 이 사거리까지는 시야를 묻지 않는다. 인접한 적은 벽 너머에 있을 수 없다.


@dataclass
class ActionExecutor(SupportActionMixin, BlastActionMixin, MoveActionMixin):
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

    def _record(
        self,
        actor_id: str,
        plan: PlannedAction,
        outcome: str,
        delta: int | None,
        expr: str = "",
    ) -> None:
        """실행 결과를 남긴다.

        Args:
            actor_id: 행위자 id.
            plan: 실행한 계획.
            outcome: 결과 설명.
            delta: 수치 변화. 없으면 None.
            expr: 왼쪽에 적을 식. 비우면 `행동 @대상` 이다.

                **계획의 `expr` 을 자동으로 쓰지 않는다.** 거기에는 규칙의 조건식이
                들어 있어, 갈아 끼우면 모든 행동의 로그 모양이 바뀌고 저장된 분석이
                갈린다. 조건 발동처럼 **적을 사유가 따로 있는 자리**만 넘긴다.
        """
        target = f" @{plan.target_id}" if plan.target_id else ""
        self.log.record(
            LogEntry(
                tick=self.state.tick,
                entity_id=actor_id,
                phase=PHASE_ACT,
                expr=expr or f"{plan.action_id}{target}",
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

        **예고를 쓰는 스킬에만 유물의 대가가 붙는다** (설계/5_스킬 §10.7). 반경을 넓히는
        유물이 평타 간격까지 늘리면 그것은 마법의 대가가 아니라 캐릭터의 벌이 되고,
        쿨타임 0 인 행동에 8 이 붙으면 평타가 8틱에 한 번이 된다.

        Args:
            entity: 행위자.
            action_id: 사용한 행동 id.
        """
        skill = find_skill(self.config.skills, action_id)
        ticks = skill.cooldown
        if skill.telegraph > 0:
            ticks += entity.cast_cooldown_add
        if ticks > 0:
            entity.cooldowns[action_id] = ticks

    def record_rest(self, entity: Entity, plan: PlannedAction) -> bool:
        """둔화로 이번 틱을 쉬는가 — 쉬면 적고 True 를 돌려준다.

        **이동만이 아니라 행동 전체다** (2026-09-10 결정). 예전에는 이동 경로에서만
        봤고, 그래서 `SLOW` 는 **안 움직여도 때리는 사격형에게 아무 효과가 없었다** —
        이미 붙은 돌진형에게도 없었다. 서리 장판이 피해 0 으로는 어느 표에서도 값을
        못 한 원인이 그것이었다 (설계/5_스킬 §10.10).

        **시전은 안 끊긴다.** 쉬는 틱은 아무 행동도 안 한 틱이고, 예고를 끊는 것은
        「다른 행동을 했다」는 사실이다 (§10.3).

        Args:
            entity: 행위자.
            plan: 이번 틱의 계획. 로그에 무엇을 하려 했는지 남긴다.

        Returns:
            쉬면 True. 그때 부르는 쪽은 그 계획을 실행하지 않는다.
        """
        if not check_slowed_this_tick(entity, self.state.tick):
            return False
        self._record(entity.entity_id, plan, "둔화 — 이번 틱은 쉰다", None)
        return True

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
        reach = find_skill(self.config.skills, plan.action_id).reach or read_reach(entity)
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
