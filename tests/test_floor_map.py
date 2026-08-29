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
)
from game.app.services.build_reward import (
    REWARD_CATALOG,
    REWARD_MODULE,
    REWARD_OPTION_COUNT,
    apply_reward,
    build_reward_options,
    create_run_state,
)
from game.app.services.run_battle import load_balance
from game.app.services.run_room_loop import RoomLoopContext, run_room_loop
from game.app.simulation.plan import OUTCOME_PLAYER_WIN
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
RATIO_TOLERANCE_PCT = 12
WINNING_SEED = 11
LOSING_SEED = 7
# 첫 방이 전투인 층. 규칙 편집이 그 방에는 반영되지 않는 것을 보는 데 쓴다.
EDIT_SEED = 42


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


def build_context(parts, seed, ruleset_id="g0_kite"):
    context = RoomLoopContext(
        floor_map=build_floor_map(seed, 1, parts["templates"]),
        templates=parts["by_id"],
        balance=parts["balance"],
        catalog=parts["catalog"],
        enemy_rulesets=parts["enemy"],
    )
    return context, parts["player"][ruleset_id]


# ── 층 생성 ──────────────────────────────────────────────────────────────────


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


# ── 보상 ─────────────────────────────────────────────────────────────────────


def test_reward_options_are_deterministic():
    first = build_reward_options(DeterministicRng(9))
    second = build_reward_options(DeterministicRng(9))
    assert [option.reward_id for option in first] == [option.reward_id for option in second]


def test_reward_options_do_not_repeat_and_differ_by_seed():
    offers = set()
    for seed in range(30):
        options = build_reward_options(DeterministicRng(seed))
        # 같은 것이 둘 나오면 후보가 셋이어도 선택지는 둘이다.
        assert len({option.reward_id for option in options}) == REWARD_OPTION_COUNT
        offers.add(tuple(option.reward_id for option in options))
    assert len(offers) > 1


def test_module_reward_widens_the_logic_budget(parts):
    # 모듈은 스탯이 아니라 표현력을 준다 (GDD §6.2). 그것이 이 게임의 성장이다.
    state = create_run_state(parts["balance"])
    before = (state.cpu_budget, state.rule_slots)
    for option in REWARD_CATALOG:
        if option.kind == REWARD_MODULE:
            apply_reward(state, option)
    assert (state.cpu_budget, state.rule_slots) > before
    assert len(state.modules) == 2


def test_hp_max_reward_also_heals(parts):
    state = create_run_state(parts["balance"])
    option = next(o for o in REWARD_CATALOG if o.target_stat == "hp_max")
    apply_reward(state, option)
    assert state.hp == state.hp_max


# ── 방 연쇄 ──────────────────────────────────────────────────────────────────


def test_room_loop_is_reproducible(parts):
    context, ruleset = build_context(parts, WINNING_SEED)
    first = run_room_loop(context, ruleset)
    second = run_room_loop(context, ruleset)
    assert (first.outcome, first.path, first.visits) == (
        second.outcome,
        second.path,
        second.visits,
    )
    assert first.state == second.state


def test_room_loop_reaches_the_boss(parts):
    context, ruleset = build_context(parts, WINNING_SEED)
    result = run_room_loop(context, ruleset)
    assert result.outcome == OUTCOME_PLAYER_WIN
    assert result.path[-1] == context.floor_map.boss_id
    assert result.visits[-1].node_type == NODE_BOSS
    # 시작 노드는 층의 입구일 뿐이라 전투도 보상도 없다.
    assert len(result.visits) == len(result.path) - 1


def test_room_loop_stops_at_the_room_that_killed_you(parts):
    context, ruleset = build_context(parts, LOSING_SEED)
    result = run_room_loop(context, ruleset)
    assert result.outcome != OUTCOME_PLAYER_WIN
    assert result.visits[-1].outcome != OUTCOME_PLAYER_WIN
    assert result.visits[-1].taken_reward_id is None, "죽은 방에서 보상을 받았다"
    assert result.cleared_nodes == len(result.visits) - 1


