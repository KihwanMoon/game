"""리플레이·스텝 실행·피해 히트맵 회귀 (W8, TDD §9 · GDD §8.3).

보는 것은 셋이다.
1. **시드와 규칙표만으로 같은 전투가 나오는가** — 이것이 깨지면 리플레이가
   저장이 아니라 거짓말이 된다 (R5).
2. **직전 N틱 추출이 맞는가** — 사망 리플레이가 보여 줄 구간이다.
3. **히트맵 합계가 실제 피해와 같은가** — 좌표 복원 과정에서 한 대라도 새면
   "어느 칸이 위험한가" 의 답이 조용히 틀린다.
"""

import json

import pytest

from game.app.core.event_log import LogEntry
from game.app.rules.rule_vm import build_rule_vm
from game.app.services.analyze_battle import (
    HEATMAP_EMPTY,
    build_damage_heatmap,
    extract_damage_hits,
    format_damage_heatmap,
)
from game.app.services.replay_battle import (
    CORE_VERSION,
    DEATH_REPLAY_TICKS,
    REPLAY_FORMAT_VERSION,
    ReplayRecord,
    build_replay_payload,
    build_replay_record,
    filter_recent_entries,
    format_playback_lines,
    is_current_core,
    load_replay,
    parse_replay,
    read_positions,
    run_replay,
    save_replay,
)
from game.app.services.run_battle import (
    assign_enemy_policies,
    build_engine,
    load_balance,
    run_battle,
)
from game.app.services.run_chain import run_room_chain
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
ROOM_ID = "corridor"
LONG_ROOM_ID = "hazard_field"
CHAIN_ROOMS = ("open_field", "corridor", "pillars")
RULESET_ID = "g0_kite"
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


# ── 재현 ─────────────────────────────────────────────────────────────────────


def test_replay_repeats_same_battle(record, templates, balance, catalog, enemy_rulesets):
    # 같은 리플레이를 두 번 돌리면 로그 한 줄까지 같아야 한다 (R5).
    first = replay(record, templates, balance, catalog, enemy_rulesets)
    second = replay(record, templates, balance, catalog, enemy_rulesets)
    assert format_playback_lines(first.last_room.entries) == format_playback_lines(
        second.last_room.entries
    )
    assert (first.outcome, first.total_ticks, first.player_hp) == (
        second.outcome,
        second.total_ticks,
        second.player_hp,
    )


def test_replay_matches_direct_run(record, templates, balance, catalog, enemy_rulesets):
    # 틱을 끊어 돌리는 관찰 경로가 전투 자체를 바꾸면 안 된다.
    playback = replay(record, templates, balance, catalog, enemy_rulesets)
    engine = build_engine(templates[ROOM_ID], balance, seed=SEED)
    engine.policies[PLAYER_ID] = build_rule_vm(record.ruleset, catalog, engine.config.kind_types)
    assign_enemy_policies(engine, balance, catalog, enemy_rulesets)
    direct = run_battle(engine)
    assert playback.last_room.outcome == direct.outcome
    assert playback.last_room.ticks == direct.ticks
    assert format_playback_lines(playback.last_room.entries) == direct.log_lines


def test_replay_reproduces_room_chain(templates, balance, catalog, enemy_rulesets, player_ruleset):
    # 마지막 방만 담으면 앞 방에서 인계된 HP·층 압력이 빠져 같은 전투가 되지 않는다.
    chained = build_replay_record(SEED, CHAIN_ROOMS, player_ruleset)
    playback = replay(chained, templates, balance, catalog, enemy_rulesets)
    expected = run_room_chain(
        tuple(templates[room_id] for room_id in CHAIN_ROOMS),
        balance,
        catalog,
        player_ruleset,
        enemy_rulesets,
        seed=SEED,
    )
    assert playback.outcome == expected.outcome
    assert playback.total_ticks == expected.total_ticks
    assert playback.player_hp == expected.player_hp
    assert len(playback.rooms) == len(expected.per_room)
    assert playback.last_room.entries[-1].tick == expected.per_room[-1].ticks


def test_replay_without_ruleset_uses_fallback(templates, balance, catalog, enemy_rulesets):
    # 폴백 런도 리플레이 대상이다. 규칙표 없이 진 런이야말로 볼 값이 있다.
    playback = replay(
        build_replay_record(SEED, (ROOM_ID,)), templates, balance, catalog, enemy_rulesets
    )
    assert playback.last_room.entries


