"""소모품 칸 라우트 — 끼우고, 채우고, 판다 (설계/4_아이템 §5).

**런 중에는 못 건드린다.** 로드아웃은 티켓을 낼 때 얼려지므로 지금 채워 봐야 이번
런에는 안 실린다. 그런데 층 정산은 **지금의 충전에서** 깎으므로, 런 중에 채우면 낸
돈이 그 자리에서 사라진다 — 그래서 막는 것이지 UX 취향이 아니다.

**빈 칸은 출격할 때 공짜로 한 번 찬다.** 예전의 `balance.player.potions` 두 개가 여기로
왔다. 빈 물약 칸 둘이 곧 예전의 기본 지급 둘이고, 바뀐 것은 채우면 더 좋아진다는 것뿐이다.
"""

from fastapi import APIRouter, HTTPException, status
from psycopg_pool import ConnectionPool

from game.api.catalog_view import format_affix
from game.api.deps import CurrentAccount, get_item_catalog, get_pool
from game.api.loadout_service import build_equipped_entries, count_slot_bonus
from game.api.schemas import (
    ConsumableOption,
    ConsumableResponse,
    ConsumableSellRequest,
    ConsumableSlotRequest,
    ConsumableSlotView,
)
from game.app.store.accounts import find_player_entity
from game.app.store.consumables import (
    ConsumableSlot,
    apply_slot_clear,
    apply_slot_fill,
    apply_slot_load,
    list_consumable_slots,
)
from game.app.store.equipment import add_currency, read_balance
from game.app.store.inventory_slots import apply_stack_take, count_stack
from game.app.store.items import list_inventory
from game.app.store.tickets import count_open_tickets
from game.schemas.consumable import (
    FREE_CHARGES,
    check_slot_fit,
    resolve_refill_cost,
    resolve_sell_price,
)
from game.schemas.item import ItemKind

router = APIRouter()

RUN_OPEN_DETAIL = "런이 도는 중이다 — 소모품은 런 사이에만 손댈 수 있다"


def build_slot_view(slot: ConsumableSlot, catalog: dict) -> ConsumableSlotView:
    """칸 하나를 화면 값으로 만든다.

    Args:
        slot: 저장소에서 읽은 칸.
        catalog: 아이템 카탈로그.

    Returns:
        화면이 그릴 값. 빈 칸은 이름도 값도 없다.
    """
    entry = catalog.get(slot.catalog_id) if slot.catalog_id else None
    if entry is None:
        return ConsumableSlotView(use_tag=slot.use_tag, slot_index=slot.slot_index)
    charge_max = max(1, entry.charges)
    return ConsumableSlotView(
        use_tag=slot.use_tag,
        slot_index=slot.slot_index,
        catalog_id=slot.catalog_id,
        label_ko=entry.label_ko,
        grade=entry.grade,
        charges=slot.charges,
        charge_max=charge_max,
        refill_cost=resolve_refill_cost(entry.grade, charge_max - slot.charges),
        # **다 써도 붙는다.** 안 그러면 안 마시는 것이 이득이 된다 (§5).
        affixes=[format_affix(affix) for affix in entry.affixes],
    )


def list_bag_options(pool: ConnectionPool, entity_id: int, catalog: dict) -> list[ConsumableOption]:
    """가방에 있어 칸에 끼울 수 있는 소모품들.

    **가방은 「종류 고르기」용이다** (§5). 보충은 돈으로 하므로, 여기 쌓인 것은 더 좋은
    것으로 갈아 끼우거나 파는 데 쓴다.

    Args:
        pool: 연결 풀.
        entity_id: 대상 개체.
        catalog: 아이템 카탈로그.

    Returns:
        카탈로그 id 순으로 정렬된 후보들 (R5).
    """
    stock: dict[str, int] = {}
    for entry in list_inventory(pool, entity_id):
        if entry.stack_catalog_id and entry.stack_count > 0:
            stock[entry.stack_catalog_id] = stock.get(entry.stack_catalog_id, 0) + entry.stack_count
    options: list[ConsumableOption] = []
    for catalog_id in sorted(stock):
        item = catalog.get(catalog_id)
        if item is None or item.kind is not ItemKind.CONSUMABLE or not item.use_tag:
            continue
        options.append(
            ConsumableOption(
                catalog_id=catalog_id,
                label_ko=item.label_ko,
                grade=item.grade,
                use_tag=item.use_tag,
                charges=max(1, item.charges),
                stock=stock[catalog_id],
                sell_price=resolve_sell_price(item.grade, max(1, item.charges)),
                affixes=[format_affix(affix) for affix in item.affixes],
            )
        )
    return options


