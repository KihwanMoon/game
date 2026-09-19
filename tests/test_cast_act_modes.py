"""시전 중 행동 규율 넷 (설계/5_스킬 §10.3, 2026-09-19).

**불리언 하나로는 모자랐다.** 예전에는 `cancel_on_act` 였고 뜻이 「다른 행동을 하면
취소」 하나뿐이라 **잠그는 길이 없었다.** 실측이 그 값을 그대로 보여 준다 — 예고 3틱인
메테오는 보호 줄(`내가 시전 중인가 → 대기`)이 없으면 **60판 중 60판이 취소**됐고, 예고
1틱인 연쇄 번개·서리 장판은 끼어들 틱이 구조적으로 0 이라 같은 플래그가 한 번도 안
닿았다. 한 값이 스킬마다 다른 뜻이 되고 있었다.

넷을 두는 이유는 지금 콘텐츠가 이미 둘을 쓰고 있어서다. 적의 굿은 전부 `FREE`(물러서
면서도 계속 시전)이고, 셋만 두면 그 행동이 통째로 바뀐다.
"""

import pytest

from game.app.services.run_battle import build_engine, load_balance
from game.app.simulation.cast_policy import CAST_HELD_EXPR, CAST_LOCKED_EXPR
from game.app.simulation.plan import PlannedAction
from game.app.skills.catalog import (
    CAST_ACT_MODES,
    CAST_CANCEL,
    CAST_FREE,
    CAST_HOLD,
    CAST_LOCK,
    SkillDef,
    SkillShape,
)
from game.config import BALANCE_PATH, ROOM_TEMPLATES_PATH
from game.schemas.room import load_room_templates

METEOR = "METEOR"


@pytest.fixture(scope="module")
def balance():
    return load_balance(BALANCE_PATH)


@pytest.fixture(scope="module")
def templates():
    return {item.template_id: item for item in load_room_templates(ROOM_TEMPLATES_PATH)}


def build_casting(balance, templates, mode):
    """그 규율로 예고를 건 엔진을 만든다.

    Args:
        balance: 밸런스 절.
        templates: 방 템플릿 표.
        mode: 시전 규율.

    Returns:
        (엔진, 플레이어, 적).
    """
    engine = build_engine(templates["open_field"], balance, seed=3)
    engine.config.skills[METEOR] = SkillDef(
        skill_id=METEOR,
        shape=SkillShape(kind="AREA", radius=2),
        coef_pct=200,
        telegraph=3,
        cast_act=mode,
    )
    player = engine.state.entities["player"]
    engine.apply_actions(
        (PlannedAction(entity_id="player", action_id="USE_SKILL", skill_id=METEOR),)
    )
    assert len(engine.telegraphs.list_active()) == 1
    return engine, player, next(iter(engine.state.list_hostiles(player)))


def approach(player, foe):
    """시전을 끊는 쪽 행동 하나."""
    return PlannedAction(entity_id=player.entity_id, action_id="APPROACH", target_id=foe.entity_id)


def test_lock_keeps_the_cast_and_pins_the_feet(balance, templates):
    """★ **잠금은 규칙표를 안 돌린다.** 시전이 남고 발이 묶인다."""
    engine, player, _foe = build_casting(balance, templates, CAST_LOCK)
    before = player.position
    engine.run_tick()
    assert len(engine.telegraphs.list_active()) == 1
    assert player.position == before


def test_lock_says_so_in_the_log(balance, templates):
    """★ **잠긴 틱이 빈 줄로 지나가면 사람은 규칙표가 고장 난 줄 안다** (P1).

    무결정 구간을 만드는 것이 잠금의 값인데, 그 구간이 로그에 안 남으면 「왜 내 규칙이
    안 떴나」에 답이 없다.
    """
    engine, _player, _foe = build_casting(balance, templates, CAST_LOCK)
    engine.run_tick()
    assert any(CAST_LOCKED_EXPR in one.expr for one in engine.log.entries)


