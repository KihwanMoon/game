"""새로 들어온 계정을 본다 (U1).

**볼 자리가 없었다.** 관리 화면 탭 열하나 중 계정을 보는 곳은 테스터 탭 하나뿐이고,
그것은 G1 의 분모를 정하려고 사람이 손으로 고르는 자리다. 「어제 몇 명이 새로
들어왔나」·「그중 누가 실제로 가입했나」를 볼 자리가 없어서 DB 를 직접 열어야 했고,
**그러면 아무도 안 본다** — 봇 탭과 지킴이 탭을 만든 것과 같은 이유다.

**계정이 생기는 순간은 「앱을 열었을 때」가 아니다.** `requireAccount` 가 "여는 것만
으로는 안 만든다 — 지금은 출격 하나다" 라고 못박고 있어서, 여기 뜨는 줄은 전부
**판을 한 번이라도 내려 한 사람**이다. 그냥 들렀다 간 사람은 `traffic_day` 가 센다
(`store/traffic.py`) — 둘을 나란히 놓아야 유입이 읽힌다.

**봇은 갈라 적는다.** 섞어 늘어놓으면 「어제 스물」이 사람 스물인지 봇 스물인지 모른다.
"""

from dataclasses import dataclass

from psycopg_pool import ConnectionPool

from game.app.store.display_name import build_display_name_sql

# 한 번에 읽을 최대 줄. 유입을 훑는 자리라 길어야 하지만, 무한히 늘면 화면이 멈춘다.
MAX_ARRIVALS = 200

# 기본으로 볼 기간(일).
DEFAULT_ARRIVAL_DAYS = 14


@dataclass(frozen=True)
class ArrivalRow:
    """새로 들어온 계정 한 줄.

    **언제 왔는가와 무엇을 했는가를 함께 준다.** 익명 계정은 번호밖에 없어서, 그것
    없이는 어느 줄이 누구인지 짐작할 단서가 화면에 하나도 없다 — 테스터 탭이 제출 수와
    마지막 접속을 함께 주는 것과 같은 이유다.

    **`is_joined` 가 이 표의 핵심이다.** 익명으로 시작해 가입으로 승격되는 구조라
    (`설계/3_저장과_멀티플레이`), 들어온 사람 중 몇이 실제로 자격증명을 붙였는지가
    「이 게임에 머무를 이유가 있는가」에 가장 가까운 수다.
    """

    account_id: int
    name: str
    is_joined: bool
    is_bot: bool
    created_at: str
    runs: int
    best_floor: int


def list_arrivals(
    pool: ConnectionPool,
    days: int = DEFAULT_ARRIVAL_DAYS,
    limit: int = MAX_ARRIVALS,
) -> tuple[ArrivalRow, ...]:
    """최근에 생긴 계정을 새것부터 읽는다.

    **한 문장으로 센다.** 계정마다 제출 수를 따로 물으면 계정 수만큼 왕복하고, 계정은
    계속 는다 — 테스터 목록이 검사 DB 5만 3천 개에서 분 단위로 걸렸던 자리와 같은
    모양이다. 미리 묶어 각 표를 한 번씩만 훑는다.

    **비활성 계정은 뺀다.** 토큰이 이미 안 통하므로 유입으로 셀 것이 아니다.

    Args:
        pool: 연결 풀.
        days: 며칠치를 볼 것인가. 오늘을 포함한다.
        limit: 최대 줄 수. 상한 안으로 물려서 쓴다.

    Returns:
        새것부터의 줄들.
    """
    wanted = max(1, min(MAX_ARRIVALS, limit))
    with pool.connection() as connection:
        rows = connection.execute(
            "WITH tried AS ("
            "  SELECT t.account_id, count(*) AS n, COALESCE(max(t.floor), 0) AS deep"
            "  FROM run_submission s JOIN run_ticket t ON t.id = s.ticket_id"
            "  GROUP BY t.account_id"
            ")"
            f" SELECT a.id, {build_display_name_sql('a')},"
            " a.login_id IS NOT NULL AND a.login_id <> '', a.is_bot,"
            " to_char(a.created_at, 'YYYY-MM-DD HH24:MI'),"
            " COALESCE(tried.n, 0), COALESCE(tried.deep, 0)"
            " FROM account a"
            " LEFT JOIN tried ON tried.account_id = a.id"
            " WHERE a.deactivated_at IS NULL"
            " AND a.created_at > now() - make_interval(days => %s)"
            " ORDER BY a.created_at DESC, a.id DESC"
            " LIMIT %s",
            (max(1, days), wanted),
        ).fetchall()
    return tuple(
        ArrivalRow(
            account_id=int(row[0]),
            name=str(row[1]),
            is_joined=bool(row[2]),
            is_bot=bool(row[3]),
            created_at=str(row[4]),
            runs=int(row[5]),
            best_floor=int(row[6]),
        )
        for row in rows
    )


@dataclass(frozen=True)
class ArrivalSummary:
    """기간 동안의 유입 요약.

    **목록만으로는 안 읽힌다.** 스무 줄을 눈으로 세는 것과 「어제 스물, 그중 둘이
    가입」을 읽는 것은 다르다. 화면이 둘 다 보여야 한다.
    """

    days: int
    arrived: int
    joined: int
    played: int


def read_arrival_summary(pool: ConnectionPool, days: int = DEFAULT_ARRIVAL_DAYS) -> ArrivalSummary:
    """기간 동안 몇이 들어왔고 몇이 가입했고 몇이 판을 냈는가.

    **봇은 안 센다.** 우리가 들인 것이라 유입이 아니다 — 섞으면 「어제 스물」이 사람
    스물인지 봇 스물인지 모른다.

    Args:
        pool: 연결 풀.
        days: 며칠치를 볼 것인가.

    Returns:
        요약. 계정이 하나도 없으면 전부 0 이다.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "WITH tried AS ("
            "  SELECT t.account_id, count(*) AS n FROM run_submission s"
            "  JOIN run_ticket t ON t.id = s.ticket_id GROUP BY t.account_id"
            ")"
            " SELECT count(*),"
            " count(*) FILTER (WHERE a.login_id IS NOT NULL AND a.login_id <> ''),"
            " count(*) FILTER (WHERE COALESCE(tried.n, 0) > 0)"
            " FROM account a"
            " LEFT JOIN tried ON tried.account_id = a.id"
            " WHERE a.deactivated_at IS NULL AND NOT a.is_bot"
            " AND a.created_at > now() - make_interval(days => %s)",
            (max(1, days),),
        ).fetchone()
    if row is None:
        return ArrivalSummary(days=days, arrived=0, joined=0, played=0)
    return ArrivalSummary(days=days, arrived=int(row[0]), joined=int(row[1]), played=int(row[2]))
