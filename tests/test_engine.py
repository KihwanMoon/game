"""틱 엔진 회귀 테스트 (TDD §4, §10).

골든 리플레이의 성격을 갖는다 — 같은 시드가 같은 결과를 내는지가 핵심이고,
그것이 깨지면 리플레이·데일리 챌린지·헤드리스 밸런싱이 한꺼번에 무너진다 (R5).
"""

import re

import pytest

from game.app.core.rng import DeterministicRng
from game.app.grid.geometry import get_manhattan_distance, iter_neighbors, iter_steps
from game.app.pathfinding.distance_field import build_distance_field, find_next_step
from game.app.services.run_battle import build_engine, load_balance, run_battle
from game.app.simulation.plan import (
    OUTCOME_ONGOING,
    OUTCOME_PLAYER_LOSS,
    OUTCOME_PLAYER_WIN,
    OUTCOME_TIMEOUT,
    PHASE_ORDER,
)
from game.app.simulation.state import FACTION_ENEMY, WorldState
from game.config import BALANCE_PATH, ROOM_TEMPLATES_PATH
from game.schemas.room import load_room_templates

PHASE_COUNT = 7
STEP_DIRECTIONS = 4
NEIGHBOR_DIRECTIONS = 8


@pytest.fixture(scope="module")
def balance():
    return load_balance(BALANCE_PATH)


@pytest.fixture(scope="module")
def templates():
    return {t.template_id: t for t in load_room_templates(ROOM_TEMPLATES_PATH)}


# ── 기하 (F-5 결정: 4방향 이동 · 맨해튼 거리) ────────────────────────────────


def test_movement_has_four_directions():
    assert len(iter_steps((5, 5))) == STEP_DIRECTIONS


def test_surround_check_uses_eight_neighbors():
    # 이동은 4방향이지만 포위 판정은 8칸이다 (GDD §4.3). 두 기준은 다르다.
    assert len(iter_neighbors((5, 5))) == NEIGHBOR_DIRECTIONS


def test_distance_is_manhattan_not_chebyshev():
    # 대각선으로 한 칸 떨어진 적은 거리 2 다. 체비셰프라면 1 이었다.
    assert get_manhattan_distance((0, 0), (1, 1)) == 2
    assert get_manhattan_distance((0, 0), (3, 0)) == 3


# ── 거리장 ───────────────────────────────────────────────────────────────────


def test_distance_field_marks_goal_as_zero(templates):
    state = WorldState(room=templates["open_field"], rng=DeterministicRng(1))
    field = build_distance_field(state, ((5, 4),))
    assert field[(5, 4)] == 0


def test_distance_field_skips_walls(templates):
    state = WorldState(room=templates["open_field"], rng=DeterministicRng(1))
    field = build_distance_field(state, ((5, 4),))
    assert (0, 0) not in field  # 모서리는 벽이다


def test_distance_field_respects_blocked_cells(templates):
    state = WorldState(room=templates["corridor"], rng=DeterministicRng(1))
    blocked = frozenset({(5, 4), (6, 4)})  # 유일한 통로를 막는다
    field = build_distance_field(state, ((1, 3),), blocked=blocked)
    assert (10, 4) not in field


def test_next_step_moves_downhill(templates):
    state = WorldState(room=templates["open_field"], rng=DeterministicRng(1))
    field = build_distance_field(state, ((5, 4),))
    step = find_next_step(field, (8, 4))
    assert step is not None
    assert field[step] < field[(8, 4)]


def test_next_step_returns_none_at_the_goal(templates):
    state = WorldState(room=templates["open_field"], rng=DeterministicRng(1))
    field = build_distance_field(state, ((5, 4),))
    assert find_next_step(field, (5, 4)) is None


# ── 페이즈 ───────────────────────────────────────────────────────────────────


def test_phase_order_is_fixed():
    # TDD §4.1 — 순서가 바뀌면 PERCEPTION/DECIDE 분리의 의미가 사라진다.
    assert len(PHASE_ORDER) == PHASE_COUNT
    assert PHASE_ORDER[:2] == ("UPKEEP", "TELEGRAPH")
    assert PHASE_ORDER.index("PERCEPTION") < PHASE_ORDER.index("DECIDE")
    assert PHASE_ORDER.index("DECIDE") < PHASE_ORDER.index("ACT")
    assert PHASE_ORDER[-1] == "CLEANUP"


def test_tick_advances_by_one(templates, balance):
    engine = build_engine(templates["open_field"], balance, seed=7)
    engine.run_tick()
    assert engine.state.tick == 1


def test_decide_does_not_mutate_the_world(templates, balance):
    # DECIDE 는 계획만 돌려주고 세계를 바꾸지 않는다 (TDD §4.1).
    engine = build_engine(templates["open_field"], balance, seed=7)
    engine.state.tick = 1
    before = {e.entity_id: (e.position, e.hp) for e in engine.state.list_actors()}
    snapshots = engine.build_perceptions()
    engine.plan_actions(snapshots)
    after = {e.entity_id: (e.position, e.hp) for e in engine.state.list_actors()}
    assert before == after


