"""RuleVM 회귀 테스트 (TDD §5).

핵심은 세 가지다 — 평가 순서(셀렉터 → 조건 → 행동), 최초로 참인 규칙 하나만 실행,
그리고 조건 문자열에 실측값이 붙는가. 셋 중 하나라도 깨지면 죽고 나서 어느 규칙이 왜
틀렸는지 특정할 수 없다 (P1).
"""

import json

import pytest

from game.app.rules.rule_vm import build_rule_vm, count_cpu_usage, evaluate_condition
from game.app.rules.selectors import resolve_target
from game.app.rules.validator import validate_ruleset
from game.app.services.run_battle import build_engine, load_balance, run_battle
from game.config import BALANCE_PATH, BLOCKS_PATH, G0_RULESETS_PATH, ROOM_TEMPLATES_PATH
from game.schemas.blocks import load_block_catalog
from game.schemas.room import load_room_templates
from game.schemas.ruleset import Condition, Rule, RuleSet, Term, load_rulesets

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


# ── 셀렉터 (F-1: 조건보다 먼저 푼다) ─────────────────────────────────────────


def test_nearest_selector_picks_the_closest(engine, balance):
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    player = engine.state.entities["player"]
    picked = resolve_target("NEAREST", player, engine.state, kinds)
    assert picked is not None
    assert picked.faction != player.faction


def test_lowest_hp_selector_picks_the_weakest(engine, balance):
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    player = engine.state.entities["player"]
    engine.state.entities["goblin_archer_1"].hp = 1
    assert resolve_target("LOWEST_HP", player, engine.state, kinds).entity_id == "goblin_archer_1"


def test_type_selector_filters_by_enemy_type(engine, balance):
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    player = engine.state.entities["player"]
    picked = resolve_target("TYPE_SUMMONER", player, engine.state, kinds)
    assert picked is not None
    assert kinds[picked.kind_id] == "SUMMONER"


def test_selector_returns_none_when_nobody_matches(engine, balance):
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    player = engine.state.entities["player"]
    # 보스는 이 방에 없다. 없는 대상을 고르라는 규칙은 발동하면 안 된다.
    assert resolve_target("BOSS", player, engine.state, kinds) is None


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
    # LOS 는 아직 없다. 0 으로 채워 참이 되면 구현되지 않은 기능이 동작하는 척한다.
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    rules = (make_rule(1, "self_exposed_to_los", "==", True, "HOLD"),)
    vm = build_rule_vm(RuleSet("x", 1, rules), catalog, kinds)
    engine.state.tick = 1
    snapshot = engine.build_perceptions()["player"]
    plan = vm.plan_action(engine.state.entities["player"], snapshot, engine.state)
    assert plan.action_id == "APPROACH"


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


def test_designed_ruleset_beats_the_fallback(rooms, balance, catalog, rulesets):
    # 로직 설계가 결과를 바꾸는가 — 이 게임의 전제다 (GDD §0 주축: 퍼즐형).
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    fallback = run_battle(build_engine(rooms["open_field"], balance, seed=12345))
    designed_engine = build_engine(rooms["open_field"], balance, seed=12345)
    designed_engine.policies["player"] = build_rule_vm(rulesets["g0_pressure"], catalog, kinds)
    designed = run_battle(designed_engine)
    assert designed.player_hp > fallback.player_hp
