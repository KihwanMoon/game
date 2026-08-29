"""RuleVM 회귀 테스트 (TDD §5).

핵심은 세 가지다 — 평가 순서(셀렉터 → 조건 → 행동), 최초로 참인 규칙 하나만 실행,
그리고 조건 문자열에 실측값이 붙는가. 셋 중 하나라도 깨지면 죽고 나서 어느 규칙이 왜
틀렸는지 특정할 수 없다 (P1).
"""

import json
import re

import pytest

from game.app.rules.rule_vm import (
    RHS_STAT_READERS,
    build_rule_vm,
    count_cpu_usage,
    evaluate_condition,
)
from game.app.rules.validator import validate_ruleset
from game.app.services.run_battle import (
    assign_enemy_policies,
    build_engine,
    load_balance,
    run_battle,
)
from game.app.simulation.selectors import resolve_target
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

G0_COUNT = 3
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
    weakest = next(e for e in engine.state.entities.values() if e.faction != player.faction)
    weakest.hp = 1
    picked = resolve_target("LOWEST_HP", player, engine.state, kinds)
    assert picked.entity_id == weakest.entity_id


def test_type_selector_filters_by_enemy_type(rooms, balance):
    # open_field 에는 돌진형만 나오므로 소환사가 있는 방을 쓴다.
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    local = build_engine(rooms["pillars"], balance, seed=1)
    player = local.state.entities["player"]
    picked = resolve_target("TYPE_SUMMONER", player, local.state, kinds)
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
