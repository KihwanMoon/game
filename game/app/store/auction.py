"""경매장 (결정 #20, docs/설계/3_저장과_멀티플레이 §6).

거래는 **재현으로 풀리지 않는 유일한 축**이다. 아이템의 진위는 서버 발급이라는 사실이
보증하지만 소유권은 계산할 수 없다 — 원장이 정한다.

경제 설계에서 이 모듈이 지는 셋.

* **수수료가 화폐를 태운다.** 등록할 때 떼며, 지금 이 게임에서 유일한 배출구다.
  없으면 화폐가 단조 증가해 몇 주 만에 가격이 무의미해진다.
* **만료가 시세를 흐르게 한다.** 안 팔린 물건이 영원히 걸려 있으면 호가가 굳는다.
* **원장이 자전거래 흔적을 남긴다.** 판 사람과 산 사람이 남으므로 계정 간 이전을 셀 수
  있다 — 막지는 못하지만 보이게 한다.

**등록하면 아이템이 소유자에게서 떠난다.** 걸어 두고 그대로 쓸 수 있으면 하나를 여러 번
팔 수 있다.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from psycopg_pool import ConnectionPool

from game.app.store.equipment import add_currency
from game.app.store.items import EVENT_DISCARD, find_empty_slot, record_item_event

STATE_OPEN = "OPEN"
STATE_SOLD = "SOLD"
STATE_CANCELLED = "CANCELLED"
STATE_EXPIRED = "EXPIRED"

# 등록 수수료 (정수 퍼센트). **화폐의 유일한 배출구다** — 없으면 화폐가 단조 증가해
# 몇 주 만에 가격이 무의미해진다. 값은 미결 #52 의 곡선과 함께 조정한다.
LISTING_FEE_PERCENT = 5
PERCENT_BASE = 100

# 등록 유효 기간. 안 팔린 물건이 영원히 걸려 있으면 호가가 굳는다.
LISTING_TTL = timedelta(days=2)

# 가격 상한. 없으면 자전거래로 임의의 금액을 옮길 수 있다 — 막지는 못해도 한 번에
# 옮길 수 있는 양은 줄인다.
MAX_PRICE = 1_000_000


@dataclass(frozen=True)
class Listing:
    """경매 한 건."""

    listing_id: int
    item_id: int
    catalog_id: str
    seller_id: int
    price: int
    state: str
    is_mine: bool


def compute_fee(price: int) -> int:
    """등록 수수료. 정수 나눗셈이며 내림이다.

    Args:
        price: 호가.

    Returns:
        떼는 금액. 최소 1 이다 — 0 이면 배출구가 막힌다.
    """
    return max(1, price * LISTING_FEE_PERCENT // PERCENT_BASE)


def create_listing(
    pool: ConnectionPool, account_id: int, entity_id: int, item_id: int, price: int
) -> int:
    """아이템을 경매에 건다. 수수료를 먼저 떼고 아이템을 인벤토리에서 뺀다.

    Args:
        pool: 연결 풀.
        account_id: 파는 계정 (수수료를 낸다).
        entity_id: 아이템을 가진 개체.
        item_id: 걸 아이템.
        price: 호가.

    Returns:
        만들어진 등록 id.

    Raises:
        ValueError: 호가가 범위를 벗어났거나 수수료가 모자란 경우.
    """
    if not 0 < price <= MAX_PRICE:
        raise ValueError(f"호가가 범위를 벗어났다: {price}")
    add_currency(pool, account_id, -compute_fee(price))
    expires_at = datetime.now(UTC) + LISTING_TTL
    with pool.connection() as connection:
        # 인벤토리에서 뺀다. 걸어 두고 그대로 쓸 수 있으면 하나를 여러 번 팔 수 있다.
        connection.execute(
            "DELETE FROM inventory_slot WHERE entity_id = %s AND item_id = %s",
            (entity_id, item_id),
        )
        connection.execute(
            "DELETE FROM equipment_slot WHERE entity_id = %s AND item_id = %s",
            (entity_id, item_id),
        )
        row = connection.execute(
            "INSERT INTO auction_listing (item_id, seller_id, price, fee, expires_at)"
            " VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (item_id, account_id, price, compute_fee(price), expires_at),
        ).fetchone()
    if row is None:
        raise RuntimeError("경매 등록에 실패했다")
    record_item_event(pool, entity_id, item_id, "list", str(price))
    return int(row[0])


def list_open(pool: ConnectionPool, account_id: int, limit: int = 50) -> tuple[Listing, ...]:
    """열려 있는 매물을 싼 것부터 읽는다. 만료된 것은 먼저 정리한다.

    Args:
        pool: 연결 풀.
        account_id: 보는 계정. 내 매물을 표시하는 데 쓴다.
        limit: 최대 줄 수.

    Returns:
        가격 순 매물들.
    """
    apply_expiry(pool)
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT l.id, l.item_id, i.catalog_id, l.seller_id, l.price, l.state"
            " FROM auction_listing l JOIN item_instance i ON i.id = l.item_id"
            " WHERE l.state = %s ORDER BY l.price ASC, l.listed_at ASC LIMIT %s",
            (STATE_OPEN, limit),
        ).fetchall()
    return tuple(
        Listing(
            listing_id=int(row[0]),
            item_id=int(row[1]),
            catalog_id=str(row[2]),
            seller_id=int(row[3]),
            price=int(row[4]),
            state=str(row[5]),
            is_mine=int(row[3]) == account_id,
        )
        for row in rows
    )


def apply_expiry(pool: ConnectionPool) -> int:
    """지난 매물을 만료 처리하고 아이템을 판 사람에게 돌려준다.

    돌려줄 칸이 없으면 **만료시키지 않는다.** 아이템을 없애는 것보다 매물로 남기는
    편이 낫다 — 사람은 칸을 비우면 되찾을 수 있다.

    Args:
        pool: 연결 풀.

    Returns:
        만료 처리한 건수.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT l.id, l.item_id, e.id FROM auction_listing l"
            " JOIN entity_record e ON e.owner_account_id = l.seller_id"
            " WHERE l.state = %s AND l.expires_at < now()",
            (STATE_OPEN,),
        ).fetchall()
    count = 0
    for listing_id, item_id, entity_id in rows:
        index = find_empty_slot(pool, int(entity_id))
        if index is None:
            continue
        with pool.connection() as connection:
            connection.execute(
                "UPDATE auction_listing SET state = %s, settled_at = now() WHERE id = %s",
                (STATE_EXPIRED, listing_id),
            )
            connection.execute(
                "INSERT INTO inventory_slot (entity_id, slot_index, item_id) VALUES (%s, %s, %s)",
                (int(entity_id), index, int(item_id)),
            )
        count += 1
    return count


