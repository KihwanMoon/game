"""부른 테스터를 표시하고 읽는다 (로드맵 §게이트 G1).

**G1 의 분모를 정하는 자리다.** 게이트는 「테스터 5명 중 3명」을 묻는데, 이 게임은
익명으로 시작하므로 접속할 때마다 계정이 하나 생긴다 — 「제출이 있는 사람 계정」을 세면
한 판 내고 떠난 사람까지 전부 테스터가 된다. 2026-09-05 실측으로 36명 중 17명이
한 판짜리였고, 그 절반이 평균 재도전을 1.2회로 눌러 놓고 있었다.

**제출 수로 거르지 않는다.** 「많이 논 계정」만 분모에 넣고 「평균 재도전 3회 이상」을
재면 기준이 저절로 통과된다 — 순환이다. 누구를 불렀는지는 사람이 알고 있으므로,
사람이 표시한다.

여기서 하는 것은 **표시와 조회뿐**이다. 세는 것은 `scripts/report_g1.py` 가 한다.

**봇도 표시할 수 있다 (2026-09-10) — 다만 G1 에는 안 센다.** 예전에는 목록에서도 빼고
표시도 막았는데, 그러면 「층 깊이 간 봇을 화면 위에 고정해 두고 지켜본다」 같은 운영이
아예 안 된다. 대신 세는 자리(`count_testers`·`report_g1`)는 사람만 본다 — G1 이 묻는
「첫 패배 후 규칙을 고쳐 재도전했는가」는 사람에게만 뜻이 있는 질문이고, 봇은 정의상
늘 재도전하므로 섞이는 순간 그 수가 「러너가 몇 번 돌았는가」가 된다.

그래서 화면은 두 수를 함께 보여 준다 — 사람 n/5 와 봇 m(안 셈). 하나만 보여 주면
표시해 놓고 왜 안 오르는지를 다시 묻게 된다.
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
    # 봇인가. **화면이 갈라 적어야 한다** — 표시는 되지만 G1 에는 안 세는 줄이라,
    # 구분 없이 늘어놓으면 「5명 중 3명」의 분모가 화면에서 틀리게 읽힌다.
    is_bot: bool = False


def list_candidates(pool: ConnectionPool, limit: int) -> tuple[TesterRow, ...]:
    """표시할 수 있는 계정을 최근 접속 순으로 읽는다.

    **비활성 계정은 뺀다.** 토큰이 이미 안 통하므로 표시해도 셀 것이 늘지 않는다.

    **봇은 뺐다가 다시 넣었다** (2026-09-10). 빼 두면 층 깊이 간 봇을 화면 위에 고정해
    두는 운영이 안 된다 — 대신 `is_bot` 을 함께 실어 화면이 갈라 적게 하고, 세는 자리는
    사람만 본다 (`count_testers`).

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
            " COALESCE(to_char(seen.at, 'YYYY-MM-DD HH24:MI'), ''), a.is_bot"
            " FROM account a"
            " LEFT JOIN seen ON seen.account_id = a.id"
            " LEFT JOIN tried ON tried.account_id = a.id"
            " WHERE a.deactivated_at IS NULL"
            # 표시된 줄이 언제나 맨 위다. 표시를 끄려면 그것을 찾을 수 있어야 하고,
            # 봇은 사람보다 훨씬 자주 접속하므로 순서를 접속에 맡기면 사람 테스터가
            # 봇 열 줄 아래로 밀린다.
            " ORDER BY a.is_tester DESC, a.is_bot, seen.at DESC NULLS LAST, a.id DESC"
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
            is_bot=bool(row[6]),
        )
        for row in rows
    )


def apply_tester_mark(pool: ConnectionPool, account_ids: tuple[int, ...], is_tester: bool) -> int:
    """계정을 테스터로 표시하거나 표시를 지운다.

    **봇에도 붙는다 (2026-09-10) — 세는 자리가 막는다.** 예전에는 여기서 막았는데,
    그러면 봇을 화면 위에 고정해 두는 운영이 안 된다. G1 이 재는 것이 러너가 되지
    않게 하는 것은 `count_testers` 와 `report_g1` 의 일이다.

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
            "UPDATE account SET is_tester = %s WHERE id = ANY(%s)",
            (is_tester, list(account_ids)),
        )
    return cursor.rowcount


def count_testers(pool: ConnectionPool) -> int:
    """표시된 **사람** 테스터 수 — G1 의 분모다.

    **봇을 세지 않는다.** 표시 자체는 봇에도 붙지만(`apply_tester_mark`), G1 이 묻는
    「첫 패배 후 규칙을 고쳐 재도전했는가」는 사람에게만 뜻이 있는 질문이다 — 봇은
    정의상 늘 재도전하므로, 섞이면 이 수가 「러너가 몇 번 돌았는가」가 된다.

    Args:
        pool: 연결 풀.

    Returns:
        표시된 사람 계정 수. 아무도 표시하지 않았으면 0.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT count(*) FROM account WHERE is_tester AND NOT is_bot"
        ).fetchone()
    return int(row[0]) if row else 0


def count_bot_testers(pool: ConnectionPool) -> int:
    """표시된 **봇** 수 — 화면에만 쓴다.

    이 수를 따로 내는 이유는 하나다. 봇을 표시해 두고 사람 수가 안 오르는 것을 보면
    「표시가 안 먹었나」를 의심하게 되는데, 옆에 이 수가 함께 있으면 「표시는 됐고 다만
    G1 에 안 센다」가 화면에서 바로 읽힌다.

    Args:
        pool: 연결 풀.

    Returns:
        표시된 봇 계정 수.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT count(*) FROM account WHERE is_tester AND is_bot"
        ).fetchone()
    return int(row[0]) if row else 0
