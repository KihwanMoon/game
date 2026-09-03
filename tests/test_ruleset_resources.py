"""규칙표 리소스 검증 — G0 예시와 적 5종 (TDD §2, 로드맵 W3·W7).

`test_resources.py` 에서 갈라 나왔다 — 앞쪽은 블록·룸·밸런스, 여기는 그것들을 조합해
쓰는 규칙표 파일이다. 규칙표는 다른 셋을 모두 참조하므로 깨지는 방향이 반대다.
"""

import json

import pytest

from game.app.bots.doppel import DOPPEL_KIND_ID
from game.app.rules.validator import validate_ruleset
from game.app.services.run_battle import load_balance
from game.config import (
    BALANCE_PATH,
    BLOCKS_PATH,
    ENEMY_RULESETS_PATH,
    G0_RULESETS_PATH,
    ROOM_TEMPLATES_PATH,
)
from game.schemas.blocks import (
    load_block_catalog,
)
from game.schemas.room import (
    load_room_templates,
)
from game.schemas.ruleset import load_rulesets

# 층 1 에 나와도 되는 적. 나머지 넷은 min_floor 2 이상인 방에만 있다.
FIRST_FLOOR_KINDS = frozenset({"goblin_rusher", "goblin_archer", "goblin_summoner", "bomb_slime"})
ENEMY_CPU_BUDGET = 4
ENEMY_RULE_SLOTS = 3
BOMBER_LEAD_TICKS = 2


@pytest.fixture(scope="module")
def catalog():
    return load_block_catalog(BLOCKS_PATH)


@pytest.fixture(scope="module")
def templates():
    return load_room_templates(ROOM_TEMPLATES_PATH)


@pytest.fixture(scope="module")
def balance():
    # load_balance 를 거친다. 스킬이 skills.json 으로 갈라져 있고 둘을 합치는 자리가
    # 거기 하나이므로, 파일을 직접 읽으면 검사가 실제로 도는 데이터와 달라진다.
    return load_balance(BALANCE_PATH)


# ── G0 규칙표 예시 ───────────────────────────────────────────────────────────

RULE_SLOTS = 5
CPU_BUDGET = 8
CPU_COST_BY_TERMS = {1: 1, 2: 2, 3: 4}


@pytest.fixture(scope="module")
def rulesets():
    return json.loads(G0_RULESETS_PATH.read_text(encoding="utf-8"))["rulesets"]


def test_g0_provides_three_examples(rulesets):
    # 게이트 G0 — 규칙표 예시 3개.
    assert len(rulesets) == 3


def test_g0_strategies_are_distinct(rulesets):
    # GDD §11 — 단일 정답으로 수렴하는지 보려면 서로 다른 전략이어야 한다.
    first_actions = [rs["rules"][1]["action"] for rs in rulesets]
    assert len(set(first_actions)) == len(first_actions)


def test_g0_rulesets_fit_the_constraints(rulesets):
    for rs in rulesets:
        assert len(rs["rules"]) <= RULE_SLOTS, rs["ruleset_id"]
        total = sum(r["cpu_cost"] for r in rs["rules"])
        assert total <= CPU_BUDGET, f"{rs['ruleset_id']} cpu {total}"
        assert total == rs["cpu_total"], rs["ruleset_id"]


def test_g0_cpu_costs_follow_the_term_table(rulesets):
    # GDD §3.6 — 비용은 조건 항 수로 정해진다. 손으로 적은 값이 어긋나면 예산이 거짓말이 된다.
    for rs in rulesets:
        for rule in rs["rules"]:
            want = CPU_COST_BY_TERMS[len(rule["conditions"]["terms"])]
            assert rule["cpu_cost"] == want, f"{rs['ruleset_id']}[{rule['priority']}]"


def test_g0_priorities_are_dense_and_ordered(rulesets):
    # 우선순위는 위에서부터 평가된다. 비거나 뒤섞이면 읽는 사람이 순서를 오해한다.
    for rs in rulesets:
        assert [r["priority"] for r in rs["rules"]] == list(range(1, len(rs["rules"]) + 1))


def test_g0_only_uses_frozen_blocks(rulesets, catalog):
    # 동결 목록 밖의 블록을 쓰면 그 규칙표는 구현할 수 없다.
    for rs in rulesets:
        for rule in rs["rules"]:
            assert rule["action"] in catalog.actions
            if rule["target"] is not None:
                assert rule["target"] in catalog.selectors
            for term in rule["conditions"]["terms"]:
                assert term["lhs"] in catalog.perceptions


