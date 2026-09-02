"""층 깊이 스케일 — balance.json 의 floor_scale 이 실제로 적용되는가.

보는 것은 두 가지다. 하나는 **층 1 이 기준이라는 것** — 층 1 에서 아무것도 곱하지
않아야 balance.json 에 적힌 값이 "층 1 의 그 적" 이라는 뜻을 갖는다. 다른 하나는
**개체를 만드는 세 자리(방 배치·소환·추격자)가 모두 같은 기준을 거친다는 것** 이다.
한 자리라도 빠뜨리면 같은 층에 서로 다른 기준의 적이 섞인다.

층 체류 스케일(pressure)과는 다른 축이며 둘은 곱해진다. 그 합성도 여기서 확인한다.
"""

import pytest

from game.app.services.run_battle import build_engine, load_balance
from game.app.simulation.abilities import resolve_summon
from game.app.simulation.pressure import (
    PressureRules,
    PressureTracker,
    calculate_scaled_attack,
)
from game.app.simulation.scaling import (
    FIRST_FLOOR,
    PERCENT_BASE,
    FloorScale,
    build_floor_scale,
    calculate_scaled_stat,
    get_scaled_enemy_stats,
)
from game.app.simulation.state import FACTION_ENEMY, Entity
from game.config import BALANCE_PATH, ROOM_TEMPLATES_PATH
from game.schemas.room import load_room_templates

RUSHER_HP = 40
RUSHER_ATTACK = 8
DEEP_FLOOR = 3
STALL_TICKS = 100


@pytest.fixture(scope="module")
def balance():
    return load_balance(BALANCE_PATH)


@pytest.fixture(scope="module")
def templates():
    return {t.template_id: t for t in load_room_templates(ROOM_TEMPLATES_PATH)}


def test_balance_declares_floor_scale(balance):
    # 값이 있어도 읽는 코드가 없으면 층이 올라가도 적이 강해지지 않는다.
    scale = build_floor_scale(balance["floor_scale"])
    assert scale.mult_pct_per_floor > PERCENT_BASE


def test_a_weakening_multiplier_is_rejected():
    # 층이 깊어질수록 적이 약해지면 층 진행이 난이도가 아니라 보상이 된다.
    with pytest.raises(ValueError, match="100 이상"):
        build_floor_scale({"enemy_mult_pct_per_floor": 90})


def test_first_floor_is_the_baseline():
    # 층 1 에서 곱하면 balance.json 의 값이 "층 1 의 그 적" 이라는 뜻을 잃는다.
    assert calculate_scaled_stat(RUSHER_HP, 110, FIRST_FLOOR) == RUSHER_HP


def test_depth_compounds_per_floor():
    # **복리다** (e3). 층마다 곱하고 내림으로 접는다 — 10층이면 1층의 약 2.36배다.
    assert calculate_scaled_stat(100, 110, 2) == 110
    assert calculate_scaled_stat(100, 110, DEEP_FLOOR) == 121
    assert calculate_scaled_stat(100, 110, 10) == 233


def test_scaling_stays_integer_and_rounds_down():
    # 부동소수를 쓰면 플랫폼마다 결과가 갈려 리플레이가 깨진다 (R5). **층마다 접는다** —
    # 한 번에 거듭제곱하면 TS 와 마지막 자리가 갈린다: 9→9(9.9 의 내림)→9 처럼, 작은
    # 값은 몇 층을 내려가도 안 자랄 수 있다. 그것이 계약이다.
    assert calculate_scaled_stat(9, 110, DEEP_FLOOR) == 9
    assert isinstance(calculate_scaled_stat(9, 110, DEEP_FLOOR), int)


def test_enemy_stats_scale_both_axes(balance):
    scale = build_floor_scale(balance["floor_scale"])
    rusher = next(kind for kind in balance["enemies"] if kind["id"] == "goblin_rusher")
    assert get_scaled_enemy_stats(rusher, scale, FIRST_FLOOR) == (RUSHER_HP, RUSHER_ATTACK)
    assert get_scaled_enemy_stats(rusher, scale, DEEP_FLOOR) == (57, 10)


