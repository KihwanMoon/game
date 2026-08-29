"""동결된 블록 목록과 룸 템플릿의 무결성 검사 (로드맵 Phase 0).

여기서 하는 일은 "값이 좋은가"가 아니라 "동결이 실제로 동결인가"다.
개수가 어긋나거나 도달 불가능한 방이 섞여 들어오면 규칙 설계 실패와 구분되지 않는다.
"""

import json

import pytest

from game.app.rules.validator import validate_ruleset
from game.config import (
    BALANCE_PATH,
    BLOCKS_PATH,
    ENEMY_RULESETS_PATH,
    G0_RULESETS_PATH,
    ROOM_TEMPLATES_PATH,
)
from game.schemas.blocks import (
    ACTION_COUNT,
    PERCEPTION_COUNT,
    RHS_STAT_COUNT,
    SELECTOR_COUNT,
    load_block_catalog,
)
from game.schemas.room import (
    TILE_DOOR,
    TILE_STAIRS,
    WALKABLE_TILES,
    check_room_reachability,
    load_room_templates,
)
from game.schemas.ruleset import load_rulesets

ROOM_TEMPLATE_COUNT = 5
ROOM_WIDTH = 12
ROOM_HEIGHT = 9
ENEMY_KIND_COUNT = 8
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
    return json.loads(BALANCE_PATH.read_text(encoding="utf-8"))


# ── 블록 동결 ────────────────────────────────────────────────────────────────


def test_block_counts_match_gdd_scope(catalog):
    # 인지 18 / 행동 13 / 셀렉터 7. 행동이 13 인 것은 v3 의 SUMMON 추가다.
    assert len(catalog.perceptions) == PERCEPTION_COUNT
    assert len(catalog.actions) == ACTION_COUNT
    assert len(catalog.selectors) == SELECTOR_COUNT
    assert len(catalog.rhs_stats) == RHS_STAT_COUNT


def test_summon_is_a_first_class_action(catalog):
    # GDD §5 — 몬스터도 플레이어와 완전히 동일한 DSL 로 기술한다. 소환만 밸런스
    # 속성으로 빠져 있으면 도감이 소환 주기를 규칙표 밖에서 따로 보여줘야 한다.
    summon = catalog.actions["SUMMON"]
    assert summon.category == "control"
    assert summon.targeted is False


def test_cooldown_block_can_address_summon(catalog):
    # 소환 주기를 규칙표가 물을 수 없으면 SUMMON 규칙이 매 틱 참이 된다.
    assert "SUMMON" in catalog.perceptions["self_cooldown_ready"].param.values


def test_rhs_stats_are_a_closed_list(catalog):
    # F-2 — 열어 두면 오타 난 스탯 이름이 조용히 거짓이 되어 규칙이 영영 안 뜬다.
    assert set(catalog.rhs_stats) == {
        "attack_range",
        "attack",
        "defense",
        "hp_max",
        "cpu_budget",
        "potions",
    }
    for stat in catalog.rhs_stats.values():
        assert stat.label_ko, f"{stat.block_id} 의 한글 라벨이 비어 있다"


def test_perception_categories_cover_four_groups(catalog):
    # GDD §3.2 는 인지 변수를 4개 카테고리로 나눈다.
    assert {p.category for p in catalog.perceptions.values()} == {
        "self",
        "enemy",
        "terrain",
        "resource",
    }


def test_perception_returns_are_declared(catalog):
    assert {p.returns for p in catalog.perceptions.values()} <= {"int", "bool"}


def test_parameterized_perceptions_declare_values(catalog):
    # 인자를 받는 인지 변수는 허용값이 닫혀 있어야 한다. 열려 있으면 검증할 수 없다.
    parameterized = [p for p in catalog.perceptions.values() if p.param is not None]
    assert {p.block_id for p in parameterized} == {
        "self_cooldown_ready",
        "self_has_status",
        "enemy_type_present",
        "flag_state",
        # 블록 목록 v2 일반화. 개수는 18 그대로다 — 두 블록을 인자화했을 뿐이다.
        "target_distance",  # F-1 잔여: 선택된 대상까지의 거리
        "nearest_tile_distance",  # F-3: 회복타일 존재를 물을 방법
    }
    for block in parameterized:
        assert block.param.values, f"{block.block_id} 의 허용값이 비어 있다"


