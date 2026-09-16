"""장 카드를 본 적 있는가 (2026-09-16).

**기기가 아니라 계정에 붙는다.** 세션 안에서만 기억하던 때는 새로고침하거나 다른 기기로
옮기면 1장 카드가 다시 떴다 — 이야기는 한 번 읽는 것이라 두 번째부터는 방해다.

**`meta_save` 와 섞지 않는다.** 저쪽은 클라이언트가 적어 보내는 것이고(설계/7_변조방지 §4)
이것은 서버가 정하는 사실이다. 섞으면 빈 초안이 실제 초안을 덮던 사고가 여기서도 난다.

**막지 않는다.** 카드가 뜨는 것은 이야기일 뿐 판정이 아니므로, 못 남겨도 게임은 돈다 —
다음 접속에 한 번 더 뜰 뿐이다. 그래서 이 표의 실패는 요청을 실패시키지 않는다.
"""

from psycopg_pool import ConnectionPool


def list_seen_cards(pool: ConnectionPool, account_id: int) -> tuple[str, ...]:
    """이 계정이 이미 본 카드들.

    Args:
        pool: 연결 풀.
        account_id: 계정 id.

    Returns:
        카드 id 들. 정렬해서 낸다 — 같은 계정이 언제 물어도 같은 글자가 나와야 캐시가 선다.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT card_id FROM story_seen WHERE account_id = %s ORDER BY card_id",
            (account_id,),
        ).fetchall()
    return tuple(str(row[0]) for row in rows)


def apply_seen_card(pool: ConnectionPool, account_id: int, card_id: str) -> bool:
    """카드 하나를 봤다고 남긴다.

    **두 번 와도 한 줄이다.** 같은 카드를 두 화면이 동시에 닫아도 충돌하지 않아야 한다.

    Args:
        pool: 연결 풀.
        account_id: 계정 id.
        card_id: 카드 id. 장 카드는 `floor:3`, 그림자 카드는 `shadow` 다.

    Returns:
        새로 남겼으면 참. 이미 있었으면 거짓.
    """
    if not card_id.strip():
        return False
    with pool.connection() as connection:
        row = connection.execute(
            "INSERT INTO story_seen (account_id, card_id) VALUES (%s, %s)"
            " ON CONFLICT (account_id, card_id) DO NOTHING RETURNING card_id",
            (account_id, card_id.strip()),
        ).fetchone()
    return row is not None
