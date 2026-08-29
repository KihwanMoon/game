"""어뷰징 차단 테스트 (GDD §7, 로드맵 W7).

세 압력을 각각 본다 — 추격자가 한계 다음 틱에 오는가, 층 체류가 적 공격력을
복리 없이 올리는가, 샘이 총 회복량을 다 쓰면 멈추고 사라지는가. 마지막으로 같은
시드가 같은 결과를 내는지를 확인한다 (R5).
"""

import pytest

from game.app.core.event_log import EventLog
from game.app.core.rng import DeterministicRng
from game.app.grid.geometry import get_manhattan_distance
from game.app.services.run_battle import load_balance
from game.app.simulation.plan import PHASE_UPKEEP
from game.app.simulation.pressure import (
    FLOOR_SCALE_TICK_UNIT,
    HUNTER_FLAG,
    MIN_SPAWN_DISTANCE,
    PressureRules,
    PressureTracker,
    build_pressure_rules,
    calculate_floor_bonus_pct,
    calculate_scaled_attack,
    list_hunter_spawns,
)
from game.app.simulation.state import FACTION_ENEMY, FACTION_PLAYER, Entity, WorldState
from game.config import BALANCE_PATH, ROOM_TEMPLATES_PATH
from game.schemas.room import load_room_templates

BASE_ATTACK = 100
OPEN_FIELD_DOORS = ((0, 4), (11, 4))
SEED = 12345
# 한계값을 여기에 다시 적지 않는다. balance.json 이 정본이고(TDD §2), 복제해 두면
# 밸런싱이 그 값을 옮길 때 테스트가 옛 수치를 지키며 실패한다.
_ANTI_ABUSE = load_balance(BALANCE_PATH)["anti_abuse"]
SPAWN_TICK = _ANTI_ABUSE["hunter_spawn_tick"]
INTERVAL = _ANTI_ABUSE["hunter_interval_ticks"]


@pytest.fixture(scope="module")
def balance():
    return load_balance(BALANCE_PATH)


@pytest.fixture(scope="module")
def templates():
    return {t.template_id: t for t in load_room_templates(ROOM_TEMPLATES_PATH)}


def make_state(templates, template_id="open_field", seed=SEED):
    """빈 방 하나를 만든다."""
    return WorldState(room=templates[template_id], rng=DeterministicRng(seed))


def add_entity(state, entity_id, position, faction=FACTION_PLAYER, attack=BASE_ATTACK):
    """테스트용 엔티티를 방에 놓는다."""
    entity = Entity(
        entity_id=entity_id,
        kind_id="dummy",
        faction=faction,
        position=position,
        hp=50,
        hp_max=50,
        attack=attack,
        defense=2,
        attack_range=1,
        initiative=10,
    )
    state.entities[entity_id] = entity
    return entity


def make_tracker(balance):
    """balance.json 의 수치를 그대로 쓰는 추적기."""
    return PressureTracker(
        rules=build_pressure_rules(balance["anti_abuse"]),
        enemy_stats={kind["id"]: kind for kind in balance["enemies"]},
    )


def run_ticks(tracker, state, log, count):
    """count 틱만큼 UPKEEP 압력을 돌리고 등장한 추격자를 모은다."""
    spawned = []
    for _ in range(count):
        state.tick += 1
        spawned.extend(tracker.run_upkeep(state, log))
    return tuple(spawned)


# ── 추격자 스폰 (GDD §7 무한 카이팅) ─────────────────────────────────────────


def test_no_hunter_before_the_threshold(templates, balance):
    state = make_state(templates)
    add_entity(state, "player", (1, 4))
    tracker = make_tracker(balance)

    assert run_ticks(tracker, state, EventLog(), SPAWN_TICK) == ()
    assert tracker.hunter_count == 0
    assert len(state.entities) == 1


def test_hunter_appears_one_tick_after_the_threshold(templates, balance):
    state = make_state(templates)
    add_entity(state, "player", (1, 4))
    tracker = make_tracker(balance)
    log = EventLog()

    run_ticks(tracker, state, log, SPAWN_TICK)
    spawned = run_ticks(tracker, state, log, 1)

    assert len(spawned) == 1
    hunter = spawned[0]
    assert hunter.faction == FACTION_ENEMY
    assert hunter.flags[HUNTER_FLAG] is True
    assert state.entities[hunter.entity_id] is hunter
    assert tracker.room_ticks == SPAWN_TICK + 1


def test_hunters_arrive_every_interval(templates, balance):
    state = make_state(templates)
    add_entity(state, "player", (1, 4))
    tracker = make_tracker(balance)
    log = EventLog()

    # 41 · 61 · 81 세 번. 그 사이 틱에는 하나도 오지 않아야 한다.
    arrivals = []
    for _ in range(SPAWN_TICK + INTERVAL * 2 + 1):
        state.tick += 1
        if tracker.run_upkeep(state, log):
            arrivals.append(state.tick)

    assert arrivals == [SPAWN_TICK + 1, SPAWN_TICK + 1 + INTERVAL, SPAWN_TICK + 1 + INTERVAL * 2]
    assert tracker.hunter_count == 3


