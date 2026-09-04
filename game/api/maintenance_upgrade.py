"""정비 규칙의 「더 좋게 만든다」 세 가지 (설계/4_아이템 §5).

`maintenance_service` 에서 갈라 나왔다. 저쪽 넷은 **덜어 내는 일**(버리기·팔기)과 **되돌리는
일**(복구·보충)이라 판단이 없다 — 파손이면 고치고, 빈 충전이면 채운다. 여기 셋은 **무엇이
더 좋은지를 골라야** 하고, 그 판단이 곧 이 파일의 내용이다.

**기준을 새로 지어내지 않는다.** 장비 교체는 봇이 쓰는 저울(`bots/upgrade`)을 그대로
쓴다. 두 벌로 두면 같은 장비가 봇 화면과 정비 미리보기에서 다른 값을 갖고, 그때 어느
쪽이 맞는지 물으면 답할 사람이 없다. 다른 것은 **저울을 고르는 방식**뿐이다 — 봇은
규칙표가 성격을 정하고, 사람은 정비 행의 인자로 공격이냐 방어냐를 고른다.
"""

from psycopg_pool import ConnectionPool

from game.api.deps import get_item_catalog
from game.api.loadout_service import build_equipped_entries, count_slot_bonus
from game.app.bots.upgrade import GEAR_PRIORITY_WEIGHTS, GearItem, find_upgrades_by_weights
from game.app.items.sealed import compute_unseal_cost, create_sealed_affix
from game.app.store.consumables import apply_slot_clear, apply_slot_load, list_consumable_slots
from game.app.store.equipment import add_currency, apply_equip, read_balance
from game.app.store.inventory_slots import apply_stack_grant, apply_stack_take
from game.app.store.items import (
    StoredItem,
    apply_unseal,
    list_affix_pool,
    list_equipment,
    list_inventory,
    record_item_event,
)
from game.schemas.item import (
    GRADE_SEALED_SLOTS,
    EquipSlot,
    ItemCatalogEntry,
    ItemKind,
)

EVENT_UNSEAL = "unseal"


def build_gear_item(stored: StoredItem, entry: ItemCatalogEntry) -> GearItem:
    """보관된 아이템을 저울이 읽는 절로 바꾼다.

    **둘을 합쳐야 한다.** 인스턴스(`StoredItem`)는 굴린 접사와 파손 여부를 갖고, 자리·손
    수·사거리는 **카탈로그**가 갖는다 — 인스턴스만 보면 양손무기를 못 알아보고, 그러면
    양손 자리를 건너뛰는 규칙이 조용히 안 걸린다.

    Args:
        stored: 보관된 아이템.
        entry: 그 아이템의 카탈로그 항목.

    Returns:
        점수를 매길 수 있는 절.
    """
    return GearItem(
        item_id=stored.item_id,
        slot=entry.slot.value if entry.slot is not None else "",
        can_equip=True,
        is_broken=stored.is_broken,
        hands=entry.hands.value if entry.hands is not None else "",
        affixes=tuple((one.stat, one.flat, one.percent) for one in stored.affixes),
        attack_range=entry.attack_range or 0,
    )


def apply_upgrade_gear_rule(
    pool: ConnectionPool, entity_id: int, priority: str, base_stats: dict[str, int]
) -> int:
    """가방에 더 나은 것이 있으면 갈아 낀다.

    **봇과 같은 저울, 같은 여유폭이다** (`UPGRADE_MARGIN`). 근소한 차이로 바꾸지 않는
    이유도 같다 — 벗은 것은 가방으로 가고, 가방에 있는 것은 죽을 때 삭제된다(결정 #34).
    1점 이득을 보려고 바꾸면 그 1점보다 큰 것을 잃을 수 있다.

    **양손 자리는 안 건드린다.** 양손무기가 보조 칸을 봉인하므로 두 칸을 동시에 보는
    판단이고, 한 칸씩 보는 이 규칙으로는 틀린다 (`bots/upgrade`).

    Args:
        pool: 연결 풀.
        entity_id: 대상 개체.
        priority: 우선순위. 어휘 밖이면 아무것도 안 한다.
        base_stats: 퍼센트를 값으로 바꾸는 기준.

    Returns:
        갈아 낀 개수.
    """
    weights = GEAR_PRIORITY_WEIGHTS.get(priority)
    if weights is None:
        return 0
    catalog = get_item_catalog()

    def build(stored: StoredItem) -> GearItem | None:
        """카탈로그와 합쳐 저울이 읽을 절로. 카탈로그에 없으면 건너뛴다."""
        entry = catalog.get(stored.catalog_id)
        if entry is None or entry.slot is None:
            return None
        return build_gear_item(stored, entry)

    bag = tuple(
        item
        for item in (
            build(entry.item) for entry in list_inventory(pool, entity_id) if entry.item is not None
        )
        if item is not None
    )
    worn = tuple(
        item
        for item in (
            build(stored)
            for _slot, stored in sorted(
                list_equipment(pool, entity_id).items(), key=lambda p: str(p[0])
            )
        )
        if item is not None
    )
    swapped = 0
    for _current, candidate in find_upgrades_by_weights(bag, worn, weights, base_stats):
        # **벗기지 않고 그냥 낀다.** `apply_equip` 이 그 자리에 있던 것을 가방으로
        # 돌려보낸다 — 먼저 벗기면 그 사이에 자리가 비는 창이 생긴다.
        apply_equip(pool, entity_id, candidate.item_id, EquipSlot(candidate.slot))
        swapped += 1
    return swapped


