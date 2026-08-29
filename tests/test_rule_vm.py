"""RuleVM 회귀 테스트 (TDD §5).

핵심은 세 가지다 — 평가 순서(셀렉터 → 조건 → 행동), 최초로 참인 규칙 하나만 실행,
그리고 조건 문자열에 실측값이 붙는가. 셋 중 하나라도 깨지면 죽고 나서 어느 규칙이 왜
틀렸는지 특정할 수 없다 (P1).
"""

import json

import pytest

from game.app.rules.rule_vm import (
    build_rule_vm,
    count_cpu_usage,
    evaluate_condition,
)
from game.app.rules.validator import validate_ruleset
from game.app.services.run_battle import (
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
    Term,
    load_rulesets,
)

G0_COUNT = 3


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


# ── 파싱 ─────────────────────────────────────────────────────────────────────


def test_rules_are_sorted_by_priority(rulesets):
    for ruleset in rulesets.values():
        priorities = [r.priority for r in ruleset.rules]
        assert priorities == sorted(priorities)


def test_all_g0_rulesets_load(rulesets):
    assert len(rulesets) == G0_COUNT


def test_enemy_rulesets_pass_validation(catalog, balance):
    # 적도 플레이어와 같은 검증을 통과해야 한다 (GDD §5). 통과하지 못하는 규칙표를
    # 도감이 보여주면 플레이어가 읽고 세운 카운터가 통하지 않는다.
    by_ruleset = {kind["ruleset_id"]: kind for kind in balance["enemies"]}
    for ruleset_id, ruleset in load_rulesets(ENEMY_RULESETS_PATH).items():
        kind = by_ruleset[ruleset_id]
        problems = validate_ruleset(ruleset, catalog, kind["cpu_budget"], kind["rule_slots"])
        assert problems == [], f"{ruleset_id}: {problems}"


def test_summoner_ruleset_plans_a_summon():
    # v3 — 소환이 엔진 속성이 아니라 규칙표의 한 줄이어야 한다.
    summoner = load_rulesets(ENEMY_RULESETS_PATH)["ai_summoner"]
    assert "SUMMON" in {rule.action for rule in summoner.rules}


def test_term_key_includes_the_parameter():
    assert Term("flag_state", "==", True, "A").key == "flag_state[A]"
    assert Term("self_hp_percent", "<", 30).key == "self_hp_percent"


# ── 검증기 (TDD §5.1) ────────────────────────────────────────────────────────


def test_g0_rulesets_pass_validation(rulesets, catalog, balance):
    budget = balance["player"]["cpu_budget"]
    slots = balance["player"]["rule_slots"]
    for ruleset in rulesets.values():
        assert validate_ruleset(ruleset, catalog, budget, slots) == []


def test_validator_rejects_slot_overflow(catalog):
    rules = tuple(make_rule(i, "self_hp_percent", "<", 50, "HOLD") for i in range(1, 7))
    problems = validate_ruleset(RuleSet("x", 1, rules), catalog, 99, 5)
    assert any("슬롯" in p for p in problems)


def test_validator_rejects_cpu_overflow(catalog):
    rules = tuple(make_rule(i, "self_hp_percent", "<", 50, "HOLD") for i in range(1, 5))
    problems = validate_ruleset(RuleSet("x", 1, rules), catalog, 2, 5)
    assert any("예산" in p for p in problems)


def test_validator_rejects_unknown_perception(catalog):
    rule = make_rule(1, "does_not_exist", "<", 1, "HOLD")
    problems = validate_ruleset(RuleSet("x", 1, (rule,)), catalog, 99, 5)
    assert any("목록에 없는 인지 변수" in p for p in problems)


def test_validator_rejects_bad_parameter(catalog):
    rule = make_rule(1, "flag_state", "==", True, "HOLD", param="Z")
    problems = validate_ruleset(RuleSet("x", 1, (rule,)), catalog, 99, 5)
    assert any("허용되지 않는다" in p for p in problems)


def test_validator_requires_target_for_targeted_action(catalog):
    rule = make_rule(1, "self_hp_percent", "<", 50, "ATTACK")
    problems = validate_ruleset(RuleSet("x", 1, (rule,)), catalog, 99, 5)
    assert any("TARGET 셀렉터가 필요하다" in p for p in problems)


