"""가방 칸에 무언가를 넣는다 (설계/4_아이템 §5).

`items.py` 에서 갈라 나왔다. 저쪽은 **무엇이 들어 있는가를 읽는 일**이고 여기는 **넣는
일**이다 — 파일이 400줄 상한을 넘은 것이 계기였지만, 가르는 선은 책임이다 (§4).

**소모품은 인스턴스가 아니라 스택이다.** 인스턴스로 넣으면 세는 쪽이 못 보고, 물약을
여섯 개 들고도 기본 지급 두 개로 싸우게 된다 — 실제로 그랬다.

인벤토리는 **가장 낮은 빈 칸**에 넣는다. 자동 폐기를 두지 않는 이유는 P1 이다 — 왜
사라졌는지 설명할 수 없는 삭제는 버그와 구분되지 않는다.
"""

from psycopg_pool import ConnectionPool

# 인벤토리 칸 수. 밸런스가 정해지기 전의 출발값이다 (docs/설계/4_아이템 §5).
INVENTORY_SIZE = 20

EVENT_GRANT = "grant"


def find_empty_slot(pool: ConnectionPool, entity_id: int) -> int | None:
    """가장 낮은 빈 칸을 찾는다.

    Args:
        pool: 연결 풀.
        entity_id: 개체 id (entity_record).

    Returns:
        칸 번호. 가득 찼으면 None.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT slot_index FROM inventory_slot WHERE entity_id = %s", (entity_id,)
        ).fetchall()
    used = {int(row[0]) for row in rows}
    for index in range(INVENTORY_SIZE):
        if index not in used:
            return index
    return None


def apply_stack_grant(pool: ConnectionPool, entity_id: int, catalog_id: str, cap: int) -> bool:
    """소모품 하나를 가방에 쌓는다.

    **소모품은 인스턴스가 아니라 스택이다** (§5). 인스턴스로 넣으면 물약 여섯 개가 가방
    스무 칸 중 여섯 칸을 먹고, 무엇보다 **세는 쪽이 스택만 보므로 전투에 안 나간다** —
    실제로 물약 여섯 개를 들고도 기본 지급 두 개로만 싸우고 있었다.

    빈 칸을 새로 쓰기 전에 **이미 쌓여 있는 칸을 먼저 채운다.** 안 그러면 같은 물약이
    칸마다 하나씩 흩어진다.

    Args:
        pool: 연결 풀.
        entity_id: 받을 개체.
        catalog_id: 소모품 id.
        cap: 한 칸에 쌓을 수 있는 최대 개수.

    Returns:
        넣었으면 True. 가방이 가득 찼고 채울 칸도 없으면 False.
    """
    with pool.connection() as connection:
        filled = connection.execute(
            "UPDATE inventory_slot SET stack_count = stack_count + 1"
            " WHERE entity_id = %s AND stack_catalog_id = %s AND stack_count < %s"
            " AND slot_index = ("
            "   SELECT min(slot_index) FROM inventory_slot"
            "   WHERE entity_id = %s AND stack_catalog_id = %s AND stack_count < %s"
            " )",
            (entity_id, catalog_id, cap, entity_id, catalog_id, cap),
        )
        if filled.rowcount == 1:
            return True
    slot = find_empty_slot(pool, entity_id)
    if slot is None:
        return False
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO inventory_slot (entity_id, slot_index, stack_catalog_id, stack_count)"
            " VALUES (%s, %s, %s, 1)",
            (entity_id, slot, catalog_id),
        )
    return True
