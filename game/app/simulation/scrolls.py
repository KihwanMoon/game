"""주문서 셋이 하는 일 (2026-09-11 결정).

**주문서는 종류가 곧 태그다.** 칸은 하나(주문서 칸)이고 거기 무엇을 끼웠느냐가
`USE_ITEM[태그]` 를 정한다 — 순간이동을 끼우면 `USE_ITEM[BLINK]` 가 돌고
`USE_ITEM[SCROLL]` 은 「불가」가 된다. 그래서 「무엇을 들고 갈까」가 선택이 된다.

**유지시간을 데이터가 아니라 여기 상수로 박는다** (실제 요청: 「유지시간이 명확해야
규칙에 넣을 수 있다」). 규칙표를 짜는 사람이 몇 틱인지 알고 써야 하는 값이고, 그 값이
아이템 등급마다 다르면 같은 규칙이 무엇을 끼웠느냐에 따라 다르게 돈다 — 등급이 바꾸는
것은 **충전 수와 끼고 있는 동안의 접사**뿐이다.

**겹쳐 쓸 수 없다** (같은 요청). 이미 걸려 있는데 또 쓰면 충전만 타므로, 그때는
「불가」로 잡아 다음 규칙에 기회를 준다 — 소모품이 없을 때와 같은 자리다 (결정 #04).
"""

from game.app.grid.geometry import get_manhattan_distance
from game.app.simulation.state import Entity, WorldState
from game.schemas.room import WALKABLE_TILES

# 주문서 태그. 칸 계열은 전부 SCROLL 이다 (`schemas/consumable.SLOT_FAMILY`).
ITEM_BLINK = "BLINK"
ITEM_FLAME = "FLAME"
ITEM_FOCUS = "FOCUS"

# 부릅이 거는 상태와 그 유지 틱. **규칙표가 읽는 값이라 한 자리에 박는다** —
# `self_has_status[FOCUS]` 로 물어 겹쳐 쓰기를 피할 수 있다.
STATUS_FOCUS = "FOCUS"
FOCUS_TICKS = 4

# 부릅이 올리는 사거리. **한 칸이다.** `적거리 <= 사거리` 가 그 몇 틱만 참이 되는 것이
# 이 주문서가 파는 것이고(P2), 두 칸을 주면 그 몇 틱이 다른 게임이 된다.
FOCUS_RANGE_BONUS = 1

# 순간이동이 물러나는 칸 수. 이동이 한 칸씩인 세계라 이것이 포위를 푸는 유일한 수단이다.
BLINK_STEPS = 3

# 화염이 태우는 반경과 계수. **예고가 없다** — 마법은 전부 예고를 쓰므로(설계/5_스킬 §10)
# 「예고 없는 광역」은 소모품만 할 수 있는 일이고, 대가는 충전 수다.
FLAME_RADIUS = 1
FLAME_COEF_PCT = 120


def find_blink_spot(state: WorldState, entity: Entity) -> tuple[int, int] | None:
    """적에게서 멀어지는 빈 칸을 찾는다.

    **가장 먼 칸이 아니라 가장 먼저 찾은 칸이다.** 후보를 정렬해 고르면 같은 판이
    실행마다 다른 칸을 고를 수 있고(R5), 무엇보다 「어디로 밀려나는가」가 규칙표가
    답할 질문이 아니다 — 답해야 하는 것은 「언제 쓸 것인가」다.

    Args:
        state: 세계 상태.
        entity: 쓰는 개체.

    Returns:
        설 칸. 갈 곳이 없으면 None.
    """
    hostiles = state.list_hostiles(entity)
    if not hostiles:
        return None
    taken = {other.position for other in state.list_actors() if other is not entity}
    here = entity.position
    near = min(get_manhattan_distance(here, one.position) for one in hostiles)
    best: tuple[int, int] | None = None
    best_gap = near
    # 행 우선으로 훑는다. 순회 순서가 결과에 새어 나가면 안 된다 (R5).
    for y in range(state.room.height):
        for x in range(state.room.width):
            spot = (x, y)
            if state.get_tile(x, y) not in WALKABLE_TILES or spot in taken:
                continue
            if get_manhattan_distance(here, spot) > BLINK_STEPS:
                continue
            gap = min(get_manhattan_distance(spot, one.position) for one in hostiles)
            if gap > best_gap:
                best_gap = gap
                best = spot
    return best


def read_reach(entity: Entity) -> int:
    """지금 이 개체가 닿는 거리.

    **한 자리에 모은 이유가 있다.** 사거리를 읽는 곳이 넷이다 — 규칙표의 `사거리` 값
    (`rhs_readers`), 폴백 정책, 시야 판정, 그리고 실제 타격(`actions`). 부릅을 한
    곳에만 반영하면 **규칙은 참인데 공격이 안 닿거나**, 반대로 닿는데 규칙이 거짓이
    된다 — 둘 다 「왜 안 때리지」로만 보인다.

    Args:
        entity: 볼 개체.

    Returns:
        기본 사거리에 걸린 버프를 더한 값.
    """
    bonus = FOCUS_RANGE_BONUS if entity.statuses.get(STATUS_FOCUS, 0) > 0 else 0
    return entity.attack_range + bonus


# 태그에서 그것이 거는 상태로. **겹쳐 쓰기를 막는 자리다** (2026-09-11 실제 요청) —
# 이미 걸려 있는데 또 쓰면 충전만 탄다. 즉발(순간이동·화염)은 여기 없다: 남는 상태가
# 없으므로 겹칠 것도 없다.
LASTING_STATUS: dict[str, str] = {"SCROLL": "GUARD", ITEM_FOCUS: STATUS_FOCUS}


def check_already_held(entity: Entity, use_tag: str) -> bool:
    """그 주문서가 거는 상태가 이미 걸려 있는가.

    Args:
        entity: 쓰려는 개체.
        use_tag: 소모품 태그.

    Returns:
        이미 걸려 있으면 True — 그때는 「불가」로 잡아 다음 규칙에 기회를 준다.
    """
    status = LASTING_STATUS.get(use_tag, "")
    return bool(status) and entity.statuses.get(status, 0) > 0