def test_validator_rejects_target_on_untargeted_action(catalog):
    rule = make_rule(1, "self_hp_percent", "<", 50, "HOLD", target="NEAREST")
    problems = validate_ruleset(RuleSet("x", 1, (rule,)), catalog, 99, 5)
    assert any("TARGET 을 받지 않는다" in p for p in problems)


def test_validator_rejects_duplicate_priority(catalog):
    rules = (
        make_rule(1, "self_hp_percent", "<", 50, "HOLD"),
        make_rule(1, "self_potion_count", ">", 0, "HOLD"),
    )
    problems = validate_ruleset(RuleSet("x", 1, rules), catalog, 99, 5)
    assert any("우선순위가 중복" in p for p in problems)


def test_validator_rejects_wrong_cpu_cost(catalog):
    rule = make_rule(1, "self_hp_percent", "<", 50, "HOLD", cost=4)
    problems = validate_ruleset(RuleSet("x", 1, (rule,)), catalog, 99, 5)
    assert any("CPU 비용" in p for p in problems)


def test_validator_honours_locked_blocks(catalog):
    rule = make_rule(1, "self_hp_percent", "<", 50, "HOLD")
    problems = validate_ruleset(
        RuleSet("x", 1, (rule,)), catalog, 99, 5, unlocked=frozenset({"HOLD"})
    )
    assert any("해금되지 않은" in p for p in problems)


# ── 실행 규약 (TDD §5.2) ─────────────────────────────────────────────────────


def test_first_true_rule_wins(engine, catalog, balance):
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    rules = (
        make_rule(1, "self_potion_count", ">", 0, "USE_POTION"),
        make_rule(2, "self_hp_percent", "<=", 100, "HOLD"),
    )
    vm = build_rule_vm(RuleSet("x", 1, rules), catalog, kinds)
    engine.state.tick = 1
    snapshot = engine.build_perceptions()["player"]
    plan = vm.plan_action(engine.state.entities["player"], snapshot, engine.state)
    assert plan.action_id == "USE_POTION"
    assert plan.rule_index == 1


def test_default_action_fires_when_all_rules_are_false(engine, catalog, balance):
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    rules = (make_rule(1, "self_hp_percent", "<", 0, "HOLD"),)
    vm = build_rule_vm(RuleSet("x", 1, rules), catalog, kinds)
    engine.state.tick = 1
    snapshot = engine.build_perceptions()["player"]
    plan = vm.plan_action(engine.state.entities["player"], snapshot, engine.state)
    assert plan.action_id == "APPROACH"
    assert "DEFAULT" in plan.expr


def test_rule_is_skipped_when_its_selector_finds_nobody(engine, catalog, balance):
    # F-1 결정의 핵심 — 없는 보스를 공격하라는 규칙은 틱을 버리지 않는다.
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    rules = (
        make_rule(1, "self_hp_percent", "<=", 100, "ATTACK", target="BOSS"),
        make_rule(2, "self_hp_percent", "<=", 100, "HOLD"),
    )
    vm = build_rule_vm(RuleSet("x", 1, rules), catalog, kinds)
    engine.state.tick = 1
    snapshot = engine.build_perceptions()["player"]
    plan = vm.plan_action(engine.state.entities["player"], snapshot, engine.state)
    assert plan.action_id == "HOLD"


def test_expression_carries_measured_values(engine, catalog, balance):
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    rules = (make_rule(1, "self_hp_percent", "<=", 100, "HOLD"),)
    vm = build_rule_vm(RuleSet("x", 1, rules), catalog, kinds)
    engine.state.tick = 1
    snapshot = engine.build_perceptions()["player"]
    plan = vm.plan_action(engine.state.entities["player"], snapshot, engine.state)
    assert plan.expr == "내 HP%(100) <= 100"