def count_opened_slots(item: StoredItem) -> int:
    """이미 연 봉인 칸 수. 등급이 준 칸에서 남은 칸을 뺀다.

    인스턴스가 등급을 복사해 갖고 있으므로 카탈로그를 안 봐도 된다 — 카탈로그를 고쳐도
    이 값이 안 흔들리는 이유다 (§15.5).

    Args:
        item: 보관된 아이템.

    Returns:
        연 칸 수.
    """
    total = GRADE_SEALED_SLOTS.get(item.grade, 0)
    return max(0, total - item.sealed_slots)


def find_cheapest_sealed(pool: ConnectionPool, entity_id: int) -> tuple[int, StoredItem] | None:
    """봉인이 남은 것 중 여는 값이 가장 싼 것.

    **착용과 가방을 함께 본다.** 처음에는 착용한 것만 봤다 — 안 쓰는 물건에 돈을 쓰지
    않게 하려는 것이었는데, 그러면 **가방에서 굴러 나온 유물이 영원히 안 열린다.** 열어
    봐야 그것이 갈아 낄 만한 물건인지 알 수 있고, 장비 교체 규칙이 그 다음을 잇는다.

    **싼 것부터 여는 이유**는 값이 이미 연 칸 수에 따라 오르기 때문이다 — 같은 잔액으로
    더 많이 열 수 있다.

    **순서를 못 박는다.** 착용을 자리 이름 순으로, 그다음 가방을 id 순으로 본다. 값이
    같을 때 어느 것을 먼저 열지가 흔들리면 같은 가방이 돌 때마다 다른 결과를 낸다 (R5).

    Args:
        pool: 연결 풀.
        entity_id: 대상 개체.

    Returns:
        (값, 아이템). 열 것이 없으면 None.
    """
    candidates: list[tuple[int, int, str, StoredItem]] = [
        (compute_unseal_cost(count_opened_slots(item)), 0, str(slot), item)
        for slot, item in sorted(list_equipment(pool, entity_id).items(), key=lambda p: str(p[0]))
        if item.sealed_slots > 0
    ]
    candidates.extend(
        (
            compute_unseal_cost(count_opened_slots(entry.item)),
            1,
            str(entry.item.item_id),
            entry.item,
        )
        for entry in list_inventory(pool, entity_id)
        if entry.item is not None and entry.item.sealed_slots > 0
    )
    if not candidates:
        return None
    cost, _kind, _key, item = min(candidates, key=lambda one: (one[0], one[1], one[2]))
    return cost, item


def apply_unseal_rule(pool: ConnectionPool, account_id: int, entity_id: int) -> tuple[int, int]:
    """가진 장비의 봉인을 잔액 안에서 연다 — 착용과 가방을 함께 본다.

    **가방 것도 연다.** 처음에는 착용한 것만 열었는데, 그러면 가방에서 굴러 나온 유물이
    영원히 안 열린다 — 열어 봐야 갈아 낄 만한 물건인지 알 수 있다. 정비 행을 「봉인 해제
    → 장비 교체」 순으로 두면 그 둘이 이어진다.

    **돈을 먼저 뺀다.** 굴린 뒤에 빼면 굴림은 성공하고 차감이 실패하는 창이 생기고, 그
    창이 공짜 해제가 된다 (`routes/unseal` 과 같은 규율).

    Args:
        pool: 연결 풀.
        account_id: 비용을 낼 계정.
        entity_id: 대상 개체.

    Returns:
        (연 칸 수, 낸 값).
    """
    opened = 0
    paid = 0
    while True:
        # 열 때마다 다시 읽는다 — 방금 연 것의 다음 칸 값이 올랐다.
        found = find_cheapest_sealed(pool, entity_id)
        if found is None:
            break
        cost, item = found
        if read_balance(pool, account_id) < cost:
            break
        add_currency(pool, account_id, -cost)
        try:
            affix = create_sealed_affix(list_affix_pool(pool))
        except ValueError:
            # 접사 표가 비었다. 낸 값을 돌려주고 멈춘다 — 조용히 먹으면 안 된다.
            add_currency(pool, account_id, cost)
            break
        if not apply_unseal(pool, item.item_id, affix):
            add_currency(pool, account_id, cost)
            break
        record_item_event(pool, entity_id, item.item_id, EVENT_UNSEAL, affix.label_ko)
        opened += 1
        paid += cost
    return opened, paid