def test_flag_block_offers_exactly_four_slots(catalog):
    # GDD §3.5 — FLAG_A ~ FLAG_D 네 개.
    assert catalog.perceptions["flag_state"].param.values == ("A", "B", "C", "D")


def test_summoner_ruleset_declares_the_summon_action():
    # 소환이 규칙표 밖(balance.json 의 kind 속성)에 있으면 도감이 그것만 따로
    # 보여줘야 한다 — GDD §5 가 없애려던 바로 그 예외다.
    raw = json.loads(ENEMY_RULESETS_PATH.read_text(encoding="utf-8"))
    summoner = next(rs for rs in raw["rulesets"] if rs["ruleset_id"] == "ai_summoner")
    assert "SUMMON" in {rule["action"] for rule in summoner["rules"]}


def test_summon_rule_is_not_unconditionally_true():
    # 무조건 참인 SUMMON 규칙은 아래 규칙과 DEFAULT 를 모두 가려 소환사를 제자리에
    # 굳힌다. 조건에 상황 항이 하나는 있어야 한다.
    raw = json.loads(ENEMY_RULESETS_PATH.read_text(encoding="utf-8"))
    summoner = next(rs for rs in raw["rulesets"] if rs["ruleset_id"] == "ai_summoner")
    rule = next(r for r in summoner["rules"] if r["action"] == "SUMMON")
    lhs_set = {term["lhs"] for term in rule["conditions"]["terms"]}
    assert lhs_set - {"self_cooldown_ready"}, "쿨타임만으로는 상황을 가리지 못한다"


def test_targeted_actions_are_attack_or_move(catalog):
    targeted = {a.block_id for a in catalog.actions.values() if a.targeted}
    assert targeted == {"ATTACK", "SKILL_1", "SKILL_2", "APPROACH", "RETREAT"}


def test_selector_ids_match_gdd(catalog):
    assert set(catalog.selectors) == {
        "NEAREST",
        "LOWEST_HP",
        "HIGHEST_THREAT",
        "TYPE_RANGED",
        "TYPE_SUMMONER",
        "CASTING",
        "BOSS",
    }


# ── 룸 템플릿 ────────────────────────────────────────────────────────────────


def test_template_count(templates):
    assert len(templates) == ROOM_TEMPLATE_COUNT


def test_template_dimensions_match_design_grid(templates):
    # 디자인 시스템의 --plan-cols/--plan-rows 가 12/9 다 (design/README.md D-2).
    for template in templates:
        assert (template.width, template.height) == (ROOM_WIDTH, ROOM_HEIGHT)


@pytest.mark.parametrize("index", range(ROOM_TEMPLATE_COUNT))
def test_every_room_is_fully_reachable(templates, index):
    # TDD §7.2 — 시작점에서 모든 문·계단·적 스폰에 닿아야 한다.
    assert check_room_reachability(templates[index]) == []


def test_spawns_stand_on_walkable_tiles(templates):
    for template in templates:
        assert template.get_tile(*template.player_spawn) in WALKABLE_TILES
        for spawn in template.enemy_spawns:
            assert template.get_tile(*spawn.position) in WALKABLE_TILES, (
                f"{template.template_id} {spawn.kind} {spawn.position}"
            )


def test_every_room_has_at_least_two_exits(templates):
    # 들어온 문과 나갈 문. 하나뿐이면 방이 막다른 길이 된다.
    for template in templates:
        exits = sum(
            template.get_tile(x, y) in {TILE_DOOR, TILE_STAIRS}
            for y in range(template.height)
            for x in range(template.width)
        )
        assert exits >= 2, f"{template.template_id} 의 출구가 {exits}개다"


def test_room_border_is_sealed(templates):
    # 테두리가 뚫려 있으면 격자 밖으로 나가는 경로가 생긴다. 문은 예외다.
    for template in templates:
        for x in range(template.width):
            for y in (0, template.height - 1):
                assert template.get_tile(x, y) not in WALKABLE_TILES - {TILE_DOOR}
        for y in range(template.height):
            for x in (0, template.width - 1):
                assert template.get_tile(x, y) not in WALKABLE_TILES - {TILE_DOOR}