def test_perception_snapshot_is_shared_within_a_tick(templates, balance):
    engine = build_engine(templates["open_field"], balance, seed=7)
    engine.state.tick = 1
    snapshots = engine.build_perceptions()
    player = snapshots["player"]
    # 스냅샷을 만든 뒤 세계가 바뀌어도 이미 고정된 값은 흔들리지 않는다.
    engine.state.entities["player"].hp = 1
    assert player.read("self_hp_percent") == 100


def test_deferred_blocks_read_as_none(templates, balance):
    # 아직 만들 수 없는 값은 0 이 아니라 None 이어야 "없음"과 "0"이 구분된다.
    engine = build_engine(templates["open_field"], balance, seed=7)
    snapshot = engine.build_perceptions()["player"]
    assert snapshot.read("self_exposed_to_los") is None
    assert snapshot.read("self_cpu_headroom") is None


def test_parameterized_perceptions_are_addressable(templates, balance):
    engine = build_engine(templates["open_field"], balance, seed=7)
    snapshot = engine.build_perceptions()["player"]
    assert snapshot.read("self_cooldown_ready", "SKILL_1") is True
    assert snapshot.read("flag_state", "A") is False
    assert snapshot.read("enemy_type_present", "MELEE") is True


# ── 결정론 ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "room_id", ["open_field", "corridor", "pillars", "hazard_field", "spring_bait"]
)
def test_same_seed_reproduces_the_battle(templates, balance, room_id):
    first = run_battle(build_engine(templates[room_id], balance, seed=4242))
    second = run_battle(build_engine(templates[room_id], balance, seed=4242))
    assert (first.outcome, first.ticks, first.player_hp) == (
        second.outcome,
        second.ticks,
        second.player_hp,
    )
    assert first.log_lines == second.log_lines


def test_battle_terminates_with_a_verdict(templates, balance):
    result = run_battle(build_engine(templates["open_field"], balance, seed=1))
    assert result.outcome in {OUTCOME_PLAYER_WIN, OUTCOME_PLAYER_LOSS, OUTCOME_TIMEOUT}
    assert result.outcome != OUTCOME_ONGOING


def test_timeout_is_reachable(templates, balance):
    # 무한 루프가 아니라 시간 초과로 끝나는지. 틱 상한을 낮춰 강제한다.
    result = run_battle(build_engine(templates["corridor"], balance, seed=1, max_ticks=3))
    assert result.outcome == OUTCOME_TIMEOUT
    assert result.ticks == 3


# ── 전투 ─────────────────────────────────────────────────────────────────────


def test_player_takes_damage_over_time(templates, balance):
    result = run_battle(build_engine(templates["open_field"], balance, seed=99))
    assert result.player_hp < balance["player"]["hp_max"]


def test_log_records_the_design_contract_fields(templates, balance):
    # 디자인의 LogRow 가 tick·rule·expr·outcome·delta·fired 를 받는다.
    engine = build_engine(templates["open_field"], balance, seed=5)
    for _ in range(12):
        engine.run_tick()
    assert engine.log.count() > 0
    entry = engine.log.entries[0]
    assert entry.tick >= 1
    assert entry.expr and entry.outcome
    assert isinstance(entry.fired, bool)


def test_log_expr_carries_measured_values(templates, balance):
    # GDD §8.2 — 평가된 조건의 실제 값이 남아야 죽고 나서 원인을 특정할 수 있다.
    engine = build_engine(templates["open_field"], balance, seed=5)
    engine.run_tick()
    # 항마다 괄호로 실측값이 붙어야 한다 — `적거리(9) > 사거리(1)` 형태.
    measured = re.compile(r"\S+\(-?\d+\)\s*(<=|>=|<|>|==|!=)\s*\S+\(-?\d+\)")
    assert any(measured.search(entry.expr) for entry in engine.log.entries)


def test_regen_is_damped_during_combat(templates, balance):
    # GDD §7 — 전투 중 base_regen 감쇠. 정수 연산이라 regen_base 1 은 0 이 된다.
    engine = build_engine(templates["open_field"], balance, seed=3)
    player = engine.state.entities["player"]
    player.hp = 50
    engine.run_upkeep()
    assert player.hp == 50


def test_regen_applies_without_enemies(templates, balance):
    engine = build_engine(templates["open_field"], balance, seed=3)
    for entity_id in [
        e.entity_id for e in engine.state.list_actors() if e.faction == FACTION_ENEMY
    ]:
        engine.state.entities[entity_id].hp = 0
    player = engine.state.entities["player"]
    player.hp = 50
    engine.run_upkeep()
    assert player.hp == 51


def test_lava_hurts_whoever_stands_on_it(templates, balance):
    engine = build_engine(templates["hazard_field"], balance, seed=3)
    player = engine.state.entities["player"]
    player.position = (2, 2)  # 용암 칸
    before = player.hp
    engine.run_upkeep()
    assert player.hp < before


def test_potion_restores_and_is_consumed(templates, balance):
    engine = build_engine(templates["open_field"], balance, seed=3)
    player = engine.state.entities["player"]
    player.hp = 20
    potions_before = player.potions
    for _ in range(3):
        engine.run_tick()
        if player.potions < potions_before:
            break
    assert player.potions < potions_before
    assert player.hp > 20
