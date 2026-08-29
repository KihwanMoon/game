"""층 그래프 생성 — 깊이 기반 DAG (TDD §7.1·§7.2·§7.3).

시작 노드 하나에서 2~3 갈래로 벌어졌다가 보스 하나로 수렴한다. 갈래가 있어야
"어느 길로 갈 것인가"가 선택이 되고, 수렴이 있어야 어느 길을 골라도 보스를 만난다.

노드 유형은 뽑기가 아니라 **정량 배분 후 셔플**로 정한다. 매 노드를 독립으로 뽑으면
같은 비율을 넣어도 층마다 회복이 0개인 층과 4개인 층이 나오는데, 그 편차는
난이도가 아니라 잡음이다. 비율(전투 60 / 이벤트 15 / 회복 15 / 상점 10)은 TDD §7.1
이 정한 값이다.

무작위성은 `seed + floor_index (+ node_id)` 로 갈린 서브 시드에서만 꺼낸다
(TDD §7.3). 층 배치의 뽑기 횟수가 바뀌어도 방 배정이 흔들리지 않아야 한다.
"""

from game.app.core.rng import DeterministicRng
from game.schemas.floor_map import (
    BATTLE_NODE_TYPES,
    NODE_BOSS,
    NODE_COMBAT,
    NODE_EVENT,
    NODE_REST,
    NODE_SHOP,
    NODE_START,
    FloorMap,
    FloorNode,
    RoomPlan,
    check_floor_map,
)
from game.schemas.room import RoomTemplate, check_room_reachability

PERCENT = 100

# 시작 1 + 중간 3 + 보스 1. 중간 깊이가 둘 이하면 갈래가 곧 수렴이라 선택이 없다.
DEFAULT_DEPTH_COUNT = 5
MIN_DEPTH_COUNT = 3

# 한 깊이의 갈래 수 (TDD §7.1).
MIN_BRANCH = 2
MAX_BRANCH = 3

# 노드 유형 배치 비율 (TDD §7.1). 합이 100 이어야 한다.
TYPE_QUOTA_PCT = ((NODE_COMBAT, 60), (NODE_EVENT, 15), (NODE_REST, 15), (NODE_SHOP, 10))

# 층이 사다리 하나로 굳지 않도록 간선을 하나 더 놓을 확률.
EXTRA_EDGE_PCT = 35

# 재생성 상한. 도달성 검사가 계속 실패하면 데이터 문제이므로 조용히 돌지 않는다.
MAX_ATTEMPTS = 8


def build_layer_sizes(rng: DeterministicRng, depth_count: int) -> tuple[int, ...]:
    """깊이별 노드 수를 정한다. 시작과 보스는 하나씩이다.

    Args:
        rng: 층 배치용 난수원.
        depth_count: 시작과 보스를 포함한 깊이 수.

    Returns:
        깊이 순서대로의 노드 수.

    Raises:
        ValueError: depth_count 가 MIN_DEPTH_COUNT 미만인 경우.
    """
    if depth_count < MIN_DEPTH_COUNT:
        raise ValueError(f"깊이는 {MIN_DEPTH_COUNT} 이상이어야 한다: {depth_count}")
    middle = [rng.get_range(MIN_BRANCH, MAX_BRANCH) for _ in range(depth_count - 2)]
    return (1, *middle, 1)


