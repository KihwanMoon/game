"""정비 규칙 실행 — 티켓이 닫힐 때 서버가 손본다 (설계/4_아이템 §5).

**행 순서가 실행 순서다.** 전투 규칙표와 같은 규약이라, 「버리고 나서 복구」와 「복구하고
나서 버리기」를 사람이 조립으로 가른다 — 곧 버릴 장비에 복구비를 쓸지는 이제 배치의
문제다.

무엇을 했는지 **한 줄로 돌려준다.** 조용한 자동화는 「왜 돈이 줄었지」가 된다 (P1).
"""

from psycopg_pool import ConnectionPool

from game.api.deps import get_item_catalog, get_pool
from game.api.loadout_service import build_equipped_entries, count_slot_bonus
from game.app.store.accounts import find_player_entity
from game.app.store.consumables import apply_slot_fill, list_consumable_slots
from game.app.store.equipment import add_currency, apply_repair, read_balance, remove_item
from game.app.store.inventory_slots import apply_stack_take
from game.app.store.items import list_equipment, list_inventory
from game.app.store.maintenance import (
    ACTION_DISCARD,
    ACTION_REFILL,
    ACTION_REPAIR,
    ACTION_SELL_STOCK,
    MaintenanceRow,
    read_maintenance,
)
from game.schemas.consumable import resolve_refill_cost, resolve_sell_price
from game.schemas.item import ItemKind


def apply_discard_rule(pool: ConnectionPool, entity_id: int, grade: str) -> int:
    """이 등급의 가방 장비를 버린다.

    **가방만 본다.** 낀 것을 버리면 스탯이 유령이 되고, 소모품 스택은 장비가 아니다.
    되찾은 것(`is_recovered`)은 남긴다 — 몬스터에게서 도로 빼앗아 온 물건을 자동으로
    버리면, 되찾기의 뜻이 사라진다.

    Args:
        pool: 연결 풀.
        entity_id: 대상 개체.
        grade: 버릴 등급.

    Returns:
        버린 개수.
    """
    dropped = 0
    for entry in list_inventory(pool, entity_id):
        item = entry.item
        if item is None or item.grade != grade or item.is_recovered:
            continue
        if remove_item(pool, entity_id, item.item_id):
            dropped += 1
    return dropped


def apply_repair_rule(pool: ConnectionPool, account_id: int, entity_id: int) -> int:
    """파손된 착용 장비를 잔액 안에서 복구한다.

    Args:
        pool: 연결 풀.
        account_id: 비용을 낼 계정.
        entity_id: 대상 개체.

    Returns:
        복구한 개수. 잔액이 마르면 거기서 멈춘다.
    """
    fixed = 0
    for _slot, item in sorted(list_equipment(pool, entity_id).items(), key=lambda p: str(p[0])):
        if not item.is_broken:
            continue
        try:
            apply_repair(pool, account_id, entity_id, item.item_id)
        except ValueError:
            # 잔액이 마른 것이다. 남은 파손은 다음 정비의 몫이다.
            break
        fixed += 1
    return fixed


def apply_refill_rule(pool: ConnectionPool, account_id: int, entity_id: int) -> tuple[int, int]:
    """끼운 소모품을 잔액 안에서 가득 채운다.

    **소모품 칸의 보충과 같은 값이다** (`routes/consumables`). 정비라고 싸지면 수동
    보충을 누를 이유가 없어진다.

    Args:
        pool: 연결 풀.
        account_id: 비용을 낼 계정.
        entity_id: 대상 개체.

    Returns:
        (채운 충전 수, 낸 값).
    """
    catalog = get_item_catalog()
    bonus = count_slot_bonus(build_equipped_entries(pool, entity_id, catalog))
    filled = 0
    paid = 0
    for slot in list_consumable_slots(pool, entity_id, bonus):
        entry = catalog.get(slot.catalog_id) if slot.catalog_id else None
        if entry is None or entry.kind is not ItemKind.CONSUMABLE:
            continue
        charge_max = max(1, entry.charges)
        missing = charge_max - slot.charges
        cost = resolve_refill_cost(entry.grade, missing)
        if missing <= 0 or cost <= 0:
            continue
        if read_balance(pool, account_id) < cost:
            # 잔액이 마른 것이다. 반쯤 채우지 않는다 — 반쯤은 「채워졌다」로 읽힌다.
            continue
        add_currency(pool, account_id, -cost)
        apply_slot_fill(pool, entity_id, slot.use_tag, slot.slot_index, charge_max)
        filled += missing
        paid += cost
    return filled, paid


def apply_sell_rule(pool: ConnectionPool, account_id: int, entity_id: int) -> tuple[int, int]:
    """가방의 소모품 재고를 전부 판다.

    끼운 칸은 안 건드린다 — 파는 것은 **남는** 재고다. 값은 수동 팔기와 같다.

    Args:
        pool: 연결 풀.
        account_id: 값을 받을 계정.
        entity_id: 대상 개체.

    Returns:
        (판 개수, 받은 값).
    """
    catalog = get_item_catalog()
    sold = 0
    earned = 0
    for entry in list_inventory(pool, entity_id):
        if entry.stack_catalog_id is None or entry.stack_count <= 0:
            continue
        item = catalog.get(entry.stack_catalog_id)
        if item is None or item.kind is not ItemKind.CONSUMABLE:
            continue
        count = entry.stack_count
        if not apply_stack_take(pool, entity_id, entry.stack_catalog_id, count):
            continue
        price = resolve_sell_price(item.grade, max(1, item.charges)) * count
        add_currency(pool, account_id, price)
        sold += count
        earned += price
    return sold, earned


def apply_row(pool: ConnectionPool, account_id: int, entity_id: int, row: MaintenanceRow) -> str:
    """정비 행 하나를 실행한다.

    Args:
        pool: 연결 풀.
        account_id: 대상 계정.
        entity_id: 대상 개체.
        row: 실행할 행.

    Returns:
        무슨 일이 있었는지. 한 일이 없으면 빈 문자열.
    """
    if row.action == ACTION_DISCARD:
        dropped = apply_discard_rule(pool, entity_id, row.grade)
        return f"{row.grade} 장비 {dropped}개 버림" if dropped else ""
    if row.action == ACTION_REPAIR:
        fixed = apply_repair_rule(pool, account_id, entity_id)
        return f"파손 {fixed}개 복구" if fixed else ""
    if row.action == ACTION_REFILL:
        filled, paid = apply_refill_rule(pool, account_id, entity_id)
        return f"충전 {filled}개 보충 (-{paid})" if filled else ""
    if row.action == ACTION_SELL_STOCK:
        sold, earned = apply_sell_rule(pool, account_id, entity_id)
        return f"재고 {sold}개 판매 (+{earned})" if sold else ""
    return ""


def apply_maintenance(account_id: int) -> str:
    """이 계정의 정비 행들을 순서대로 실행한다.

    **티켓이 닫힐 때만 부른다.** 층 청구마다 돌면 런 중에 가방이 바뀐다 — 죽기 전에
    주운 것이 층 정산 한 번에 사라질 수 있다.

    Args:
        account_id: 대상 계정.

    Returns:
        무엇을 했는지 한 줄. 한 일이 없으면 빈 문자열.
    """
    pool = get_pool()
    rows = read_maintenance(pool, account_id)
    if not rows:
        return ""
    entity_id = find_player_entity(pool, account_id)
    notes = [note for row in rows if (note := apply_row(pool, account_id, entity_id, row))]
    return f"정비: {' · '.join(notes)}" if notes else ""