def test_template_ids_are_unique(templates):
    ids = [t.template_id for t in templates]
    assert len(ids) == len(set(ids))


# ── 밸런스 ───────────────────────────────────────────────────────────────────


def test_w7_ships_eight_enemy_kinds(balance):
    # GDD §9 콘텐츠 범위 — 적 8종. Phase 1 W3 의 3종에 W7 이 5종을
    # 더했다. 보스 3종은 페이즈별 규칙표 교체가 필요해 Phase 4 다.
    assert len(balance["enemies"]) == ENEMY_KIND_COUNT
    ids = [e["id"] for e in balance["enemies"]]
    assert len(ids) == len(set(ids))


def test_enemy_types_cover_the_gdd_roster(balance):
    # GDD §5 의 6유형에서 보스를 뺀 다섯이 전부 있어야 한다.
    assert {e["type"] for e in balance["enemies"]} == {
        "MELEE",
        "RANGED",
        "SUMMONER",
        "BOMBER",
        "HEALER",
    }


def test_cpu_cost_table_matches_gdd(balance):
    # GDD §3.6 — 1항=1, 2항=2, 3항=4.
    assert balance["cpu_cost_by_term_count"] == {"1": 1, "2": 2, "3": 4}


def test_damage_formula_uses_integers_only(balance):
    # R5 — 부동소수는 플랫폼마다 결과가 갈려 리플레이를 깬다.
    numeric = [v for v in balance["damage_formula"].values() if isinstance(v, (int, float))]
    assert numeric and all(isinstance(v, int) for v in numeric)
    for skill in balance["skills"]:
        assert isinstance(skill["coef_pct"], int)


def test_skill_ids_exist_in_block_catalog(balance, catalog):
    # 밸런스가 참조하는 스킬이 동결된 행동 목록에 실제로 있어야 한다.
    for skill in balance["skills"]:
        assert skill["id"] in catalog.actions


def test_summoner_cannot_spawn_without_limit(balance):
    # GDD §7 — 무한 증식을 막는 상한이 있어야 한다.
    summoner = next(e for e in balance["enemies"] if e["type"] == "SUMMONER")
    assert summoner["summon"]["max_alive"] > 0


def test_anti_abuse_numbers_are_present(balance):
    # GDD §7 이 지목한 어뷰징 세 갈래에 각각 값이 있어야 한다.
    anti = balance["anti_abuse"]
    assert anti["combat_regen_pct"] < 100  # 회복 타일 무한 대기
    assert anti["hunter_spawn_tick"] > 0  # 무한 카이팅
    assert anti["floor_attack_pct_per_10_ticks"] > 0  # 층 지연


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


def test_healer_can_spend_what_its_rules_use(balance, enemy_rulesets):
    # 규칙표가 USE_POTION 을 쓰는데 포션이 0 이면 매 틱 헛돈다.
    healer = next(e for e in balance["enemies"] if e["type"] == "HEALER")
    actions = {rule.action for rule in enemy_rulesets[healer["ruleset_id"]].rules}
    assert "USE_POTION" in actions
    assert healer["potions"] > 0


def test_healer_heal_rule_checks_remaining_potions(enemy_raw):
    # 남은 포션을 묻지 않으면 다 쓴 뒤에도 규칙이 참이라 사제가
    # 제자리에 굳는다 — SUMMON 이 이미 겪은 함정이다.
    mender = next(rs for rs in enemy_raw if rs["ruleset_id"] == "ai_mender")
    rule = next(r for r in mender["rules"] if r["action"] == "USE_POTION")
    lhs = {term["lhs"] for term in rule["conditions"]["terms"]}
    assert "self_potion_count" in lhs


def test_healer_type_is_not_addressable_by_frozen_blocks(catalog, balance):
    # 알려진 공백을 못박는다. 동결된 `적 유형 존재` 의 값에 HEALER 가
    # 없고 TYPE_HEALER 셀렉터도 없다 — 치유형을 유형으로 지목할 방법이
    # DSL 에 없다. 블록 목록 v4 가 열리면 이 테스트를 지운다.
    declared = {e["type"] for e in balance["enemies"]}
    assert declared - set(catalog.perceptions["enemy_type_present"].param.values) == {"HEALER"}
    assert "TYPE_HEALER" not in catalog.selectors


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
