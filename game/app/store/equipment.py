"""착용·해제·버리기와 지갑 (docs/설계/4_아이템 §5·§7, 결정 #34).

착용 판정은 `app/items/requirements.py` 가 한다 — **소재 능력치만 본다.** 여기서
장비 보너스를 섞으면 착용 순서가 결과를 바꾸고, 그러면 서버가 (계정, 아이템)만으로
재판정할 수 없게 된다.

파손과 복구가 여기 있는 이유는 결정 #34 다. 사망 시 뽑힌 장비가 장착 중이었으면
사라지지 않고 파손되며, 복구비용을 내야 다시 쓴다. 가방에 있었으면 삭제된다 —
"좋은 건 끼고 다녀라" 는 유인이 그 차이에서 나온다.
"""

from psycopg_pool import ConnectionPool

from game.app.store.items import (
    EVENT_BREAK,
    EVENT_DISCARD,
    EVENT_EQUIP,
    EVENT_REPAIR,
    EVENT_UNEQUIP,
    find_empty_slot,
    record_item_event,
)
from game.schemas.item import EquipSlot

# 복구비용. 지금은 고정값이며 곡선은 미결이다 (결정 대기 #52) — 너무 싸면 사망이
# 무의미하고, 비싸면 장비를 안 낀다.
REPAIR_COST = 120


def read_balance(pool: ConnectionPool, account_id: int) -> int:
    """지갑 잔액을 읽는다. 없으면 0 이다.

    **계정 단위다.** 화폐는 사람의 것이지 개체의 것이 아니다 — 개체 단위로 두면
    몬스터가 지갑을 갖는 셈이 되고, 거래가 붙을 때 누구의 돈인지가 흐려진다.

    Args:
        pool: 연결 풀.
        account_id: 계정 id.

    Returns:
        잔액.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT balance FROM wallet WHERE account_id = %s", (account_id,)
        ).fetchone()
    return int(row[0]) if row is not None else 0


def add_currency(pool: ConnectionPool, account_id: int, amount: int) -> int:
    """화폐를 더한다. **계정 단위다** (read_balance 참조).

    Args:
        pool: 연결 풀.
        account_id: 계정 id.
        amount: 더할 양. 음수면 뺀다.

    Returns:
        바뀐 뒤의 잔액.

    Raises:
        ValueError: 잔액이 모자란 경우. 음수 잔액을 만드는 것보다 거절이 낫다.
    """
    with pool.connection() as connection:
        # 행을 먼저 만든다. INSERT 와 조건부 UPDATE 를 한 문장으로 합치면, 행이 없을 때
        # INSERT 경로가 조건을 건너뛴다 — 첫 복구가 잔액 없이 성공하는 버그가 그것이었다.
        connection.execute(
            "INSERT INTO wallet (account_id, balance) VALUES (%s, 0) ON CONFLICT DO NOTHING",
            (account_id,),
        )
        row = connection.execute(
            "UPDATE wallet SET balance = balance + %s, updated_at = now()"
            " WHERE account_id = %s AND balance + %s >= 0"
            " RETURNING balance",
            (amount, account_id, amount),
        ).fetchone()
    if row is None:
        raise ValueError("잔액이 모자란다")
    return int(row[0])


def apply_equip(pool: ConnectionPool, entity_id: int, item_id: int, slot: EquipSlot) -> None:
    """아이템을 슬롯에 착용한다. 그 자리에 있던 것은 인벤토리로 돌아간다.

    Args:
        pool: 연결 풀.
        entity_id: 개체 id (entity_record).
        item_id: 착용할 아이템.
        slot: 대상 슬롯.

    Raises:
        ValueError: 이미 찬 자리를 비울 인벤토리 칸이 없는 경우.
    """
    with pool.connection() as connection:
        existing = connection.execute(
            "SELECT item_id FROM equipment_slot WHERE entity_id = %s AND slot = %s",
            (entity_id, str(slot)),
        ).fetchone()
    if existing is not None:
        apply_unequip(pool, entity_id, slot)
    with pool.connection() as connection:
        # 인벤토리에서 빼고 슬롯에 넣는다. 한 트랜잭션이라 둘 중 하나만 되는 일이 없다.
        connection.execute(
            "DELETE FROM inventory_slot WHERE entity_id = %s AND item_id = %s",
            (entity_id, item_id),
        )
        connection.execute(
            "INSERT INTO equipment_slot (entity_id, slot, item_id) VALUES (%s, %s, %s)",
            (entity_id, str(slot), item_id),
        )
    record_item_event(pool, entity_id, item_id, EVENT_EQUIP, str(slot))


def apply_unequip(pool: ConnectionPool, entity_id: int, slot: EquipSlot) -> int | None:
    """슬롯을 비우고 인벤토리로 돌려보낸다.

    Args:
        pool: 연결 풀.
        entity_id: 개체 id (entity_record).
        slot: 비울 슬롯.

    Returns:
        돌아온 아이템 id. 빈 슬롯이면 None.

    Raises:
        ValueError: 인벤토리가 가득 차서 받을 칸이 없는 경우. 아이템을 없애는 것보다
            해제를 거절하는 편이 낫다.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT item_id FROM equipment_slot WHERE entity_id = %s AND slot = %s",
            (entity_id, str(slot)),
        ).fetchone()
    if row is None:
        return None
    item_id = int(row[0])
    index = find_empty_slot(pool, entity_id)
    if index is None:
        raise ValueError("인벤토리가 가득 차 해제할 수 없다")
    with pool.connection() as connection:
        connection.execute(
            "DELETE FROM equipment_slot WHERE entity_id = %s AND slot = %s",
            (entity_id, str(slot)),
        )
        connection.execute(
            "INSERT INTO inventory_slot (entity_id, slot_index, item_id) VALUES (%s, %s, %s)",
            (entity_id, index, item_id),
        )
    record_item_event(pool, entity_id, item_id, EVENT_UNEQUIP, str(slot))
    return item_id


