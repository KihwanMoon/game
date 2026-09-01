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

CHAIN_IDS = ("open_field", "corridor", "pillars")
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


# ── 전략 공간 (R2 조기 감지) ─────────────────────────────────────────────────


def test_benchmark_rulesets_all_validate(parts):
    from game.app.rules.validator import validate_ruleset
    from game.config import BENCHMARK_RULESETS_PATH

    budget = parts["balance"]["player"]["cpu_budget"]
    slots = parts["balance"]["player"]["rule_slots"]
    for ruleset in load_rulesets(BENCHMARK_RULESETS_PATH).values():
        assert validate_ruleset(ruleset, parts["catalog"], budget, slots) == []


def test_rule_order_changes_the_outcome(parts):
    # sniper 와 g0_kite 는 거의 같은 블록을 쓴다. 차이는 플래그로 후퇴와 사격을
    # 교대시키느냐뿐이고, 그것이 승패를 가른다 — 이 게임이 파는 재미의 실증이다.
    from game.config import BENCHMARK_RULESETS_PATH

    benchmark = load_rulesets(BENCHMARK_RULESETS_PATH)
    common = dict(
        templates=parts["chain"],
        balance=parts["balance"],
        catalog=parts["catalog"],
        enemy_rulesets=parts["enemy"],
        runs=BATCH_RUNS,
        base_seed=1,
    )
    kite = run_batch("g0_kite", player_ruleset=parts["player"]["g0_kite"], **common)
    sniper = run_batch("sniper", player_ruleset=benchmark["sniper"], **common)
    assert kite.win_rate_pct > sniper.win_rate_pct


# ── 사후 분석 (GDD §8.3) ─────────────────────────────────────────────────────


def test_rule_stats_expose_the_broken_rule(parts):
    # sniper 는 후퇴가 사격보다 위에 있어 사격 규칙까지 평가가 내려가지 않는다.
    # 성적표 한 줄이 그것을 말해야 로그를 처음부터 읽지 않아도 고칠 곳이 특정된다.
    from game.app.rules.rule_vm import build_rule_vm
    from game.app.services.analyze_battle import build_rule_stats
    from game.app.services.run_battle import assign_enemy_policies, build_engine, run_battle
    from game.config import BENCHMARK_RULESETS_PATH

    benchmark = load_rulesets(BENCHMARK_RULESETS_PATH)
    engine = build_engine(parts["chain"][0], parts["balance"], seed=12345)
    engine.policies["player"] = build_rule_vm(
        benchmark["sniper"], parts["catalog"], engine.config.kind_types
    )
    assign_enemy_policies(engine, parts["balance"], parts["catalog"], parts["enemy"])
    run_battle(engine)

    stats = {s.label: s for s in build_rule_stats(engine.log, "player")}
    assert stats["[2]"].fired > stats["[3]"].fired * 5, "후퇴 편중이 드러나야 한다"


def test_damage_is_attributed_to_the_rule_that_caused_it(parts):
    # 규칙이 죽인 적이 DEFAULT 의 공으로 집계되면 사후 분석이 "어느 규칙이 통했는가" 를
    # 거짓으로 말한다. 디버깅 화면이 이 게임의 메인 UI 이므로(GDD §8) 치명적이다.
    from game.app.rules.rule_vm import build_rule_vm
    from game.app.services.run_battle import assign_enemy_policies, build_engine, run_battle

    engine = build_engine(parts["chain"][2], parts["balance"], seed=12345)
    engine.policies["player"] = build_rule_vm(
        parts["player"]["g0_kite"], parts["catalog"], engine.config.kind_types
    )
    assign_enemy_policies(engine, parts["balance"], parts["catalog"], parts["enemy"])
    run_battle(engine)

    strikes = [
        entry
        for entry in engine.log.entries
        if entry.entity_id == "player" and entry.delta is not None and entry.delta < 0
    ]
    assert strikes, "플레이어가 한 번도 때리지 않았다"
    attributed = [entry for entry in strikes if entry.rule is not None]
    assert attributed, "모든 피해가 DEFAULT 로 집계됐다 — 규칙 귀속이 끊겼다"


