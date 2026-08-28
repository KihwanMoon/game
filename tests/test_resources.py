"""동결된 블록 목록과 룸 템플릿의 무결성 검사 (로드맵 Phase 0).

여기서 하는 일은 "값이 좋은가"가 아니라 "동결이 실제로 동결인가"다.
개수가 어긋나거나 도달 불가능한 방이 섞여 들어오면 규칙 설계 실패와 구분되지 않는다.
"""

import json

import pytest

from game.config import (
    BALANCE_PATH,
    BLOCKS_PATH,
    G0_RULESETS_PATH,
    ROOM_TEMPLATES_PATH,
)
from game.schemas.blocks import (
    ACTION_COUNT,
    PERCEPTION_COUNT,
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

ROOM_TEMPLATE_COUNT = 5
ROOM_WIDTH = 12
ROOM_HEIGHT = 9
ENEMY_KIND_COUNT = 3


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
    # GDD §9 가 정한 인지 18 / 행동 12 / 셀렉터 7. 이후 변경 금지 대상이다.
    assert len(catalog.perceptions) == PERCEPTION_COUNT
    assert len(catalog.actions) == ACTION_COUNT
    assert len(catalog.selectors) == SELECTOR_COUNT


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
        for pos in template.enemy_spawns:
            assert template.get_tile(*pos) in WALKABLE_TILES, f"{template.template_id} {pos}"


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


def test_phase1_ships_three_enemy_kinds(balance):
    # 로드맵 Phase 1 W3 — 적 3종(돌진/사격/소환).
    assert len(balance["enemies"]) == ENEMY_KIND_COUNT
    assert {e["type"] for e in balance["enemies"]} == {"MELEE", "RANGED", "SUMMONER"}


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