def test_g0_parameterized_terms_supply_allowed_values(rulesets, catalog):
    for rs in rulesets:
        for rule in rs["rules"]:
            for term in rule["conditions"]["terms"]:
                block = catalog.perceptions[term["lhs"]]
                if block.param is None:
                    assert "lhs_param" not in term
                else:
                    assert term["lhs_param"] in block.param.values


def test_g0_targeted_actions_declare_a_selector(rulesets, catalog):
    for rs in rulesets:
        for rule in rs["rules"]:
            if catalog.actions[rule["action"]].targeted:
                assert rule["target"] is not None, f"{rs['ruleset_id']}[{rule['priority']}]"


def test_g0_target_rooms_exist(rulesets, templates):
    known = {t.template_id for t in templates}
    for rs in rulesets:
        assert rs["target_room"] in known


def test_room_chain_ramps_difficulty(templates):
    # 첫 방은 돌진형만 나온다. 처음부터 3종이 다 나오면 배울 틈이 없다 —
    # 방 설계 의도(포위를 가르친다 / 통로 유인 / 엄폐)가 순서에 반영돼야 한다.
    by_id = {t.template_id: t for t in templates}
    first = {s.kind for s in by_id["open_field"].enemy_spawns}
    assert first == {"goblin_rusher"}
    assert "goblin_archer" in {s.kind for s in by_id["corridor"].enemy_spawns}
    assert "goblin_summoner" in {s.kind for s in by_id["pillars"].enemy_spawns}


def test_every_spawn_kind_exists_in_balance(templates, balance):
    known = {e["id"] for e in balance["enemies"]}
    for template in templates:
        for spawn in template.enemy_spawns:
            assert spawn.kind in known, f"{template.template_id}: {spawn.kind}"


def test_every_enemy_kind_actually_shows_up_in_a_room(templates, balance):
    # 정의와 규칙표와 도감만 있고 어느 방에도 나오지 않는 적은 없는 적이다.
    # 자폭형(예고의 유일한 사용처)과 치유형이 그 상태였다.
    placed = {spawn.kind for template in templates for spawn in template.enemy_spawns}
    # **도플갱어는 예외다.** 남의 자리를 스냅샷으로 이어받는 개체라 템플릿에 제 자리가
    # 없다 — 그것이 이 종의 정의다. 예외를 여기 적어 두는 이유는 「어느 방에도 안 나오는
    # 적」과 구별하기 위해서다: 그쪽은 결함이고 이쪽은 설계다.
    assert {e["id"] for e in balance["enemies"]} - {DOPPEL_KIND_ID} == placed


def test_min_floor_is_declared_for_every_room(templates):
    # 층 1 미만은 없다. 값이 0 이면 거르는 쪽이 늘 참이 되어 곡선이 사라진다.
    for template in templates:
        assert template.min_floor >= 1, template.template_id


def test_first_floor_rooms_stay_learnable(templates):
    # "첫 방은 배울 수 있어야 한다" — 층 1 에 나올 수 있는 방은 고블린 3종과 폭탄
    # 슬라임까지다. 정예 3종과 사제가 층 1 에 섞이면 첫 방에서 배울 것이 없어진다.
    for template in templates:
        if template.min_floor > 1:
            continue
        kinds = {spawn.kind for spawn in template.enemy_spawns}
        assert kinds <= FIRST_FLOOR_KINDS, f"{template.template_id}: {kinds}"


def test_deeper_kinds_are_gated_behind_min_floor(templates, balance):
    # 층 2~3 을 상정한 넷은 min_floor 2 이상인 방에서만 나와야 한다. 난이도 곡선을
    # 적 스탯이 아니라 "어느 층에 나오는가" 로 표현한 자리다 (docs/04 P-2).
    deeper = {e["id"] for e in balance["enemies"]} - FIRST_FLOOR_KINDS
    for template in templates:
        kinds = {spawn.kind for spawn in template.enemy_spawns}
        if kinds & deeper:
            assert template.min_floor >= 2, f"{template.template_id}: {kinds & deeper}"


def test_every_floor_has_at_least_one_room(templates):
    # 어떤 층에도 후보가 0 이면 build_floor 가 층을 만들지 못한다.
    deepest = max(template.min_floor for template in templates)
    for floor in range(1, deepest + 1):
        assert [t for t in templates if t.min_floor <= floor], f"층 {floor} 후보 없음"


# ── 적 규칙표 (W7 적 5종) ────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def enemy_raw():
    return json.loads(ENEMY_RULESETS_PATH.read_text(encoding="utf-8"))["rulesets"]


@pytest.fixture(scope="module")
def enemy_rulesets():
    return load_rulesets(ENEMY_RULESETS_PATH)


