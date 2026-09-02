"""블록 목록 v2·v3 테스트 — 대상/타일 거리 일반화와 조건 우변의 스탯 (F-1 잔여, F-2, F-3).

`test_rule_vm.py` 에서 갈라 나왔다. 나중에 붙인 블록들이 앞서 있던 평가 규약을 그대로
따르는지를 본다 — 값이 아니라 규약이 대상이다.
"""

import json
import re

import pytest

from game.app.rules.rule_vm import (
    RHS_STAT_READERS,
    build_rule_vm,
    evaluate_condition,
)
from game.app.rules.validator import validate_ruleset
from game.app.services.run_battle import (
    assign_enemy_policies,
    build_engine,
    load_balance,
    run_battle,
)
from game.config import (
    BALANCE_PATH,
    BLOCKS_PATH,
    ENEMY_RULESETS_PATH,
    G0_RULESETS_PATH,
    ROOM_TEMPLATES_PATH,
)
from game.schemas.blocks import load_block_catalog
from game.schemas.room import load_room_templates
from game.schemas.ruleset import (
    Condition,
    Rule,
    RuleSet,
    StatRef,
    Term,
    load_rulesets,
    parse_rhs,
    parse_term,
)

# 이 횟수 이상 시도하고도 전부 실패하면 우연이 아니라 구조 문제다.
MIN_ATTEMPTS_TO_JUDGE = 3


@pytest.fixture(scope="module")
def catalog():
    return load_block_catalog(BLOCKS_PATH)


@pytest.fixture(scope="module")
def balance():
    return load_balance(BALANCE_PATH)


@pytest.fixture(scope="module")
def rooms():
    return {t.template_id: t for t in load_room_templates(ROOM_TEMPLATES_PATH)}


@pytest.fixture(scope="module")
def rulesets():
    return load_rulesets(G0_RULESETS_PATH)


@pytest.fixture(scope="module")
def target_rooms():
    raw = json.loads(G0_RULESETS_PATH.read_text(encoding="utf-8"))
    return {r["ruleset_id"]: r["target_room"] for r in raw["rulesets"]}


@pytest.fixture
def engine(rooms, balance):
    return build_engine(rooms["open_field"], balance, seed=12345)


def make_rule(priority, lhs, cmp_op, rhs, action, target=None, param=None, cost=1, flag=None):
    return Rule(
        priority=priority,
        conditions=Condition(op="SINGLE", terms=(Term(lhs, cmp_op, rhs, param),)),
        action=action,
        target=target,
        set_flag=flag,
        cpu_cost=cost,
    )


# ── 블록 목록 v2 (F-1 잔여 / F-3 해결) ───────────────────────────────────────


def test_target_distance_is_addressable_per_selector(engine, catalog, balance):
    # 규칙이 자기 TARGET 과 무관하게 어느 셀렉터의 대상까지든 거리를 물을 수 있어야
    # `쿨타임 완료 → 사격 @소환사` 가 사거리 밖에서 헛치지 않는다.
    engine.state.tick = 1
    snapshot = engine.build_perceptions()["player"]
    for selector in ("NEAREST", "TYPE_SUMMONER", "LOWEST_HP"):
        assert isinstance(snapshot.read("target_distance", selector), int)


def test_target_distance_is_minus_one_when_nobody_matches(engine):
    # 보스는 이 방에 없다. -1 이어야 `<= 4` 같은 조건이 참이 되지 않는다.
    engine.state.tick = 1
    snapshot = engine.build_perceptions()["player"]
    assert snapshot.read("target_distance", "BOSS") == -1


def test_nearest_tile_distance_answers_for_heal_tiles(rooms, balance):
    # F-3 — 회복타일이 있는 방과 없는 방을 구분할 수 있어야 한다.
    with_spring = build_engine(rooms["spring_bait"], balance, seed=1)
    without = build_engine(rooms["open_field"], balance, seed=1)
    with_spring.state.tick = without.state.tick = 1
    assert with_spring.build_perceptions()["player"].read("nearest_tile_distance", "SPRING") >= 0
    assert without.build_perceptions()["player"].read("nearest_tile_distance", "SPRING") == -1


def test_skill_uses_its_own_range(rooms, balance, catalog):
    # balance.json 이 SKILL_2 에 사거리 4 를 선언한다. 엔진이 그것을 무시하면
    # 원거리 스킬을 전제한 규칙표가 매 틱 '사거리 밖'으로 헛돈다.
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    rules = (
        Rule(
            priority=1,
            conditions=Condition(op="SINGLE", terms=(Term("target_distance", "<=", 4, "NEAREST"),)),
            action="SKILL_2",
            target="NEAREST",
            cpu_cost=1,
        ),
    )
    local = build_engine(rooms["open_field"], balance, seed=1)
    local.policies["player"] = build_rule_vm(RuleSet("x", 1, rules), catalog, kinds)
    for _ in range(12):
        local.run_tick()
    hits = [e for e in local.log.entries if e.entity_id == "player" and e.delta is not None]
    assert hits, "사거리 4 스킬이 한 번도 맞지 않았다"


