"""공격이 아닌 행동들 — 소환·회복·포션·방어·대기·플래그.

`actions.py` 에서 갈라 나왔다. 한 파일이 §4 의 400줄 상한을 넘었고, 가르는 선은 책임이다 —
저쪽은 **이동하고 때리는 것**, 이쪽은 **그 밖의 것**이다. 둘의 공통 도구(로그 기록·쿨타임)는
저쪽에 남겨 두고 믹스인으로 얹는다.

한 클래스를 둘로 쪼개지 않은 이유는 엔진이 실행기 하나만 들기 때문이다. 둘로 나누면
엔진이 어느 쪽에 넘길지를 알아야 하고, 그 판단이 늘어날 때마다 엔진이 두꺼워진다.
"""

from collections.abc import Callable

from game.app.core.event_log import EventLog, LogEntry
from game.app.simulation import abilities, scrolls
from game.app.simulation.plan import (
    GUARD_SKILL_ID,
    PHASE_ACT,
    STATUS_GUARD,
    EngineConfig,
    PlannedAction,
)
from game.app.simulation.state import Entity, WorldState
from game.app.skills.catalog import find_skill

# 주문서 태그에서 그것을 푸는 함수로 (2026-09-11). **표로 두는 이유**는 종류가 늘 때
# `apply_item` 의 가지가 늘지 않게 하려는 것이다 — 마법이 `apply_cast` 로 겪은 자리다
# (설계/5_스킬 §10.8): 이름으로 갈리는 실행기는 새 종류가 어느 갈래에도 안 닿는다.
#
# **세계가 아니라 실행기를 받는다.** 화염은 피해를 넣어야 하고, 피해는 `apply_damage`
# 하나를 거쳐야 방어 태세·시전 취소·피격자별 로그가 함께 따라온다 — 직접 HP 를 깎으면
# 그 셋이 조용히 빠지고, 사후 분석의 피해 지도에서 화염이 안 보인다.
ScrollResolver = Callable[["SupportActionMixin", Entity, PlannedAction], tuple[int | None, str]]