@router.get("/api/consumables", response_model=ConsumableResponse)
def read_consumables(account: CurrentAccount) -> ConsumableResponse:
    """소모품 칸과 끼울 수 있는 것들을 함께 읽는다.

    Args:
        account: 토큰으로 푼 계정.

    Returns:
        칸·후보·잔액. 런이 도는 중이면 `is_run_open` 이 참이다.
    """
    pool = get_pool()
    entity_id = find_player_entity(pool, account.account_id)
    catalog = get_item_catalog()
    return ConsumableResponse(
        slots=[
            build_slot_view(slot, catalog)
            for slot in list_consumable_slots(pool, entity_id, read_slot_bonus(pool, entity_id))
        ],
        options=list_bag_options(pool, entity_id, catalog),
        balance=read_balance(pool, account.account_id),
        free_charges=FREE_CHARGES,
        is_run_open=count_open_tickets(pool, account.account_id) > 0,
    )


def check_run_closed(account_id: int) -> None:
    """런이 안 도는 중인지 본다.

    Args:
        account_id: 대상 계정.

    Raises:
        HTTPException: 런이 도는 중이면 409.
    """
    if count_open_tickets(get_pool(), account_id) > 0:
        raise HTTPException(status.HTTP_409_CONFLICT, RUN_OPEN_DETAIL)


@router.post("/api/consumable/load", response_model=ConsumableResponse)
def create_consumable_load(
    request: ConsumableSlotRequest, account: CurrentAccount
) -> ConsumableResponse:
    """가방의 소모품 하나를 칸에 끼운다. 칸은 가득 찬 채로 시작한다.

    Args:
        request: 칸과 끼울 소모품.
        account: 토큰으로 푼 계정.

    Returns:
        갱신된 칸 화면.

    Raises:
        HTTPException: 런 중이거나, 없는 소모품이거나, 칸과 쓰임새가 안 맞거나,
            가방에 그것이 없는 경우.
    """
    check_run_closed(account.account_id)
    entry = get_item_catalog().get(request.catalog_id or "")
    if entry is None or entry.kind is not ItemKind.CONSUMABLE:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "소모품이 아니다")
    if not check_slot_fit(entry.use_tag, request.use_tag):
        raise HTTPException(status.HTTP_409_CONFLICT, f"{request.use_tag} 칸에 못 넣는다")
    pool = get_pool()
    entity_id = find_player_entity(pool, account.account_id)
    if find_slot(pool, entity_id, request.use_tag, request.slot_index) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "없는 칸이다")
    if not apply_stack_take(pool, entity_id, entry.catalog_id, 1):
        raise HTTPException(status.HTTP_409_CONFLICT, "가방에 없다")
    apply_slot_load(
        pool,
        entity_id,
        request.use_tag,
        request.slot_index,
        entry.catalog_id,
        max(1, entry.charges),
    )
    return read_consumables(account)


@router.post("/api/consumable/clear", response_model=ConsumableResponse)
def create_consumable_clear(
    request: ConsumableSlotRequest, account: CurrentAccount
) -> ConsumableResponse:
    """칸을 비운다. **남은 충전은 안 돌려준다** — 돌려주면 끼웠다 빼기로 옮길 수 있다.

    Args:
        request: 비울 칸.
        account: 토큰으로 푼 계정.

    Returns:
        갱신된 칸 화면.

    Raises:
        HTTPException: 런이 도는 중인 경우.
    """
    check_run_closed(account.account_id)
    pool = get_pool()
    entity_id = find_player_entity(pool, account.account_id)
    apply_slot_clear(pool, entity_id, request.use_tag, request.slot_index)
    return read_consumables(account)