@pytest.mark.parametrize("ruleset_id", ["g0_pressure", "g0_kite"])
def test_designed_ruleset_beats_the_fallback(
    rulesets, catalog, balance, rooms, target_rooms, ruleset_id
):
    # 로직 설계가 결과를 바꾸는가 (GDD §0 — 성장은 로직 설계 실력으로).
    #
    # g0_cover 는 여기서 뺀다. 그 전략의 핵심인 MOVE_TO_COVER 와 LOS 조건이 아직
    # 없어서(Phase 2 W6) 규칙 5개 중 2개가 한 번도 발동하지 않는다. W6 이 들어오면
    # 이 목록에 다시 넣는다.
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    room = rooms[target_rooms[ruleset_id]]
    fallback = run_battle(build_engine(room, balance, seed=12345))
    local = build_engine(room, balance, seed=12345)
    local.policies["player"] = build_rule_vm(rulesets[ruleset_id], catalog, kinds)
    designed = run_battle(local)
    assert designed.player_hp > fallback.player_hp


@pytest.mark.parametrize("ruleset_id", ["g0_pressure", "g0_kite", "g0_cover"])
def test_g0_rulesets_waste_no_ticks(rulesets, catalog, balance, rooms, target_rooms, ruleset_id):
    # 발동했는데 아무 일도 못 하는 규칙이 있으면 플레이어는 자기 논리를 의심한다 (P1).
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    local = build_engine(rooms[target_rooms[ruleset_id]], balance, seed=12345)
    local.policies["player"] = build_rule_vm(rulesets[ruleset_id], catalog, kinds)
    # 적도 자기 규칙표로 싸우게 한다. 폴백으로 두면 실제와 다른 상황을 재는 셈이다.
    assign_enemy_policies(local, balance, catalog, load_rulesets(ENEMY_RULESETS_PATH))
    run_battle(local)

    # 가끔 헛치는 것은 결함이 아니다 — 궁수가 물러나면 DECIDE 시점에 참이던 사거리
    # 조건이 ACT 시점에 거짓이 된다. 그것은 PERCEPTION/ACT 분리의 정상적 귀결이고
    # 로그에 `사거리 밖(2 > 1)` 로 이유가 남는다.
    #
    # 잡아야 하는 것은 **한 번도 성공하지 못하는 규칙**이다. 그런 규칙은 구조가
    # 틀린 것이며, 플레이어는 자기 논리를 의심하게 된다 (P1).
    attempts: dict[int | None, list[bool]] = {}
    for entry in local.log.entries:
        if entry.entity_id != "player" or entry.phase != "ACT":
            continue
        attempts.setdefault(entry.rule, []).append("낭비" not in entry.outcome)

    dead_rules = [
        rule
        for rule, results in attempts.items()
        if len(results) >= MIN_ATTEMPTS_TO_JUDGE and not any(results)
    ]
    assert dead_rules == [], f"{ruleset_id}: 규칙 {dead_rules} 가 한 번도 성공하지 못했다"


# ── 블록 목록 v3 / F-2 (조건 우변에 스탯) ────────────────────────────────────


def test_literal_rhs_still_parses_as_a_literal():
    # 하위 호환 — 기존 규칙표 JSON 은 손대지 않고 그대로 돌아야 한다.
    assert parse_rhs(3) == 3
    assert parse_rhs(True) is True
    assert parse_term({"lhs": "self_hp_percent", "cmp": "<", "rhs": 20}).rhs == 20


def test_stat_rhs_parses_into_a_reference():
    term = parse_term(
        {
            "lhs": "target_distance",
            "lhs_param": "NEAREST",
            "cmp": "<=",
            "rhs": {"stat": "attack_range"},
        }
    )
    assert term.rhs == StatRef("attack_range")


def test_malformed_stat_rhs_is_rejected_at_parse_time():
    # 조용히 통과시키면 그 항은 영영 거짓이 되고, 플레이어는 자기 논리를 의심한다 (P1).
    with pytest.raises(ValueError, match="stat"):
        parse_rhs({"stats": "attack_range"})
    with pytest.raises(ValueError, match="우변"):
        parse_rhs("attack_range")


