"""격자 좌표 연산 — 방향과 거리의 정의 (로드맵 Phase 0 F-5 결정).

**이동은 4방향, 거리는 맨해튼이다.** 대각 이동을 허용하지 않는 이유는 P2(그리드는
이유가 있어야 한다)에 있다 — 대각선으로 사선을 빠져나갈 수 있으면 통로 유인과 엄폐가
동시에 약해져 방 설계가 전술을 만들지 못한다.

GDD §3.2 의 포위도는 주변 8칸을 센다. 이동 4방향과 기준이 다른 것은 의도된 것이다 —
근접 적은 인접 8칸을 점유하지만(GDD §4.3) 이동은 상하좌우로만 한다. 두 값을 섞어
쓰지 않도록 함수를 따로 둔다.
"""

# 이동 가능한 방향. 순서를 고정한다 — 같은 비용의 경로가 여럿일 때 이 순서가
# 결과를 가르므로, 바꾸면 저장된 리플레이가 재현되지 않는다 (R5).
STEP_OFFSETS = ((0, -1), (1, 0), (0, 1), (-1, 0))

# 포위 판정용 8방향. 이동에는 쓰지 않는다.
NEIGHBOR_OFFSETS = (
    (-1, -1),
    (0, -1),
    (1, -1),
    (-1, 0),
    (1, 0),
    (-1, 1),
    (0, 1),
    (1, 1),
)


def get_manhattan_distance(origin: tuple[int, int], target: tuple[int, int]) -> int:
    """두 좌표 사이의 맨해튼 거리를 잰다.

    Args:
        origin: 기준 좌표.
        target: 대상 좌표.

    Returns:
        상하좌우로만 이동할 때의 최소 칸 수.
    """
    return abs(origin[0] - target[0]) + abs(origin[1] - target[1])


def iter_steps(origin: tuple[int, int]) -> tuple[tuple[int, int], ...]:
    """이동 가능한 이웃 4칸을 STEP_OFFSETS 순서로 돌려준다.

    Args:
        origin: 기준 좌표.

    Returns:
        이웃 좌표 4개. 통행 가능 여부는 보지 않는다.
    """
    return tuple((origin[0] + dx, origin[1] + dy) for dx, dy in STEP_OFFSETS)


def iter_neighbors(origin: tuple[int, int]) -> tuple[tuple[int, int], ...]:
    """포위 판정용 이웃 8칸을 돌려준다.

    Args:
        origin: 기준 좌표.

    Returns:
        이웃 좌표 8개.
    """
    return tuple((origin[0] + dx, origin[1] + dy) for dx, dy in NEIGHBOR_OFFSETS)