@router.post("/api/consumable/refill", response_model=ConsumableResponse)
def create_consumable_refill(
    request: ConsumableSlotRequest, account: CurrentAccount
) -> ConsumableResponse:
    """빈 충전을 돈을 내고 채운다 (§5).

    Args:
        request: 채울 칸.
        account: 토큰으로 푼 계정.

    Returns:
        갱신된 칸 화면.

    Raises:
        HTTPException: 런 중이거나, 빈 칸이거나, 이미 가득 찼거나, 잔액이 모자란 경우.
    """
    check_run_closed(account.account_id)
    pool = get_pool()
    entity_id = find_player_entity(pool, account.account_id)
    catalog = get_item_catalog()
    slot = find_slot(pool, entity_id, request.use_tag, request.slot_index)
    entry = catalog.get(slot.catalog_id) if slot and slot.catalog_id else None
    if slot is None or entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "끼운 것이 없는 칸이다")
    charge_max = max(1, entry.charges)
    cost = resolve_refill_cost(entry.grade, charge_max - slot.charges)
    if cost <= 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 가득 찼다")
    if read_balance(pool, account.account_id) < cost:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{cost} 이 필요하다")
    add_currency(pool, account.account_id, -cost)
    apply_slot_fill(pool, entity_id, request.use_tag, request.slot_index, charge_max)
    return read_consumables(account)


def read_slot_bonus(pool: ConnectionPool, entity_id: int) -> dict[str, int]:
    """장비 접사가 이 개체의 소모품 칸을 몇 개 늘렸는지 읽는다.

    **읽는 쪽과 깎는 쪽이 같은 값을 봐야 한다** (§5). 다르면 늘어난 칸에서 쓴 것이 안
    깎여 그 칸만 공짜가 된다.

    Args:
        pool: 연결 풀.
        entity_id: 대상 개체.

    Returns:
        쓰임새에서 늘어난 칸 수로.
    """
    return count_slot_bonus(build_equipped_entries(pool, entity_id, get_item_catalog()))


def find_slot(
    pool: ConnectionPool, entity_id: int, use_tag: str, slot_index: int
) -> ConsumableSlot | None:
    """칸 하나를 찾는다.

    Args:
        pool: 연결 풀.
        entity_id: 대상 개체.
        use_tag: 칸의 쓰임새.
        slot_index: 칸 번호.

    Returns:
        찾은 칸. 없는 칸이면 None.
    """
    for slot in list_consumable_slots(pool, entity_id, read_slot_bonus(pool, entity_id)):
        if slot.use_tag == use_tag and slot.slot_index == slot_index:
            return slot
    return None


@router.post("/api/consumable/sell", response_model=ConsumableResponse)
def create_consumable_sell(
    request: ConsumableSellRequest, account: CurrentAccount
) -> ConsumableResponse:
    """가방의 남는 소모품을 판다 (§5).

    보충이 돈으로만 되므로, 이미 끼운 종류가 또 나오면 팔아서 그 돈이 된다 — **드롭이
    곧 보충 비용이다.** 파는 값이 채우는 값보다 싸므로 끼우는 편이 언제나 낫다.

    Args:
        request: 팔 소모품과 개수.
        account: 토큰으로 푼 계정.

    Returns:
        갱신된 칸 화면.

    Raises:
        HTTPException: 소모품이 아니거나 가방에 그만큼 없는 경우.
    """
    entry = get_item_catalog().get(request.catalog_id)
    if entry is None or entry.kind is not ItemKind.CONSUMABLE:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "소모품이 아니다")
    count = max(1, request.count)
    pool = get_pool()
    entity_id = find_player_entity(pool, account.account_id)
    if count_stack(pool, entity_id, entry.catalog_id) < count:
        raise HTTPException(status.HTTP_409_CONFLICT, "가방에 그만큼 없다")
    if not apply_stack_take(pool, entity_id, entry.catalog_id, count):
        raise HTTPException(status.HTTP_409_CONFLICT, "가방에 그만큼 없다")
    add_currency(
        pool, account.account_id, resolve_sell_price(entry.grade, max(1, entry.charges)) * count
    )
    return read_consumables(account)
