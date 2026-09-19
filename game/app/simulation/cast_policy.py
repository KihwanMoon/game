"""시전 규율이 규칙표를 대신하는 자리 (설계/5_스킬 §10.3).

`engine.py` 에서 갈라 나왔다. 파일이 400줄 상한을 넘은 것이 계기였을 뿐, **가르는 선은
책임이다** (§4) — 저쪽은 「틱이 어떤 순서로 도는가」이고 여기는 「시전 중인 엔티티가
이번 틱에 무엇을 할 수 있는가」다. `slow.py` 를 `actions.py` 에서 뗀 것과 같은 결이다.

**규칙 VM 에 두지 않는 이유.** 예고를 모르는 정책도 있다 — 폴백·봇·검사용 더미가 그렇다.
VM 에 두면 그것들이 같은 규율을 각자 다시 구현해야 하고, 하나가 빠지면 그 정책만 제
시전을 끊는다. 엔진이 계획을 받아 든 뒤에 한 번 보는 것이 규율을 한 벌로 남긴다.
"""

from dataclasses import replace

from game.app.core.event_log import EventLog
from game.app.simulation.plan import BlockedRule, PlannedAction
from game.app.simulation.state import Entity, WorldState
from game.app.simulation.telegraph import CANCEL_BY_ACT, TelegraphBoard
from game.app.skills.catalog import (
    CAST_CANCEL,
    CAST_FREE,
    CAST_HOLD,
    CAST_LOCK,
    SkillDef,
    find_skill,
)

# **시전을 안 끊는 행동들** (설계/5_스킬 §10.3).
#
# §10.3 은 「다른 행동을 하면 시전이 취소된다」고 적고, 그래야 취소가 벌이 아니라
# **선택**이 되며 규칙표가 「마법을 포기할 것인가」를 답한다고 했다. 그런데 답의 한쪽인
# **「포기하지 않는다」를 적을 수단이 없었다** — 버티는 것도 행동이라 HOLD 가 제 예고를
# 끊었고, 규칙이 전부 거짓이면 엔진이 DEFAULT 로 접근을 채워 그것이 또 끊었다.
#
# 실측(1층 60런): focus_lowest_guard 뼈대(46%)의 한 줄만 마법으로 바꾸면 1% 였다.
# 로그가 이유를 그대로 적고 있었다 — `T001 예고 16칸 · T002 예고 취소 → 다른 행동`.
# 예고를 쓰는 스킬은 **어느 규칙표에서도 한 번도 안 터지는** 상태였다.
#
# 세계를 안 건드리는 둘만 뺀다. 이동·타격·소모품은 그대로 끊는다.
KEEP_CAST_ACTIONS = frozenset({"HOLD", "SET_FLAG"})

# 엄한 순서. `read_cast_act` 가 이 순서로 처음 걸리는 것을 돌려준다.
CAST_STRICTNESS: tuple[str, ...] = (CAST_LOCK, CAST_HOLD, CAST_CANCEL, CAST_FREE)

# 시전 규율이 규칙표를 대신했을 때 로그에 적는 말. **왜 그 행동이 아니었는지를 화면이
# 말해야 한다** — 잠긴 틱이 빈 줄로 지나가면 사람은 규칙표가 고장 난 줄 안다 (P1).
CAST_LOCKED_EXPR = "시전 중 — 잠김"
CAST_HELD_EXPR = "시전 중 — 버팀"
CAST_HELD_REASON = "시전 중"

# 발동하고 나서 굳어 있는 틱에 적는 말. 잠금과 가르는 이유는 **사람이 기다리는 것**이
# 다르기 때문이다 — 잠금은 「아직 안 터졌다」이고 이것은 「이미 터졌다」다.
RECOVER_EXPR = "굳음 — 후경직"

# 잠기거나 버틸 때 대신 서는 행동. 세계를 안 건드리는 쪽이라야 시전이 남는다.
HELD_ACTION = "HOLD"

# 재주로 치는 행동들. 굳힐지 가르는 데만 쓴다 — `actions.ATTACK_ACTIONS` 를 들여오면
# 순환이 난다(저쪽이 이 모듈을 거슬러 부른다).
ATTACK_ACTION_IDS = frozenset({"ATTACK", "SKILL_1", "SKILL_2", "AREA_ATTACK"})


def read_locked_plan(board: TelegraphBoard, entity: Entity) -> PlannedAction | None:
    """굳어 있으면 규칙표를 안 돌리고 버티는 계획을 낸다.

    **두 가지가 굳힌다** — 발동 전의 잠금(`CAST_LOCK`)과 발동 뒤의 후경직
    (`recover_ticks`)이다. 둘 다 「이 틱은 규칙표가 안 돈다」로 같고, 로그에 적는 말만
    가른다: 사람이 기다리는 것이 다르기 때문이다.

    **후경직을 먼저 본다.** 한 틱에 둘 다 서는 일은 지금 없지만(굳은 동안에는 새 시전을
    못 건다), 순서를 안 정해 두면 그 조합이 생기는 날 어느 말이 찍힐지 모른다.

    Args:
        board: 예고판.
        entity: 결정 주체.

    Returns:
        버티는 계획. 굳어 있지 않으면 None — 그때는 규칙표가 돈다.
    """
    if entity.recover_ticks > 0:
        return PlannedAction(entity_id=entity.entity_id, action_id=HELD_ACTION, expr=RECOVER_EXPR)
    if read_cast_act(board, entity.entity_id) != CAST_LOCK:
        return None
    return PlannedAction(entity_id=entity.entity_id, action_id=HELD_ACTION, expr=CAST_LOCKED_EXPR)


