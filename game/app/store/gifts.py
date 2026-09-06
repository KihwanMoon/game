"""사람이 봇에게 아이템을 넘긴다 (T11, 결정 #02·#07).

**방향이 전부를 가른다.** 사람 → 봇은 아이템이 사람 경제에서 나가는 것이라 안전하다.
봇 → 사람은 봇이 파밍해서 넘기는 길이며, 그것이 T11 이자 아이템의 문을 검증된 런 하나로
묶은 결정 #02 가 막으려던 것이다.

그래서 이 모듈에는 **받는 함수만 있고 돌려주는 함수가 없다.** 그리고 도착하는 순간
귀속시킨다 — 귀속된 물건은 경매에 못 걸리므로(결정 #07), 한 번 봇에게 간 것은 어떤
경로로도 사람에게 돌아오지 않는다. 도플갱어·되찾기·경매 셋이 이미 막혀 있고 이것이
넷째 길목이다.

**받는 쪽이 봇인지 반드시 확인한다.** 확인을 빼면 이것은 관리자가 중개하는 사람↔사람
이관이 되고, 그 순간 자전거래를 막던 귀속 규칙이 우회된다.
"""

from psycopg_pool import ConnectionPool

from game.app.store.accounts import find_player_entity
from game.app.store.inventory_slots import find_empty_slot


def apply_bot_gift(
    pool: ConnectionPool, item_id: int, from_entity_id: int, to_account_id: int
) -> str:
    """아이템 하나를 봇에게 넘긴다.

    **한 트랜잭션에 넣는다.** 빼기와 넣기가 갈리면 중간에 끊겼을 때 아이템이 어느 쪽에도
    없거나 양쪽에 있다.

    Args:
        pool: 연결 풀.
        item_id: 넘길 아이템.
        from_entity_id: 주는 사람의 플레이어 개체.
        to_account_id: 받을 봇의 계정.

    Returns:
        넘긴 아이템의 카탈로그 id.

    Raises:
        ValueError: 받는 쪽이 봇이 아니거나, 가진 물건이 아니거나, 봇의 가방이 찬 경우.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT is_bot FROM account WHERE id = %s", (to_account_id,)
        ).fetchone()
        # **봇에게만 준다.** 사람에게 줄 수 있으면 이것은 관리자가 중개하는 사람↔사람
        # 이관이고, 귀속으로 막아 둔 자전거래가 그 길로 되살아난다.
        if not (row and row[0]):
            raise ValueError("봇에게만 줄 수 있다")
    # **개체는 `find_player_entity` 가 문이다.** 표를 직접 읽으면 아직 한 판도 안 돈
    # 계정에서 개체가 없어 실패한다 — 그 함수는 없으면 만든다.
    to_entity_id = find_player_entity(pool, to_account_id)
    index = find_empty_slot(pool, to_entity_id)
    if index is None:
        raise ValueError("그 봇의 가방이 가득 찼다")

    with pool.connection() as connection:
        # 가방 칸에서 뺀다. 낀 것은 여기 없다 — 장착 중인 물건은 부르는 쪽이 먼저 뺀다.
        cursor = connection.execute(
            "DELETE FROM inventory_slot WHERE entity_id = %s AND item_id = %s",
            (from_entity_id, item_id),
        )
        if cursor.rowcount != 1:
            raise ValueError("가방에 없는 아이템이다")
        # **도착하는 순간 귀속된다** (결정 #07). 귀속된 물건은 경매에 못 걸리므로 이
        # 한 줄이 「돌아오지 않는다」를 만든다.
        moved = connection.execute(
            "UPDATE item_instance SET owner_entity_id = %s, is_bound = TRUE"
            " WHERE id = %s RETURNING catalog_id",
            (to_entity_id, item_id),
        ).fetchone()
        if moved is None:
            raise ValueError("없는 아이템이다")
        connection.execute(
            "INSERT INTO inventory_slot (entity_id, slot_index, item_id) VALUES (%s, %s, %s)",
            (to_entity_id, index, item_id),
        )
    return str(moved[0])


def apply_bot_coin_gift(
    pool: ConnectionPool, amount: int, from_account_id: int, to_account_id: int
) -> int:
    """화폐를 봇에게 넘긴다 (2026-09-06).

    **한 트랜잭션에 넣는다.** 빼기와 넣기가 갈리면 중간에 끊겼을 때 돈이 어느 쪽에도
    없거나 양쪽에 있다 — 아이템 선물과 같은 이유다.

    **한 방향이다.** 아이템 선물과 같은 규율이며(결정 #07), 돌려받는 길을 두면 봇을
    금고로 쓰는 계정이 생긴다.

    **화폐를 만들지 않는다.** 주는 쪽에서 빠진 만큼만 받는 쪽에 들어가므로 총량이 그대로다
    — 늘리는 문은 검증된 런 하나뿐이다.

    Args:
        pool: 연결 풀.
        amount: 넘길 양. 0 이하는 거절한다.
        from_account_id: 주는 계정.
        to_account_id: 받을 봇의 계정.

    Returns:
        주고 난 뒤 **주는 쪽**의 잔액.

    Raises:
        ValueError: 양이 0 이하이거나, 잔액이 모자라거나, 자기 자신에게 주는 경우.
    """
    if amount <= 0:
        raise ValueError("넘길 양이 0 보다 커야 한다")
    if from_account_id == to_account_id:
        # 자기에게 주면 잔액이 그대로인데 원장에는 오간 것으로 남는다.
        raise ValueError("자기 자신에게는 넘길 수 없다")
    with pool.connection() as connection:
        for account_id in (from_account_id, to_account_id):
            connection.execute(
                "INSERT INTO wallet (account_id, balance) VALUES (%s, 0) ON CONFLICT DO NOTHING",
                (account_id,),
            )
        row = connection.execute(
            "UPDATE wallet SET balance = balance - %s, updated_at = now()"
            " WHERE account_id = %s AND balance >= %s RETURNING balance",
            (amount, from_account_id, amount),
        ).fetchone()
        if row is None:
            raise ValueError("잔액이 모자란다")
        connection.execute(
            "UPDATE wallet SET balance = balance + %s, updated_at = now() WHERE account_id = %s",
            (amount, to_account_id),
        )
    return int(row[0])