def test_hold_keeps_the_cast_but_still_runs_the_rules(balance, templates):
    """★ **버팀은 규칙표를 돌린다** — 무엇이 막혔는지가 로그에 남는 것이 잠금과의 차이다.

    같은 결과(시전 유지·버티기)를 내지만, 버팀은 **고르려던 행동을 적어 둔다.** 규칙표를
    고치는 사람에게 그 한 줄이 「이 줄은 시전 중이라 못 섰다」를 말한다.
    """
    engine, player, foe = build_casting(balance, templates, CAST_HOLD)
    engine.apply_actions((approach(player, foe),))
    assert len(engine.telegraphs.list_active()) == 1
    plans = engine.plan_actions(engine.build_perceptions())
    mine = next(one for one in plans if one.entity_id == player.entity_id)
    assert mine.action_id == "HOLD"
    assert mine.expr == CAST_HELD_EXPR
    assert mine.blocked, "무엇이 막혔는지를 안 적었다"


def test_cancel_still_cancels(balance, templates):
    """★ **취소를 없애지 않았다** — 「적이 붙었으니 마법을 버리고 후퇴」가 남아야 한다.

    잠금이 기본이 되면서 이 길이 사라졌다고 생각하기 쉬운데, 그렇게 두면 §10.3 이
    세우려던 선택이 통째로 없어진다. 스킬이 고르면 된다.
    """
    engine, player, foe = build_casting(balance, templates, CAST_CANCEL)
    engine.apply_actions((approach(player, foe),))
    assert engine.telegraphs.list_active() == ()


def test_free_keeps_the_cast_through_an_action(balance, templates):
    """★ **자유는 지금 적들의 동작이다** — 물러서면서도 계속 시전한다.

    불티 무당 표의 주석이 그것을 적어 뒀다: 「물러서도 굿은 안 끊긴다」. 여기가 깨지면
    주술형 전부가 제 굿을 스스로 끊는다.
    """
    engine, player, foe = build_casting(balance, templates, CAST_FREE)
    before = player.position
    engine.apply_actions((approach(player, foe),))
    assert len(engine.telegraphs.list_active()) == 1
    assert player.position != before


def test_being_hit_is_a_separate_axis(balance, templates):
    """★ **잠금이 피격까지 막지는 않는다.**

    둘을 한 축에 두면 잠긴 시전이 무적이 되고, 「안전한 자리에서 쏘는가」가 규칙표의
    질문에서 사라진다.
    """
    engine, player, _foe = build_casting(balance, templates, CAST_LOCK)
    engine.config.skills[METEOR] = SkillDef(
        skill_id=METEOR,
        shape=SkillShape(kind="AREA", radius=2),
        coef_pct=200,
        telegraph=3,
        cast_act=CAST_LOCK,
        cancel_on_hit=True,
    )
    engine.telegraphs.pending[0].cancel_on_hit = True
    engine.actions.apply_damage(player, 5, "ACT", "시험", "e1")
    assert engine.telegraphs.list_active() == ()


def test_the_shipped_skills_declare_a_known_mode():
    """★ **모르는 값은 조용히 자유가 된다** — 오타 하나가 잠금을 푼다.

    예고를 쓰는 스킬은 전부 아는 값을 적어야 하고, 안 적은 스킬은 파서가 잠금으로
    떨어뜨린다(`load_skills` 의 기본값). 그 둘이 어긋나면 데이터가 거짓말을 한다.
    """
    import json
    from pathlib import Path

    from game.config import SKILLS_PATH

    raw = json.loads(Path(SKILLS_PATH).read_text(encoding="utf-8"))
    bad = [
        one["id"]
        for one in raw["skills"]
        if int(one.get("telegraph", 0)) > 0 and one.get("cast_act") not in CAST_ACT_MODES
    ]
    assert bad == [], f"모르는 시전 규율: {bad}"


def test_the_old_switch_is_gone():
    """★ 두 축이 같은 것을 말하면 한쪽만 고쳐지는 날이 온다."""
    import json
    from pathlib import Path

    from game.config import SKILLS_PATH

    raw = json.loads(Path(SKILLS_PATH).read_text(encoding="utf-8"))
    assert [one["id"] for one in raw["skills"] if "cancel_on_act" in one] == []
