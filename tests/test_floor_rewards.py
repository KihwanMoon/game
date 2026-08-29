"""층 보상과 방 연쇄 테스트 (로드맵 W8, GDD §2.2).

`test_floor_map.py` 에서 갈라 나왔다 — 앞쪽은 "층이 제대로 생겼는가", 여기는 "생긴 층을
따라 걸으면 무엇이 쌓이는가" 다.
"""

import pytest

from game.app.core.rng import DeterministicRng
from game.app.services.build_floor import (
    build_floor_map,
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
    NODE_START,
)
from game.schemas.room import load_room_templates
from game.schemas.ruleset import load_rulesets

# 룸 템플릿에 층 1 용 방(blast_yard)이 하나 늘면서 두 시드의 방 배정이 서로 바뀌었다.
# 시드 자체에 뜻이 있는 것이 아니라 "이기는 층 하나 · 죽는 층 하나" 가 필요할 뿐이다.
WINNING_SEED = 7
LOSING_SEED = 11
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
