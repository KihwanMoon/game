"""인벤토리·장비·지갑 라우트 (D단계).

**요구조건은 소재 능력치로만 판정한다** (docs/설계/4_아이템 §7). 장비 보너스를 섞으면
착용 순서가 결과를 바꾸고, 서버가 (계정, 아이템)만으로 재판정할 수 없게 된다.

**봉인은 응답을 만들 때 계산한다.** 저장하면 착용·해제 순서에 따라 갈린다 (§2.1).
"""

from fastapi import APIRouter, HTTPException, status

from game.api.deps import CurrentAccount, get_context, get_item_catalog, get_pool
from game.api.schemas import (
    EquipRequest,
    InventoryResponse,
    InventorySlotView,
    ItemActionRequest,
    ItemView,
    RequirementView,
    WalletResponse,
)
from game.app.items.catalog import find_item as find_catalog_item
from game.app.items.requirements import check_requirements
from game.app.items.stats import get_effective_slots
from game.app.store.accounts import find_player_entity
from game.app.store.equipment import (
    REPAIR_COST,
    add_currency,
    apply_equip,
    apply_repair,
    apply_unequip,
    read_balance,
    remove_item,
)
from game.app.store.items import StoredItem, find_item, list_equipment, list_inventory
from game.schemas.item import EquipSlot, ItemKind

router = APIRouter()

# 요구조건 판정에 쓰는 소재 능력치. #51(힘·민첩·지능 변환표)이 정해지기 전이라
# 지금은 코어에 실제로 있는 값만 본다 — 없는 축을 요구하면 언제나 미달로 읽힌다.
BASE_STAT_KEYS = ("attack", "defense", "hp_max", "cpu_budget")


def build_base_stats(context_balance: dict) -> dict[str, int]:
    """요구조건 판정의 기준이 되는 소재 능력치.

    **장비 보너스가 들어가지 않는다.** 들어가면 착용 순서가 결과를 바꾼다 (§7).

    Args:
        context_balance: balance.json 을 읽은 딕셔너리.

    Returns:
        능력치 이름에서 값으로의 대응표.
    """
    player = context_balance["player"]
    return {key: int(player[key]) for key in BASE_STAT_KEYS if key in player}


def build_item_view(
    stored: StoredItem, catalog: dict, base_stats: dict[str, int], slot: str | None = None
) -> ItemView:
    """아이템 하나를 응답 절로 만든다.

    요구조건은 **실측값을 함께** 낸다. "장착할 수 없습니다" 만 띄우면 무엇이 얼마나
    모자란지 알 수 없어 P1 위반이다 (§6.1).

    Args:
        stored: 보관된 아이템.
        catalog: 아이템 카탈로그.
        base_stats: 소재 능력치.
        slot: 착용 중인 슬롯. 인벤토리에 있으면 None.

    Returns:
        응답 절.
    """
    entry = find_catalog_item(catalog, stored.catalog_id)
    checks = check_requirements(entry, base_stats)
    return ItemView(
        item_id=stored.item_id,
        catalog_id=stored.catalog_id,
        label_ko=entry.label_ko,
        kind=str(entry.kind),
        slot=str(entry.slot) if entry.slot else None,
        hands=str(entry.hands) if entry.hands else None,
        equipped_slot=slot,
        is_broken=stored.is_broken,
        is_bound=stored.is_bound,
        affixes=[
            {"stat": a.stat, "flat": a.flat, "percent": a.percent, "label_ko": a.label_ko}
            for a in stored.affixes
        ],
        requirements=[
            RequirementView(stat=c.stat, actual=c.actual, minimum=c.minimum, is_met=c.is_met)
            for c in checks
        ],
        can_equip=all(c.is_met for c in checks) and not stored.is_broken,
    )


@router.get("/api/inventory", response_model=InventoryResponse)
def read_inventory(account: CurrentAccount) -> InventoryResponse:
    """인벤토리·장비·지갑을 함께 읽는다.

    Args:
        account: 토큰으로 푼 계정.

    Returns:
        칸 번호 순 인벤토리와 슬롯 순 장비. 봉인된 슬롯은 `is_sealed` 가 참이다.
    """
    pool = get_pool()
    entity_id = find_player_entity(pool, account.account_id)
    catalog = get_item_catalog()
    base_stats = build_base_stats(get_context().balance)

    equipped = list_equipment(pool, entity_id)
    entries = {slot: find_catalog_item(catalog, item.catalog_id) for slot, item in equipped.items()}
    sealed = {slot: entry is None for slot, entry in get_effective_slots(entries)}

    return InventoryResponse(
        size=len(list_inventory(pool, entity_id)),
        slots=[
            InventorySlotView(
                slot_index=entry.slot_index,
                item=None
                if entry.item is None
                else build_item_view(entry.item, catalog, base_stats),
                stack_catalog_id=entry.stack_catalog_id,
                stack_count=entry.stack_count,
            )
            for entry in list_inventory(pool, entity_id)
        ],
        equipment=[
            InventorySlotView(
                slot_index=index,
                item=build_item_view(item, catalog, base_stats, slot=str(slot)),
                stack_catalog_id=None,
                stack_count=0,
                slot=str(slot),
                is_sealed=sealed.get(slot, False) and slot in equipped,
            )
            for index, (slot, item) in enumerate(sorted(equipped.items(), key=lambda p: str(p[0])))
        ],
        balance=read_balance(pool, account.account_id),
        repair_cost=REPAIR_COST,
    )


