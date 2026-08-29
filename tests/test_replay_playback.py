"""되감기 재생과 피해 히트맵 테스트 (로드맵 W8, GDD §8.3).

`test_replay.py` 에서 갈라 나왔다 — 앞쪽은 "같은 판이 다시 나오는가", 여기는 "나온 판을
어떻게 되돌려 보는가" 다.
"""

import pytest

from game.app.core.event_log import LogEntry
from game.app.services.analyze_battle import (
    HEATMAP_EMPTY,
    build_damage_heatmap,
    extract_damage_hits,
    format_damage_heatmap,
)
from game.app.services.replay_battle import (
    build_replay_record,
    format_playback_lines,
    read_positions,
    run_replay,
)
from game.app.services.run_battle import (
    assign_enemy_policies,
    build_engine,
    load_balance,
    run_battle,
)
from game.app.services.run_stepped_battle import (
    SPEED_INSTANT,
    SPEED_PAUSE,
    get_step_ticks,
    iter_tick_batches,
    run_tick_batch,
)
from game.app.simulation.phases import PHASE_ACT, PHASE_UPKEEP
from game.config import (
    BALANCE_PATH,
    BLOCKS_PATH,
    ENEMY_RULESETS_PATH,
    G0_RULESETS_PATH,
    ROOM_TEMPLATES_PATH,
)
from game.schemas.blocks import load_block_catalog
from game.schemas.room import load_room_templates
from game.schemas.ruleset import load_rulesets

SEED = 12345
RULESET_ID = "g0_kite"
ROOM_ID = "corridor"
PLAYER_ID = "player"
ROOM_WIDTH = 12
ROOM_HEIGHT = 9


@pytest.fixture(scope="module")
def balance():
    return load_balance(BALANCE_PATH)


@pytest.fixture(scope="module")
def catalog():
    return load_block_catalog(BLOCKS_PATH)


@pytest.fixture(scope="module")
def templates():
    return {t.template_id: t for t in load_room_templates(ROOM_TEMPLATES_PATH)}


@pytest.fixture(scope="module")
def enemy_rulesets():
    return load_rulesets(ENEMY_RULESETS_PATH)


@pytest.fixture(scope="module")
def player_ruleset():
    return load_rulesets(G0_RULESETS_PATH)[RULESET_ID]


@pytest.fixture
def record(player_ruleset):
    return build_replay_record(SEED, (ROOM_ID,), player_ruleset)


def replay(record, templates, balance, catalog, enemy_rulesets):
    return run_replay(record, templates, balance, catalog, enemy_rulesets)


# ── 스텝 실행 (배속) ─────────────────────────────────────────────────────────


def test_step_ticks_map_to_speed_labels():
    assert get_step_ticks(SPEED_PAUSE) == 0
    assert get_step_ticks("1x") == 1
    assert get_step_ticks("2x") == 2
    assert get_step_ticks("4x") == 4
    assert get_step_ticks(SPEED_INSTANT, max_ticks=400) == 400


def test_unknown_speed_label_fails_loudly():
    with pytest.raises(ValueError, match="모르는 배속"):
        get_step_ticks("8x")


def test_tick_batch_stops_after_requested_ticks(templates, balance):
    engine = build_engine(templates[ROOM_ID], balance, seed=SEED)
    batch = run_tick_batch(engine, 3)
    assert (batch.start_tick, batch.end_tick) == (1, 3)
    assert engine.state.tick == 3
    assert {entry.tick for entry in batch.entries} == {1, 2, 3}
    # 다음 구간은 이어서 시작한다.
    following = run_tick_batch(engine, 2)
    assert (following.start_tick, following.end_tick) == (4, 5)


def test_paused_step_runs_nothing(templates, balance):
    engine = build_engine(templates[ROOM_ID], balance, seed=SEED)
    batch = run_tick_batch(engine, get_step_ticks(SPEED_PAUSE))
    assert engine.state.tick == 0
    assert batch.entries == ()
    # 0틱을 계속 돌리면 전투가 끝나지 않으므로 구간을 하나도 내지 않는다.
    assert iter_tick_batches(engine, 0) == ()


def test_stepped_run_equals_single_run(templates, balance, catalog, enemy_rulesets):
    def build_local():
        engine = build_engine(templates[ROOM_ID], balance, seed=SEED)
        assign_enemy_policies(engine, balance, catalog, enemy_rulesets)
        return engine

    stepped = build_local()
    batches = iter_tick_batches(stepped, 4)
    whole = run_battle(build_local())
    lines = [line for batch in batches for line in format_playback_lines(batch.entries)]
    assert tuple(lines) == whole.log_lines
    assert batches[-1].outcome == whole.outcome
    assert batches[-1].end_tick == whole.ticks


# ── 피해 히트맵 ──────────────────────────────────────────────────────────────


