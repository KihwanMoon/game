"""층 그래프 생성과 방 연쇄 (로드맵 Phase 2 W4, TDD §7).

층 생성이 결정론을 깨면 데일리 챌린지도 리플레이도 성립하지 않는다 (R5). 여기서
보는 것은 세 가지다 — 같은 시드가 같은 층을 내는가, 시작에서 보스까지 실제로 갈 수
있는가, 방마다 제시되는 보상 후보가 재현되는가.
"""

from collections import Counter

import pytest

from game.app.core.rng import DeterministicRng
from game.app.services.build_floor import (
    MIN_DEPTH_COUNT,
    TYPE_QUOTA_PCT,
    build_floor_map,
    build_layer_edges,
    build_type_bag,
    list_floor_templates,
)
from game.app.services.run_battle import load_balance
from game.config import (
    BALANCE_PATH,
    BLOCKS_PATH,
    ENEMY_RULESETS_PATH,
    G0_RULESETS_PATH,
    ROOM_TEMPLATES_PATH,
)
from game.schemas.blocks import load_block_catalog
from game.schemas.floor_map import (
    BATTLE_NODE_TYPES,
    NODE_BOSS,
    NODE_COMBAT,
    NODE_START,
    FloorMap,
    FloorNode,
    RoomPlan,
    check_floor_map,
    check_floor_reachability,
    check_node_links,
    convert_floor_to_dict,
    find_boss_path,
    parse_floor_map,
)
from game.schemas.room import load_room_templates
from game.schemas.ruleset import load_rulesets

SAMPLE_SEEDS = tuple(range(1, 61))
# 시드 자체에 뜻이 있는 것이 아니라, 룸 템플릿 구성이 바뀌면 함께 바뀌는 값이다.
# 필요한 것은 "보스까지 갈 수 있는 층 하나" 뿐이다.
WINNING_SEED = 7
RATIO_TOLERANCE_PCT = 12


@pytest.fixture(scope="module")
def templates():
    return load_room_templates(ROOM_TEMPLATES_PATH)


@pytest.fixture(scope="module")
def parts(templates):
    return {
        "templates": templates,
        "by_id": {t.template_id: t for t in templates},
        "balance": load_balance(BALANCE_PATH),
        "catalog": load_block_catalog(BLOCKS_PATH),
        "enemy": load_rulesets(ENEMY_RULESETS_PATH),
        "player": load_rulesets(G0_RULESETS_PATH),
    }


# ── 층 생성 ──────────────────────────────────────────────────────────────────


def test_deep_rooms_never_show_up_on_the_first_floor(templates):
    # 난이도 곡선을 min_floor 로 표현한다 (docs/04 P-2). 거르지 않으면 층 1 첫 방에서
    # 대소환사를 만나 "배울 수 있는 첫 방" 이 성립하지 않는다.
    first = list_floor_templates(templates, 1)
    assert {t.template_id for t in first} < {t.template_id for t in templates}
    assert all(t.min_floor == 1 for t in first)


def test_deeper_floors_keep_the_shallow_rooms(templates):
    # 층이 깊어져도 얕은 방은 계속 나온다. 층마다 방 목록을 갈아 치우면 같은 방을
    # 다른 층에서 다시 만나는 학습(같은 지형·다른 세기)이 사라진다.
    deepest = max(t.min_floor for t in templates)
    assert set(list_floor_templates(templates, 1)) < set(list_floor_templates(templates, deepest))
    assert len(list_floor_templates(templates, deepest)) == len(templates)


def test_a_floor_with_no_room_is_an_error(templates):
    with pytest.raises(ValueError, match="룸 템플릿이 없다"):
        list_floor_templates(templates, 0)


def test_floor_one_only_places_shallow_rooms(templates):
    allowed = {t.template_id for t in list_floor_templates(templates, 1)}
    floor_map = build_floor_map(WINNING_SEED, 1, templates)
    assert {room.template_id for room in floor_map.rooms} <= allowed


def test_same_seed_builds_the_same_floor(templates):
    first = build_floor_map(4242, 2, templates)
    second = build_floor_map(4242, 2, templates)
    next_floor = build_floor_map(4242, 3, templates)
    assert convert_floor_to_dict(first) == convert_floor_to_dict(second)
    # seed + floor_index 로 갈리지 않으면 한 런의 모든 층이 같은 모양이 된다 (TDD §7.3).
    assert convert_floor_to_dict(first) != convert_floor_to_dict(next_floor)


def test_different_seeds_build_different_floors(templates):
    shapes = {
        str(convert_floor_to_dict(build_floor_map(seed, 1, templates))) for seed in SAMPLE_SEEDS
    }
    assert len(shapes) > len(SAMPLE_SEEDS) // 2


def test_generated_floors_pass_every_check(templates):
    for seed in SAMPLE_SEEDS:
        assert check_floor_map(build_floor_map(seed, 1, templates)) == []


def test_every_floor_has_a_path_from_start_to_boss(templates):
    for seed in SAMPLE_SEEDS:
        floor_map = build_floor_map(seed, 1, templates)
        path = find_boss_path(floor_map)
        assert path, f"시드 {seed} 에서 보스까지 갈 수 없다"
        assert path[0] == floor_map.start_id
        assert path[-1] == floor_map.boss_id


