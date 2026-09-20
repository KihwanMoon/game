"""오늘의 도전 — 같은 판을 모두가 돈 결과 (재방문 고리).

**데일리는 이미 돌고 있었다.** 티켓을 하루 한 번 내주고 시드를 날짜로 고정하는 것까지
서버가 하고 있었는데, **그 결과를 아무도 못 봤다.** 같은 판을 다 같이 돈다는 사실이
화면에 없으면 그것은 그냥 「어제와 다른 한 판」이고, 내일 다시 올 이유가 되지 못한다.

**순위표(`leaderboard`)를 안 쓴다.** 저쪽은 시즌(`core_version`)으로 갈리고 점수를
누적하는 표다. 오늘의 도전은 **하루가 곧 판**이라, 그날의 티켓이 어디까지 갔는지만
보면 된다 — `daily_entry` 와 `run_ticket.cleared_floor` 가 이미 그것을 들고 있다.
"""

from datetime import date

from psycopg_pool import ConnectionPool

from game.app.store.display_name import build_display_name_sql


def list_daily_board(pool: ConnectionPool, day: date, limit: int = 20) -> tuple[dict, ...]:
    """그날의 도전 순위를 읽는다.

    **깬 층이 0 인 줄도 낸다.** 티켓만 받고 아직 안 돈 사람을 빼면 「몇 명이 오늘 이
    판을 잡고 있는가」가 안 보인다 — 그것이 혼자가 아니라는 유일한 신호다.

    동점이면 먼저 받은 쪽이 위다. 늦게 같은 층에 닿았다고 앞서면 안 된다.

    Args:
        pool: 연결 풀.
        day: 볼 날짜.
        limit: 최대 줄 수.

    Returns:
        순위 순 줄들.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            f"SELECT {build_display_name_sql('a')}, t.cleared_floor, d.account_id"
            " FROM daily_entry d"
            " JOIN run_ticket t ON t.id = d.ticket_id"
            " JOIN account a ON a.id = d.account_id"
            # 비활성 계정은 뺀다. 순위표와 같은 규율이다 — 검사가 만든 계정이 위에 있으면
            # 이 표가 말하는 것이 실력이 아니라 내 탐침 횟수가 된다.
            " WHERE d.day = %s AND a.deactivated_at IS NULL"
            " ORDER BY t.cleared_floor DESC, d.created_at ASC LIMIT %s",
            (day, limit),
        ).fetchall()
    return tuple(
        {
            "rank": index + 1,
            "handle": str(row[0]),
            "floor": int(row[1]),
            "account_id": int(row[2]),
        }
        for index, row in enumerate(rows)
    )


def read_daily_entry(pool: ConnectionPool, day: date, account_id: int) -> dict | None:
    """내가 그날 받은 티켓과 그 성적.

    Args:
        pool: 연결 풀.
        day: 볼 날짜.
        account_id: 내 계정.

    Returns:
        티켓 id 와 깬 층. 안 받았으면 None.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT t.id, t.cleared_floor FROM daily_entry d"
            " JOIN run_ticket t ON t.id = d.ticket_id"
            " WHERE d.day = %s AND d.account_id = %s",
            (day, account_id),
        ).fetchone()
    return None if row is None else {"ticket_id": str(row[0]), "floor": int(row[1])}


def count_daily_players(pool: ConnectionPool, day: date) -> int:
    """그날 이 판을 잡은 사람 수.

    **윗자리만 보여 주면 혼자인지 백 명인지 모른다.** 스무 줄이 상한이라 그 아래가
    몇인지는 따로 세어야 한다.

    Args:
        pool: 연결 풀.
        day: 볼 날짜.

    Returns:
        사람 수.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT count(*) FROM daily_entry d JOIN account a ON a.id = d.account_id"
            " WHERE d.day = %s AND a.deactivated_at IS NULL",
            (day,),
        ).fetchone()
    return 0 if row is None else int(row[0])
