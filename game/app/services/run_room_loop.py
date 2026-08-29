"""Room Loop — 방 연쇄 진행과 보상 선택 (GDD §2.2, 로드맵 Phase 2 W4).

    방 입장 -> 전투(자동) -> 클리어 -> 보상 선택 -> [규칙 편집] -> 다음 방

**규칙 편집 창구는 방과 방 사이에만 열린다.** 그 규약을 코드로 못박는 자리가
`edit_ruleset` 호출 위치다 — 전투는 방에 들어가기 전에 확정된 규칙표로 끝까지 돌고,
편집기는 방을 나온 뒤에만 불린다. 전투 중 개입을 허용하면 사전 설계의 가치가 사라져
게임이 실시간 조작물이 된다.

갈래·보상·편집의 결정권자를 전부 바깥에서 받는다. UI 가 없는 지금은 기본 선택기가
대신하고, 헤드리스 배치는 여기에 다른 전략을 꽂아 층 전체를 비교할 수 있다.

기존 `run_chain.py` 는 고정 맵 3개를 일렬로 도는 Phase 1 산출물이다. 이 모듈이 그
자리를 잇지만 대체하지는 않는다 — 배치 러너(run_batch)가 아직 그쪽을 쓴다.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from game.app.core.rng import DeterministicRng
from game.app.rules.rule_vm import build_rule_vm
from game.app.services.build_reward import (
    RewardOption,
    RunState,
    apply_reward,
    build_reward_options,
    create_run_state,
)
from game.app.services.run_battle import (
    BattleResult,
    assign_enemy_policies,
    build_engine,
    run_battle,
)
from game.app.simulation.plan import OUTCOME_PLAYER_WIN
from game.config import DEFAULT_MAX_TICKS
from game.schemas.blocks import BlockCatalog
from game.schemas.floor_map import (
    BATTLE_NODE_TYPES,
    NODE_EVENT,
    NODE_REST,
    NODE_SHOP,
    NODE_START,
    FloorMap,
    FloorNode,
    RoomPlan,
)
from game.schemas.room import RoomTemplate
from game.schemas.ruleset import RuleSet

PERCENT = 100

# 회복·이벤트가 움직이는 HP 폭. 정수 퍼센트다 (부동소수를 쓰지 않는다).
REST_HEAL_PCT = 30
EVENT_SWING_PCT = 10
EVENT_GOOD_PCT = 50
SHOP_POTIONS = 1

# 이벤트로는 죽지 않는다. 전투 밖의 사망은 "어느 규칙이 왜 틀렸는가"로 환원되지 않아
# P1(실패는 정보다)을 깬다.
MIN_EVENT_HP = 1


@dataclass(frozen=True)
class NodeVisit:
    """방 하나를 지난 기록. 층을 다시 돌리지 않고도 무엇이 있었는지 읽을 수 있다."""

    node_id: int
    node_type: str
    outcome: str
    ticks: int
    note: str = ""
    taken_reward_id: str | None = None
    offered_reward_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class RoomLoopContext:
    """방 연쇄를 도는 데 필요한 정적 자원. 도는 동안 바뀌지 않는 것만 담는다."""

    floor_map: FloorMap
    templates: dict[str, RoomTemplate]
    balance: dict
    catalog: BlockCatalog
    enemy_rulesets: dict[str, RuleSet] = field(default_factory=dict)
    max_ticks: int = DEFAULT_MAX_TICKS


@dataclass(frozen=True)
class RoomLoopResult:
    """층 하나를 돈 결과."""

    outcome: str
    path: tuple[int, ...]
    visits: tuple[NodeVisit, ...]
    state: RunState

    @property
    def cleared_nodes(self) -> int:
        """클리어한 방 수. 죽은 방은 세지 않는다."""
        return sum(1 for visit in self.visits if visit.outcome == OUTCOME_PLAYER_WIN)

    @property
    def total_ticks(self) -> int:
        """모든 방의 틱 합계."""
        return sum(visit.ticks for visit in self.visits)


RouteChooser = Callable[[FloorMap, FloorNode, tuple[FloorNode, ...]], int]
RewardChooser = Callable[[FloorNode, tuple[RewardOption, ...]], int]
RuleEditor = Callable[[FloorNode, RunState, RuleSet | None], RuleSet | None]


def get_leftmost_route(
    floor_map: FloorMap, node: FloorNode, candidates: tuple[FloorNode, ...]
) -> int:
    """언제나 첫 갈래를 고른다. 선택기를 넘기지 않았을 때의 기본값이다.

    Args:
        floor_map: 도는 중인 층.
        node: 지금 서 있는 노드.
        candidates: 갈 수 있는 다음 노드들.

    Returns:
        고른 갈래의 인덱스.
    """
    return 0


def get_first_reward(node: FloorNode, options: tuple[RewardOption, ...]) -> int:
    """언제나 첫 후보를 고른다. 선택기를 넘기지 않았을 때의 기본값이다.

    Args:
        node: 보상을 준 노드.
        options: 제시된 후보들.

    Returns:
        고른 후보의 인덱스.
    """
    return 0


def get_unchanged_ruleset(
    node: FloorNode, state: RunState, ruleset: RuleSet | None
) -> RuleSet | None:
    """규칙표를 그대로 둔다. 편집기를 넘기지 않았을 때의 기본값이다.

    Args:
        node: 방금 지난 노드.
        state: 지금까지의 런 상태.
        ruleset: 지금 쓰는 규칙표.

    Returns:
        받은 규칙표 그대로.
    """
    return ruleset


def get_clamped_index(raw_index: int, options: Sequence[object]) -> int:
    """선택기가 돌려준 인덱스를 후보 범위 안으로 자른다.

    바깥이 고르는 값이라 범위 밖이 올 수 있다. 예외로 런을 끊지 않는 이유는 선택기가
    UI 든 배치 스크립트든 같은 규칙을 받게 하려는 것이다.

    Args:
        raw_index: 선택기가 돌려준 값.
        options: 고른 대상.

    Returns:
        0 이상 len(options) 미만의 인덱스.
    """
    return max(0, min(raw_index, len(options) - 1))


def apply_node_effect(node: FloorNode, state: RunState, rng: DeterministicRng) -> str:
    """전투가 아닌 노드의 효과를 적용한다.

    Args:
        node: 들어간 노드.
        state: 바뀔 런 상태.
        rng: 이 방 전용 난수원.

    Returns:
        일어난 일의 한 줄 설명. 아무 일도 없으면 빈 문자열.
    """
    swing = state.hp_max * EVENT_SWING_PCT // PERCENT
    if node.node_type == NODE_REST:
        healed = min(state.hp_max - state.hp, state.hp_max * REST_HEAL_PCT // PERCENT)
        state.hp += healed
        return f"휴식 — HP +{healed}"
    if node.node_type == NODE_SHOP:
        state.potions += SHOP_POTIONS
        return f"상점 — 포션 +{SHOP_POTIONS}"
    if node.node_type == NODE_EVENT:
        if rng.get_below(PERCENT) < EVENT_GOOD_PCT:
            state.hp = min(state.hp_max, state.hp + swing)
            return f"이벤트 — HP +{swing}"
        state.hp = max(MIN_EVENT_HP, state.hp - swing)
        return f"이벤트 — HP -{swing}"
    return ""


def run_node_battle(
    context: RoomLoopContext,
    plan: RoomPlan,
    state: RunState,
    ruleset: RuleSet | None,
    seed: int,
) -> BattleResult:
    """방 하나의 전투를 돌리고 결과를 런 상태에 되받는다.

    Args:
        context: 층과 정적 자원.
        plan: 이 노드에 배정된 방.
        state: 들고 온 런 상태. HP 와 포션이 이 함수에서 갱신된다.
        ruleset: 방에 들어갈 때 확정된 플레이어 규칙표. None 이면 폴백 정책.
        seed: 이 방의 전투 시드.

    Returns:
        전투 결과.
    """
    # 층 번호를 넘겨야 TDD §8 의 방어 감쇠식 `defense + 50 + 10*floor` 항이 산다.
    engine = build_engine(
        context.templates[plan.template_id],
        context.balance,
        seed=seed,
        max_ticks=context.max_ticks,
        floor=context.floor_map.floor,
    )
    player = engine.state.entities["player"]
    player.hp_max = state.hp_max
    player.hp = min(state.hp, state.hp_max)
    player.attack = state.attack
    player.defense = state.defense
    player.potions = state.potions
    player.cpu_budget = state.cpu_budget
    if ruleset is not None:
        engine.policies["player"] = build_rule_vm(
            ruleset, context.catalog, engine.config.kind_types
        )
    assign_enemy_policies(engine, context.balance, context.catalog, context.enemy_rulesets)

    result = run_battle(engine)
    state.hp = player.hp
    state.potions = player.potions
    return result


def create_node_visit(
    context: RoomLoopContext,
    node: FloorNode,
    state: RunState,
    ruleset: RuleSet | None,
    base_rng: DeterministicRng,
    choose_reward: RewardChooser,
) -> NodeVisit:
    """방 하나에 들어가 전투·효과·보상 선택까지 마친다.

    난수원은 축마다 갈라 쓴다 (TDD §7.3). 전투 길이가 바뀌어도 보상 후보가 흔들리지
    않아야 "이 보상을 골랐더니 결과가 달라졌다"를 비교할 수 있다.

    Args:
        context: 층과 정적 자원.
        node: 들어갈 노드.
        state: 들고 온 런 상태.
        ruleset: 방에 들어갈 때 확정된 규칙표.
        base_rng: 런 시드에서 만든 기준 난수원.
        choose_reward: 보상 후보 중 하나를 고르는 쪽.

    Returns:
        이 방의 기록. 죽었다면 보상 항목은 비어 있다.
    """
    label = f"floor:{context.floor_map.floor}/node:{node.node_id}"
    outcome = OUTCOME_PLAYER_WIN
    ticks = 0
    note = ""
    if node.node_type in BATTLE_NODE_TYPES:
        result = run_node_battle(
            context,
            context.floor_map.get_room(node.node_id),
            state,
            ruleset,
            base_rng.create_stream(f"{label}/battle").seed,
        )
        outcome, ticks = result.outcome, result.ticks
    else:
        note = apply_node_effect(node, state, base_rng.create_stream(f"{label}/event"))

    if outcome != OUTCOME_PLAYER_WIN:
        return NodeVisit(node.node_id, node.node_type, outcome, ticks, note)

    options = build_reward_options(base_rng.create_stream(f"{label}/reward"))
    taken = options[get_clamped_index(choose_reward(node, options), options)]
    apply_reward(state, taken)
    return NodeVisit(
        node_id=node.node_id,
        node_type=node.node_type,
        outcome=outcome,
        ticks=ticks,
        note=note,
        taken_reward_id=taken.reward_id,
        offered_reward_ids=tuple(option.reward_id for option in options),
    )


def run_room_loop(
    context: RoomLoopContext,
    player_ruleset: RuleSet | None,
    choose_route: RouteChooser = get_leftmost_route,
    choose_reward: RewardChooser = get_first_reward,
    edit_ruleset: RuleEditor = get_unchanged_ruleset,
) -> RoomLoopResult:
    """시작 노드에서 보스까지 방을 이어 돈다 (GDD §2.2).

    편집기는 방을 나온 뒤에만 부른다 — "규칙 편집은 방 사이에서만"을 코드로 못박은
    자리다. 시작 노드는 층의 입구일 뿐이라 전투도 보상도 없고, 거기서 열리는 창구가
    첫 방에 들어가기 전의 편집(프리셋 로드)에 해당한다.

    Args:
        context: 층과 정적 자원.
        player_ruleset: 런을 시작할 때의 플레이어 규칙표. None 이면 폴백 정책.
        choose_route: 갈래를 고르는 쪽.
        choose_reward: 보상을 고르는 쪽.
        edit_ruleset: 방 사이에 규칙표를 고치는 쪽.

    Returns:
        층을 돈 결과. 죽었다면 그 방까지의 기록만 담긴다.
    """
    floor_map = context.floor_map
    base_rng = DeterministicRng(floor_map.seed)
    state = create_run_state(context.balance)
    ruleset = player_ruleset
    node = floor_map.get_node(floor_map.start_id)
    path = [node.node_id]
    visits: list[NodeVisit] = []
    outcome = OUTCOME_PLAYER_WIN

    while True:
        if node.node_type != NODE_START:
            visit = create_node_visit(context, node, state, ruleset, base_rng, choose_reward)
            visits.append(visit)
            outcome = visit.outcome
            if outcome != OUTCOME_PLAYER_WIN:
                break
        candidates = floor_map.list_next(node)
        if not candidates:
            break
        # 편집 창구는 다음 방이 있을 때만 열린다. 보스를 잡은 뒤의 편집은 반영될
        # 방이 없어, 열어 두면 결과에 영향 없는 호출로 UI 를 혼란스럽게 만든다.
        ruleset = edit_ruleset(node, state, ruleset)
        node = candidates[get_clamped_index(choose_route(floor_map, node, candidates), candidates)]
        path.append(node.node_id)

    return RoomLoopResult(outcome=outcome, path=tuple(path), visits=tuple(visits), state=state)
