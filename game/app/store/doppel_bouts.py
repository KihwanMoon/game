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

from game.app.store.display_name import build_display_name_sql

# 둔갑 승수 판의 이름. `/api/leaderboard?mode=` 가 이 값으로 갈린다.
MODE_DOPPEL = "doppel"


def record_bout(
    pool: ConnectionPool,
    record_id: int,
    opponent_account_id: int,
    floor: int,
    is_doppel_win: bool,
    core_version: str = "",
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
        core_version: 이 판이 돈 코어 버전. 순위표가 시즌을 이것으로 가른다 (결정 #06) —
            비우면 어느 시즌에도 안 잡힌다.

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
            " (record_id, origin_account_id, opponent_account_id, floor, is_doppel_win,"
            "  core_version)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            (record_id, int(row[0]), opponent_account_id, floor, is_doppel_win, core_version),
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
            f"SELECT b.floor, b.is_doppel_win, COALESCE({build_display_name_sql('a')}, ''), b.at"
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


def list_retired_doppels(pool: ConnectionPool, account_id: int, limit: int) -> tuple[dict, ...]:
    """물러난 내 둔갑들과 그것이 남긴 활자.

    **셈이 끝나는 자리가 안 보였다** (2026-09-15). 이긴 판은 활자가 되는데 들어오는 것은
    이긴 순간이 아니라 그림자가 사라질 때라, 화면에 「이겼는데 활자가 안 늘었다」로
    보였다. 여기서 끝난 것들을 적는다.

    **표를 새로 안 만든다.** 개체가 지워져도 전적은 남으므로(`record_id` 에 외래키를 안
    걸었다), 「전적은 있는데 개체가 없는 것」이 곧 물러난 둔갑이다.

    Args:
        pool: 연결 풀.
        account_id: 주인 계정.
        limit: 최대 줄 수.

    Returns:
        최근에 물러난 순서의 줄들. 만난 적이 없는 둔갑은 전적이 없으므로 안 나온다.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT b.record_id, max(b.floor),"
            " count(*) FILTER (WHERE b.is_doppel_win),"
            " count(*) FILTER (WHERE NOT b.is_doppel_win), max(b.at)"
            " FROM doppel_bout b"
            " WHERE b.origin_account_id = %s"
            " AND NOT EXISTS ("
            "   SELECT 1 FROM entity_record e WHERE e.id = b.record_id AND e.is_doppel"
            " )"
            " GROUP BY b.record_id ORDER BY max(b.at) DESC LIMIT %s",
            (account_id, limit),
        ).fetchall()
    return tuple(
        {
            "record_id": int(row[0]),
            "floor": int(row[1] or 0),
            "won": int(row[2]),
            "lost": int(row[3]),
            "at": str(row[4]),
        }
        for row in rows
    )


def list_doppel_leaderboard(
    pool: ConnectionPool, core_version: str, limit: int = 50
) -> tuple[dict, ...]:
    """둔갑 순위표 — 내 내력이 남의 장에서 몇을 이겼나.

    **누적 경험치 판과 재는 것이 다르다.** 저쪽은 얼마나 멀리 왔는가라 오래 돌린 쪽이
    이기고, 이쪽은 **내가 없는 동안 내 규칙표가 버틴 횟수**다 — 성장과 무관한 유일한
    수치다 (2026-09-15).

    **동률이면 적은 판으로 이룬 쪽이 위다.** 같은 열 번을 이겼다면 스무 판 만에 이룬
    쪽이 쉰 판 만에 이룬 쪽보다 잘 적은 것이다.

    **한 번도 못 이긴 계정은 안 싣는다.** 0 승이 줄줄이 서면 순위표가 참가자 명부가 된다.

    Args:
        pool: 연결 풀.
        core_version: 시즌. 규칙이 바뀐 뒤의 승리와 그 전의 승리를 한 줄에 세우지 않는다.
        limit: 최대 줄 수.

    Returns:
        순위 순 줄들. `score` 가 이긴 판, `met` 이 만난 판이다.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            f"SELECT {build_display_name_sql('a')}, a.id,"
            " count(*) FILTER (WHERE b.is_doppel_win) AS won, count(*) AS met"
            " FROM doppel_bout b JOIN account a ON a.id = b.origin_account_id"
            # 비활성 계정은 순위표에서 빠진다 — 누적 경험치 판과 같은 규율이다.
            " WHERE b.core_version = %s AND a.deactivated_at IS NULL"
            " GROUP BY a.id, a.handle, a.login_id, a.nickname"
            " HAVING count(*) FILTER (WHERE b.is_doppel_win) > 0"
            " ORDER BY won DESC, met ASC, a.id ASC LIMIT %s",
            (core_version, limit),
        ).fetchall()
    return tuple(
        {
            "rank": index + 1,
            "handle": str(row[0]),
            "score": int(row[2]),
            "met": int(row[3]),
            "level": 0,
            "account_id": int(row[1]),
        }
        for index, row in enumerate(rows)
    )


def read_doppel_owner_name(pool: ConnectionPool, record_id: int) -> str:
    """그 그림자가 누구의 것인지, 화면에 뜨는 이름으로.

    **「도플갱어」라고만 뜨면 누구를 만난 것인지 모른다** (2026-09-16). 이 기제의 전제가
    「거기까지 실제로 내려간 빌드」인데, 그 빌드가 누구 것인지 안 보이면 남는 것은 숫자
    큰 정예 몹 하나다.

    Args:
        pool: 연결 풀.
        record_id: 그림자 개체.

    Returns:
        주인의 표시 이름. 주인이 없거나 지워졌으면 빈 문자열.
    """
    with pool.connection() as connection:
        row = connection.execute(
            f"SELECT {build_display_name_sql('a')} FROM entity_record e"
            " JOIN account a ON a.id = e.origin_account_id"
            " WHERE e.id = %s AND e.is_doppel",
            (record_id,),
        ).fetchone()
    return str(row[0]) if row else ""