def apply_purchase(
    pool: ConnectionPool, listing_id: int, buyer_account_id: int, buyer_entity_id: int
) -> Listing:
    """매물을 산다. 돈이 오가고 소유자가 바뀐다.

    Args:
        pool: 연결 풀.
        listing_id: 살 매물.
        buyer_account_id: 사는 계정.
        buyer_entity_id: 받을 개체.

    Returns:
        팔린 매물.

    Raises:
        ValueError: 없는 매물이거나, 자기 매물이거나, 잔액·칸이 모자란 경우.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT item_id, seller_id, price FROM auction_listing WHERE id = %s AND state = %s",
            (listing_id, STATE_OPEN),
        ).fetchone()
    if row is None:
        raise ValueError("살 수 없는 매물이다")
    item_id, seller_id, price = int(row[0]), int(row[1]), int(row[2])
    if seller_id == buyer_account_id:
        # 자기 것을 사는 것은 수수료만 태우는 자전거래다. 막지 않으면 원장이 그것으로 찬다.
        raise ValueError("자기 매물은 살 수 없다")
    index = find_empty_slot(pool, buyer_entity_id)
    if index is None:
        raise ValueError("인벤토리가 가득 차 살 수 없다")

    add_currency(pool, buyer_account_id, -price)
    add_currency(pool, seller_id, price)
    with pool.connection() as connection:
        # 조건부 갱신이다. 동시에 두 사람이 사는 것을 여기서 끊는다.
        cursor = connection.execute(
            "UPDATE auction_listing SET state = %s, buyer_id = %s, settled_at = now()"
            " WHERE id = %s AND state = %s",
            (STATE_SOLD, buyer_account_id, listing_id, STATE_OPEN),
        )
        if cursor.rowcount != 1:
            raise ValueError("이미 팔린 매물이다")
        connection.execute(
            "UPDATE item_instance SET owner_entity_id = %s WHERE id = %s",
            (buyer_entity_id, item_id),
        )
        connection.execute(
            "INSERT INTO inventory_slot (entity_id, slot_index, item_id) VALUES (%s, %s, %s)",
            (buyer_entity_id, index, item_id),
        )
    record_item_event(pool, buyer_entity_id, item_id, "buy", str(price))
    return Listing(
        listing_id=listing_id,
        item_id=item_id,
        catalog_id="",
        seller_id=seller_id,
        price=price,
        state=STATE_SOLD,
        is_mine=False,
    )


def apply_cancel(pool: ConnectionPool, listing_id: int, account_id: int, entity_id: int) -> None:
    """내 매물을 내린다. 수수료는 돌려주지 않는다 — 돌려주면 무료로 시세를 떠볼 수 있다.

    Args:
        pool: 연결 풀.
        listing_id: 내릴 매물.
        account_id: 내리는 계정.
        entity_id: 받을 개체.

    Raises:
        ValueError: 내 매물이 아니거나 받을 칸이 없는 경우.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT item_id FROM auction_listing WHERE id = %s AND seller_id = %s AND state = %s",
            (listing_id, account_id, STATE_OPEN),
        ).fetchone()
    if row is None:
        raise ValueError("내릴 수 없는 매물이다")
    index = find_empty_slot(pool, entity_id)
    if index is None:
        raise ValueError("인벤토리가 가득 차 내릴 수 없다")
    with pool.connection() as connection:
        connection.execute(
            "UPDATE auction_listing SET state = %s, settled_at = now() WHERE id = %s",
            (STATE_CANCELLED, listing_id),
        )
        connection.execute(
            "INSERT INTO inventory_slot (entity_id, slot_index, item_id) VALUES (%s, %s, %s)",
            (entity_id, index, int(row[0])),
        )
    record_item_event(pool, entity_id, int(row[0]), EVENT_DISCARD, "cancel")
