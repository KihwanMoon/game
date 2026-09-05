"""부른 테스터를 표시하고 읽는다 (로드맵 §게이트 G1).

**G1 의 분모를 정하는 자리다.** 게이트는 「테스터 5명 중 3명」을 묻는데, 이 게임은
익명으로 시작하므로 접속할 때마다 계정이 하나 생긴다 — 「제출이 있는 사람 계정」을 세면
한 판 내고 떠난 사람까지 전부 테스터가 된다. 2026-09-05 실측으로 36명 중 17명이
한 판짜리였고, 그 절반이 평균 재도전을 1.2회로 눌러 놓고 있었다.

**제출 수로 거르지 않는다.** 「많이 논 계정」만 분모에 넣고 「평균 재도전 3회 이상」을
재면 기준이 저절로 통과된다 — 순환이다. 누구를 불렀는지는 사람이 알고 있으므로,
사람이 표시한다.

여기서 하는 것은 **표시와 조회뿐**이다. 세는 것은 `scripts/report_g1.py` 가 한다.
"""

from dataclasses import dataclass

from psycopg_pool import ConnectionPool

# 로드맵이 전제하는 테스터 수 (§게이트 G1). **정본이 여기 하나다** — 보고서와 화면이
# 각자 적어 두면 로드맵을 고쳤을 때 한쪽만 따라가고, 그러면 같은 게이트가 두 기준으로
# 판정된다. 화면에는 응답에 실어 보낸다 (`MAX_RUNS_PER_HOUR` 과 같은 규약).
MIN_TESTERS = 5


@dataclass(frozen=True)
class TesterRow:
    """표시 화면에 뿌릴 계정 한 줄.

    표시 여부만이 아니라 **제출 수와 마지막 접속을 함께 준다.** 익명 계정은 번호밖에
    없어서, 그것 없이는 어느 줄이 누구인지 짐작할 단서가 화면에 하나도 없다.
    """

    account_id: int
    handle: str
    login_id: str
    is_tester: bool
    attempts: int
    last_seen: str


def list_candidates(pool: ConnectionPool, limit: int) -> tuple[TesterRow, ...]:
    """표시할 수 있는 계정을 최근 접속 순으로 읽는다.

    **봇과 비활성 계정은 뺀다.** 봇은 정의상 테스터가 아니고, 비활성 계정은 토큰이 이미
    안 통하므로 표시해도 셀 것이 늘지 않는다.

    Args:
        pool: 연결 풀.
        limit: 최대 줄 수. 익명 계정이 계속 늘어나므로 상한이 없으면 화면이 못 쓰게 된다.

    Returns:
        최근에 논 것부터 늘어놓은 줄들. 표시된 계정은 접속이 오래됐어도 늘 앞에 온다 —
        표시를 끄려면 그것을 찾을 수 있어야 한다.
    """
    with pool.connection() as connection:
        # **계정마다 세지 않는다.** 상관 서브쿼리로 쓰면 정렬 때문에 LIMIT 이 먹기 전에
        # 계정 수만큼 돌고, 계정은 계속 는다 — 검사 DB 가 5만 3천 개까지 쌓였을 때
        # 이 조회 하나가 분 단위로 걸렸다. 미리 묶어 두면 각 표를 한 번씩만 훑는다.
        rows = connection.execute(
            "WITH seen AS ("
            "  SELECT account_id, max(last_seen_at) AS at FROM account_token GROUP BY account_id"
            "), tried AS ("
            "  SELECT t.account_id, count(*) AS n FROM run_submission s"
            "  JOIN run_ticket t ON t.id = s.ticket_id GROUP BY t.account_id"
            ")"
            " SELECT a.id, a.handle, COALESCE(a.login_id, ''), a.is_tester,"
            " COALESCE(tried.n, 0),"
            " COALESCE(to_char(seen.at, 'YYYY-MM-DD HH24:MI'), '')"
            " FROM account a"
            " LEFT JOIN seen ON seen.account_id = a.id"
            " LEFT JOIN tried ON tried.account_id = a.id"
            " WHERE NOT a.is_bot AND a.deactivated_at IS NULL"
            " ORDER BY a.is_tester DESC, seen.at DESC NULLS LAST, a.id DESC"
            " LIMIT %s",
            (limit,),
        ).fetchall()
    return tuple(
        TesterRow(
            account_id=int(row[0]),
            handle=str(row[1]),
            login_id=str(row[2]),
            is_tester=bool(row[3]),
            attempts=int(row[4]),
            last_seen=str(row[5]),
        )
        for row in rows
    )


def apply_tester_mark(pool: ConnectionPool, account_ids: tuple[int, ...], is_tester: bool) -> int:
    """계정을 테스터로 표시하거나 표시를 지운다.

    **봇에는 안 붙는다.** 붙으면 G1 이 재는 것이 다시 러너가 된다.

    Args:
        pool: 연결 풀.
        account_ids: 대상 계정들.
        is_tester: 표시할지.

    Returns:
        바뀐 계정 수.
    """
    if not account_ids:
        return 0
    with pool.connection() as connection:
        cursor = connection.execute(
            "UPDATE account SET is_tester = %s WHERE id = ANY(%s) AND NOT is_bot",
            (is_tester, list(account_ids)),
        )
    return cursor.rowcount


def count_testers(pool: ConnectionPool) -> int:
    """표시된 테스터 수.

    Args:
        pool: 연결 풀.

    Returns:
        표시된 계정 수. 아무도 표시하지 않았으면 0.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT count(*) FROM account WHERE is_tester AND NOT is_bot"
        ).fetchone()
    return int(row[0]) if row else 0
