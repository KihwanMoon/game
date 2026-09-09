"""플레이어가 예고를 건다 (설계/5_스킬 §10, 도입 순서 H3).

**메테오는 이미 있었다 — 방향만 반대였다.** 자폭형 몬스터가 하던 것이 정확히 그것이고
(`abilities.register_blast` 의 「즉발 광역기 대신 예고를 건다」), 없던 것은 **스킬이
예고를 정하는 길**이었다. 예고가 개체 종류에만 달려 있으면 그것은 그 종류의 성질이라
플레이어가 쓸 수 없다.

여기서 보는 것은 셋이다 — 스킬이 예고를 정하면 그것이 먼저인가, 피해가 시전 시점에
얼어붙는가, 그리고 **아무 스킬도 예고를 안 쓰는 지금 동작이 그대로인가**.
"""

import pytest

from game.app.services.run_battle import build_engine, load_balance
from game.app.simulation.plan import PlannedAction
from game.app.skills.catalog import SkillDef, SkillShape
from game.config import BALANCE_PATH, ROOM_TEMPLATES_PATH
from game.schemas.room import load_room_templates

METEOR = "METEOR"


@pytest.fixture(scope="module")
def balance():
    return load_balance(BALANCE_PATH)


@pytest.fixture(scope="module")
def templates():
    return {item.template_id: item for item in load_room_templates(ROOM_TEMPLATES_PATH)}


def build_probe(balance, templates, telegraph=0, radius=3, coef=200):
    engine = build_engine(templates["open_field"], balance, seed=3)
    engine.config.skills[METEOR] = SkillDef(
        skill_id=METEOR,
        shape=SkillShape(kind="AREA", radius=radius),
        coef_pct=coef,
        telegraph=telegraph,
    )
    return engine, engine.state.entities["player"]


def build_plan():
    return PlannedAction(entity_id="player", action_id="USE_SKILL", skill_id=METEOR)


def test_a_skill_with_a_telegraph_registers_instead_of_striking(balance, templates):
    """★ **이것이 H3 의 전부다.** 즉발 대신 붉은 칸이 먼저 뜬다."""
    engine, _player = build_probe(balance, templates, telegraph=3)
    engine.apply_actions((build_plan(),))
    active = engine.telegraphs.list_active()
    assert len(active) == 1
    assert active[0].skill_id == METEOR
    assert active[0].remaining_ticks == 3


def test_the_radius_comes_from_the_shape(balance, templates):
    """★ 반경도 데이터다 — 상수로 돌면 데이터를 고쳐도 안 달라진다."""
    engine, player = build_probe(balance, templates, telegraph=2, radius=1)
    engine.apply_actions((build_plan(),))
    tiles = engine.telegraphs.list_active()[0].tiles
    assert all(abs(x - player.position[0]) + abs(y - player.position[1]) <= 1 for x, y in tiles)


def test_the_damage_freezes_at_cast_time(balance, templates):
    """★ **발동 시점에 다시 계산하면 그 사이의 버프가 회피 판정에 섞인다.**

    예고 피해는 방어력 감쇠를 안 거치는 고정값이라(`telegraph.py` 머리말), 「누가
    걸었는가」는 반영되고 「그 뒤에 무슨 일이 있었는가」는 안 반영돼야 한다.
    """
    engine, player = build_probe(balance, templates, telegraph=2, coef=200)
    before = player.attack
    engine.apply_actions((build_plan(),))
    frozen = engine.telegraphs.list_active()[0].damage
    assert frozen == before * 2
    player.attack = before * 10
    assert engine.telegraphs.list_active()[0].damage == frozen


def test_a_skill_without_a_telegraph_still_strikes_now(balance, templates):
    """★ **지금 동작이 그대로여야 한다.** 어느 스킬도 예고를 안 쓰므로 골든이 안 깨진다."""
    engine, _player = build_probe(balance, templates, telegraph=0)
    engine.apply_actions((build_plan(),))
    assert engine.telegraphs.list_active() == ()


def test_the_caster_sees_its_own_cast(balance, templates):
    """★ `self_is_casting` 이 없으면 「마법을 버리고 후퇴」를 지을 수 없다 (§10.3).

    시전을 잠그지 않고 취소되게 했으므로, 취소가 선택이 되려면 규칙표가 물을 수 있어야
    한다 — 못 물으면 잠그는 것과 같아진다.
    """
    from game.app.simulation.perception import build_snapshot

    engine, player = build_probe(balance, templates, telegraph=3)
    engine.apply_actions((build_plan(),))
    engine.state.tick = 1
    engine.run_telegraph()
    snapshot = build_snapshot(
        engine.state, player, engine.config.kind_types, board=engine.telegraphs
    )
    assert snapshot.values["self_is_casting"] is True
