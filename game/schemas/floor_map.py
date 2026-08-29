"""층 그래프 스키마 — 노드 DAG 와 방 배치 (TDD §3.4, §7.1).

TDD §3.4 의 맵 형식은 `nodes` 와 `rooms` 두 절이다. 노드는 층의 진행 구조(어디서
어디로 갈 수 있는가)이고, 방은 그 노드에 들어갔을 때 무엇이 있는가다.

`rooms` 에 타일 격자를 복사해 넣지 않고 템플릿 id 만 적는다. 손으로 그린 템플릿이
정본인데(TDD §7.2) 사본을 층 데이터에 함께 두면 둘이 갈라질 수 있고, 갈라진 뒤에는
어느 쪽이 맞는지 판정할 방법이 없다.

층은 DAG 여야 한다. 뒤로 도는 간선이 하나라도 생기면 방 연쇄가 끝나지 않는데,
그것은 전투 결과가 아니라 생성 버그이므로 진행 전에 걸러야 한다.
"""

from collections import deque
from dataclasses import dataclass

from game.schemas.room import EnemySpawn

NODE_START = "START"
NODE_COMBAT = "COMBAT"
NODE_EVENT = "EVENT"
NODE_REST = "REST"
NODE_SHOP = "SHOP"
NODE_BOSS = "BOSS"

NODE_TYPES = (NODE_START, NODE_COMBAT, NODE_EVENT, NODE_REST, NODE_SHOP, NODE_BOSS)

# 전투가 벌어지는 유형. 보상 선택과 적 배치 검사가 이 둘만 대상으로 한다.
BATTLE_NODE_TYPES = frozenset({NODE_COMBAT, NODE_BOSS})


@dataclass(frozen=True)
class FloorNode:
    """층 그래프의 노드 하나 (TDD §3.4 의 nodes 항목)."""

    node_id: int
    node_type: str
    depth: int
    next_ids: tuple[int, ...]


@dataclass(frozen=True)
class RoomPlan:
    """노드 하나에 배정된 방 (TDD §3.4 의 rooms 항목)."""

    node_id: int
    template_id: str
    size: tuple[int, int]
    spawns: tuple[EnemySpawn, ...]


@dataclass(frozen=True)
class FloorMap:
    """층 하나. 노드와 방은 node_id 오름차순으로 담는다."""

    floor: int
    seed: int
    nodes: tuple[FloorNode, ...]
    rooms: tuple[RoomPlan, ...]

    @property
    def start_id(self) -> int:
        """시작 노드의 id."""
        return self._get_only_id(NODE_START)

    @property
    def boss_id(self) -> int:
        """보스 노드의 id."""
        return self._get_only_id(NODE_BOSS)

    def _get_only_id(self, node_type: str) -> int:
        """그 유형의 노드가 정확히 하나일 때 그 id 를 돌려준다.

        Args:
            node_type: 찾을 노드 유형.

        Returns:
            찾은 노드의 id.

        Raises:
            ValueError: 그 유형의 노드가 하나가 아닌 경우.
        """
        found = [node.node_id for node in self.nodes if node.node_type == node_type]
        if len(found) != 1:
            raise ValueError(f"{node_type} 노드가 하나가 아니다: {found}")
        return found[0]

    def get_node(self, node_id: int) -> FloorNode:
        """id 로 노드를 찾는다.

        Args:
            node_id: 찾을 노드 id.

        Returns:
            찾은 노드.

        Raises:
            KeyError: 그런 노드가 없는 경우.
        """
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        raise KeyError(f"노드 {node_id} 가 층에 없다")

    def get_room(self, node_id: int) -> RoomPlan:
        """노드에 배정된 방을 찾는다.

        Args:
            node_id: 찾을 노드 id.

        Returns:
            배정된 방.

        Raises:
            KeyError: 그 노드에 방이 없는 경우.
        """
        for plan in self.rooms:
            if plan.node_id == node_id:
                return plan
        raise KeyError(f"노드 {node_id} 에 배정된 방이 없다")

    def list_next(self, node: FloorNode) -> tuple[FloorNode, ...]:
        """그 노드에서 갈 수 있는 다음 노드들.

        Args:
            node: 기준 노드.

        Returns:
            next_ids 순서 그대로의 노드들. 보스라면 빈 튜플.
        """
        return tuple(self.get_node(next_id) for next_id in node.next_ids)


def find_reachable_ids(floor_map: FloorMap) -> frozenset[int]:
    """시작 노드에서 간선을 따라 닿는 노드 id 들을 모은다.

    Args:
        floor_map: 대상 층.

    Returns:
        닿는 노드 id 들. 시작 노드를 포함한다.
    """
    reached = {floor_map.start_id}
    frontier = [floor_map.start_id]
    while frontier:
        current = floor_map.get_node(frontier.pop())
        for next_id in current.next_ids:
            if next_id in reached:
                continue
            reached.add(next_id)
            frontier.append(next_id)
    return frozenset(reached)


def find_boss_path(floor_map: FloorMap) -> tuple[int, ...]:
    """시작에서 보스까지의 최단 경로를 찾는다.

    같은 길이의 경로가 여럿이면 next_ids 에 적힌 순서가 앞선 쪽을 고른다 — 임의로
    고르면 같은 시드가 다른 경로를 낸다 (R5).

    Args:
        floor_map: 대상 층.

    Returns:
        시작과 보스를 포함한 노드 id 들. 닿을 수 없으면 빈 튜플.
    """
    goal = floor_map.boss_id
    queue: deque[tuple[int, ...]] = deque([(floor_map.start_id,)])
    seen = {floor_map.start_id}
    while queue:
        path = queue.popleft()
        if path[-1] == goal:
            return path
        for next_id in floor_map.get_node(path[-1]).next_ids:
            if next_id in seen:
                continue
            seen.add(next_id)
            queue.append((*path, next_id))
    return ()


