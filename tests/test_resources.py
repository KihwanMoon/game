"""동결된 블록 목록과 룸 템플릿의 무결성 검사 (로드맵 Phase 0).

여기서 하는 일은 "값이 좋은가"가 아니라 "동결이 실제로 동결인가"다.
개수가 어긋나거나 도달 불가능한 방이 섞여 들어오면 규칙 설계 실패와 구분되지 않는다.
"""

import json

import pytest

from game.config import (
    BALANCE_PATH,
    BLOCKS_PATH,
    ENEMY_RULESETS_PATH,
    ROOM_TEMPLATES_PATH,
)
from game.schemas.blocks import (
    ACTION_COUNT,
    FACTION_ALLY,
    FACTION_ENEMY,
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

ROOM_TEMPLATE_COUNT = 10
ROOM_WIDTH = 12
ROOM_HEIGHT = 9
ENEMY_KIND_COUNT = 8


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
    # 인지 18 / 행동 14 / 셀렉터 9. v4 가 HEAL 과 셀렉터 둘을 더했다.
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


def test_targeted_actions_declare_a_faction(catalog):
    # v4 부터 대상을 받는 행동은 자기가 요구하는 진영을 선언한다. 빠뜨리면
    # 검증기가 `HEAL @NEAREST`(적을 회복)를 통과시킨다.
    targeted = {a.block_id for a in catalog.actions.values() if a.targeted}
    assert targeted == {"ATTACK", "SKILL_1", "SKILL_2", "APPROACH", "RETREAT", "HEAL"}
    for block in catalog.actions.values():
        assert (block.target_faction is not None) is block.targeted, block.block_id
    assert catalog.actions["HEAL"].target_faction == FACTION_ALLY
    assert catalog.actions["ATTACK"].target_faction == FACTION_ENEMY


def test_selector_ids_match_gdd(catalog):
    assert set(catalog.selectors) == {
        "NEAREST",
        "LOWEST_HP",
        "HIGHEST_THREAT",
        "TYPE_RANGED",
        "TYPE_SUMMONER",
        "TYPE_HEALER",
        "CASTING",
        "BOSS",
        "ALLY_WOUNDED",
    }


def test_only_one_selector_crosses_to_the_ally_side(catalog):
    # 아군 축을 최소한으로 연다는 v4 의 결정(docs/04 H-3)을 기계로 못박는다.
    # 셀렉터마다 진영 인자를 주면 대상 공간이 두 배가 되고 늘어난 칸의
    # 대부분이 뜻 없는 조합이 된다 — P3 가 먼저 무너진다.
    ally = {s.block_id for s in catalog.selectors.values() if s.faction == FACTION_ALLY}
    assert ally == {"ALLY_WOUNDED"}


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
