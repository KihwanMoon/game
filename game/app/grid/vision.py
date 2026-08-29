"""시야(LOS) — 직선 시야 판정과 엄폐 (GDD §4.1·§4.4, TDD §5.4).

원거리 적이 직선 시야가 통할 때만 쏘고 벽 뒤로 숨는 것이 유효한 대응이 되어야
그리드가 존재할 이유가 생긴다 (P2). 이 모듈은 그 판정만 책임지며, 누가 언제 그것을
묻는지는 simulation 계층이 정한다.

**정수 브레젠험만 쓴다.** 부동소수 기울기로 그으면 같은 시드가 다른 선을 낼 수 있고
그 순간 리플레이가 깨진다 (R5).

**대칭은 좌표 정렬로 보장한다.** 브레젠험은 오차가 정확히 반일 때 진행 방향에 따라
다른 칸을 지나므로 A→B 와 B→A 가 갈릴 수 있다. 항상 사전순으로 작은 좌표에서 긋도록
고정하면 두 방향이 같은 선을 쓴다. "내가 보이면 상대도 보인다"가 깨지면 플레이어는
자기 규칙표로 설명할 수 없는 패배를 겪는다 (P1). 대신 완전 대각선은 사이의 두 직교
칸을 보지 않고 모서리를 스친다 — 이동이 4방향이라 그런 모서리가 잘 생기지 않고,
막으려면 대칭 보장이 복잡해진다. 방 설계가 이것을 이용하면 W7 에서 좁힌다.

TDD §5.4 에 따라 방 진입 시 관측자별 가시성 맵을 미리 만들고(build_visibility_map),
그다음부터는 위치가 바뀐 관측자만 갱신한다(VisionCache.refresh). 조회는 O(1) 이다.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from game.app.grid.geometry import get_manhattan_distance
from game.schemas.room import TILE_BREAKABLE_WALL, TILE_COVER, TILE_WALL, WALKABLE_TILES

Position = tuple[int, int]

# 시야를 막는 타일 (GDD §4.4). 가시덤불(3)은 이동만 늦출 뿐 시야는 막지 않는다.
# 파괴 가능 벽(2)은 부서지기 전까지 막으며, 부순 뒤에는 WorldState 의 타일 덮어쓰기가
# 반영되므로 이 목록은 그대로 두고 시야가 열린다.
BLOCKING_TILES = frozenset({TILE_WALL, TILE_BREAKABLE_WALL, TILE_COVER})

# 엄폐할 곳이 없을 때의 거리. perception 의 "방에 없음" 규약과 같은 값이라 규칙표가
# 두 변수를 같은 방식으로 비교할 수 있다.
NO_COVER_DISTANCE = -1


class TileReader(Protocol):
    """좌표 하나의 타일을 읽을 수 있는 것.

    RoomTemplate 과 WorldState 가 둘 다 만족한다. 둘을 가르는 것은 파괴된 벽이며,
    전투 중 판정은 그것을 반영하는 WorldState 쪽을 넘겨야 한다.
    """

    def get_tile(self, x: int, y: int) -> int:
        """좌표의 타일 ID 를 돌려준다.

        Args:
            x: 가로 좌표.
            y: 세로 좌표.

        Returns:
            타일 ID.
        """


@dataclass(frozen=True)
class VisionGrid:
    """타일 읽기와 방 크기를 묶은, 시야 함수들이 받는 격자.

    WorldState 는 파괴된 벽을 반영한 타일을 주지만 크기는 room 이 안다. 둘을 여기서
    묶는다. RoomTemplate 은 VisionGrid(t, t.width, t.height) 로 감싼다.
    """

    tiles: TileReader
    width: int
    height: int

    def get_tile(self, x: int, y: int) -> int:
        """좌표의 타일 ID 를 돌려준다.

        Args:
            x: 가로 좌표.
            y: 세로 좌표.

        Returns:
            타일 ID. 격자 밖은 벽으로 취급한다.
        """
        if not (0 <= x < self.width and 0 <= y < self.height):
            return TILE_WALL
        return self.tiles.get_tile(x, y)


@dataclass(frozen=True)
class VisibilityMap:
    """한 시점(視點)에서 방 전체를 본 결과 (TDD §5.4). 만들어진 뒤 바뀌지 않는다."""

    origin: Position
    visible: frozenset[Position]


def is_blocking_tile(tile_id: int) -> bool:
    """그 타일이 시야를 막는가.

    Args:
        tile_id: 타일 ID.

    Returns:
        벽·파괴 가능 벽·엄폐물이면 True.
    """
    return tile_id in BLOCKING_TILES


def _iter_line_cells(origin: Position, target: Position) -> tuple[Position, ...]:
    """두 칸을 잇는 브레젠험 직선 위의 칸들을 양 끝 포함해 돌려준다 (R5: 정수 덧셈만).

    Args:
        origin: 시작 좌표.
        target: 끝 좌표.

    Returns:
        origin 에서 target 까지 지나는 칸들.
    """
    x, y = origin
    end_x, end_y = target
    step_x = 1 if end_x > x else -1
    step_y = 1 if end_y > y else -1
    span_x = abs(end_x - x)
    span_y = -abs(end_y - y)
    error = span_x + span_y

    cells: list[Position] = [(x, y)]
    while (x, y) != target:
        doubled = 2 * error
        if doubled >= span_y:
            error += span_y
            x += step_x
        if doubled <= span_x:
            error += span_x
            y += step_y
        cells.append((x, y))
    return tuple(cells)


def check_line_of_sight(grid: VisionGrid, origin: Position, target: Position) -> bool:
    """두 칸 사이에 직선 시야가 통하는가 (GDD §4.1).

    양 끝 칸은 판정에서 뺀다 — 서 있는 칸이 자기 시야를 막지는 않는다. 선을 늘 사전순
    작은 좌표에서 긋기 때문에 두 인자를 바꿔 넣어도 답이 같다.

    Args:
        grid: 타일을 읽을 격자.
        origin: 보는 쪽 좌표.
        target: 보이는 쪽 좌표.

    Returns:
        중간에 시야를 막는 타일이 없으면 True.
    """
    if origin == target:
        return True
    start, end = sorted((origin, target))
    return not any(
        is_blocking_tile(grid.get_tile(*cell)) for cell in _iter_line_cells(start, end)[1:-1]
    )


def build_visibility_map(
    grid: VisionGrid, origin: Position, max_range: int | None = None
) -> VisibilityMap:
    """한 좌표에서 보이는 칸을 방 전체에 대해 미리 계산한다 (TDD §5.4).

    방 진입 시 관측자마다 한 번 부르는 것이 용도다. LOS 는 O(적 수 × 사거리) 라
    매 틱 전량 재계산하면 틱 예산을 먹는다.

    Args:
        grid: 타일을 읽을 격자.
        origin: 시점 좌표.
        max_range: 이 맨해튼 거리까지만 본다. None 이면 방 전체.

    Returns:
        origin 에서 보이는 칸들을 담은 맵.
    """
    visible = [
        (x, y)
        for y in range(grid.height)
        for x in range(grid.width)
        if (max_range is None or get_manhattan_distance(origin, (x, y)) <= max_range)
        and check_line_of_sight(grid, origin, (x, y))
    ]
    return VisibilityMap(origin=origin, visible=frozenset(visible))


def check_visibility(vision_map: VisibilityMap, position: Position) -> bool:
    """사전 계산된 맵에서 그 칸이 보이는지 조회한다. O(1) 이다.

    Args:
        vision_map: build_visibility_map 이 만든 맵.
        position: 조회할 칸.

    Returns:
        맵의 시점에서 그 칸이 보이면 True.
    """
    return position in vision_map.visible


def list_visible_positions(vision_map: VisibilityMap) -> tuple[Position, ...]:
    """보이는 칸들을 행 우선 순서로 돌려준다.

    frozenset 을 그대로 순회해 게임 상태를 만들면 순서가 보장되지 않는다 (R5).

    Args:
        vision_map: build_visibility_map 이 만든 맵.

    Returns:
        (y, x) 오름차순 좌표들.
    """
    return tuple(sorted(vision_map.visible, key=lambda pos: (pos[1], pos[0])))


@dataclass
class VisionCache:
    """방 하나의 관측자별 가시성 맵 (TDD §5.4).

    방 진입 시 전원분을 만들고 이후에는 움직인 관측자만 갱신한다. LOS 가 대칭이라
    맵 하나가 "이 적이 보는 것"과 "이 적에게 노출된 것"을 함께 답한다.
    """

    grid: VisionGrid
    max_range: int | None = None
    maps: dict[str, VisibilityMap] = field(default_factory=dict)

    def register(self, viewer_id: str, origin: Position) -> VisibilityMap:
        """관측자의 맵을 새로 계산해 넣는다.

        벽이 부서져 지형이 바뀌었을 때도 이것을 부른다 — refresh 는 위치만 본다.

        Args:
            viewer_id: 관측자 엔티티 id.
            origin: 관측자의 현재 좌표.

        Returns:
            새로 계산한 맵.
        """
        vision_map = build_visibility_map(self.grid, origin, self.max_range)
        self.maps[viewer_id] = vision_map
        return vision_map

    def refresh(self, viewer_id: str, origin: Position) -> VisibilityMap:
        """움직인 관측자만 다시 계산한다.

        Args:
            viewer_id: 관측자 엔티티 id.
            origin: 관측자의 현재 좌표.

        Returns:
            위치가 그대로면 이전 맵 그대로, 움직였으면 새 맵.
        """
        cached = self.maps.get(viewer_id)
        if cached is not None and cached.origin == origin:
            return cached
        return self.register(viewer_id, origin)

    def read(self, viewer_id: str) -> VisibilityMap | None:
        """등록된 맵을 꺼낸다.

        Args:
            viewer_id: 관측자 엔티티 id.

        Returns:
            맵. 등록된 적이 없으면 None — "없다"와 "안 보인다"는 다른 답이다.
        """
        return self.maps.get(viewer_id)

    def check(self, viewer_id: str, position: Position) -> bool:
        """관측자가 그 칸을 보는가.

        등록되지 않은 관측자를 False 로 답하지 않는다 — 맵을 만들지 않은 버그가
        "안 보인다"는 정상 판정과 구분되지 않는다.

        Args:
            viewer_id: 관측자 엔티티 id.
            position: 조회할 칸.

        Returns:
            보이면 True.

        Raises:
            KeyError: 아직 맵을 만들지 않은 관측자인 경우.
        """
        vision_map = self.maps.get(viewer_id)
        if vision_map is None:
            raise KeyError(f"가시성 맵이 없는 관측자다: {viewer_id}")
        return position in vision_map.visible

    def drop(self, viewer_id: str) -> None:
        """죽었거나 방을 떠난 관측자의 맵을 버린다.

        Args:
            viewer_id: 관측자 엔티티 id. 없으면 아무 일도 하지 않는다.
        """
        self.maps.pop(viewer_id, None)


def check_exposure(grid: VisionGrid, position: Position, threats: Sequence[Position]) -> bool:
    """그 칸이 위협 중 하나에게라도 보이는가 (인지 변수 self_exposed_to_los).

    Args:
        grid: 타일을 읽을 격자.
        position: 판정할 칸.
        threats: 위협 좌표들. 정렬된 시퀀스를 넘긴다 (R5).

    Returns:
        하나라도 시야가 통하면 True. 위협이 없으면 False 다.
    """
    return any(check_line_of_sight(grid, threat, position) for threat in threats)


def check_cover(grid: VisionGrid, position: Position, threats: Sequence[Position]) -> bool:
    """그 칸이 모든 위협으로부터 가려지는가. 위협 하나만 물어도 된다.

    Args:
        grid: 타일을 읽을 격자.
        position: 판정할 칸.
        threats: 위협 좌표들. 정렬된 시퀀스를 넘긴다 (R5).

    Returns:
        어느 위협에도 보이지 않으면 True. 위협이 없으면 True 다.
    """
    return not check_exposure(grid, position, threats)


def find_cover_positions(
    grid: VisionGrid, threats: Sequence[Position], occupied: frozenset[Position] = frozenset()
) -> tuple[Position, ...]:
    """모든 위협의 시야에서 벗어난 이동 가능 칸들을 모은다 (행동 MOVE_TO_COVER).

    거리장의 목표로 그대로 넘기라고 행 우선 순서로 준다. 닿을 수 있는지는 길찾기 몫이다.

    Args:
        grid: 타일을 읽을 격자.
        threats: 피해야 할 위협 좌표들.
        occupied: 다른 엔티티가 서 있어 갈 수 없는 칸.

    Returns:
        엄폐가 성립하는 칸들. 위협이 없으면 숨을 이유도 없으므로 빈 튜플.
    """
    if not threats:
        return ()
    return tuple(
        (x, y)
        for y in range(grid.height)
        for x in range(grid.width)
        if grid.get_tile(x, y) in WALKABLE_TILES
        and (x, y) not in occupied
        and check_cover(grid, (x, y), threats)
    )


def find_nearest_cover(
    grid: VisionGrid,
    origin: Position,
    threats: Sequence[Position],
    occupied: frozenset[Position] = frozenset(),
) -> Position | None:
    """가장 가까운 엄폐 칸을 찾는다.

    거리가 같으면 행 우선 순서에서 먼저 오는 칸을 고른다 — 고정하지 않으면 같은
    시드가 다른 칸을 골라 리플레이가 깨진다 (R5).

    Args:
        grid: 타일을 읽을 격자.
        origin: 기준 좌표.
        threats: 피해야 할 위협 좌표들.
        occupied: 다른 엔티티가 서 있어 갈 수 없는 칸.

    Returns:
        가장 가까운 엄폐 칸. 하나도 없으면 None.
    """
    candidates = find_cover_positions(grid, threats, occupied)
    if not candidates:
        return None
    return min(candidates, key=lambda pos: (get_manhattan_distance(origin, pos), pos[1], pos[0]))


def calculate_cover_distance(
    grid: VisionGrid,
    origin: Position,
    threats: Sequence[Position],
    occupied: frozenset[Position] = frozenset(),
) -> int:
    """엄폐 가능한 가장 가까운 칸까지의 거리 (인지 변수 cover_wall_distance).

    "엄폐 가능 벽"은 벽 자체가 아니라 **그 뒤에 서면 시야가 끊기는 칸**이다. 벽까지의
    거리를 재면 등 뒤의 벽도 가깝다고 답해 움직여도 노출이 그대로다.

    Args:
        grid: 타일을 읽을 격자.
        origin: 기준 좌표.
        threats: 피해야 할 위협 좌표들.
        occupied: 다른 엔티티가 서 있어 갈 수 없는 칸.

    Returns:
        맨해튼 거리. 이미 가려져 있으면 0, 엄폐할 곳이 없으면 NO_COVER_DISTANCE.
    """
    nearest = find_nearest_cover(grid, origin, threats, occupied)
    if nearest is None:
        return NO_COVER_DISTANCE
    return get_manhattan_distance(origin, nearest)