@router.post("/api/equip", response_model=InventoryResponse)
def create_equip(request: EquipRequest, account: CurrentAccount) -> InventoryResponse:
    """아이템을 착용한다.

    Args:
        request: 아이템 id 와 슬롯.
        account: 토큰으로 푼 계정.

    Returns:
        갱신된 인벤토리.

    Raises:
        HTTPException: 남의 아이템이거나, 그 슬롯에 못 들어가거나, 요구조건을 못 채운 경우.
    """
    pool = get_pool()
    entity_id = find_player_entity(pool, account.account_id)
    stored = find_item(pool, entity_id, request.item_id)
    if stored is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "가진 아이템이 아니다")
    catalog = get_item_catalog()
    entry = find_catalog_item(catalog, stored.catalog_id)
    if entry.kind is not ItemKind.EQUIPMENT or entry.slot is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "장비가 아니다")
    slot = EquipSlot(request.slot)
    if entry.slot is not slot:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{entry.label_ko} 는 그 자리가 아니다")
    if stored.is_broken:
        raise HTTPException(status.HTTP_409_CONFLICT, "파손된 장비다 — 먼저 복구한다")

    base_stats = build_base_stats(get_context().balance)
    unmet = [c for c in check_requirements(entry, base_stats) if not c.is_met]
    if unmet:
        first = unmet[0]
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{first.stat}({first.actual}) >= 요구({first.minimum}) 거짓",
        )
    apply_equip(pool, entity_id, request.item_id, slot)
    return read_inventory(account)


@router.post("/api/unequip", response_model=InventoryResponse)
def create_unequip(request: EquipRequest, account: CurrentAccount) -> InventoryResponse:
    """장비를 벗는다.

    Args:
        request: 슬롯. 아이템 id 는 보지 않는다.
        account: 토큰으로 푼 계정.

    Returns:
        갱신된 인벤토리.

    Raises:
        HTTPException: 인벤토리가 가득 차 받을 칸이 없는 경우.
    """
    try:
        apply_unequip(
            get_pool(), find_player_entity(get_pool(), account.account_id), EquipSlot(request.slot)
        )
    except ValueError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    return read_inventory(account)


@router.post("/api/item/discard", response_model=InventoryResponse)
def create_discard(request: ItemActionRequest, account: CurrentAccount) -> InventoryResponse:
    """아이템을 버린다.

    Args:
        request: 아이템 id.
        account: 토큰으로 푼 계정.

    Returns:
        갱신된 인벤토리.

    Raises:
        HTTPException: 가진 아이템이 아닌 경우.
    """
    if not remove_item(
        get_pool(), find_player_entity(get_pool(), account.account_id), request.item_id
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "가진 아이템이 아니다")
    return read_inventory(account)


@router.post("/api/item/repair", response_model=WalletResponse)
def create_repair(request: ItemActionRequest, account: CurrentAccount) -> WalletResponse:
    """복구비용을 내고 파손을 푼다 (결정 #34).

    Args:
        request: 아이템 id.
        account: 토큰으로 푼 계정.

    Returns:
        복구 뒤 잔액.

    Raises:
        HTTPException: 가진 아이템이 아니거나 잔액이 모자란 경우.
    """
    pool = get_pool()
    entity_id = find_player_entity(pool, account.account_id)
    if find_item(pool, entity_id, request.item_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "가진 아이템이 아니다")
    try:
        balance = apply_repair(pool, account.account_id, entity_id, request.item_id)
    except ValueError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    return WalletResponse(balance=balance, repair_cost=REPAIR_COST)


@router.get("/api/wallet", response_model=WalletResponse)
def read_wallet(account: CurrentAccount) -> WalletResponse:
    """지갑 잔액을 본다.

    Args:
        account: 토큰으로 푼 계정.

    Returns:
        잔액과 복구비용.
    """
    return WalletResponse(
        balance=read_balance(get_pool(), account.account_id), repair_cost=REPAIR_COST
    )


def add_run_currency(account_id: int, amount: int) -> None:
    """런 보상 화폐를 넣는다. 런 라우트가 부른다.

    Args:
        account_id: 받을 계정.
        amount: 넣을 양.
    """
    add_currency(get_pool(), account_id, amount)
