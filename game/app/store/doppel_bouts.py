"""둔갑의 전적 — **돌아오는 길** (2026-09-15).

`doppels.py` 에서 갈라 나왔다. 저쪽은 **그림자를 세우고 지우는 일**이고 여기는 **그
그림자가 무엇을 했는지 주인에게 돌려주는 일**이다. 파일이 400줄을 넘은 것이 계기였을
뿐, 가르는 선은 책임이다 (§4).

**왜 이 표가 필요한가.** 이 게임의 축은 거의 다 플레이어를 따라온다 — 층 스케일도,
둔갑의 레벨도, 선공도. 그래서 세져도 체감 난이도가 같고, 순위는 누적 경험치라 **오래
돌린 사람이 1등**이다. 「잘 적었다」가 쌓이는 자리가 어디에도 없었다.

내 빌드가 남의 장에 서서 누구를 만나고 이겼는지는 **성장과 무관한 사실**이다. 그것을
돌려주는 것이 이 표의 전부다.
"""

from psycopg_pool import ConnectionPool


def record_bout(
    pool: ConnectionPool,
    record_id: int,
    opponent_account_id: int,
    floor: int,
    is_doppel_win: bool,
) -> bool:
    """둔갑이 누군가와 만난 한 판을 남긴다.

    **돌아오는 길이 없었다.** 내 빌드가 남의 장에 서는데 몇 번 섰고 누구를 만났는지가
    주인에게 아무것도 안 갔다 — 그래서 성장이 곧 난이도가 되는 자리만 남고, 「내가 잘
    적었다」는 어디에도 안 쌓였다.

    **주인이 없으면 안 남긴다.** 봇이 세운 둔갑에도 주인은 있지만(봇 계정), 주인을 못
    찾는 경우는 이미 지워진 개체다 — 그때 억지로 남기면 누구의 전적인지 모르는 줄이 된다.

    **제 둔갑과 만난 판은 안 센다.** 자기 그림자를 잡는 것은 전적이 아니라 되풀이다.

    Args:
        pool: 연결 풀.
        record_id: 둔갑 개체.
        opponent_account_id: 맞선 사람의 계정.
        floor: 만난 장.
        is_doppel_win: 둔갑이 이겼는가.

    Returns:
        남겼으면 True.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT origin_account_id FROM entity_record"
            " WHERE id = %s AND is_doppel AND origin_account_id IS NOT NULL",
            (record_id,),
        ).fetchone()
        if row is None or int(row[0]) == opponent_account_id:
            return False
        connection.execute(
            "INSERT INTO doppel_bout"
            " (record_id, origin_account_id, opponent_account_id, floor, is_doppel_win)"
            " VALUES (%s, %s, %s, %s, %s)",
            (record_id, int(row[0]), opponent_account_id, floor, is_doppel_win),
        )
    return True


def count_bouts(pool: ConnectionPool, account_id: int) -> tuple[int, int]:
    """내 둔갑이 몇을 만났고 몇을 이겼나.

    Args:
        pool: 연결 풀.
        account_id: 주인 계정.

    Returns:
        (만난 판, 이긴 판).
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT count(*), count(*) FILTER (WHERE is_doppel_win)"
            " FROM doppel_bout WHERE origin_account_id = %s",
            (account_id,),
        ).fetchone()
    if row is None:
        return (0, 0)
    return (int(row[0]), int(row[1]))


def list_bouts(pool: ConnectionPool, account_id: int, limit: int) -> tuple[dict, ...]:
    """내 둔갑의 최근 전적.

    **상대는 이름으로 낸다.** 계정 번호로 적으면 「누가 잡았나」에 답이 안 되고, 그
    물음이 이 기능의 전부다.

    Args:
        pool: 연결 풀.
        account_id: 주인 계정.
        limit: 읽을 줄 수.

    Returns:
        최근 순의 전적들.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT b.floor, b.is_doppel_win, COALESCE(a.handle, ''), b.at"
            " FROM doppel_bout b LEFT JOIN account a ON a.id = b.opponent_account_id"
            " WHERE b.origin_account_id = %s ORDER BY b.at DESC, b.id DESC LIMIT %s",
            (account_id, limit),
        ).fetchall()
    return tuple(
        {
            "floor": int(row[0]),
            "is_doppel_win": bool(row[1]),
            "opponent": str(row[2]),
            "at": row[3].isoformat(),
        }
        for row in rows
    )


def list_my_doppels(pool: ConnectionPool, account_id: int) -> tuple[dict, ...]:
    """지금 서 있는 내 둔갑들.

    Args:
        pool: 연결 풀.
        account_id: 주인 계정.

    Returns:
        장이 얕은 순의 개체들.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT id, COALESCE(zone_floor, 0), level, lives FROM entity_record"
            " WHERE is_doppel AND origin_account_id = %s AND alive"
            " ORDER BY COALESCE(zone_floor, 0), id",
            (account_id,),
        ).fetchall()
    return tuple(
        {"record_id": int(row[0]), "floor": int(row[1]), "level": int(row[2]), "lives": int(row[3])}
        for row in rows
    )