def test_stat_rhs_reads_the_actors_own_value(engine, catalog, balance):
    # 플레이어 사거리는 1 이고 적은 멀리 있다. 우변이 스탯이어도 판정은 그대로다.
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    rules = (
        make_rule(
            1, "target_distance", "<=", StatRef("attack_range"), "ATTACK", "NEAREST", "NEAREST"
        ),
        make_rule(2, "self_hp_percent", "<=", 100, "HOLD"),
    )
    vm = build_rule_vm(RuleSet("x", 1, rules), catalog, kinds)
    engine.state.tick = 1
    snapshot = engine.build_perceptions()["player"]
    plan = vm.plan_action(engine.state.entities["player"], snapshot, engine.state)
    assert plan.action_id == "HOLD"


def test_stat_rhs_follows_the_stat_not_the_literal(engine, catalog, balance):
    # F-2 의 요지 — 장비가 사거리를 바꾸면 규칙도 함께 바뀌어야 한다.
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    rules = (
        make_rule(
            1, "target_distance", "<=", StatRef("attack_range"), "ATTACK", "NEAREST", "NEAREST"
        ),
    )
    vm = build_rule_vm(RuleSet("x", 1, rules), catalog, kinds)
    player = engine.state.entities["player"]
    player.attack_range = 99
    engine.state.tick = 1
    snapshot = engine.build_perceptions()["player"]
    plan = vm.plan_action(player, snapshot, engine.state)
    assert plan.action_id == "ATTACK"
    assert "사거리(99)" in plan.expr


def test_stat_rhs_renders_both_measured_values(engine, catalog, balance):
    # GDD §8.2 — `적거리(2) <= 사거리(3)` 형태여야 고칠 곳이 특정된다.
    engine.state.tick = 1
    snapshot = engine.build_perceptions()["player"]
    condition = Condition(
        op="SINGLE",
        terms=(Term("target_distance", "<=", StatRef("attack_range"), "NEAREST"),),
    )
    _, expr = evaluate_condition(
        condition, snapshot, None, catalog, actor=engine.state.entities["player"]
    )
    assert re.fullmatch(r"대상 거리\[NEAREST\]\(\d+\) <= 사거리\(1\)", expr)


def test_unknown_stat_evaluates_false_not_true(engine, catalog, balance):
    # 값을 만들 수 없는 우변은 거짓이다. 0 으로 채우면 없는 스탯이 동작하는 척한다.
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    rules = (
        make_rule(
            1, "target_distance", "<=", StatRef("no_such_stat"), "ATTACK", "NEAREST", "NEAREST"
        ),
        make_rule(2, "self_hp_percent", "<=", 100, "HOLD"),
    )
    vm = build_rule_vm(RuleSet("x", 1, rules), catalog, kinds)
    engine.state.tick = 1
    snapshot = engine.build_perceptions()["player"]
    plan = vm.plan_action(engine.state.entities["player"], snapshot, engine.state)
    assert plan.action_id == "HOLD"


def test_validator_rejects_an_unknown_stat(catalog):
    rule = make_rule(1, "target_distance", "<=", StatRef("no_such_stat"), "HOLD", param="NEAREST")
    problems = validate_ruleset(RuleSet("x", 1, (rule,)), catalog, 99, 5)
    assert any("목록에 없는 스탯" in p for p in problems)


def test_validator_rejects_a_stat_compared_with_a_boolean_block(catalog):
    # `내 위치가 회복타일인가 == 사거리` 는 값이 나와도 뜻이 없다.
    rule = make_rule(1, "self_on_heal_tile", "==", StatRef("attack_range"), "HOLD")
    problems = validate_ruleset(RuleSet("x", 1, (rule,)), catalog, 99, 5)
    assert any("비교할 수 없다" in p for p in problems)


def test_stat_readers_cover_the_declared_list(catalog):
    # blocks.json 이 허용 목록의 정본이다. VM 이 읽지 못하는 스탯이 목록에 있으면
    # 그 스탯을 쓴 규칙이 검증은 통과하고 실행에서 조용히 거짓이 된다.
    assert set(RHS_STAT_READERS) == set(catalog.rhs_stats)


def test_self_selector_targets_the_actor(probe_world):
    """★ 자기 자신 셀렉터 (v8) — 만피여도 자신을 고른다.

    거르면 「참인데 대상 없음」과 「거짓」이 섞여 로그가 거짓말한다. ALLY_WOUNDED 가
    자신을 빼는 것과 짝이다 — 자기 회복·자기 강화를 지을 자리가 없었다.
    """
    from game.app.simulation.selectors import resolve_target

    world, player = probe_world(skills=())
    assert resolve_target("SELF", player, world, {}) is player
