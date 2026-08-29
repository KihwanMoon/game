"""생명의 샘 — 회복 타일의 잔여량과 소멸 (GDD §7, 로드맵 W7).

`pressure.py` 에서 갈라 나왔다. 시간에 값을 매기는 축은 셋인데(추격자·층 스케일·샘)
앞의 둘은 "적을 강하게 한다"이고 샘은 "회복원을 고갈시킨다"라 상태도 페이즈도 다르다.
샘은 방의 타일을 바꾸고(RESOLVE), 추격자·스케일은 개체를 바꾼다(UPKEEP).

전부 정수 연산이다. 잔여량은 개수이지 비율이 아니다 (R5).
"""

from game.app.core.event_log import EventLog, LogEntry
from game.app.simulation.phases import PHASE_RESOLVE
from game.app.simulation.state import WorldState
from game.schemas.room import TILE_FLOOR, TILE_SPRING

# 샘 하나가 낼 총 회복량. balance.json 의 anti_abuse 절이 정본이고 이 값은 안전망이다.
DEFAULT_SPRING_POOL = 30

# 특정 개체가 아니라 방 자체가 낸 이벤트의 주체.
WORLD_ENTITY_ID = "world"


def record_world_event(log: EventLog, tick: int, expr: str, outcome: str, phase: str) -> None:
    """방이 낸 이벤트 한 줄을 남긴다. expr 에는 실측값을 병기한다 (GDD §8.2).

    Args:
        log: 이벤트 로그.
        tick: 남길 틱 번호.
        expr: 실측값을 병기한 조건 문자열.
        outcome: 그 조건이 만든 결과 문구.
        phase: 이벤트가 난 페이즈 이름.
    """
    log.record(
        LogEntry(
            tick=tick,
            entity_id=WORLD_ENTITY_ID,
            phase=phase,
            expr=expr,
            outcome=outcome,
            fired=True,
        )
    )


def list_tiles_of_kind(state: WorldState, tile_id: int) -> tuple[tuple[int, int], ...]:
    """방에서 그 종류의 타일 좌표를 훑는다.

    Args:
        state: 세계 상태.
        tile_id: 찾을 타일 ID.

    Returns:
        y, x 순서로 훑은 좌표들. 순서가 고정이라 같은 방이면 같은 결과다 (R5).
    """
    return tuple(
        (x, y)
        for y in range(state.room.height)
        for x in range(state.room.width)
        if state.get_tile(x, y) == tile_id
    )


def init_spring_pools(state: WorldState, pool_size: int = DEFAULT_SPRING_POOL) -> int:
    """방의 생명의 샘마다 총 회복량을 채운다.

    **엔진 조립 직후 반드시 한 번 불러야 한다.** 채우지 않으면 잔여량이 늘 0 이라
    샘은 회복을 한 점도 못 낸 채 첫 RESOLVE 에서 소멸한다 — 차단이 아니라 고장이다.
    이미 값이 있는 좌표는 건드리지 않는다.

    Args:
        state: 세계 상태.
        pool_size: 샘 하나가 낼 총 회복량.

    Returns:
        새로 채운 샘의 수.
    """
    filled = 0
    for position in list_tiles_of_kind(state, TILE_SPRING):
        if position in state.spring_pools:
            continue
        state.spring_pools[position] = pool_size
        filled += 1
    return filled


def apply_spring_drain(state: WorldState, position: tuple[int, int], amount: int) -> int:
    """샘에서 회복량을 꺼내고 잔여량을 그만큼 깎는다.

    Args:
        state: 세계 상태.
        position: 샘 좌표.
        amount: 꺼내려는 양.

    Returns:
        실제로 꺼낸 양. 잔여량이 모자라면 남은 만큼만, 다 썼으면 0 이다.
    """
    pool = state.spring_pools.get(position, 0)
    drawn = max(0, min(amount, pool))
    if drawn > 0:
        state.spring_pools[position] = pool - drawn
    return drawn


def remove_drained_springs(
    state: WorldState, log: EventLog | None = None
) -> tuple[tuple[int, int], ...]:
    """잔여량이 바닥난 샘을 바닥 타일로 지운다 (페이즈 6 RESOLVE).

    Args:
        state: 세계 상태.
        log: 이벤트 로그. None 이면 남기지 않는다.

    Returns:
        이번에 소멸한 샘의 좌표들. 방 좌표 순서를 지킨다.
    """
    drained = tuple(
        position
        for position in list_tiles_of_kind(state, TILE_SPRING)
        if state.spring_pools.get(position, 0) <= 0
    )
    for position in drained:
        state.tile_overrides[position] = TILE_FLOOR
        if log is not None:
            record_world_event(
                log, state.tick, f"샘 잔여량(0) {position}", "샘 소멸", PHASE_RESOLVE
            )
    return drained