def test_rule_stats_do_not_credit_default_for_rule_work(parts):
    # 발동보다 성공이 많으면 다른 규칙의 성과가 흘러들어온 것이다.
    from game.app.rules.rule_vm import build_rule_vm
    from game.app.services.analyze_battle import build_rule_stats
    from game.app.services.run_battle import assign_enemy_policies, build_engine, run_battle

    engine = build_engine(parts["chain"][2], parts["balance"], seed=12345)
    engine.policies["player"] = build_rule_vm(
        parts["player"]["g0_kite"], parts["catalog"], engine.config.kind_types
    )
    assign_enemy_policies(engine, parts["balance"], parts["catalog"], parts["enemy"])
    run_battle(engine)

    for stat in build_rule_stats(engine.log, "player"):
        assert stat.acted + stat.wasted <= stat.fired, f"{stat.label} 성적이 발동 횟수를 넘는다"


# ── 패배의 기울기 (W18) ──────────────────────────────────────────────────────


def test_a_win_leaves_no_enemy_hp(parts):
    """★ 이겼으면 적이 다 죽은 것이다 — 0 이 아니면 이 지표를 못 믿는다."""
    stats = run_batch(
        "g0_kite",
        templates=parts["chain"],
        balance=parts["balance"],
        catalog=parts["catalog"],
        player_ruleset=parts["player"]["g0_kite"],
        enemy_rulesets=parts["enemy"],
        runs=BATCH_RUNS,
        base_seed=1,
    )
    assert stats.win_rate_pct == 100
    assert stats.enemy_hp_left_pct == 0


def test_the_margin_separates_two_kinds_of_loss(parts):
    """★ **승률이 감추던 것을 여기서 가른다.**

    시드는 틱과 HP 만 흔들고 승패는 거의 바꾸지 않아, 승률이 0% 아니면 100% 로만 나온다.
    그러면 「적 HP 를 거의 다 깎고 진 것」과 「한 대도 못 때리고 진 것」이 같은 0% 로
    적히고, 튜닝할 곳을 고를 수 없다.

    앞은 수치를 만지면 되고, 뒤는 **그 방에서 규칙표가 아예 작동하지 않는 것**이라
    고치는 방법이 다르다.
    """
    from game.config import BENCHMARK_RULESETS_PATH

    bench = load_rulesets(BENCHMARK_RULESETS_PATH)
    common = dict(
        templates=parts["chain"],
        balance=parts["balance"],
        catalog=parts["catalog"],
        enemy_rulesets=parts["enemy"],
        runs=BATCH_RUNS,
        base_seed=1,
    )
    # 소환사를 노리는 규칙표인데 첫 방에는 소환사가 없다 — 네 규칙이 전부 거짓이라
    # 가만히 서서 죽는다.
    idle = run_batch("focus_summoner", player_ruleset=bench["focus_summoner"], **common)
    # 끝까지 싸우고 아깝게 진다 — 적 HP 를 한 자리수만 남긴다.
    #
    # 예전에는 `spring_camp` 이었는데, **시야에 막힌 원거리 공격이 굳던 것을 고치자
    # 이겨 버렸다.** 지는 쪽 표본은 밸런스가 바뀔 때마다 다시 골라야 한다 — 그것이 이
    # 검사가 재는 것(전략 공간의 모양)이 실제로 움직인다는 뜻이기도 하다.
    close = run_batch("focus_lowest_guard", player_ruleset=bench["focus_lowest_guard"], **common)

    assert idle.win_rate_pct == close.win_rate_pct == 0, "둘 다 져야 이 검사가 뜻을 갖는다"
    assert idle.enemy_hp_left_pct == 100, idle
    assert close.enemy_hp_left_pct < idle.enemy_hp_left_pct, (close, idle)


# ── 폴백 한 줄 (전략 공간) ───────────────────────────────────────────────────


def test_guarded_variants_exist_for_every_selector_strategy():
    """★ 선택자 전략마다 폴백 있는 짝이 있다.

    없으면 배치가 "선택자 전략은 약하다" 로 읽히는데, 실제로는 **규칙표에 한 줄이
    빠진 것**이다. 짝이 있어야 그 둘이 구별된다.
    """
    from game.config import BENCHMARK_RULESETS_PATH

    bench = load_rulesets(BENCHMARK_RULESETS_PATH)
    for base in ("focus_lowest", "focus_threat", "focus_summoner", "focus_ranged"):
        assert f"{base}_guard" in bench, base