def build_layer_edges(
    rng: DeterministicRng, source_ids: tuple[int, ...], target_ids: tuple[int, ...]
) -> tuple[tuple[int, ...], ...]:
    """한 깊이에서 다음 깊이로 가는 간선을 놓는다.

    두 방향을 모두 보장한다 — 모든 출발 노드는 나갈 곳이 하나 이상 있고, 모든 도착
    노드는 들어올 곳이 하나 이상 있다. 한쪽만 보장하면 막다른 길이나 고립된 방이
    생기고, 그것은 도달성 검사에서야 드러난다.

    Args:
        rng: 층 배치용 난수원.
        source_ids: 출발 깊이의 노드 id 들.
        target_ids: 도착 깊이의 노드 id 들.

    Returns:
        source_ids 와 같은 순서의, 각 노드가 이어지는 대상 id 들.
    """
    links: list[list[int]] = [[] for _ in source_ids]
    for step in range(max(len(source_ids), len(target_ids))):
        source_index = min(step, len(source_ids) - 1)
        links[source_index].append(target_ids[min(step, len(target_ids) - 1)])
    for targets in links:
        if rng.get_below(PERCENT) >= EXTRA_EDGE_PCT:
            continue
        extra = target_ids[rng.get_below(len(target_ids))]
        if extra not in targets:
            targets.append(extra)
    return tuple(tuple(sorted(targets)) for targets in links)