def test_floor_starts_with_one_node_and_ends_with_the_boss(templates):
    for seed in SAMPLE_SEEDS[:20]:
        floor_map = build_floor_map(seed, 1, templates)
        depths = Counter(node.depth for node in floor_map.nodes)
        assert depths[0] == 1
        assert depths[max(depths)] == 1
        # 분기 2~3 (TDD §7.1). 시작과 보스 깊이를 뺀 중간 깊이만 본다.
        middle = [count for depth, count in depths.items() if 0 < depth < max(depths)]
        assert all(2 <= count <= 3 for count in middle)


def test_node_type_ratio_is_close_to_the_table(templates):
    # 전투 60 / 이벤트 15 / 회복 15 / 상점 10 (TDD §7.1). 중간 노드가 층당 예닐곱
    # 개뿐이라 한 층만으로는 비율이 성립하지 않는다. 여러 층의 합으로 본다.
    counts = Counter()
    for seed in SAMPLE_SEEDS:
        counts.update(
            node.node_type
            for node in build_floor_map(seed, 1, templates).nodes
            if node.node_type not in {NODE_START, NODE_BOSS}
        )
    total = sum(counts.values())
    for node_type, quota_pct in TYPE_QUOTA_PCT:
        share = counts[node_type] * 100 // total
        assert abs(share - quota_pct) <= RATIO_TOLERANCE_PCT, f"{node_type} 비율 {share}%"


def test_type_bag_keeps_the_ratio_for_one_floor():
    bag = build_type_bag(DeterministicRng(1), 20)
    counts = Counter(bag)
    assert len(bag) == 20
    assert counts[NODE_COMBAT] == 12


def test_layer_edges_cover_both_directions():
    rng = DeterministicRng(5)
    links = build_layer_edges(rng, (0, 1), (2, 3, 4))
    assert all(targets for targets in links), "나갈 곳 없는 노드가 있다"
    reached = {target for targets in links for target in targets}
    assert reached == {2, 3, 4}, "들어올 곳 없는 노드가 있다"


def test_shallow_depth_is_rejected(templates):
    with pytest.raises(ValueError, match="깊이"):
        build_floor_map(1, 1, templates, depth_count=MIN_DEPTH_COUNT - 1)


# ── 검사 (실패를 잡는가) ─────────────────────────────────────────────────────


def build_broken_floor(nodes):
    # 적 없는 방을 배정한다. 전투 노드라면 그것 자체가 검사 대상이다.
    rooms = tuple(
        RoomPlan(node.node_id, "open_field", (12, 9), ())
        for node in nodes
        if node.node_type != NODE_START
    )
    return FloorMap(floor=1, seed=1, nodes=tuple(nodes), rooms=rooms)


# 뒤로 도는 간선은 방 연쇄를 끝나지 않게 하고, 막다른 길은 층을 클리어 불가능하게
# 만든다. 둘 다 전투 결과가 아니라 생성 버그이므로 진행 전에 잡혀야 한다.
BROKEN_LINKS = [
    ([(0, NODE_START, (1,)), (1, NODE_COMBAT, (0, 2)), (2, NODE_BOSS, ())], "앞으로 가지 않는다"),
    ([(0, NODE_START, (1,)), (1, NODE_COMBAT, ()), (2, NODE_BOSS, ())], "다음 노드가 없다"),
]


@pytest.mark.parametrize(("shape", "message"), BROKEN_LINKS)
def test_broken_links_are_caught(shape, message):
    nodes = [FloorNode(nid, kind, depth, nxt) for depth, (nid, kind, nxt) in enumerate(shape)]
    problems = check_node_links(build_broken_floor(nodes))
    assert any(message in problem for problem in problems)


def test_unreachable_node_is_caught():
    floor_map = build_broken_floor(
        [
            FloorNode(0, NODE_START, 0, (1,)),
            FloorNode(1, NODE_COMBAT, 1, (3,)),
            FloorNode(2, NODE_COMBAT, 1, (3,)),
            FloorNode(3, NODE_BOSS, 2, ()),
        ]
    )
    assert check_node_links(floor_map) == []
    assert any("닿을 수 없다" in problem for problem in check_floor_reachability(floor_map))


def test_combat_room_without_enemies_is_caught():
    floor_map = build_broken_floor(
        [
            FloorNode(0, NODE_START, 0, (1,)),
            FloorNode(1, NODE_COMBAT, 1, (2,)),
            FloorNode(2, NODE_BOSS, 2, ()),
        ]
    )
    assert any("적이 없다" in problem for problem in check_floor_map(floor_map))


def test_rooms_are_assigned_to_every_node_but_the_start(templates):
    floor_map = build_floor_map(3, 1, templates)
    planned = {plan.node_id for plan in floor_map.rooms}
    for node in floor_map.nodes:
        assert (node.node_id in planned) == (node.node_type != NODE_START)
        if node.node_type in BATTLE_NODE_TYPES:
            assert floor_map.get_room(node.node_id).spawns


def test_floor_survives_a_round_trip(templates):
    floor_map = build_floor_map(77, 3, templates)
    assert parse_floor_map(convert_floor_to_dict(floor_map)) == floor_map