def test_the_guard_differs_by_exactly_one_rule():
    """★ **한 줄만 달라야 한다.**

    여러 줄이 다르면 결과 차이가 무엇 때문인지 말할 수 없고, 그러면 이 짝은 아무것도
    가르치지 못한다 — 튜토리얼이 sniper/g0_kite 를 쓰는 것과 같은 이유다.
    """
    from game.config import BENCHMARK_RULESETS_PATH

    bench = load_rulesets(BENCHMARK_RULESETS_PATH)
    for base_id in ("focus_lowest", "focus_threat", "focus_summoner", "focus_ranged"):
        base = bench[base_id]
        guard = bench[f"{base_id}_guard"]
        assert len(guard.rules) == len(base.rules) + 1, base_id
        # 끼운 줄을 빼면 나머지는 순서까지 같아야 한다.
        kept = [r for r in guard.rules if not (r.action == "ATTACK" and r.target == "NEAREST")]
        base_kept = [r for r in base.rules if not (r.action == "ATTACK" and r.target == "NEAREST")]
        assert [r.action for r in kept] == [r.action for r in base_kept], base_id


def test_the_guard_must_sit_above_the_approach():
    """★ 폴백이 접근 규칙 **아래**면 아무 일도 안 일어난다.

    접근 조건(`목표 거리 > 1`)이 먼저 참이라 차례가 오지 않는다 — 실제로 아래에 넣어
    재봤을 때 결과가 한 톨도 바뀌지 않았다. 튜토리얼 2단계가 가르치는 그것이다.
    """
    from game.config import BENCHMARK_RULESETS_PATH

    bench = load_rulesets(BENCHMARK_RULESETS_PATH)
    for base_id in ("focus_lowest", "focus_threat", "focus_summoner", "focus_ranged"):
        rules = bench[f"{base_id}_guard"].rules
        guard_at = next(
            i for i, r in enumerate(rules) if r.action == "ATTACK" and r.target == "NEAREST"
        )
        approach_at = next(i for i, r in enumerate(rules) if r.action == "APPROACH")
        assert guard_at < approach_at, base_id


def test_the_guard_actually_lands_hits(parts):
    """★ **여기가 이 짝의 전부다.**

    폴백이 없으면 좁은 복도에서 목표를 쫓다 길이 막히고, 바로 옆의 적을 한 번도 때리지
    못한 채 죽는다 — 로그가 「길 막힘 — 틱 낭비」로 그것을 말한다.
    """
    from game.config import BENCHMARK_RULESETS_PATH

    bench = load_rulesets(BENCHMARK_RULESETS_PATH)
    common = dict(
        templates=parts["chain"],
        balance=parts["balance"],
        catalog=parts["catalog"],
        enemy_rulesets=parts["enemy"],
        runs=BATCH_RUNS,
        base_seed=1,
    )
    bare = run_batch("focus_lowest", player_ruleset=bench["focus_lowest"], **common)
    guarded = run_batch("focus_lowest_guard", player_ruleset=bench["focus_lowest_guard"], **common)
    assert bare.enemy_hp_left_pct == 100, "폴백 없는 쪽이 한 대도 못 때려야 대비가 성립한다"
    assert guarded.enemy_hp_left_pct < bare.enemy_hp_left_pct, (guarded, bare)
    assert guarded.average_cleared > bare.average_cleared


def test_the_guard_fits_the_default_budget(parts):
    """★ 예산을 넘으면 플레이어가 이 규칙표를 쓸 수 없다."""
    from game.app.rules.validator import validate_ruleset
    from game.config import BENCHMARK_RULESETS_PATH

    bench = load_rulesets(BENCHMARK_RULESETS_PATH)
    budget = parts["balance"]["player"]["cpu_budget"]
    slots = parts["balance"]["player"]["rule_slots"]
    for base_id in ("focus_lowest", "focus_threat", "focus_summoner", "focus_ranged"):
        assert validate_ruleset(bench[f"{base_id}_guard"], parts["catalog"], budget, slots) == []