def test_room_spawns_carry_the_floor_scale(balance, templates):
    # 방 배치가 스케일을 거치지 않으면 층이 올라가도 방이 그대로다.
    shallow = build_engine(
        templates["open_field"], balance, seed=1, floor=FIRST_FLOOR, is_varied=False
    )
    deep = build_engine(templates["open_field"], balance, seed=1, floor=DEEP_FLOOR, is_varied=False)
    weak = shallow.state.entities["goblin_rusher_0"]
    strong = deep.state.entities["goblin_rusher_0"]
    assert (weak.hp_max, weak.attack) == (RUSHER_HP, RUSHER_ATTACK)
    assert (strong.hp_max, strong.attack) == (57, 10)
    # 스케일은 최대 HP 를 올리는 것이지 다친 채로 시작시키는 것이 아니다.
    assert strong.hp == strong.hp_max


def test_summoned_minions_carry_the_floor_scale(balance, templates):
    # 걸지 않으면 층 3 의 소환사가 층 1 기준 잡몹을 불러, 소환을 방치하는 쪽이
    # 층이 깊어질수록 유리해진다.
    engine = build_engine(templates["pillars"], balance, seed=1, floor=DEEP_FLOOR, is_varied=False)
    summoner = engine.state.entities["goblin_summoner_1"]
    minion, _ = resolve_summon(engine.state, engine.config, summoner)
    assert minion is not None
    assert (minion.hp_max, minion.attack) == (57, 10)


def test_hunters_carry_the_floor_scale(balance, templates):
    # 추격자만 층 1 스탯이면 "시간을 끌면 오히려 약한 적이 온다" 가 된다.
    engine = build_engine(
        templates["open_field"], balance, seed=1, floor=DEEP_FLOOR, is_varied=False
    )
    hunter = engine.pressure.create_hunter(engine.state)
    assert hunter is not None
    assert (hunter.hp_max, hunter.attack) == (57, 10)


def test_depth_and_dwell_scales_multiply(balance, templates):
    # 두 축은 곱해진다 (docs/04 P-1). 체류 압력이 "지금 이 적이 가진 힘의 몇 %" 여야
    # 층이 깊어질수록 시간을 끄는 대가도 함께 커진다.
    engine = build_engine(
        templates["open_field"], balance, seed=1, floor=DEEP_FLOOR, is_varied=False
    )
    tracker = engine.pressure
    tracker.floor_ticks = STALL_TICKS
    bonus_pct = tracker.apply_scale(engine.state)
    rusher = engine.state.entities["goblin_rusher_0"]
    depth_scaled = calculate_scaled_stat(RUSHER_ATTACK, 120, DEEP_FLOOR)
    assert rusher.attack == calculate_scaled_attack(depth_scaled, bonus_pct)


def test_engine_floor_overrides_a_reused_tracker(balance, templates):
    # 추적기는 층 단위 객체라 방마다 재사용된다. 층을 덮어쓰지 않으면 뒤늦게 나온
    # 추격자만 이전 층 기준으로 선다.
    tracker = PressureTracker(rules=PressureRules(), floor=FIRST_FLOOR, floor_scale=FloorScale())
    build_engine(
        templates["open_field"],
        balance,
        seed=1,
        floor=DEEP_FLOOR,
        pressure=tracker,
        is_varied=False,
    )
    assert tracker.floor == DEEP_FLOOR


def test_scaling_does_not_touch_the_player(balance, templates):
    # floor_scale 은 enemy_* 다. 양쪽이 함께 오르면 층 진행의 압력이 0 이 된다.
    shallow = build_engine(
        templates["open_field"], balance, seed=1, floor=FIRST_FLOOR, is_varied=False
    )
    deep = build_engine(templates["open_field"], balance, seed=1, floor=DEEP_FLOOR, is_varied=False)
    for field in ("hp_max", "attack", "defense"):
        assert getattr(shallow.state.entities["player"], field) == getattr(
            deep.state.entities["player"], field
        )


def test_extra_entities_can_be_scaled_by_hand():
    # 골든 스크립트처럼 템플릿 밖에서 개체를 세우는 자리도 같은 함수를 쓴다.
    stats = {"hp_max": RUSHER_HP, "attack": RUSHER_ATTACK}
    hp_max, attack = get_scaled_enemy_stats(stats, FloorScale(), DEEP_FLOOR)
    entity = Entity(
        entity_id="x",
        kind_id="goblin_rusher",
        faction=FACTION_ENEMY,
        position=(1, 1),
        hp=hp_max,
        hp_max=hp_max,
        attack=attack,
        defense=0,
        attack_range=1,
        initiative=0,
    )
    assert (entity.hp_max, entity.attack) == (57, 10)
