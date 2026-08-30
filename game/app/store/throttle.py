"""로그인 시도 제한 (docs/설계/7_변조방지 S0).

**scrypt 만으로는 못 막는다.** 시도당 수십 ms 가 들어도 병렬로 보내면 서버 CPU 만 태우고
시도는 계속된다. 세어서 끊는 수단이 따로 있어야 한다.

아이디로 센다. 그것이 지켜야 할 대상이기 때문이며, 주소로만 세면 프록시 뒤의 정상
사용자가 함께 막히고 주소를 바꾸는 쪽은 안 막힌다. **남는 것은 아이디를 바꿔 가며
훑는 살포다** — 계정이 늘면 주소 기준 제한을 함께 둔다 (docs/결정/1_결정대기목록).

성공하면 세던 것을 지운다. 비밀번호를 한 번 틀렸다가 맞춘 사람이 다음 로그인에서
막히면 안 된다.
"""

from dataclasses import dataclass
from datetime import timedelta

from psycopg_pool import ConnectionPool

# 창 안에서 이만큼 실패하면 잠근다. 사람이 오타를 내는 횟수보다 넉넉하고, 대량 시도에는
# 좁다 — 5회/10분이면 시간당 30회이고 웬만한 비밀번호는 그 속도로 뚫리지 않는다.
MAX_FAILURES = 5
FAILURE_WINDOW = timedelta(minutes=10)

# 기록을 지우는 기준. 창보다 넉넉히 잡아 조사에 쓸 수 있게 두되, 무한히 쌓지 않는다.
RETENTION = timedelta(days=7)


@dataclass(frozen=True)
class ThrottleState:
    """지금 이 아이디가 얼마나 막혀 있는가."""

    failures: int
    is_locked: bool


def count_recent_failures(pool: ConnectionPool, login_id: str) -> int:
    """창 안의 연속 실패 수를 센다.

    Args:
        pool: 연결 풀.
        login_id: 정규화된 아이디.

    Returns:
        창 안의 실패 횟수.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT count(*) FROM login_attempt"
            " WHERE login_id = %s AND is_ok = false AND attempted_at > now() - %s",
            (login_id, FAILURE_WINDOW),
        ).fetchone()
    return int(row[0]) if row is not None else 0


def check_login_allowed(pool: ConnectionPool, login_id: str) -> ThrottleState:
    """지금 시도해도 되는지 본다.

    Args:
        pool: 연결 풀.
        login_id: 정규화된 아이디.

    Returns:
        실패 수와 잠김 여부.
    """
    failures = count_recent_failures(pool, login_id)
    return ThrottleState(failures=failures, is_locked=failures >= MAX_FAILURES)


def record_login_attempt(pool: ConnectionPool, login_id: str, is_ok: bool) -> None:
    """시도 하나를 남긴다. 성공이면 이 아이디의 실패 기록을 지운다.

    성공에도 한 줄을 남기는 이유는 조사다 — "언제부터 남이 들어와 있었나" 를 실패
    기록만으로는 알 수 없다.

    Args:
        pool: 연결 풀.
        login_id: 정규화된 아이디.
        is_ok: 성공했는가.
    """
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO login_attempt (login_id, is_ok) VALUES (%s, %s)", (login_id, is_ok)
        )
        if is_ok:
            connection.execute(
                "DELETE FROM login_attempt WHERE login_id = %s AND is_ok = false", (login_id,)
            )
        # 오래된 것은 그때그때 지운다. 별도 배치를 두면 그것이 안 돌 때 표가 자란다.
        connection.execute(
            "DELETE FROM login_attempt WHERE attempted_at < now() - %s", (RETENTION,)
        )