def remove_item(pool: ConnectionPool, entity_id: int, item_id: int) -> bool:
    """아이템을 버린다. 착용 중이면 슬롯도 비워진다.

    Args:
        pool: 연결 풀.
        entity_id: 개체 id (entity_record).
        item_id: 버릴 아이템.

    Returns:
        실제로 지웠으면 True.
    """
    with pool.connection() as connection:
        cursor = connection.execute(
            "DELETE FROM item_instance WHERE id = %s AND owner_entity_id = %s",
            (item_id, entity_id),
        )
        removed = cursor.rowcount == 1
    if removed:
        record_item_event(pool, entity_id, None, EVENT_DISCARD, str(item_id))
    return removed


def mark_item_broken(pool: ConnectionPool, entity_id: int, item_id: int) -> None:
    """장비를 파손 상태로 만든다 (결정 #34).

    Args:
        pool: 연결 풀.
        entity_id: 개체 id (entity_record).
        item_id: 파손할 아이템.
    """
    with pool.connection() as connection:
        connection.execute(
            "UPDATE item_instance SET is_broken = true WHERE id = %s AND owner_entity_id = %s",
            (item_id, entity_id),
        )
    record_item_event(pool, entity_id, item_id, EVENT_BREAK)


def apply_repair(pool: ConnectionPool, account_id: int, entity_id: int, item_id: int) -> int:
    """복구비용을 내고 파손을 푼다.

    돈은 **계정**에서 나가고 아이템은 **개체**의 것이다 — 둘 다 받는 이유가 그것이다.

    Args:
        pool: 연결 풀.
        account_id: 비용을 낼 계정.
        entity_id: 아이템을 가진 개체.
        item_id: 복구할 아이템.

    Returns:
        복구 뒤의 잔액.

    Raises:
        ValueError: 잔액이 모자란 경우.
    """
    balance = add_currency(pool, account_id, -REPAIR_COST)
    with pool.connection() as connection:
        connection.execute(
            "UPDATE item_instance SET is_broken = false WHERE id = %s AND owner_entity_id = %s",
            (item_id, entity_id),
        )
    record_item_event(pool, entity_id, item_id, EVENT_REPAIR, str(REPAIR_COST))
    return balance