def test_heatmap_total_equals_actual_damage(record, templates, balance, catalog, enemy_rulesets):
    room = replay(record, templates, balance, catalog, enemy_rulesets).last_room
    logged = sum(
        -entry.delta
        for entry in room.entries
        if entry.target_id == PLAYER_ID and entry.delta is not None and entry.delta < 0
    )
    grid = build_damage_heatmap(room.hits, room.width, room.height, target_id=PLAYER_ID)
    assert logged > 0
    assert sum(sum(row) for row in grid) == logged


def test_heatmap_counts_every_entity_when_untargeted(
    record, templates, balance, catalog, enemy_rulesets
):
    room = replay(record, templates, balance, catalog, enemy_rulesets).last_room
    logged = sum(
        -entry.delta
        for entry in room.entries
        if entry.target_id is not None and entry.delta is not None and entry.delta < 0
    )
    grid = build_damage_heatmap(room.hits, room.width, room.height)
    assert sum(sum(row) for row in grid) == logged


def test_heatmap_has_room_shape(record, templates, balance, catalog, enemy_rulesets):
    room = replay(record, templates, balance, catalog, enemy_rulesets).last_room
    grid = build_damage_heatmap(room.hits, room.width, room.height)
    assert (room.width, room.height) == (ROOM_WIDTH, ROOM_HEIGHT)
    assert len(grid) == ROOM_HEIGHT
    assert all(len(row) == ROOM_WIDTH for row in grid)


def test_heatmap_marks_the_tile_that_was_hit(record, templates, balance, catalog, enemy_rulesets):
    room = replay(record, templates, balance, catalog, enemy_rulesets).last_room
    hit = next(hit for hit in room.hits if hit.target_id == PLAYER_ID)
    grid = build_damage_heatmap(room.hits, room.width, room.height, target_id=PLAYER_ID)
    x, y = hit.position
    assert grid[y][x] >= hit.amount


def test_heatmap_text_has_a_row_per_tile_row():
    grid = build_damage_heatmap((), ROOM_WIDTH, ROOM_HEIGHT)
    lines = format_damage_heatmap(grid).splitlines()
    # 머리글 한 줄 + 세로 칸 수만큼.
    assert len(lines) == ROOM_HEIGHT + 1
    assert lines[-1].count(HEATMAP_EMPTY) == ROOM_WIDTH
    assert format_damage_heatmap(()) == ""


def test_pre_move_damage_uses_the_tile_it_happened_on():
    # UPKEEP 의 용암 피해는 출발 칸에서 난다. 도착 칸으로 세면 지나온 위험이
    # 지도에서 지워져, 히트맵을 보고 경로를 고칠 수 없게 된다.
    start = {PLAYER_ID: (1, 1)}
    end = {PLAYER_ID: (2, 1)}
    lava = LogEntry(
        tick=1,
        entity_id=PLAYER_ID,
        phase=PHASE_UPKEEP,
        expr="용암 위",
        outcome="player HP 97/100",
        delta=-3,
        target_id=PLAYER_ID,
    )
    struck = LogEntry(
        tick=1,
        entity_id="goblin_rusher_0",
        phase=PHASE_ACT,
        expr="ATTACK @player",
        outcome="player HP 88/100",
        delta=-9,
        target_id=PLAYER_ID,
    )
    hits = extract_damage_hits((lava, struck), start, end)
    assert [hit.position for hit in hits] == [(1, 1), (2, 1)]
    assert [hit.amount for hit in hits] == [3, 9]


def test_non_damage_entries_are_not_hits():
    heal = LogEntry(
        tick=1,
        entity_id=PLAYER_ID,
        phase=PHASE_ACT,
        expr="USE_POTION",
        outcome="회복",
        delta=30,
        target_id=PLAYER_ID,
    )
    decided = LogEntry(tick=1, entity_id=PLAYER_ID, phase=PHASE_ACT, expr="", outcome="")
    assert extract_damage_hits((heal, decided), {PLAYER_ID: (0, 0)}, {PLAYER_ID: (0, 0)}) == ()


def test_newcomer_damage_falls_back_to_end_positions():
    # 그 틱에 소환된 개체는 시작 좌표표에 없다. 버리면 소환물이 맞은 피해가 샌다.
    summoned = LogEntry(
        tick=4,
        entity_id=PLAYER_ID,
        phase=PHASE_ACT,
        expr="ATTACK @slime_4",
        outcome="slime_4 HP 1/6",
        delta=-5,
        target_id="slime_4",
    )
    hits = extract_damage_hits((summoned,), {}, {"slime_4": (7, 2)})
    assert hits[0].position == (7, 2)


def test_positions_include_the_dead(templates, balance, catalog, enemy_rulesets):
    # 죽인 그 한 방이 난 칸이 히트맵에서 가장 중요한 칸이다.
    engine = build_engine(templates[ROOM_ID], balance, seed=SEED)
    assign_enemy_policies(engine, balance, catalog, enemy_rulesets)
    run_battle(engine)
    positions = read_positions(engine.state)
    assert set(positions) == set(engine.state.entities)
    assert len(positions) > len(engine.state.list_actors())