def test_every_enemy_declares_a_ruleset(balance, enemy_rulesets):
    # 규칙표가 없는 적은 폴백 정책으로 싸운다. 그러면 도감이 보여줄
    # 표와 실제 행동이 달라져 카운터 설계가 통하지 않는다 (GDD §5).
    assert {e["ruleset_id"] for e in balance["enemies"]} == set(enemy_rulesets)


def test_enemy_rulesets_pass_validation(balance, catalog, enemy_rulesets):
    # W7 의 다섯도 기존 셋과 같은 검증을 통과해야 한다.
    for kind in balance["enemies"]:
        ruleset = enemy_rulesets[kind["ruleset_id"]]
        problems = validate_ruleset(ruleset, catalog, kind["cpu_budget"], kind["rule_slots"])
        assert problems == [], f"{kind['id']}: {problems}"


def test_enemy_budgets_are_uniform(balance):
    # 적의 제약은 CPU 4 / 슬롯 3 이다. 종류마다 다르면 도감의 예산
    # 표시가 같은 자리에서 다른 뜻을 갖는다.
    for kind in balance["enemies"]:
        assert kind["cpu_budget"] == ENEMY_CPU_BUDGET, kind["id"]
        assert kind["rule_slots"] == ENEMY_RULE_SLOTS, kind["id"]


def test_enemy_cpu_totals_match_the_rules(enemy_raw):
    # 손으로 적은 cpu_total 이 어긋나면 예산 표시가 거짓말이 된다.
    for item in enemy_raw:
        got = sum(rule["cpu_cost"] for rule in item["rules"])
        assert got == item["cpu_total"], item["ruleset_id"]


def test_enemy_rule_costs_follow_the_term_table(enemy_raw):
    # GDD §3.6 — 비용은 조건 항 수로 정해진다.
    for item in enemy_raw:
        for rule in item["rules"]:
            want = CPU_COST_BY_TERMS[len(rule["conditions"]["terms"])]
            assert rule["cpu_cost"] == want, f"{item['ruleset_id']}[{rule['priority']}]"


def test_enemy_priorities_are_dense_and_ordered(enemy_raw):
    # 우선순위는 위에서부터 평가된다. 비거나 뒤섞이면 도감을 읽는
    # 사람이 순서를 오해한다.
    for item in enemy_raw:
        got = [rule["priority"] for rule in item["rules"]]
        assert got == list(range(1, len(got) + 1)), item["ruleset_id"]


def test_enemy_rules_only_use_frozen_blocks(enemy_raw, catalog):
    # 동결 목록 밖의 블록을 쓰면 그 규칙표는 실행할 수 없다.
    for item in enemy_raw:
        for rule in item["rules"]:
            assert rule["action"] in catalog.actions
            if rule["target"] is not None:
                assert rule["target"] in catalog.selectors
            for term in rule["conditions"]["terms"]:
                block = catalog.perceptions[term["lhs"]]
                if block.param is None:
                    assert "lhs_param" not in term
                else:
                    assert term["lhs_param"] in block.param.values


def test_enemy_head_rules_are_situational(enemy_raw):
    # 첫 규칙이 상황과 무관하게 참이면 아래 규칙도 DEFAULT 도 영영
    # 평가되지 않아 그 적이 한 행동에 굳는다 (ai_summoner 의 교훈).
    situational = {"target_distance", "self_hp_percent", "visible_enemy_count"}
    for item in enemy_raw:
        head = item["rules"][0]
        lhs = {term["lhs"] for term in head["conditions"]["terms"]}
        assert lhs & situational, item["ruleset_id"]


def test_bomber_declares_a_two_tick_telegraph(balance):
    # GDD §5 자폭형 — 접근 후 2틱 예고 뒤 폭발. 예고가 없으면
    # `위험 예고 타일 위에 있는가` 는 영영 거짓인 죽은 블록이 된다.
    bomber = next(e for e in balance["enemies"] if e["type"] == "BOMBER")
    telegraph = bomber["telegraph"]
    assert telegraph["lead_ticks"] == BOMBER_LEAD_TICKS
    assert telegraph["damage"] > 0
    assert telegraph["radius"] >= 1


def test_bomber_telegraph_is_cancelled_by_killing_it(balance):
    # GDD §5 는 자폭형의 답을 둘로 적었다 — 예고 타일 회피와 사거리
    # 밖 처리. 취소되지 않으면 두 번째 답이 사라진다.
    bomber = next(e for e in balance["enemies"] if e["type"] == "BOMBER")
    assert bomber["telegraph"]["cancel_on_death"] is True


