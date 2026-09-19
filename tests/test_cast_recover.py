"""후경직 — 발동하고 나서 굳는 틱 (설계/5_스킬 §10.3, 2026-09-19).

**시전에 앞만 있고 뒤가 없었다.** `telegraph` 가 「터지기 전」을 재는데 「터진 뒤」를
재는 축은 아예 없었고, `cooldown` 은 **그 재주를 다시 쓰기까지**이지 그동안 다른 것을
못 한다는 뜻이 아니다 — 큰 것을 쓰고 곧바로 물러서는 일이 공짜였다.

**모든 재주가 같은 축을 갖는다.** 즉발도 예고형도 이것을 읽는다. 축이 마법에만 있으면
「같은 알고리즘」이 아니라 마법의 예외가 하나 더 생기는 것이다.

**기본은 0 이다.** 지금 배포된 재주 열여섯 전부가 0 이라 이 축을 연 것만으로는 게임이
안 바뀐다 — 값은 관리 화면에서 정한다.
"""

import pytest

from game.app.services.run_battle import build_engine, load_balance
from game.app.simulation.cast_policy import RECOVER_EXPR
from game.app.simulation.plan import PlannedAction
from game.app.skills.catalog import CAST_FREE, SkillDef, SkillShape
from game.config import BALANCE_PATH, ROOM_TEMPLATES_PATH
from game.schemas.room import load_room_templates

PROBE = "SKILL_1"


@pytest.fixture(scope="module")
def balance():
    return load_balance(BALANCE_PATH)


@pytest.fixture(scope="module")
def templates():
    return {item.template_id: item for item in load_room_templates(ROOM_TEMPLATES_PATH)}


def build_probe(balance, templates, *, recover, telegraph=0):
    """그 경직을 가진 재주를 꽂은 엔진.

    Args:
        balance: 밸런스 절.
        templates: 방 템플릿 표.
        recover: 후경직 틱.
        telegraph: 예고 틱.

    Returns:
        (엔진, 플레이어, 적).
    """
    engine = build_engine(templates["open_field"], balance, seed=3)
    engine.config.skills[PROBE] = SkillDef(
        skill_id=PROBE,
        shape=SkillShape(kind="AREA" if telegraph else "SINGLE", radius=2),
        coef_pct=100,
        telegraph=telegraph,
        cast_act=CAST_FREE,
        recover=recover,
    )
    player = engine.state.entities["player"]
    return engine, player, next(iter(engine.state.list_hostiles(player)))


def use(player, foe):
    """그 재주를 쓰는 계획."""
    return PlannedAction(
        entity_id=player.entity_id, action_id="USE_SKILL", skill_id=PROBE, target_id=foe.entity_id
    )


def test_an_instant_skill_stiffens_on_use(balance, templates):
    """★ **즉발은 쓴 그 틱에 굳는다.** 예고가 없어도 뒤가 있다."""
    engine, player, foe = build_probe(balance, templates, recover=2)
    engine.apply_actions((use(player, foe),))
    assert player.recover_ticks == 2


def test_zero_recover_changes_nothing(balance, templates):
    """★ **기본은 0 이다** — 축을 연 것만으로 지금 게임이 바뀌면 안 된다."""
    engine, player, foe = build_probe(balance, templates, recover=0)
    engine.apply_actions((use(player, foe),))
    assert player.recover_ticks == 0


def test_the_stiff_entity_does_not_run_its_rules(balance, templates):
    """★ **굳은 틱에는 규칙표가 안 돈다.** 안 그러면 경직이 이름뿐이다."""
    engine, player, foe = build_probe(balance, templates, recover=2)
    engine.apply_actions((use(player, foe),))
    before = player.position
    engine.run_tick()
    assert player.position == before
    assert any(RECOVER_EXPR in one.expr for one in engine.log.entries)


def test_the_stiffness_wears_off(balance, templates):
    """★ 굳은 것은 풀린다 — 유지 단계가 매 틱 줄인다."""
    engine, player, foe = build_probe(balance, templates, recover=1)
    engine.apply_actions((use(player, foe),))
    assert player.recover_ticks == 1
    engine.run_tick()
    assert player.recover_ticks == 0


def test_a_telegraphed_skill_stiffens_when_it_lands(balance, templates):
    """★ **예고형은 터진 틱에 굳는다** — 도는 동안은 잠금이 이미 묶고 있다.

    시전 시작에 굳히면 같은 대가를 두 번 치른다: 예고 3틱 + 경직 2틱이 아니라
    3틱 내내 굳고 그 뒤 또 2틱이 된다.
    """
    engine, player, foe = build_probe(balance, templates, recover=2, telegraph=2)
    engine.apply_actions((use(player, foe),))
    assert player.recover_ticks == 0, "시전 시작에 굳으면 안 된다"
    engine.run_tick()
    engine.run_tick()
    assert player.recover_ticks > 0, "터졌는데 안 굳었다"


def test_the_longer_stiffness_wins(balance, templates):
    """★ 겹치면 긴 쪽이 남는다 — 짧은 것으로 덮으면 앞의 긴 경직이 지워진다."""
    from game.app.simulation.cast_policy import apply_recover

    engine, player, _foe = build_probe(balance, templates, recover=1)
    player.recover_ticks = 5
    apply_recover(player, SkillDef(skill_id="x", recover=2))
    assert player.recover_ticks == 5


def test_the_shipped_skills_are_all_zero():
    """★ **배포된 재주는 전부 0 이다.** 하나라도 값이 있으면 골든이 함께 움직인다.

    축을 열면서 수치를 같이 넣으면 「축이 생겨서」 달라진 것인지 「값을 줘서」 달라진
    것인지 못 가른다. 값은 관리 화면에서 정한다.
    """
    import json
    from pathlib import Path

    from game.config import SKILLS_PATH

    raw = json.loads(Path(SKILLS_PATH).read_text(encoding="utf-8"))
    assert [one["id"] for one in raw["skills"] if int(one.get("recover", 0)) != 0] == []
