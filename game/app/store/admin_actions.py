"""관리자 개입 — 세계 상태를 직접 고치는 것들.

**여기 있는 것은 전부 되돌릴 수 없다.** 그래서 세 가지를 지킨다.

1. **사유를 받는다.** 무엇을 했는지만 남으면 "왜 그랬지" 를 나중에 아무도 답할 수 없다.
2. **원장에 남긴다.** 부르는 쪽이 `record_admin_action` 을 함께 부른다.
3. **경제를 흔드는 것은 만들지 않았다.** 아이템 *발급* 은 여기 없다 — 서버가 검증된 런의
   결과로만 아이템을 만든다는 결정 #02 가 관리자 경로 하나로 뚫리면, 그 뒤로는 어떤
   아이템도 "정상적으로 나온 것" 이라고 말할 수 없다. 잘못 나간 것을 **회수**하는 것만
   둔다 — 그쪽은 발급 경로를 늘리지 않는다.
"""

from dataclasses import dataclass

from psycopg_pool import ConnectionPool

# 회수한 아이템이 가는 곳. 지우지 않는 이유는 원장이 그 id 를 가리키기 때문이다 —
# 지우면 "이 아이템이 어디로 갔나" 를 추적할 수 없다.
RECALL_STATE = "recalled"


@dataclass(frozen=True)
class RecallOutcome:
    """회수 결과."""

    item_id: int
    catalog_id: str
    owner_entity_id: int


def apply_listing_cancel(pool: ConnectionPool, listing_id: int) -> str:
    """열린 매물을 강제로 내린다 — 아이템은 판 사람에게 돌아간다.

    수수료는 돌려주지 않는다 — 일반 취소와 같다. 관리자가 내렸다고 수수료를 되돌리면
    "관리자에게 부탁하면 수수료가 없다" 가 되고, 그 순간 유일한 화폐 배출구가 샌다.

    Args:
        pool: 연결 풀.
        listing_id: 내릴 매물.

    Returns:
        무슨 일이 있었는지 적은 한 줄. 내릴 수 없으면 빈 문자열.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT item_id, seller_id, price FROM auction_listing"
            " WHERE id = %s AND state = 'OPEN'",
            (listing_id,),
        ).fetchone()
        if row is None:
            return ""
        item_id, seller_id, price = int(row[0]), int(row[1]), int(row[2])
        connection.execute(
            "UPDATE auction_listing SET state = 'CANCELLED', settled_at = now() WHERE id = %s",
            (listing_id,),
        )
        # 판 사람의 개체로 돌려준다. 칸이 없으면 인벤토리 밖에 남는데, 그것이 사라지는
        # 것보다 낫다 — 화면에는 안 보여도 원장이 가리키는 아이템은 존재해야 한다.
        connection.execute(
            "INSERT INTO inventory_slot (entity_id, slot_index, item_id)"
            " SELECT e.id, coalesce(max(s.slot_index) + 1, 0), %s"
            " FROM entity_record e LEFT JOIN inventory_slot s ON s.entity_id = e.id"
            " WHERE e.owner_account_id = %s GROUP BY e.id"
            " ON CONFLICT DO NOTHING",
            (item_id, seller_id),
        )
    return f"매물 #{listing_id} · 아이템 #{item_id} · 호가 {price}"


def apply_item_recall(pool: ConnectionPool, item_id: int) -> RecallOutcome | None:
    """아이템 하나를 세계에서 거둔다.

    **지우지 않는다.** 원장이 이 id 를 가리키므로, 지우면 "이 아이템이 어디로 갔나" 를
    추적할 수 없다. 소유·장착·매물에서만 떼어 낸다.

    Args:
        pool: 연결 풀.
        item_id: 거둘 아이템.

    Returns:
        회수 결과. 없는 아이템이면 None.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT catalog_id, owner_entity_id FROM item_instance WHERE id = %s", (item_id,)
        ).fetchone()
        if row is None:
            return None
        connection.execute("DELETE FROM inventory_slot WHERE item_id = %s", (item_id,))
        connection.execute("DELETE FROM equipment_slot WHERE item_id = %s", (item_id,))
        connection.execute(
            "UPDATE auction_listing SET state = 'CANCELLED', settled_at = now()"
            " WHERE item_id = %s AND state = 'OPEN'",
            (item_id,),
        )
        # 소유는 남긴다. 원장이 가리키는 것이 사라지면 조사가 끊긴다.
        connection.execute("UPDATE item_instance SET is_broken = true WHERE id = %s", (item_id,))
    return RecallOutcome(item_id=item_id, catalog_id=str(row[0]), owner_entity_id=int(row[1]))