def test_room_loop_carries_damage_between_rooms(parts):
    context, ruleset = build_context(parts, WINNING_SEED)
    result = run_room_loop(context, ruleset)
    # 방마다 HP 가 초기화되면 연쇄가 난이도를 만들지 못한다.
    assert 0 < result.state.hp < result.state.hp_max


def test_battle_rooms_take_ticks_and_others_do_not(parts):
    context, ruleset = build_context(parts, WINNING_SEED)
    for visit in run_room_loop(context, ruleset).visits:
        assert (visit.ticks > 0) == (visit.node_type in BATTLE_NODE_TYPES)
        assert (visit.note != "") == (visit.node_type not in BATTLE_NODE_TYPES)


def test_offered_rewards_are_deterministic_per_node(parts):
    context, ruleset = build_context(parts, WINNING_SEED)
    first = run_room_loop(context, ruleset)
    second = run_room_loop(context, ruleset)
    assert [visit.offered_reward_ids for visit in first.visits] == [
        visit.offered_reward_ids for visit in second.visits
    ]
    assert all(visit.offered_reward_ids for visit in first.visits)


def test_choosing_a_different_reward_changes_the_run(parts):
    context, ruleset = build_context(parts, WINNING_SEED)

    def get_last_reward(node, options):
        return len(options) - 1

    first = run_room_loop(context, ruleset)
    other = run_room_loop(context, ruleset, choose_reward=get_last_reward)
    assert first.state != other.state


def test_choosing_a_different_route_changes_the_path(parts):
    context, ruleset = build_context(parts, WINNING_SEED)

    def get_rightmost_route(floor_map, node, candidates):
        return len(candidates) - 1

    first = run_room_loop(context, ruleset)
    other = run_room_loop(context, ruleset, choose_route=get_rightmost_route)
    assert first.path != other.path
    assert other.path[-1] == context.floor_map.boss_id


def test_route_chooser_out_of_range_is_clamped(parts):
    context, ruleset = build_context(parts, WINNING_SEED)

    def get_absurd_route(floor_map, node, candidates):
        return 999

    result = run_room_loop(context, ruleset, choose_route=get_absurd_route)
    assert result.path[-1] == context.floor_map.boss_id


def test_rule_editing_window_opens_once_per_room(parts):
    # 편집 창구는 방마다 한 번, 다음 방이 있을 때만 열린다 (GDD §2.2).
    context, ruleset = build_context(parts, WINNING_SEED)
    seen = []

    def get_logged_ruleset(node, state, current):
        seen.append((node.node_id, state.hp))
        return current

    result = run_room_loop(context, ruleset, edit_ruleset=get_logged_ruleset)
    # 보스를 잡은 뒤에는 반영될 방이 없으므로 마지막 노드에서는 열리지 않는다.
    assert [node_id for node_id, _ in seen] == list(result.path[:-1])
    assert len(seen) == len(result.visits)


def test_rules_are_frozen_during_a_battle(parts):
    # 전투 중 개입을 허용하면 사전 설계의 가치가 사라진다 (GDD §2.2). 첫 방을
    # 지난 뒤 규칙표를 바꿔도, 이미 싸운 방의 결과는 한 틱도 달라지지 않아야 한다.
    context, kite = build_context(parts, EDIT_SEED)
    pressure = parts["player"]["g0_pressure"]

    def get_late_swap(node, state, current):
        return current if node.node_type == NODE_START else pressure

    baseline = run_room_loop(context, kite)
    swapped = run_room_loop(context, kite, edit_ruleset=get_late_swap)
    assert baseline.visits[0].node_type in BATTLE_NODE_TYPES, "첫 방이 전투가 아니다"
    assert swapped.visits[0] == baseline.visits[0]
    assert swapped.visits != baseline.visits, "편집이 다음 방에 반영되지 않았다"
