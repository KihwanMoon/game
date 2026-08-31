"""공격이 아닌 행동들 — 소환·회복·포션·방어·대기·플래그.

`actions.py` 에서 갈라 나왔다. 한 파일이 §4 의 400줄 상한을 넘었고, 가르는 선은 책임이다 —
저쪽은 **이동하고 때리는 것**, 이쪽은 **그 밖의 것**이다. 둘의 공통 도구(로그 기록·쿨타임)는
저쪽에 남겨 두고 믹스인으로 얹는다.

한 클래스를 둘로 쪼개지 않은 이유는 엔진이 실행기 하나만 들기 때문이다. 둘로 나누면
엔진이 어느 쪽에 넘길지를 알아야 하고, 그 판단이 늘어날 때마다 엔진이 두꺼워진다.
"""

from game.app.core.event_log import EventLog, LogEntry
from game.app.simulation import abilities
from game.app.simulation.plan import (
    GUARD_SKILL_ID,
    PHASE_ACT,
    STATUS_GUARD,
    EngineConfig,
    PlannedAction,
)
from game.app.simulation.state import Entity, WorldState


class SupportActionMixin:
    """공격이 아닌 행동들. `ActionExecutor` 가 이것을 상속한다.

    아래 다섯은 **구체 클래스가 채우는 것**이고, 여기 적어 두는 이유는 그것이 계약이기
    때문이다 — 적지 않으면 검사기도 사람도 이 믹스인이 무엇에 기대는지 알 수 없고,
    상속 대상을 바꿀 때 무엇이 깨지는지 알 방법이 없다.
    """

    state: WorldState
    config: EngineConfig
    log: EventLog

    def _record(self, actor_id: str, plan: PlannedAction, outcome: str, delta: int | None) -> None:
        """로그 한 줄을 남긴다. 구체 클래스가 구현한다.

        Args:
            actor_id: 행위자 id.
            plan: 실행한 계획.
            outcome: 결과 문구.
            delta: 수치 변화. 없으면 None.
        """
        raise NotImplementedError

    def _apply_cooldown(self, entity: Entity, action_id: str) -> None:
        """성공한 행동에 쿨타임을 건다. 구체 클래스가 구현한다.

        Args:
            entity: 행위자.
            action_id: 사용한 행동 id.
        """
        raise NotImplementedError

    def apply_summon(self, entity: Entity, plan: PlannedAction) -> None:
        """잡몹을 부른다 (GDD §5). 주기는 쿨타임[SUMMON] 이 맡는다.

        Args:
            entity: 소환사.
            plan: 실행할 계획.
        """
        _, outcome = abilities.resolve_summon(self.state, self.config, entity)
        self._record(entity.entity_id, plan, outcome, None)

    def apply_heal(self, entity: Entity, plan: PlannedAction) -> None:
        """아군 하나를 회복한다 (GDD §5). 대상은 셀렉터가 이미 골랐다.

        Args:
            entity: 시전자.
            plan: 실행할 계획.
        """
        healed, outcome = abilities.resolve_heal(self.state, self.config, entity, plan)
        if healed > 0:
            self._apply_cooldown(entity, plan.action_id)
        self._record(entity.entity_id, plan, outcome, healed or None)

    def apply_item(self, entity: Entity, plan: PlannedAction) -> None:
        """소모품을 쓴다 (v6, #54).

        **종류로 갈린다.** `USE_POTION` 은 `USE_ITEM[POTION]` 의 별칭이므로 태그가 없으면
        포션으로 본다 — 저장된 규칙표와 골든이 그 id 를 쓰기 때문이다.

        Args:
            entity: 사용자.
            plan: 실행할 계획.
        """
        kind = plan.item_kind or abilities.ITEM_POTION
        if kind == abilities.ITEM_SCROLL:
            ticks = self.config.skill_guard_ticks.get(GUARD_SKILL_ID, 0)
            held, outcome = abilities.resolve_scroll(entity, ticks)
            self._record(entity.entity_id, plan, outcome, held)
            return
        healed, outcome = abilities.resolve_potion(entity)
        self._record(entity.entity_id, plan, outcome, healed)

    def apply_guard(self, entity: Entity, plan: PlannedAction) -> None:
        """방어 태세를 세운다 (블록 v5, 결정 #16).

        상태에 남은 틱 수로 들어가고 UPKEEP 이 줄인다. 피해 감소는 `apply_damage` 가
        본다 — 감소를 여기서 미리 계산해 두면 그동안 들어온 피해원마다 다르게 적용되고,
        그 차이가 로그에 안 남는다.

        Args:
            entity: 시전자.
            plan: 실행할 계획.
        """
        ticks = self.config.skill_guard_ticks.get(plan.action_id, 0)
        entity.statuses[STATUS_GUARD] = ticks
        percent = self.config.skill_guard_pct.get(plan.action_id, 0)
        self.log.record(
            LogEntry(
                tick=self.state.tick,
                entity_id=entity.entity_id,
                phase=PHASE_ACT,
                expr=plan.expr,
                outcome=f"{plan.action_id} 방어 {percent}% / {ticks}틱",
                rule=plan.rule_index,
                fired=True,
            )
        )
        self._apply_cooldown(entity, plan.action_id)

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