def test_hunter_enters_through_a_door(templates, balance):
    # 방 밖에서 쫓아온 것이므로 벽 안쪽에 솟으면 안 된다.
    state = make_state(templates)
    add_entity(state, "player", (1, 4))
    tracker = make_tracker(balance)

    spawned = run_ticks(tracker, state, EventLog(), SPAWN_TICK + 1)
    assert spawned[0].position in OPEN_FIELD_DOORS


def test_hunter_falls_back_when_doors_are_blocked(templates, balance):
    state = make_state(templates)
    player = add_entity(state, "player", (1, 4))
    for index, door in enumerate(OPEN_FIELD_DOORS):
        add_entity(state, f"blocker_{index}", door, FACTION_ENEMY)
    tracker = make_tracker(balance)

    spawned = run_ticks(tracker, state, EventLog(), SPAWN_TICK + 1)
    position = spawned[0].position
    assert position not in OPEN_FIELD_DOORS
    assert get_manhattan_distance(position, player.position) >= MIN_SPAWN_DISTANCE


def test_hunter_copies_balance_stats(templates, balance):
    state = make_state(templates)
    add_entity(state, "player", (1, 4))
    tracker = make_tracker(balance)

    hunter = run_ticks(tracker, state, EventLog(), SPAWN_TICK + 1)[0]
    stats = next(k for k in balance["enemies"] if k["id"] == tracker.rules.hunter_entity)
    assert hunter.kind_id == stats["id"]
    assert hunter.hp == stats["hp_max"]
    assert hunter.attack == stats["attack"]


def test_hunter_without_stats_is_skipped(templates, balance):
    # 스탯이 없으면 조용히 넘기지 않고 로그로 알린다 (P1 실패는 정보다).
    state = make_state(templates)
    add_entity(state, "player", (1, 4))
    tracker = PressureTracker(rules=build_pressure_rules(balance["anti_abuse"]))
    log = EventLog()

    assert run_ticks(tracker, state, log, SPAWN_TICK + 1) == ()
    assert "추격자 스탯 없음" in log.entries[-1].outcome


def test_room_reset_restarts_the_hunter_clock(templates, balance):
    state = make_state(templates)
    add_entity(state, "player", (1, 4))
    tracker = make_tracker(balance)
    log = EventLog()

    run_ticks(tracker, state, log, SPAWN_TICK + 1)
    tracker.reset_room()

    assert tracker.hunter_count == 0
    assert run_ticks(tracker, state, log, SPAWN_TICK) == ()
    assert len(run_ticks(tracker, state, log, 1)) == 1


def test_spawn_candidates_skip_occupied_tiles(templates):
    state = make_state(templates)
    add_entity(state, "player", (1, 4))
    add_entity(state, "guard", OPEN_FIELD_DOORS[0], FACTION_ENEMY)

    assert list_hunter_spawns(state) == (OPEN_FIELD_DOORS[1],)


# ── 층 스케일 (GDD §7 층 지연) ───────────────────────────────────────────────


def test_floor_bonus_is_one_percent_per_ten_ticks():
    assert calculate_floor_bonus_pct(0, 1) == 0
    assert calculate_floor_bonus_pct(FLOOR_SCALE_TICK_UNIT - 1, 1) == 0
    assert calculate_floor_bonus_pct(FLOOR_SCALE_TICK_UNIT, 1) == 1
    assert calculate_floor_bonus_pct(95, 1) == 9


def test_scaled_attack_is_floored_integer_math():
    # 부동소수를 쓰지 않는다 (R5). 12 * 1.01 = 12.12 는 내림해서 12 다.
    assert calculate_scaled_attack(12, 1) == 12
    assert calculate_scaled_attack(BASE_ATTACK, 5) == 105


def test_enemy_attack_grows_with_floor_ticks(templates, balance):
    state = make_state(templates)
    enemy = add_entity(state, "enemy", (9, 2), FACTION_ENEMY)
    tracker = make_tracker(balance)

    run_ticks(tracker, state, EventLog(), FLOOR_SCALE_TICK_UNIT)
    assert enemy.attack == BASE_ATTACK + 1

    run_ticks(tracker, state, EventLog(), FLOOR_SCALE_TICK_UNIT * 4)
    assert enemy.attack == BASE_ATTACK + 5


def test_scale_does_not_compound(templates, balance):
    # 매 틱 현재값에 곱하면 복리가 되어 몇십 틱 만에 발산한다.
    state = make_state(templates)
    enemy = add_entity(state, "enemy", (9, 2), FACTION_ENEMY)
    tracker = make_tracker(balance)

    run_ticks(tracker, state, EventLog(), FLOOR_SCALE_TICK_UNIT * 10)
    assert enemy.attack == calculate_scaled_attack(BASE_ATTACK, 10)
    assert tracker.base_attacks["enemy"] == BASE_ATTACK


