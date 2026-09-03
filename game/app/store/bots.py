"""봇 계정 — 가상 유저의 신원과 성격 (T11 대응, 결정 #48 준비).

**봇은 진짜 계정이다.** 같은 라우트로 티켓을 받고 같은 재시뮬로 확정받는다. 서비스
계층을 직접 부르는 봇이었다면 티켓 1회용·코어버전 대조·정비 같은 라우트 규율을 우회하게
되고, 그러면 봇의 런은 「진짜 경로가 도는지」를 더 이상 증명하지 못한다.

**표시하는 것이 설계다.** `설계/7_변조방지` T11 이 봇 파밍을 위협으로 적는데, 우리가
들인 봇을 표시하지 않으면 우리 손으로 만든 것과 잡아야 할 것이 구별되지 않는다.

스펙을 손으로 박지 않는다. 규칙표·리듬·실력 셋만 다르게 주면 장비·도달 층·도감은
굴러가면서 저절로 갈린다 — 그것이 사람이 여럿인 세계의 모습이다.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from psycopg_pool import ConnectionPool

# 실력의 하한. 0 이면 규칙표가 통째로 꺼져 폴백만 남고, 그런 봇은 무엇도 배우지 못한다.
MIN_SKILL_PCT = 20

# 실력의 상한. 100 이 「규칙표를 그대로 쓴다」다.
MAX_SKILL_PCT = 100


@dataclass(frozen=True)
class BotProfile:
    """봇 하나의 성격."""

    account_id: int
    label: str
    ruleset_id: str
    cadence_sec: int
    skill_pct: int
    token: str


def _build_profile(row: tuple) -> BotProfile:
    """조회 행을 성격으로 옮긴다.

    Args:
        row: `SELECT` 순서대로의 값들.

    Returns:
        성격.
    """
    return BotProfile(
        account_id=int(row[0]),
        label=str(row[1]),
        ruleset_id=str(row[2]),
        cadence_sec=int(row[3]),
        skill_pct=int(row[4]),
        token=str(row[5] or ""),
    )


def create_bot(
    pool: ConnectionPool,
    account_id: int,
    label: str,
    ruleset_id: str,
    cadence_sec: int,
    skill_pct: int,
) -> None:
    """계정 하나를 봇으로 만든다.

    **계정을 새로 만들지 않는다.** 봇도 익명 계정으로 태어나 승격되는 것이 사람과 같고,
    그래야 계정 id 가 그대로라 세이브·티켓·제출이 전부 따라온다.

    Args:
        pool: 연결 풀.
        account_id: 봇으로 삼을 계정.
        label: 화면에 적을 이름.
        ruleset_id: 이 봇이 쓸 규칙표.
        cadence_sec: 판 사이에 쉬는 시간(초).
        skill_pct: 실력. 낮으면 규칙 몇 줄을 끄고 나간다.
    """
    with pool.connection() as connection:
        connection.execute("UPDATE account SET is_bot = TRUE WHERE id = %s", (account_id,))
        connection.execute(
            "INSERT INTO bot_profile"
            " (account_id, label, ruleset_id, cadence_sec, skill_pct)"
            " VALUES (%s, %s, %s, %s, %s)"
            " ON CONFLICT (account_id) DO UPDATE SET"
            " label = EXCLUDED.label, ruleset_id = EXCLUDED.ruleset_id,"
            " cadence_sec = EXCLUDED.cadence_sec, skill_pct = EXCLUDED.skill_pct",
            (
                account_id,
                label,
                ruleset_id,
                cadence_sec,
                max(MIN_SKILL_PCT, min(MAX_SKILL_PCT, skill_pct)),
            ),
        )


def save_bot_token(pool: ConnectionPool, account_id: int, token: str) -> None:
    """봇의 기기 토큰을 적어 둔다.

    봇은 로그인하지 않으므로 이것이 유일한 신원이다. 401 이면 러너가 새로 받아 덮는다.

    Args:
        pool: 연결 풀.
        account_id: 대상 봇.
        token: 기기 토큰.
    """
    with pool.connection() as connection:
        connection.execute(
            "UPDATE bot_profile SET token = %s WHERE account_id = %s", (token, account_id)
        )


def list_bots(pool: ConnectionPool) -> tuple[BotProfile, ...]:
    """봇 전량을 읽는다.

    Args:
        pool: 연결 풀.

    Returns:
        계정 id 순의 성격들. 순서를 고정하는 것은 러너가 매번 같은 순서로 돌기 위해서다.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT account_id, label, ruleset_id, cadence_sec, skill_pct, token"
            " FROM bot_profile ORDER BY account_id"
        ).fetchall()
    return tuple(_build_profile(row) for row in rows)


def list_due_bots(pool: ConnectionPool) -> tuple[BotProfile, ...]:
    """지금 나갈 차례인 봇들을 읽는다.

    Args:
        pool: 연결 풀.

    Returns:
        `next_run_at` 이 지난 봇들. 계정 id 순이다.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT account_id, label, ruleset_id, cadence_sec, skill_pct, token"
            " FROM bot_profile WHERE next_run_at <= now() ORDER BY account_id"
        ).fetchall()
    return tuple(_build_profile(row) for row in rows)


def apply_bot_rest(pool: ConnectionPool, account_id: int, cadence_sec: int) -> None:
    """다음 출격 시각을 미룬다.

    **판이 끝나자마자 미룬다.** 끝난 뒤에 미루면 실패한 판에서 예외가 나갔을 때 그 봇이
    같은 판을 쉬지 않고 되풀이한다.

    Args:
        pool: 연결 풀.
        account_id: 대상 봇.
        cadence_sec: 쉴 시간(초).
    """
    with pool.connection() as connection:
        connection.execute(
            "UPDATE bot_profile SET next_run_at = %s WHERE account_id = %s",
            (datetime.now(UTC) + timedelta(seconds=max(1, cadence_sec)), account_id),
        )


def check_is_bot(pool: ConnectionPool, account_id: int) -> bool:
    """이 계정이 봇인가.

    Args:
        pool: 연결 풀.
        account_id: 볼 계정.

    Returns:
        봇이면 참. 없는 계정도 거짓이다.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT is_bot FROM account WHERE id = %s", (account_id,)
        ).fetchone()
    return bool(row and row[0])