def test_bomber_telegraph_skill_is_a_frozen_action(balance, catalog):
    # 예고가 부르는 스킬도 동결 목록 안이어야 도감이 그것을 보여준다.
    bomber = next(e for e in balance["enemies"] if e["type"] == "BOMBER")
    assert bomber["telegraph"]["skill"] in catalog.actions


def test_healer_heals_its_allies_from_the_rule_table(balance, enemy_rulesets):
    # GDD §5 치유형의 존재 이유가 '아군 HP% 낮으면 회복' 이다. 규칙표
    # 밖에서 처리하면 도감이 그 한 줄을 보여주지 못해 카운터가 서지 않는다.
    healer = next(e for e in balance["enemies"] if e["type"] == "HEALER")
    rules = enemy_rulesets[healer["ruleset_id"]].rules
    heal = next(rule for rule in rules if rule.action == "HEAL")
    assert heal.target == "ALLY_WOUNDED"


def test_healer_heal_rule_checks_range_and_cooldown(enemy_raw):
    # 거리 항이 없으면 사거리 밖 아군에게 헛돌며 쿨타임도 걸리지 않아 이
    # 규칙에 굳고, 쿨타임 항이 없으면 매 틱 참이라 아래 규칙이 영영
    # 평가되지 않는다 — SUMMON 이 이미 겪은 함정이다.
    mender = next(rs for rs in enemy_raw if rs["ruleset_id"] == "ai_mender")
    rule = next(r for r in mender["rules"] if r["action"] == "HEAL")
    terms = {(term["lhs"], term.get("lhs_param")) for term in rule["conditions"]["terms"]}
    assert ("target_distance", "ALLY_WOUNDED") in terms
    assert ("self_cooldown_ready", "HEAL") in terms


def test_healer_type_is_addressable_by_frozen_blocks(catalog, balance):
    # v3 까지의 공백을 v4 가 메웠다. 유형으로 물을 수 있어야(`적 유형 존재`)
    # 조건이 서고, 유형으로 고를 수 있어야(TYPE_HEALER) 먼저 끊는 카운터가
    # 규칙표에 적힌다 — 소환형이 TYPE_SUMMONER 로 갖고 있던 것과 같다.
    declared = {e["type"] for e in balance["enemies"]}
    assert declared <= set(catalog.perceptions["enemy_type_present"].param.values)
    assert "TYPE_HEALER" in catalog.selectors


def test_heal_action_declares_its_amount_and_cooldown(balance, catalog):
    # 회복량이 없으면 HEAL 이 0 을 채우고 매 틱 '여지 없음' 으로 헛돈다.
    # 쿨타임이 0 이면 사제가 아군을 무한히 되살린다.
    heal = next(skill for skill in balance["skills"] if skill["id"] == "HEAL")
    assert heal["id"] in catalog.actions
    assert 0 < heal["heal_pct"] <= 100
    assert heal["cooldown"] > 0


def test_summoners_call_kinds_that_exist(balance):
    # 없는 종류를 부르면 소환이 조용히 실패한다.
    known = {e["id"] for e in balance["enemies"]}
    summoners = [e for e in balance["enemies"] if "summon" in e]
    assert len(summoners) == 2
    for kind in summoners:
        assert kind["summon"]["spawns"] in known, kind["id"]
        assert kind["summon"]["max_alive"] > 0, kind["id"]
        assert kind["summon"]["every_ticks"] > 0, kind["id"]


def test_elite_variants_outclass_their_base(balance):
    # 층 2~3 강화판이 원본보다 약하면 층 진행이 난이도가 아니라
    # 이름만 바뀌는 일이 된다.
    by_id = {e["id"]: e for e in balance["enemies"]}
    pairs = (
        ("veteran_rusher", "goblin_rusher"),
        ("longbow_archer", "goblin_archer"),
        ("arch_summoner", "goblin_summoner"),
    )
    for elite, base in pairs:
        assert by_id[elite]["hp_max"] > by_id[base]["hp_max"], elite
        assert by_id[elite]["attack"] > by_id[base]["attack"], elite


def test_longbow_outranges_the_player_ranged_skill(balance):
    # 장궁병의 사거리가 플레이어의 사격(SKILL_2)보다 길어야 '같은
    # 사거리 싸움' 이 아니라 엄폐·급속 접근을 요구하게 된다.
    longbow = next(e for e in balance["enemies"] if e["id"] == "longbow_archer")
    skill_2 = next(s for s in balance["skills"] if s["id"] == "SKILL_2")
    assert longbow["attack_range"] > skill_2["range"]