SCROLL_RESOLVERS: dict[str, ScrollResolver] = {
    scrolls.ITEM_BLINK: lambda actor, entity, _plan: abilities.resolve_blink(actor.state, entity),
    scrolls.ITEM_FLAME: lambda actor, entity, plan: actor.resolve_flame(entity, plan),
    # 부릅은 세계를 안 읽는다. 시그니처를 맞춰 표에 넣는다 — 표가 갈리면 그때부터
    # 「어느 표에 있더라」를 찾아야 한다.
    scrolls.ITEM_FOCUS: lambda _actor, entity, _plan: abilities.resolve_focus(entity),
}


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

    def apply_damage(
        self,
        target: Entity,
        amount: int,
        phase: str,
        expr: str,
        actor_id: str,
        rule: int | None = None,
    ) -> None:
        """피해를 넣고 로그를 남긴다. 구체 클래스가 구현한다.

        Args:
            target: 피격자.
            amount: 피해량.
            phase: 발생한 페이즈.
            expr: 로그에 남길 문자열.
            actor_id: 피해를 일으킨 주체.
            rule: 이 피해를 일으킨 규칙의 우선순위. 없으면 None.
        """
        raise NotImplementedError

    def resolve_flame(self, entity: Entity, plan: PlannedAction) -> tuple[int | None, str]:
        """화염 주문서 — 예고 없이 둘레를 태운다 (2026-09-11).

        **예고가 없는 것이 이 주문서의 전부다.** 마법은 전부 예고를 쓰므로(설계/5_스킬
        §10) 「비켜설 틈을 안 주는 광역」은 소모품만 할 수 있는 일이고, 대가는 충전 수다.

        **적이 없으면 주문서를 안 태운다.** 빈 허공에 쓴 한 장이 그냥 사라지면, 규칙표를
        고칠 사람에게는 「주문서가 왜 벌써 없지」로만 보인다.

        Args:
            entity: 쓰는 개체.
            plan: 실행할 계획. 피해 로그에 규칙 번호를 싣는다.

        Returns:
            (준 피해 합, 로그 문자열). 못 썼으면 피해가 None 이다.
        """
        victims = abilities.list_flame_victims(self.state, entity)
        if not victims:
            return None, "반경 안에 적 없음 — 틱 낭비"
        if not abilities.remove_item(entity, scrolls.ITEM_FLAME):
            return None, "화염 주문서 없음 — 틱 낭비"
        amount = abilities.read_flame_damage(entity)
        for victim in victims:
            self.apply_damage(
                victim,
                amount,
                PHASE_ACT,
                f"화염 @{victim.entity_id}",
                actor_id=entity.entity_id,
                rule=plan.rule_index,
            )
        return amount * len(victims), f"화염 {len(victims)}명 × {amount}"

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

    def apply_item(self, entity: Entity, plan: PlannedAction, use_tag: str = "") -> None:
        """소모품을 쓴다 (v6, #54).

        **종류로 갈린다.** `USE_POTION` 은 `USE_ITEM[POTION]` 의 별칭이므로 태그가 없으면
        포션으로 본다 — 저장된 규칙표와 골든이 그 id 를 쓰기 때문이다.

        **모르는 종류는 아무것도 안 쓴다.** 예전에는 포션으로 떨어졌는데, 규칙이 가리킨
        것은 그 태그이고 실제로 빠지는 것은 포션이라 **엉뚱한 소모품이 사라졌다.**
        지금은 블록 파라미터가 둘뿐이라 안 걸리지만, 소모품을 하나 늘리는 순간 걸린다.

        Args:
            entity: 사용자.
            plan: 실행할 계획.
            use_tag: 쓸 태그. 비우면 계획이 가리킨 것을 쓴다 — 자리를 안 먹는 호출은
                계획의 행동이 다른 것이므로 여기로 넘긴다 (`plan.FREE_ITEMS`).
        """
        kind = use_tag or plan.item_kind or abilities.ITEM_POTION
        if kind == abilities.ITEM_SCROLL:
            ticks = find_skill(self.config.skills, GUARD_SKILL_ID).guard_ticks
            held, outcome = abilities.resolve_scroll(entity, ticks)
            self._record(entity.entity_id, plan, outcome, held)
            return
        if kind in SCROLL_RESOLVERS:
            amount, outcome = SCROLL_RESOLVERS[kind](self, entity, plan)
            self._record(entity.entity_id, plan, outcome, amount)
            return
        if kind != abilities.ITEM_POTION:
            self._record(entity.entity_id, plan, f"{kind} 쓸 줄 모른다 — 틱 낭비", None)
            return
        healed, outcome = abilities.resolve_potion(entity)
        self._record(entity.entity_id, plan, outcome, healed)

    def apply_guard(self, entity: Entity, plan: PlannedAction, skill_id: str = "") -> None:
        """방어 태세를 세운다 (블록 v5, 결정 #16).

        상태에 남은 틱 수로 들어가고 UPKEEP 이 줄인다. 피해 감소는 `apply_damage` 가
        본다 — 감소를 여기서 미리 계산해 두면 그동안 들어온 피해원마다 다르게 적용되고,
        그 차이가 로그에 안 남는다.

        **이 틱을 안 쓴다** (2026-09-10 결정). 엔진이 행동 고리보다 **앞에서** 부르고,
        그 뒤 개체는 제 할 일을 그대로 한다 — 켜는 데 한 틱을 내던 것이 방벽이 어느
        구간에서도 값을 못 하던 이유였다 (설계/5_스킬 §2.1).

        Args:
            entity: 시전자.
            plan: 실행할 계획. 로그에 규칙 번호와 식을 싣는다.
            skill_id: 켤 스킬. 비우면 계획의 행동 id 를 쓴다 — 자리를 안 먹는 호출은
                계획의 행동이 다른 것이므로 여기로 넘긴다.
        """
        used = skill_id or plan.action_id
        ticks = find_skill(self.config.skills, used).guard_ticks
        entity.statuses[STATUS_GUARD] = ticks
        percent = find_skill(self.config.skills, used).guard_pct
        self.log.record(
            LogEntry(
                tick=self.state.tick,
                entity_id=entity.entity_id,
                phase=PHASE_ACT,
                expr=plan.expr,
                outcome=f"{used} 방어 {percent}% / {ticks}틱",
                rule=plan.rule_index,
                fired=True,
            )
        )
        self._apply_cooldown(entity, used)

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
