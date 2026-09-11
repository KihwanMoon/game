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

**저절로 터진다** (2026-09-11 개정). 주문서 한 줄은 규칙 슬롯 1 과 cpu 2 를 먹는데
실측이 +3%p 였다 — 5칸이 꽉 찬 규칙표에서는 내줄 줄이 없어 「못 쓰는 것」이 맞았다.
그래서 **아이템마다 고정 트리거를 주고, 그 조건이 맞으면 규칙 줄 없이 발동·소비된다.**

확률이 아니라 **조건**인 이유가 둘이다. 전투 판정에는 난수가 없고(닿는 곳이 이니셔티브
동률과 전투 전 배치뿐이다), 충전이 1~2장이라 확률은 대개 체력이 멀쩡할 때 터져 버린다 —
방어용 소모품이 가장 안 아쉬울 때 사라진다.

**규칙표가 그 태그를 직접 쓰면 자동은 물러난다** (`PlannedAction.managed_items`). 내가
적은 줄이 기본보다 세다 — 안 그러면 「내 규칙이 영영 안 뜬다」가 된다.
"""

from collections.abc import Callable

from game.app.grid.geometry import get_manhattan_distance
from game.app.simulation.plan import MELEE_REACH
from game.app.simulation.state import PERCENT_BASE, Entity, WorldState
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


# ── 조건 발동 (2026-09-11) ─────────────────────────────────────────────
#
# **태그마다 하나씩, 코드에 박는다.** 유지시간과 같은 규율이다 — 트리거가 아이템 등급마다
# 다르면 같은 주문서가 무엇을 주웠느냐에 따라 다른 때 터지고, 그러면 들고 가는 사람이
# 「언제 터지는지」를 모른다. 등급이 바꾸는 것은 충전 수와 접사뿐이다.
#
# **넷이 서로 다른 곤경을 덮는다.** 특히 순간이동과 화염은 **같은 상황의 두 답**이다 —
# 포위됐을 때 빠질 것인가 태울 것인가. 그것이 곧 「어느 주문서를 들고 갈까」다 (P3).

# 포위로 치는 인접 적 수. 둘이면 이미 협공 보정이 붙는 자리다 (`actions.apply_strike`).
SURROUNDED_COUNT = 2

# 보호가 자세를 잡는 체력 문턱. 규칙표의 흔한 문턱(25~30%)과 같은 자리에 둔다.
GUARD_HP_PCT = 30


def count_adjacent_hostiles(state: WorldState, entity: Entity) -> int:
    """붙어 있는 적의 수.

    Args:
        state: 세계 상태.
        entity: 볼 개체.

    Returns:
        인접(맨해튼 1) 적의 수.
    """
    return sum(
        1
        for other in state.list_hostiles(entity)
        if get_manhattan_distance(entity.position, other.position) <= MELEE_REACH
    )


def check_guard_trigger(state: WorldState, entity: Entity) -> tuple[bool, str]:
    """보호 — 체력이 문턱 아래로 내려가 있고 적이 붙어 있는가.

    **맞는 순간이 아니라 틱 머리에서 본다.** 피격 시점에 끼워 넣으면 피해 경로가 갈라져
    두 코어가 어긋나기 쉽고(G3), 「문턱을 넘으면 자세를 잡는다」가 사람에게도 더 쉽다.

    Args:
        state: 세계 상태.
        entity: 들고 있는 개체.

    Returns:
        (발동할까, 실측값을 병기한 문장).
    """
    hp_pct = entity.hp * PERCENT_BASE // max(1, entity.hp_max)
    near = count_adjacent_hostiles(state, entity)
    fired = hp_pct < GUARD_HP_PCT and near > 0
    return fired, f"내 HP%({hp_pct}) < {GUARD_HP_PCT} AND 인접 적({near}) > 0"


def check_blink_trigger(state: WorldState, entity: Entity) -> tuple[bool, str]:
    """순간이동 — 포위됐는가.

    **인접 적 수는 규칙표가 못 묻는 값이다.** 인지 변수에 없으므로, 이 트리거는 규칙
    줄로는 지을 수 없는 판단을 한다 — 그것이 이 주문서가 파는 것이다.

    Args:
        state: 세계 상태.
        entity: 들고 있는 개체.

    Returns:
        (발동할까, 실측값을 병기한 문장).
    """
    near = count_adjacent_hostiles(state, entity)
    return near >= SURROUNDED_COUNT, f"인접 적({near}) >= {SURROUNDED_COUNT}"


def check_flame_trigger(state: WorldState, entity: Entity) -> tuple[bool, str]:
    """화염 — 포위됐는가. 순간이동과 **같은 조건이고 답이 반대다**.

    Args:
        state: 세계 상태.
        entity: 들고 있는 개체.

    Returns:
        (발동할까, 실측값을 병기한 문장).
    """
    near = count_adjacent_hostiles(state, entity)
    return near >= SURROUNDED_COUNT, f"인접 적({near}) >= {SURROUNDED_COUNT}"


def check_focus_trigger(state: WorldState, entity: Entity) -> tuple[bool, str]:
    """부릅 — 적이 있는데 한 칸 차이로 **안 닿는가**?

    닿는 적이 하나라도 있으면 안 터진다. 때릴 수 있는데 사거리를 사는 것은 낭비다.

    Args:
        state: 세계 상태.
        entity: 들고 있는 개체.

    Returns:
        (발동할까, 실측값을 병기한 문장).
    """
    hostiles = state.list_hostiles(entity)
    if not hostiles:
        return False, "적 없음"
    reach = read_reach(entity)
    near = min(get_manhattan_distance(entity.position, one.position) for one in hostiles)
    fired = near == reach + FOCUS_RANGE_BONUS
    return fired, f"적거리({near}) == 사거리({reach}) + {FOCUS_RANGE_BONUS}"


# 태그에서 그것이 저절로 터지는 조건으로. 여기 없는 태그는 규칙표로만 쓴다 — 물약이
# 그렇다: 언제 마실지는 이 게임이 파는 판단 그 자체라 기본값을 두지 않는다.
TRIGGERS: dict[str, Callable[[WorldState, Entity], tuple[bool, str]]] = {
    "SCROLL": check_guard_trigger,
    ITEM_BLINK: check_blink_trigger,
    ITEM_FLAME: check_flame_trigger,
    ITEM_FOCUS: check_focus_trigger,
}


def list_auto_scrolls(
    state: WorldState, entity: Entity, managed: tuple[str, ...]
) -> tuple[tuple[str, str], ...]:
    """이번 틱에 저절로 터질 주문서들.

    **`TRIGGERS` 의 순서대로 본다.** 딕셔너리를 순회해 상태를 만들지만 그 표가 **박아 둔
    상수**라 순서가 고정돼 있다 (R5 가 막는 것은 흔들리는 순회지 고정된 순서가 아니다).

    **규칙표가 직접 다루는 태그는 뺀다.** 내가 적은 줄이 기본보다 세다 — 안 그러면
    자동이 먼저 태워서 「내 규칙이 영영 안 뜬다」가 된다.

    Args:
        state: 세계 상태.
        entity: 들고 있는 개체.
        managed: 규칙표가 직접 쓰는 태그들.

    Returns:
        (태그, 실측값을 병기한 문장) 들. 터질 것이 없으면 빈 튜플.
    """
    fired: list[tuple[str, str]] = []
    for use_tag, check in TRIGGERS.items():
        if use_tag in managed or entity.consumables.get(use_tag, 0) <= 0:
            continue
        if check_already_held(entity, use_tag):
            continue
        ok, expr = check(state, entity)
        if ok:
            fired.append((use_tag, expr))
    return tuple(fired)