def compute_consumable_score(entry: ItemCatalogEntry) -> tuple[int, int]:
    """소모품 하나가 얼마나 값하는가.

    **충전 용량이 먼저다.** 등급이 정하는 것이 그것이고(§5), 「몇 번 쓸 수 있나」가
    소모품의 값 그 자체다. 같으면 붙는 접사의 크기로 끊는다 — 순서가 흔들리면 같은
    가방에서 볼 때마다 다른 것이 끼워진다 (R5).

    Args:
        entry: 카탈로그 항목.

    Returns:
        (충전 용량, 접사 크기 합). 클수록 좋다.
    """
    charges = max(1, entry.charges)
    bonus = sum(abs(affix.flat) + abs(affix.percent) for affix in entry.affixes)
    return charges, bonus


def find_better_stock(
    catalog: dict, stock: dict[str, int], use_tag: str, current: ItemCatalogEntry
) -> str:
    """이 칸에 낄 더 나은 재고를 찾는다.

    Args:
        catalog: 아이템 카탈로그.
        stock: 카탈로그 id 에서 남은 개수로.
        use_tag: 이 칸의 쓰임새.
        current: 지금 끼워진 것.

    Returns:
        더 나은 것의 카탈로그 id. 없으면 빈 문자열.
    """
    best_id = ""
    best_score = compute_consumable_score(current)
    # **정렬해서 본다.** 딕셔너리 순서로 돌면 같은 가방이 볼 때마다 다른 것을 고른다 (R5).
    for catalog_id in sorted(stock):
        if stock[catalog_id] <= 0:
            continue
        item = catalog.get(catalog_id)
        if item is None or item.kind is not ItemKind.CONSUMABLE or item.use_tag != use_tag:
            continue
        score = compute_consumable_score(item)
        if score > best_score:
            best_id, best_score = catalog_id, score
    return best_id


def count_bag_stock(pool: ConnectionPool, entity_id: int) -> dict[str, int]:
    """가방에 쌓인 소모품을 센다.

    Args:
        pool: 연결 풀.
        entity_id: 대상 개체.

    Returns:
        카탈로그 id 에서 개수로.
    """
    stock: dict[str, int] = {}
    for entry in list_inventory(pool, entity_id):
        if entry.stack_catalog_id and entry.stack_count > 0:
            stock[entry.stack_catalog_id] = stock.get(entry.stack_catalog_id, 0) + entry.stack_count
    return stock


def apply_upgrade_consumable_rule(pool: ConnectionPool, entity_id: int) -> int:
    """끼운 소모품보다 나은 재고가 있으면 갈아 낀다.

    **빈 칸은 안 건드린다.** 빈 칸을 채우는 것은 「끼우기」이지 「교체」가 아니고, 빈 칸은
    출격할 때 공짜 충전을 받으므로 채우는 것이 늘 이득이라고 말할 수 없다.

    **가득 찬 칸만 바꾼다.** 쓰던 칸을 갈아 끼우면 남은 충전이 사라지고, 그것은 사람이
    직접 누를 때만 감수할 일이다. 그래서 밀려난 것은 온전한 채로 가방에 돌아간다.

    Args:
        pool: 연결 풀.
        entity_id: 대상 개체.

    Returns:
        갈아 낀 칸 수.
    """
    catalog = get_item_catalog()
    bonus = count_slot_bonus(build_equipped_entries(pool, entity_id, catalog))
    stock = count_bag_stock(pool, entity_id)
    swapped = 0
    for slot in list_consumable_slots(pool, entity_id, bonus):
        current = catalog.get(slot.catalog_id) if slot.catalog_id else None
        if current is None or current.kind is not ItemKind.CONSUMABLE:
            continue
        if slot.charges < max(1, current.charges):
            continue
        best_id = find_better_stock(catalog, stock, slot.use_tag, current)
        if not best_id or not apply_stack_take(pool, entity_id, best_id, 1):
            continue
        apply_stack_grant(pool, entity_id, slot.catalog_id, 1)
        apply_slot_clear(pool, entity_id, slot.use_tag, slot.slot_index)
        apply_slot_load(
            pool,
            entity_id,
            slot.use_tag,
            slot.slot_index,
            best_id,
            max(1, catalog[best_id].charges),
        )
        stock[best_id] = stock.get(best_id, 0) - 1
        stock[slot.catalog_id] = stock.get(slot.catalog_id, 0) + 1
        swapped += 1
    return swapped
