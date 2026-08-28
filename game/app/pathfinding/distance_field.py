"""거리장 — 목표까지의 최소 이동 비용을 방 전체에 미리 깔아 둔다 (TDD §6).

문·계단·회복타일처럼 목표가 고정된 이동은 방 진입 시 한 번만 계산하면 되고, 이후
탐색 비용이 0 이다. 적 추적만 매 틱 갱신한다.

Phase 1 은 균일 비용이라 BFS 면 충분하다. 가시덤불(이동 2틱)이 들어오는 순간
가중 Dijkstra 로 바꿔야 하며, 그때 이 모듈의 인터페이스는 그대로 둔다.
"""

from collections import deque

from game.app.grid.geometry import STEP_OFFSETS
from game.app.simulation.state import WorldState
from game.schemas.room import WALKABLE_TILES

Position = tuple[int, int]


def build_distance_field(
    state: WorldState, goals: tuple[Position, ...], blocked: frozenset[Position] = frozenset()
) -> dict[Position, int]:
    """목표들로부터의 최소 걸음 수를 방 전체에 채운다.

    Args:
        state: 세계 상태. 타일 통행 가능 여부를 여기서 읽는다.
        goals: 거리 0 이 되는 목표 칸들.
        blocked: 통행 불가로 취급할 추가 칸. 다른 엔티티가 서 있는 자리 등.

    Returns:
        좌표에서 걸음 수로의 대응표. 닿을 수 없는 칸은 빠진다.
    """
    field: dict[Position, int] = {}
    frontier: deque[Position] = deque()
    for goal in goals:
        if goal not in field:
            field[goal] = 0
            frontier.append(goal)

    while frontier:
        x, y = frontier.popleft()
        for dx, dy in STEP_OFFSETS:
            step = (x + dx, y + dy)
            if step in field or step in blocked:
                continue
            if state.get_tile(*step) not in WALKABLE_TILES:
                continue
            field[step] = field[(x, y)] + 1
            frontier.append(step)
    return field


def find_next_step(field: dict[Position, int], origin: Position) -> Position | None:
    """거리장을 따라 한 칸 내려간다.

    같은 거리의 이웃이 여럿이면 STEP_OFFSETS 순서에서 먼저 오는 쪽을 고른다.
    순서를 고정하지 않으면 같은 시드가 다른 경로를 내 리플레이가 깨진다 (R5).

    Args:
        field: build_distance_field 가 만든 거리장.
        origin: 현재 위치.

    Returns:
        한 걸음 나아간 좌표. 이미 목표이거나 길이 없으면 None.
    """
    here = field.get(origin)
    if here is None or here == 0:
        return None
    for dx, dy in STEP_OFFSETS:
        step = (origin[0] + dx, origin[1] + dy)
        if field.get(step) == here - 1:
            return step
    return None