# ── 저장·로드 ────────────────────────────────────────────────────────────────


def test_replay_survives_serialization_round_trip(record, tmp_path):
    target = tmp_path / "nested" / "run.json"
    save_replay(record, target)
    loaded = load_replay(target)
    assert loaded == record
    # 수 KB 여야 서버에 쌓아 둘 수 있다 (TDD §9).
    assert target.stat().st_size < 8192


def test_saved_replay_is_byte_identical(record, tmp_path):
    # 같은 런이 실행마다 다른 파일이 되면 파일 비교가 런 비교를 대신하지 못한다.
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    save_replay(record, first)
    save_replay(record, second)
    assert first.read_bytes() == second.read_bytes()


def test_loaded_replay_runs_the_same_battle(
    record, templates, balance, catalog, enemy_rulesets, tmp_path
):
    target = tmp_path / "run.json"
    save_replay(record, target)
    original = replay(record, templates, balance, catalog, enemy_rulesets)
    restored = replay(load_replay(target), templates, balance, catalog, enemy_rulesets)
    assert format_playback_lines(original.last_room.entries) == format_playback_lines(
        restored.last_room.entries
    )


def test_replay_payload_keeps_only_seed_and_ruleset(record):
    payload = build_replay_payload(record)
    assert set(payload) == {
        "format_version",
        "core_version",
        "seed",
        "room_ids",
        "max_ticks",
        "ruleset",
    }
    # 틱마다의 상태를 담지 않는 것이 이 형식의 요점이다.
    assert "entities" not in json.dumps(payload)


def test_old_core_replay_is_read_but_not_replayed(
    record, templates, balance, catalog, enemy_rulesets
):
    # 세대가 다르면 읽기는 한다 — 읽지 못하면 "구버전" 배지조차 붙일 수 없다.
    payload = build_replay_payload(record)
    payload["core_version"] = CORE_VERSION - 1
    stale = parse_replay(payload)
    assert stale.core_version == CORE_VERSION - 1
    assert not is_current_core(stale)
    with pytest.raises(ValueError, match="재생할 수 없는"):
        run_replay(stale, templates, balance, catalog, enemy_rulesets)


def test_current_record_is_current_core(record):
    assert is_current_core(record)
    assert record.format_version == REPLAY_FORMAT_VERSION


def test_replay_of_unknown_room_fails_loudly(templates, balance, catalog, enemy_rulesets):
    missing = ReplayRecord(seed=SEED, room_ids=("없는_방",))
    with pytest.raises(KeyError):
        run_replay(missing, templates, balance, catalog, enemy_rulesets)


# ── 직전 N틱 ─────────────────────────────────────────────────────────────────


def test_recent_entries_keep_only_last_ticks(templates, balance, catalog, enemy_rulesets):
    # 15틱보다 긴 전투라야 잘라 내는 동작이 실제로 검사된다.
    long_run = build_replay_record(SEED, (LONG_ROOM_ID,))
    room = replay(long_run, templates, balance, catalog, enemy_rulesets).last_room
    assert room.ticks > DEATH_REPLAY_TICKS
    recent = filter_recent_entries(room.entries, DEATH_REPLAY_TICKS)
    first_tick = room.ticks - DEATH_REPLAY_TICKS + 1
    ticks = {entry.tick for entry in recent}
    assert min(ticks) == first_tick
    assert max(ticks) == room.ticks
    assert len(recent) < len(room.entries)
    # 잘라 낸 뒤에도 원본의 순서를 지킨다.
    assert list(recent) == [entry for entry in room.entries if entry.tick >= first_tick]


def test_recent_entries_handle_short_battles():
    entries = tuple(
        LogEntry(tick=tick, entity_id=PLAYER_ID, phase=PHASE_ACT, expr="", outcome="")
        for tick in (1, 2, 3)
    )
    # 전투가 요청한 틱보다 짧으면 있는 것을 전부 낸다.
    assert filter_recent_entries(entries, DEATH_REPLAY_TICKS) == entries
    assert filter_recent_entries(entries, 1) == entries[-1:]
    assert filter_recent_entries(entries, 0) == ()
    assert filter_recent_entries((), DEATH_REPLAY_TICKS) == ()


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
