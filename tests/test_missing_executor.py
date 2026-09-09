"""부를 줄 모르는 스킬이 로그에 남는가 (설계/5_스킬 §10.8).

**조용히 사라지는 것이 제일 나쁜 실패다.** `USE_SKILL[X]` 는 `resolve_skill_plan` 이
`action_id = X` 로 풀어 주는데, X 가 실행기의 어느 갈래에도 안 걸리면 그냥 끝났다 —
문법 검증도 통과하고(`validator` 는 대상 진영만 본다) 「불가」로도 안 잡힌다
(`check_has_skill` 은 장착 여부만 본다). 오류도 로그도 안 남았다.

그래서 스킬을 데이터로 더해도 **아무 일이 안 일어나는데 아무도 몰랐다.** 마법 세 종을
넣기 전에 이 구멍부터 막는다.
"""

import pytest

from game.app.services.run_battle import build_engine, load_balance
from game.app.simulation.plan import PlannedAction
from game.config import BALANCE_PATH, ROOM_TEMPLATES_PATH
from game.schemas.room import load_room_templates


@pytest.fixture(scope="module")
def balance():
    return load_balance(BALANCE_PATH)


@pytest.fixture(scope="module")
def templates():
    return {item.template_id: item for item in load_room_templates(ROOM_TEMPLATES_PATH)}


def list_act_lines(engine):
    return [entry for entry in engine.log.entries if entry.phase == "ACT"]


def test_an_unknown_skill_says_so(templates, balance):
    """★ 실행기가 없으면 **로그가 그렇게 말해야** 한다."""
    engine = build_engine(templates["open_field"], balance, seed=3)
    player = engine.state.entities["player"]
    plan = PlannedAction(
        entity_id=player.entity_id, action_id="USE_SKILL", skill_id="NO_SUCH_SPELL"
    )
    engine.apply_actions((plan,))
    lines = [entry for entry in list_act_lines(engine) if "쓸 줄 모른다" in entry.outcome]
    assert lines, "부를 줄 모르는 스킬이 조용히 사라졌다"
    assert lines[0].expr.startswith("NO_SUCH_SPELL")


def test_a_known_skill_says_nothing_of_the_sort(templates, balance):
    """★ 있는 스킬에까지 붙으면 로그가 거짓이 된다."""
    engine = build_engine(templates["open_field"], balance, seed=3)
    player = engine.state.entities["player"]
    plan = PlannedAction(entity_id=player.entity_id, action_id="USE_SKILL", skill_id="ATTACK")
    engine.apply_actions((plan,))
    assert not [entry for entry in list_act_lines(engine) if "쓸 줄 모른다" in entry.outcome]


def test_moving_never_says_it(templates, balance):
    """★ **이동에 붙으면 안 된다.**

    엔진이 루프를 두 번 돌고 둘째 루프가 이동 계획에도 `_apply_settled` 를 부른다.
    `skill_id` 로 안 가리면 이동마다 이 줄이 붙어 로그가 두 배가 된다.
    """
    engine = build_engine(templates["open_field"], balance, seed=3)
    player = engine.state.entities["player"]
    plan = PlannedAction(entity_id=player.entity_id, action_id="APPROACH", target_id="e1")
    engine.apply_actions((plan,))
    assert not [entry for entry in list_act_lines(engine) if "쓸 줄 모른다" in entry.outcome]


def test_a_plain_action_never_says_it(templates, balance):
    """★ `USE_SKILL` 을 안 거친 행동도 마찬가지다 — `HOLD` 는 실행기가 있다."""
    engine = build_engine(templates["open_field"], balance, seed=3)
    player = engine.state.entities["player"]
    engine.apply_actions((PlannedAction(entity_id=player.entity_id, action_id="HOLD"),))
    assert not [entry for entry in list_act_lines(engine) if "쓸 줄 모른다" in entry.outcome]
