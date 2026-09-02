"""맵 연쇄와 헤드리스 배치 러너 (로드맵 Phase 1 W3, TDD §10).

배치 러너의 값어치는 "밸런싱을 감이 아니라 데이터로" 하는 데 있다. 그러려면 같은
시드가 같은 통계를 내야 한다 — 그것이 깨지면 어제의 승률과 오늘의 승률을 비교할 수 없다.
"""

import pytest

from game.app.services.run_batch import run_batch
from game.app.services.run_battle import load_balance
from game.app.services.run_chain import run_room_chain
from game.app.simulation.plan import OUTCOME_PLAYER_WIN
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

# 스킬 v3(쿨타임 2배) 뒤 기준 카이팅이 pillars 를 못 깨서, 표본 연쇄를 실측으로
# 다시 골랐다 — kite 100% · pressure 0% · sniper 0% (12런, 시드 1).
CHAIN_IDS = ("open_field", "twin_door", "corridor")
BATCH_RUNS = 12


@pytest.fixture(scope="module")
def parts():
    rooms = {t.template_id: t for t in load_room_templates(ROOM_TEMPLATES_PATH)}
    return {
        "catalog": load_block_catalog(BLOCKS_PATH),
        "balance": load_balance(BALANCE_PATH),
        "chain": tuple(rooms[room_id] for room_id in CHAIN_IDS),
        "player": load_rulesets(G0_RULESETS_PATH),
        "enemy": load_rulesets(ENEMY_RULESETS_PATH),
    }


def run_chain_with(parts, ruleset_id, seed=1):
    return run_room_chain(
        parts["chain"],
        parts["balance"],
        parts["catalog"],
        parts["player"][ruleset_id] if ruleset_id else None,
        parts["enemy"],
        seed=seed,
    )


# ── 연쇄 ─────────────────────────────────────────────────────────────────────


def test_chain_stops_at_the_room_that_killed_you(parts):
    result = run_chain_with(parts, "g0_pressure")
    assert result.cleared_rooms < len(CHAIN_IDS)
    assert len(result.per_room) == result.cleared_rooms + 1


def test_chain_carries_hp_between_rooms(parts):
    result = run_chain_with(parts, "g0_kite")
    assert result.cleared_rooms == len(CHAIN_IDS)
    # 방마다 HP 가 초기화되면 연쇄가 난이도를 만들지 못한다.
    assert result.player_hp < parts["balance"]["player"]["hp_max"]


def test_chain_is_reproducible(parts):
    first = run_chain_with(parts, "g0_kite", seed=99)
    second = run_chain_with(parts, "g0_kite", seed=99)
    assert (first.outcome, first.cleared_rooms, first.total_ticks, first.player_hp) == (
        second.outcome,
        second.cleared_rooms,
        second.total_ticks,
        second.player_hp,
    )


def test_chain_seeds_differ_per_room(parts):
    # 한 수열을 공유하면 앞 방이 바뀔 때 뒷 방까지 흔들린다 (R5).
    result = run_chain_with(parts, "g0_kite")
    assert len({r.ticks for r in result.per_room}) > 1


def test_winning_chain_reports_win(parts):
    result = run_chain_with(parts, "g0_kite")
    assert result.outcome == OUTCOME_PLAYER_WIN


# ── 배치 ─────────────────────────────────────────────────────────────────────


def test_batch_reports_win_rate(parts):
    stats = run_batch(
        "g0_kite",
        parts["chain"],
        parts["balance"],
        parts["catalog"],
        parts["player"]["g0_kite"],
        parts["enemy"],
        runs=BATCH_RUNS,
    )
    assert stats.runs == BATCH_RUNS
    assert 0 <= stats.win_rate_pct <= 100


def test_batch_is_reproducible(parts):
    kwargs = dict(
        templates=parts["chain"],
        balance=parts["balance"],
        catalog=parts["catalog"],
        player_ruleset=parts["player"]["g0_pressure"],
        enemy_rulesets=parts["enemy"],
        runs=BATCH_RUNS,
        base_seed=7,
    )
    first = run_batch("a", **kwargs)
    second = run_batch("a", **kwargs)
    assert (first.wins, first.average_ticks, first.average_hp) == (
        second.wins,
        second.average_ticks,
        second.average_hp,
    )


def test_batch_records_a_seed_to_reproduce_the_worst_run(parts):
    # 진 런을 시드만 들고 그대로 재현할 수 있어야 원인을 볼 수 있다 (P1).
    stats = run_batch(
        "g0_pressure",
        parts["chain"],
        parts["balance"],
        parts["catalog"],
        parts["player"]["g0_pressure"],
        parts["enemy"],
        runs=BATCH_RUNS,
        base_seed=1,
    )
    replay = run_chain_with(parts, "g0_pressure", seed=stats.worst_seed)
    assert replay.outcome != OUTCOME_PLAYER_WIN


def test_batch_detects_the_strategy_gap(parts):
    # 카이팅만 클리어하고 나머지는 첫 방에서 멈춘다. GDD §11 의 '단일 정답 수렴'
    # (R2) 이 실제로 일어나는지 배치가 보여줘야 한다.
    common = dict(
        templates=parts["chain"],
        balance=parts["balance"],
        catalog=parts["catalog"],
        enemy_rulesets=parts["enemy"],
        runs=BATCH_RUNS,
        base_seed=1,
    )
    kite = run_batch("g0_kite", player_ruleset=parts["player"]["g0_kite"], **common)
    pressure = run_batch("g0_pressure", player_ruleset=parts["player"]["g0_pressure"], **common)
    assert kite.win_rate_pct > pressure.win_rate_pct