def build_type_bag(rng: DeterministicRng, count: int) -> tuple[str, ...]:
    """중간 노드에 배치할 유형을 비율대로 만들어 섞는다.

    Args:
        rng: 층 배치용 난수원.
        count: 중간 노드 수.

    Returns:
        길이가 count 인 노드 유형들.
    """
    quotas = [count * quota_pct // PERCENT for _, quota_pct in TYPE_QUOTA_PCT]
    # 최대잉여법으로 남는 자리를 나눈다. 늘 전투에 몰아주면 상점(10%)은 중간 노드가
    # 일고여덟 개뿐인 층에서 영영 나오지 않아, 비율표에 적힌 유형이 데이터에서 사라진다.
    # 나머지 비교는 정수로만 한다 (부동소수를 쓰지 않는다).
    by_remainder = sorted(
        range(len(TYPE_QUOTA_PCT)),
        key=lambda index: (-((count * TYPE_QUOTA_PCT[index][1]) % PERCENT), index),
    )
    for offset in range(count - sum(quotas)):
        quotas[by_remainder[offset % len(by_remainder)]] += 1

    bag: list[str] = []
    for (node_type, _), quota in zip(TYPE_QUOTA_PCT, quotas, strict=True):
        bag.extend([node_type] * quota)
    # Fisher-Yates. 자리마다 다시 뽑으면 비율이 흔들려 정량 배분을 한 뜻이 없어진다.
    for index in range(len(bag) - 1, 0, -1):
        swap = rng.get_below(index + 1)
        bag[index], bag[swap] = bag[swap], bag[index]
    return tuple(bag)


def build_floor_nodes(rng: DeterministicRng, sizes: tuple[int, ...]) -> tuple[FloorNode, ...]:
    """깊이별 노드 수로부터 노드와 간선을 만든다.

    Args:
        rng: 층 배치용 난수원.
        sizes: 깊이 순서대로의 노드 수.

    Returns:
        node_id 오름차순의 노드들.
    """
    ids_by_depth: list[tuple[int, ...]] = []
    next_id = 0
    for size in sizes:
        ids_by_depth.append(tuple(range(next_id, next_id + size)))
        next_id += size

    bag = build_type_bag(rng, sum(sizes[1:-1]))
    last_depth = len(sizes) - 1
    nodes: list[FloorNode] = []
    taken = 0
    for depth, layer in enumerate(ids_by_depth):
        links: tuple[tuple[int, ...], ...] = ((),) * len(layer)
        if depth < last_depth:
            links = build_layer_edges(rng, layer, ids_by_depth[depth + 1])
        for position, node_id in enumerate(layer):
            node_type = NODE_START if depth == 0 else NODE_BOSS
            if 0 < depth < last_depth:
                node_type = bag[taken]
                taken += 1
            nodes.append(FloorNode(node_id, node_type, depth, links[position]))
    return tuple(nodes)


def create_room_plan(
    node: FloorNode, templates: tuple[RoomTemplate, ...], rng: DeterministicRng
) -> RoomPlan:
    """노드에 방 하나를 배정한다.

    도달성 검사에 걸린 템플릿은 건너뛰고 다음 것을 본다 (TDD §7.2 의 "실패 시
    재생성"). 손으로 그린 템플릿이라도 벽 하나가 잘못 찍히면 클리어 불가능한 방이
    되는데, 그것은 규칙 설계 실패와 구분되지 않는다.

    Args:
        node: 방을 받을 노드.
        templates: 고를 수 있는 템플릿들.
        rng: 이 노드 전용 난수원.

    Returns:
        배정된 방. 전투 노드가 아니면 적을 두지 않는다.

    Raises:
        ValueError: 도달 가능한 템플릿이 하나도 없는 경우.
    """
    ordered = tuple(sorted(templates, key=lambda template: template.template_id))
    if not ordered:
        raise ValueError("룸 템플릿이 비어 있다")
    start = rng.get_below(len(ordered))
    for offset in range(len(ordered)):
        template = ordered[(start + offset) % len(ordered)]
        if check_room_reachability(template):
            continue
        spawns = template.enemy_spawns if node.node_type in BATTLE_NODE_TYPES else ()
        return RoomPlan(
            node_id=node.node_id,
            template_id=template.template_id,
            size=(template.width, template.height),
            spawns=spawns,
        )
    raise ValueError("도달 가능한 룸 템플릿이 하나도 없다")


def build_floor_rooms(
    seed: int, floor_index: int, nodes: tuple[FloorNode, ...], templates: tuple[RoomTemplate, ...]
) -> tuple[RoomPlan, ...]:
    """시작을 뺀 모든 노드에 방을 배정한다.

    노드마다 난수원을 갈라 준다 (TDD §7.3). 한 수열을 공유하면 앞 노드의 템플릿
    후보 수가 바뀔 때 뒤 노드의 방까지 전부 달라진다.

    Args:
        seed: 런 시드.
        floor_index: 층 번호.
        nodes: 방을 배정할 노드들.
        templates: 고를 수 있는 템플릿들.

    Returns:
        node_id 오름차순의 방들.
    """
    base = DeterministicRng(seed)
    plans = [
        create_room_plan(
            node, templates, base.create_stream(f"floor:{floor_index}/node:{node.node_id}/room")
        )
        for node in nodes
        if node.node_type != NODE_START
    ]
    return tuple(sorted(plans, key=lambda plan: plan.node_id))


def build_floor_map(
    seed: int,
    floor_index: int,
    templates: tuple[RoomTemplate, ...],
    depth_count: int = DEFAULT_DEPTH_COUNT,
) -> FloorMap:
    """층 하나를 만들고 검사까지 마친 뒤 돌려준다.

    검사에 걸리면 시도 번호를 바꿔 다시 만든다. 시도 번호가 서브 시드에 들어가므로
    재생성도 결정론적이다 — 같은 시드는 같은 실패를 겪고 같은 층에 도달한다.

    Args:
        seed: 런 시드.
        floor_index: 층 번호. 같은 시드라도 층마다 다른 그래프가 나온다.
        templates: 고를 수 있는 룸 템플릿들.
        depth_count: 시작과 보스를 포함한 깊이 수.

    Returns:
        검사를 통과한 층.

    Raises:
        ValueError: MAX_ATTEMPTS 번 만들어도 검사를 통과하지 못한 경우.
    """
    problems: list[str] = []
    for attempt in range(MAX_ATTEMPTS):
        label = f"floor:{floor_index}/attempt:{attempt}"
        layout_rng = DeterministicRng(seed).create_stream(label)
        nodes = build_floor_nodes(layout_rng, build_layer_sizes(layout_rng, depth_count))
        candidate = FloorMap(
            floor=floor_index,
            seed=seed,
            nodes=nodes,
            rooms=build_floor_rooms(seed, floor_index, nodes, templates),
        )
        problems = check_floor_map(candidate)
        if not problems:
            return candidate
    raise ValueError(f"층 {floor_index} 생성 실패: {problems}")
