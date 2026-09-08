"""스킬 정의를 데이터로 읽는다 (설계/5_스킬 §9 4단계).

**같은 개념이 두 곳에 있었고 데이터 쪽이 거짓이었다.** `skills.json` 은 처음부터
`shape` 를 적고 있었는데 읽는 코드가 없었고, 실제 반경은 `actions.AREA_ATTACK_RADIUS = 2`
라는 상수였다. 상수를 고치면 게임이 달라지는데 데이터는 그대로였고, 데이터를 고치면
아무 일도 안 일어났다.

여기서 보는 것은 **읽어 냈는가**가 아니라 **실행이 그것을 쓰는가**다. 읽기만 확인하면
로더 테스트는 통과하는데 게임은 여전히 상수로 도는 상태를 못 잡는다 — W6 배선 회귀가
말하는 그 실패 방식이다.
"""

import pytest

from game.app.services.run_battle import build_engine, load_balance
from game.app.simulation.plan import PlannedAction
from game.app.simulation.state import FACTION_ENEMY, Entity
from game.app.skills.catalog import (
    DEFAULT_COEF_PCT,
    SHAPE_AREA,
    SHAPE_SINGLE,
    build_skill_def,
    find_skill,
    load_skill_defs,
)
from game.config import BALANCE_PATH, ROOM_TEMPLATES_PATH
from game.schemas.room import load_room_templates

AREA_SKILL = "AREA_ATTACK"


@pytest.fixture(scope="module")
def balance():
    return load_balance(BALANCE_PATH)


@pytest.fixture(scope="module")
def templates():
    return {item.template_id: item for item in load_room_templates(ROOM_TEMPLATES_PATH)}


def build_plan(entity_id, action_id):
    return PlannedAction(entity_id=entity_id, action_id=action_id)


def place_enemy(engine, entity_id, position):
    """반경 시험용 허수아비. 예고를 안 쓰는 종류라야 즉발 광역기가 돈다."""
    enemy = Entity(
        entity_id=entity_id,
        kind_id="goblin_rusher",
        faction=FACTION_ENEMY,
        position=position,
        hp=200,
        hp_max=200,
        attack=1,
        defense=0,
        attack_range=1,
        initiative=10,
    )
    engine.state.entities[entity_id] = enemy
    return enemy


# ── 읽기 ─────────────────────────────────────────────────────────────────


def test_the_shape_is_read_from_the_file(balance):
    """★ `shape` 를 읽는 코드가 없어서 이 절이 거짓이었다."""
    defs = load_skill_defs(balance["skills"])
    assert defs[AREA_SKILL].shape.kind == SHAPE_AREA
    assert defs[AREA_SKILL].shape.radius == 2


def test_an_unknown_skill_is_a_blank_record(balance):
    """★ None 을 돌려주면 부르는 쪽마다 없음 처리가 생기고, 그중 하나가 빠지면 터진다."""
    blank = find_skill(load_skill_defs(balance["skills"]), "NO_SUCH_SKILL")
    assert blank.skill_id == "NO_SUCH_SKILL"
    assert blank.cooldown == 0
    assert blank.reach is None
    assert blank.coef_pct == DEFAULT_COEF_PCT


def test_an_old_row_without_a_shape_still_reads():
    """★ 필드를 하나 더할 때마다 옛 콘텐츠 팩이 통째로 안 읽히면 안 된다.

    발행된 팩은 되돌릴 수 없다 (설계/4_아이템 §18).
    """
    entry = build_skill_def({"id": "LEGACY"})
    assert entry.shape.kind == SHAPE_SINGLE
    assert entry.coef_pct == DEFAULT_COEF_PCT


def test_a_null_range_means_the_entity_range(balance):
    """★ 0 으로 읽으면 그 스킬이 매 틱 「사거리 밖」으로 헛돈다."""
    assert load_skill_defs(balance["skills"])["ATTACK"].reach is None


# ── 실행이 그것을 쓰는가 ─────────────────────────────────────────────────


def test_the_radius_that_lands_comes_from_the_data(templates, balance):
    """★ **이것이 이 변경의 판정이다.** 데이터를 고치면 맞는 범위가 달라져야 한다.

    상수로 돌던 때는 `shape.radius` 를 무엇으로 바꿔도 결과가 같았다. 반경 안팎에 하나씩
    세워 두고 데이터만 줄여서, 밖에 있던 것이 아니라 **안에 있던 것까지** 빠지는지 본다.
    """
    engine = build_engine(templates["open_field"], balance, seed=3)
    player = engine.state.entities["player"]
    near = place_enemy(engine, "near", (player.position[0] + 1, player.position[1]))
    far = place_enemy(engine, "far", (player.position[0] + 2, player.position[1]))

    engine.config.skills[AREA_SKILL] = find_skill(engine.config.skills, AREA_SKILL)
    engine.actions.apply_area_attack(player, build_plan(player.entity_id, AREA_SKILL))
    assert near.hp < near.hp_max, "반경 2 안의 적이 안 맞았다"
    assert far.hp < far.hp_max, "반경 2 안의 적이 안 맞았다"


def test_shrinking_the_radius_in_data_shrinks_the_blast(templates, balance):
    """★ 데이터를 1 로 줄이면 두 칸 떨어진 적은 빠져야 한다.

    이것이 실패하면 실행이 아직 상수를 보고 있는 것이다.
    """
    from dataclasses import replace

    engine = build_engine(templates["open_field"], balance, seed=3)
    player = engine.state.entities["player"]
    near = place_enemy(engine, "near", (player.position[0] + 1, player.position[1]))
    far = place_enemy(engine, "far", (player.position[0] + 2, player.position[1]))

    entry = find_skill(engine.config.skills, AREA_SKILL)
    engine.config.skills[AREA_SKILL] = replace(entry, shape=replace(entry.shape, radius=1))
    engine.actions.apply_area_attack(player, build_plan(player.entity_id, AREA_SKILL))
    assert near.hp < near.hp_max, "반경 1 안의 적이 안 맞았다"
    assert far.hp == far.hp_max, "데이터를 줄였는데 두 칸 밖까지 맞았다 — 아직 상수로 돈다"