def check_node_links(floor_map: FloorMap) -> list[str]:
    """노드 연결이 DAG 규약을 지키는지 본다.

    Args:
        floor_map: 검사할 층.

    Returns:
        문제 설명 목록. 이상이 없으면 빈 리스트.
    """
    problems: list[str] = []
    known = {node.node_id: node for node in floor_map.nodes}
    for node_type, expected in ((NODE_START, 1), (NODE_BOSS, 1)):
        found = sum(1 for node in floor_map.nodes if node.node_type == node_type)
        if found != expected:
            problems.append(f"{node_type} 노드가 {found}개다")
    for node in floor_map.nodes:
        if node.node_type not in NODE_TYPES:
            problems.append(f"노드 {node.node_id}: 모르는 유형 {node.node_type}")
        if node.node_type != NODE_BOSS and not node.next_ids:
            problems.append(f"노드 {node.node_id}: 다음 노드가 없다")
        if node.node_type == NODE_BOSS and node.next_ids:
            problems.append(f"보스 노드 {node.node_id} 뒤에 노드가 있다")
        # 깊이가 늘지 않는 간선은 순환의 씨앗이다. 깊이 순서만 지키면 DAG 가 된다.
        problems.extend(
            f"노드 {node.node_id}: 간선 {next_id} 가 앞으로 가지 않는다"
            for next_id in node.next_ids
            if next_id not in known or known[next_id].depth <= node.depth
        )
    return problems


def check_floor_reachability(floor_map: FloorMap) -> list[str]:
    """시작 노드에서 모든 노드에 닿는지 flood fill 로 확인한다 (TDD §7.2).

    Args:
        floor_map: 검사할 층.

    Returns:
        문제 설명 목록. 이상이 없으면 빈 리스트.
    """
    reached = find_reachable_ids(floor_map)
    return [
        f"노드 {node.node_id}({node.node_type}) 에 시작점에서 닿을 수 없다"
        for node in floor_map.nodes
        if node.node_id not in reached
    ]


def check_room_plans(floor_map: FloorMap) -> list[str]:
    """노드마다 방이 제대로 배정됐는지 본다.

    Args:
        floor_map: 검사할 층.

    Returns:
        문제 설명 목록. 이상이 없으면 빈 리스트.
    """
    problems: list[str] = []
    planned = {plan.node_id for plan in floor_map.rooms}
    for node in floor_map.nodes:
        if node.node_type == NODE_START:
            continue
        if node.node_id not in planned:
            problems.append(f"노드 {node.node_id}: 방이 배정되지 않았다")
            continue
        if node.node_type in BATTLE_NODE_TYPES and not floor_map.get_room(node.node_id).spawns:
            problems.append(f"노드 {node.node_id}: 전투 방인데 적이 없다")
    return problems


def check_floor_map(floor_map: FloorMap) -> list[str]:
    """층 하나를 통째로 검사한다.

    연결 검사를 먼저 하고 문제가 있으면 거기서 멈춘다. 시작·보스 노드가 하나씩
    있다는 것이 도달성 검사의 전제라, 그것이 깨진 채로 flood fill 을 돌리면 검사
    자체가 예외로 죽는다.

    Args:
        floor_map: 검사할 층.

    Returns:
        문제 설명 목록. 이상이 없으면 빈 리스트.
    """
    problems = check_node_links(floor_map)
    if problems:
        return problems
    problems.extend(check_floor_reachability(floor_map))
    problems.extend(check_room_plans(floor_map))
    return problems


def convert_floor_to_dict(floor_map: FloorMap) -> dict:
    """층을 TDD §3.4 의 JSON 형식으로 바꾼다.

    Args:
        floor_map: 변환할 층.

    Returns:
        floor·seed·nodes·rooms 를 담은 딕셔너리. rooms 의 키는 node_id 문자열이다.
    """
    return {
        "floor": floor_map.floor,
        "seed": floor_map.seed,
        "nodes": [
            {
                "node_id": node.node_id,
                "type": node.node_type,
                "depth": node.depth,
                "next": list(node.next_ids),
            }
            for node in floor_map.nodes
        ],
        "rooms": {
            str(plan.node_id): {
                "template_id": plan.template_id,
                "size": list(plan.size),
                "spawns": [
                    {"entity": spawn.kind, "pos": list(spawn.position)} for spawn in plan.spawns
                ],
            }
            for plan in floor_map.rooms
        },
    }


def parse_floor_map(raw: dict) -> FloorMap:
    """TDD §3.4 형식의 딕셔너리에서 층을 읽는다.

    Args:
        raw: convert_floor_to_dict 가 낸 것과 같은 형식의 딕셔너리.

    Returns:
        읽어들인 층. 노드와 방은 node_id 오름차순이다.
    """
    nodes = tuple(
        sorted(
            (
                FloorNode(
                    node_id=item["node_id"],
                    node_type=item["type"],
                    depth=item["depth"],
                    next_ids=tuple(item["next"]),
                )
                for item in raw["nodes"]
            ),
            key=lambda node: node.node_id,
        )
    )
    rooms = tuple(
        sorted(
            (
                RoomPlan(
                    node_id=int(node_key),
                    template_id=item["template_id"],
                    size=(item["size"][0], item["size"][1]),
                    spawns=tuple(
                        EnemySpawn(kind=spawn["entity"], position=tuple(spawn["pos"]))
                        for spawn in item["spawns"]
                    ),
                )
                for node_key, item in sorted(raw["rooms"].items())
            ),
            key=lambda plan: plan.node_id,
        )
    )
    return FloorMap(floor=raw["floor"], seed=raw["seed"], nodes=nodes, rooms=rooms)