def test_deferred_block_evaluates_false_not_true(engine, catalog, balance):
    # 값을 만들 수 없는 항은 거짓이다. 0 으로 채워 참이 되면 구현되지 않은 기능이
    # 동작하는 척한다. W6 통합으로 LOS 는 값을 갖게 됐으므로, 지형 격자를 넘기지
    # 않아 값이 만들어지지 않은 스냅샷으로 그 계약을 확인한다.
    from game.app.simulation.perception import build_snapshot

    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    rules = (make_rule(1, "self_exposed_to_los", "==", True, "HOLD"),)
    vm = build_rule_vm(RuleSet("x", 1, rules), catalog, kinds)
    engine.state.tick = 1
    player = engine.state.entities["player"]
    blind = build_snapshot(engine.state, player, kinds)
    assert blind.read("self_exposed_to_los") is None
    plan = vm.plan_action(player, blind, engine.state)
    assert plan.action_id == "APPROACH"


def test_los_block_has_a_value_after_integration(engine, catalog, balance):
    # 엔진이 격자를 넘기면 같은 항이 실제 값을 갖는다 (W6).
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    rules = (make_rule(1, "self_exposed_to_los", "==", True, "HOLD"),)
    vm = build_rule_vm(RuleSet("x", 1, rules), catalog, kinds)
    engine.state.tick = 1
    snapshot = engine.build_perceptions()["player"]
    assert isinstance(snapshot.read("self_exposed_to_los"), bool)
    plan = vm.plan_action(engine.state.entities["player"], snapshot, engine.state)
    assert plan.action_id == ("HOLD" if snapshot.read("self_exposed_to_los") else "APPROACH")


def test_and_condition_needs_every_term(catalog):
    condition = Condition(
        op="AND",
        terms=(Term("self_hp_percent", "<", 50), Term("self_potion_count", ">", 0)),
    )
    snapshot = type(
        "S",
        (),
        {"read": lambda self, b, p=None: {"self_hp_percent": 80, "self_potion_count": 2}.get(b)},
    )()
    fired, expr = evaluate_condition(condition, snapshot, None, catalog)
    assert fired is False
    assert " AND " in expr


def test_or_condition_needs_one_term(catalog):
    condition = Condition(
        op="OR",
        terms=(Term("self_hp_percent", "<", 50), Term("self_potion_count", ">", 0)),
    )
    snapshot = type(
        "S",
        (),
        {"read": lambda self, b, p=None: {"self_hp_percent": 80, "self_potion_count": 2}.get(b)},
    )()
    fired, expr = evaluate_condition(condition, snapshot, None, catalog)
    assert fired is True
    assert " OR " in expr


def test_cpu_headroom_reflects_the_ruleset(engine, catalog, balance):
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    rules = (make_rule(1, "self_cpu_headroom", ">=", 7, "HOLD"),)
    vm = build_rule_vm(RuleSet("x", 1, rules), catalog, kinds)
    engine.state.tick = 1
    snapshot = engine.build_perceptions()["player"]
    plan = vm.plan_action(engine.state.entities["player"], snapshot, engine.state)
    # 예산 8, 규칙 하나가 1 을 쓰므로 여유는 7 이다.
    assert plan.action_id == "HOLD"
    assert count_cpu_usage(RuleSet("x", 1, rules)) == 1


def test_set_flag_is_applied_during_act(rooms, balance, catalog):
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    rules = (make_rule(1, "self_hp_percent", "<=", 100, "HOLD", flag="A=true"),)
    local = build_engine(rooms["open_field"], balance, seed=1)
    local.policies["player"] = build_rule_vm(RuleSet("x", 1, rules), catalog, kinds)
    local.run_tick()
    assert local.state.entities["player"].flags.get("A") is True


# ── 종단 ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("ruleset_id", ["g0_pressure", "g0_kite", "g0_cover"])
def test_g0_rulesets_run_deterministically(
    rulesets, catalog, balance, rooms, target_rooms, ruleset_id
):
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    room = rooms[target_rooms[ruleset_id]]
    results = []
    for _ in range(2):
        local = build_engine(room, balance, seed=777, max_ticks=120)
        local.policies["player"] = build_rule_vm(rulesets[ruleset_id], catalog, kinds)
        results.append(run_battle(local))
    assert results[0].log_lines == results[1].log_lines
    assert results[0].outcome == results[1].outcome
