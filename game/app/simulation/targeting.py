"""누가 맞는가 — 한 벌 (설계/5_스킬 §2, 2026-09-19).

**같은 규칙이 두 곳에 다르게 박혀 있었다.** 즉발 범위(`blast_actions.apply_area_attack`)는
시전자 중심 반경 안의 **적만** 쳤고, 예고형(`telegraph._apply_blast`)은 칸에 선 것을
**진영 없이** 쳤다. 둘 다 `AREA` 인데 판정이 정반대였고, 데이터만 봐서는 구별이 안 됐다.

그래서 축을 세운다. **규칙이 코드가 아니라 재주에 적힌다** — 관리 화면이 그것을 고르개로
고치고, 새 재주가 들어올 때 「이건 어느 쪽이더라」를 코드를 읽어 알아낼 필요가 없다.

**지금 동작을 그대로 옮긴다.** 축을 여는 것과 값을 바꾸는 것은 다른 일이라, 배포된
재주는 전부 지금 하던 판정을 그대로 적는다 — 골든이 안 움직이는 것이 그 증거다.
"""

from game.app.grid.geometry import get_manhattan_distance
from game.app.simulation.state import Entity, WorldState

# 대상 하나. 셀렉터가 고른 그 개체가 맞는다 — 비켜설 수 없다.
HITS_TARGET = "TARGET"
# 시전자 중심 반경 안의 **적만**. 즉발 범위 공격이 이것이다.
HITS_HOSTILE_AREA = "HOSTILE_AREA"
# 칸에 선 것 **전부**. 예고가 좌표에 떨어지므로 아군도 시전자도 맞는다 (GDD §4.3) —
# 그래야 통로로 유인하는 전술이 성립한다.
HITS_TILES = "TILES"

# 아는 값 전부. 모르는 값이 데이터로 들어오면 조용히 대상 하나가 되므로 부르는 쪽이 본다.
HITS_MODES: frozenset[str] = frozenset({HITS_TARGET, HITS_HOSTILE_AREA, HITS_TILES})


def list_area_victims(state: WorldState, caster: Entity, radius: int) -> list[Entity]:
    """시전자 중심 반경 안의 적을 모은다 (`HOSTILE_AREA`).

    Args:
        state: 세계 상태.
        caster: 시전자.
        radius: 맨해튼 반경.

    Returns:
        맞을 개체들. 목록 순서는 `list_hostiles` 가 정한다 (R5 — 집합을 안 돈다).
    """
    return [
        other
        for other in state.list_hostiles(caster)
        if get_manhattan_distance(caster.position, other.position) <= radius
    ]


def list_tile_victims(state: WorldState, tiles: frozenset[tuple[int, int]]) -> list[Entity]:
    """그 칸들에 선 것을 전부 모은다 (`HITS_TILES`).

    **진영을 안 가린다.** 예고는 좌표에 떨어지므로 시전자의 아군도 맞는다.

    Args:
        state: 세계 상태.
        tiles: 맞는 칸들. **포함 검사에만 쓴다** — 순회하면 순서가 흔들린다 (R5).

    Returns:
        맞을 개체들. 순서는 `list_actors` 가 정한다.
    """
    return [entity for entity in state.list_actors() if entity.position in tiles]