def apply_hold_policy(board: TelegraphBoard, plan: PlannedAction) -> PlannedAction:
    """버팀이면 시전을 끊는 행동을 「불가」로 적고 버틴다.

    **잠금과 결과가 같고 로그가 다르다.** 버팀은 고르려던 행동을 적어 두므로, 규칙표를
    고치는 사람이 「이 줄은 시전 중이라 못 섰다」를 읽을 수 있다 (P1 — 실패는 정보다).

    Args:
        board: 예고판.
        plan: 규칙표가 낸 계획.

    Returns:
        그대로이거나, 버티는 계획으로 바뀐 것.
    """
    if read_cast_act(board, plan.entity_id) != CAST_HOLD:
        return plan
    if plan.action_id in KEEP_CAST_ACTIONS:
        return plan
    held = BlockedRule(rule_index=plan.rule_index or 0, expr=plan.expr, reason=CAST_HELD_REASON)
    return replace(
        plan,
        action_id=HELD_ACTION,
        target_id=None,
        skill_id=None,
        item_kind=None,
        expr=CAST_HELD_EXPR,
        rule_index=None,
        blocked=(*plan.blocked, held),
    )


def read_cast_act(board: TelegraphBoard, entity_id: str) -> str:
    """그 엔티티가 지금 거는 예고의 시전 규율.

    **여럿이면 제일 엄한 것을 따른다.** 한 엔티티가 예고 둘을 동시에 걸 수 있고,
    그때 「하나는 잠기고 하나는 자유」는 한 틱에 둘 다 성립하지 못한다 — 느슨한 쪽을
    고르면 잠금으로 지키려던 예고가 끊긴다.

    Args:
        board: 예고판.
        entity_id: 확인할 엔티티 id.

    Returns:
        시전 규율. 거는 예고가 없으면 `CAST_FREE` — 잠글 것이 없다.
    """
    modes = {telegraph.cast_act for telegraph in board.pending if telegraph.caster_id == entity_id}
    for mode in CAST_STRICTNESS:
        if mode in modes:
            return mode
    return CAST_FREE


def apply_act_cancel(
    board: TelegraphBoard, state: WorldState, log: EventLog, entity_id: str, action_id: str
) -> None:
    """이번 행동이 그 엔티티의 예고를 끊는가 (§10.3).

    **판단이 여기 사는 이유.** 「무엇이 끊는 행동인가」는 엔진의 갈래가 아니라 예고의
    성질이다. 엔진에 두면 취소 규칙이 디스패치 표 한가운데 끼어, 다음 사람이 행동을
    더할 때 이 줄을 함께 봐야 하는지 알 수 없다.

    Args:
        board: 예고판.
        state: 세계 상태.
        log: 이벤트 로그.
        entity_id: 행위자 id.
        action_id: 이번 틱에 실행할 행동 id.
    """
    if action_id not in KEEP_CAST_ACTIONS:
        board.apply_cancel(state, log, entity_id, CANCEL_BY_ACT)


def apply_recover(entity: Entity, skill: SkillDef) -> None:
    """재주가 발동했으니 그만큼 굳힌다 (§10.3).

    **부르는 자리가 둘이다.** 즉발은 쓴 그 틱에, 예고형은 **터진 틱에** 굳기 시작한다 —
    예고가 도는 동안은 이미 잠금이 묶고 있어서, 거기에 경직을 더하면 같은 대가를 두 번
    치른다. 규칙은 여기 하나에 두고 부르는 자리만 둘이다.

    **더 긴 쪽을 남긴다.** 겹칠 때 짧은 것으로 덮으면 앞의 긴 경직이 지워진다 —
    상태이상을 겹칠 때와 같은 규율이다.

    Args:
        entity: 쓴 개체.
        skill: 쓴 재주.
    """
    if skill.recover > 0:
        entity.recover_ticks = max(entity.recover_ticks, skill.recover)


def apply_action_recover(entity: Entity, skills: dict[str, SkillDef], plan: PlannedAction) -> None:
    """이번 행동이 재주였으면 그만큼 굳힌다 (즉발 쪽 자리).

    **판단이 여기 사는 이유.** 「무엇이 재주인가」는 엔진의 디스패치 갈래가 아니라 시전
    규율의 일이다 — `apply_act_cancel` 을 여기 둔 것과 같은 근거이고, 엔진의 갈래표가
    그만큼 단순해진다.

    예고형은 여기 안 닿는다. `apply_cast` 가 먼저 받아 일찍 돌아가고, 그쪽은 **터진
    틱에** 굳는다.

    Args:
        entity: 행위자.
        skills: 재주 카탈로그.
        plan: 이번 틱의 계획.
    """
    if plan.skill_id is None and plan.action_id not in ATTACK_ACTION_IDS:
        return
    apply_recover(entity, find_skill(skills, plan.action_id))