def test_player_attack_is_untouched(templates, balance):
    # 양쪽이 함께 오르면 상대 압력이 0 이 된다.
    state = make_state(templates)
    player = add_entity(state, "player", (1, 4))
    tracker = make_tracker(balance)

    run_ticks(tracker, state, EventLog(), FLOOR_SCALE_TICK_UNIT * 3)
    assert player.attack == BASE_ATTACK
    assert "player" not in tracker.base_attacks


def test_scale_is_logged_only_when_it_changes(templates, balance):
    state = make_state(templates)
    add_entity(state, "enemy", (9, 2), FACTION_ENEMY)
    tracker = make_tracker(balance)
    log = EventLog()

    run_ticks(tracker, state, log, FLOOR_SCALE_TICK_UNIT * 2)
    scaled = [e for e in log.entries if e.phase == PHASE_UPKEEP and "공격력" in e.outcome]
    assert len(scaled) == 2
    assert "+2%" in scaled[-1].outcome


def test_floor_ticks_survive_a_room_change(templates, balance):
    # 방을 옮겨 시간을 리셋하는 우회를 막는다 — 층 지연은 층 단위로 센다.
    tracker = make_tracker(balance)
    first = make_state(templates)
    add_entity(first, "enemy_0", (9, 2), FACTION_ENEMY)
    run_ticks(tracker, first, EventLog(), FLOOR_SCALE_TICK_UNIT * 3)

    tracker.reset_room()
    second = make_state(templates, "corridor")
    fresh = add_entity(second, "enemy_0", (9, 2), FACTION_ENEMY)
    run_ticks(tracker, second, EventLog(), 1)

    assert tracker.floor_ticks == FLOOR_SCALE_TICK_UNIT * 3 + 1
    assert fresh.attack == BASE_ATTACK + 3


def test_floor_reset_clears_the_bonus(templates, balance):
    state = make_state(templates)
    enemy = add_entity(state, "enemy", (9, 2), FACTION_ENEMY)
    tracker = make_tracker(balance)

    run_ticks(tracker, state, EventLog(), FLOOR_SCALE_TICK_UNIT * 3)
    tracker.reset_floor()
    enemy.attack = BASE_ATTACK
    run_ticks(tracker, state, EventLog(), 1)

    assert tracker.floor_ticks == 1
    assert enemy.attack == BASE_ATTACK


# ── 규칙 로드 ────────────────────────────────────────────────────────────────


def test_rules_come_from_balance_json(balance):
    rules = build_pressure_rules(balance["anti_abuse"])
    raw = balance["anti_abuse"]
    assert rules.hunter_spawn_tick == raw["hunter_spawn_tick"]
    assert rules.hunter_interval_ticks == raw["hunter_interval_ticks"]
    assert rules.hunter_entity == raw["hunter_entity"]
    assert rules.floor_attack_pct_per_10_ticks == raw["floor_attack_pct_per_10_ticks"]
    assert rules.combat_regen_pct == raw["combat_regen_pct"]
    assert rules.spring_pool_default == raw["spring_pool_default"]


def test_missing_section_falls_back_to_defaults():
    assert build_pressure_rules({}) == PressureRules()


def test_zero_interval_is_rejected():
    # 0 이면 한 틱에 무한히 스폰한다.
    with pytest.raises(ValueError, match="hunter_interval_ticks"):
        build_pressure_rules({"hunter_interval_ticks": 0})


# ── 결정론 (R5) ─────────────────────────────────────────────────────────────


def create_scenario(templates, balance, seed):
    """추격자가 세 번 올 때까지 돌리고 로그와 배치를 돌려준다."""
    state = make_state(templates, seed=seed)
    add_entity(state, "player", (1, 4))
    add_entity(state, "enemy", (9, 2), FACTION_ENEMY)
    tracker = make_tracker(balance)
    log = EventLog()
    run_ticks(tracker, state, log, SPAWN_TICK + INTERVAL * 2 + 1)
    placements = tuple((e.entity_id, e.position, e.attack) for e in state.list_actors())
    return log.format_lines(), placements


def test_same_seed_gives_the_same_result(templates, balance):
    first = create_scenario(templates, balance, SEED)
    assert first == create_scenario(templates, balance, SEED)


def test_hunter_ids_are_unique(templates, balance):
    _, placements = create_scenario(templates, balance, SEED)
    ids = [entity_id for entity_id, _, _ in placements]
    assert len(set(ids)) == len(ids)


def test_spawn_position_comes_from_the_world_rng(templates, balance):
    # random 이나 시간이 아니라 WorldState.rng 를 쓴다는 것을 수열 전진으로 본다.
    state = make_state(templates)
    add_entity(state, "player", (1, 4))
    tracker = make_tracker(balance)
    run_ticks(tracker, state, EventLog(), SPAWN_TICK + 1)

    assert state.rng.get_uint64() != DeterministicRng(SEED).get_uint64()
