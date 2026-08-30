"""제출과 결과 보관 (docs/설계/7_변조방지 §4).

**제출에 결과를 담지 않는다.** 스키마에 컬럼이 없고 여기에도 인자가 없다. 결과는
`save_run_result` 로만 들어오며, 그 값은 서버가 재시뮬해서 만든 것이다.
"""

from dataclasses import dataclass
from typing import Any

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

VERDICT_VERIFIED = "verified"
VERDICT_MISMATCH = "mismatch"
VERDICT_REJECTED = "rejected"


@dataclass(frozen=True)
class StoredResult:
    """저장된 판정 하나."""

    submission_id: int
    outcome: str
    ticks: int
    player_hp: int
    verdict: str
    detail: str


def save_submission(
    pool: ConnectionPool, ticket_id: str, ruleset_payload: dict[str, Any], core_version: str
) -> int:
    """제출을 저장한다.

    Args:
        pool: 연결 풀.
        ticket_id: 이 제출이 쓰는 티켓.
        ruleset_payload: 규칙표 절. **클라이언트가 보낸 것 중 저장하는 유일한 값이다.**
        core_version: 클라이언트가 주장하는 코어 버전.

    Returns:
        만들어진 제출 id.

    Raises:
        RuntimeError: 삽입이 실패한 경우.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "INSERT INTO run_submission (ticket_id, ruleset, core_version)"
            " VALUES (%s, %s, %s) RETURNING id",
            (ticket_id, Jsonb(ruleset_payload), core_version),
        ).fetchone()
    if row is None:
        raise RuntimeError("제출을 저장하지 못했다")
    return int(row[0])


def save_run_result(pool: ConnectionPool, result: StoredResult) -> None:
    """서버가 확정한 결과를 저장한다.

    Args:
        pool: 연결 풀.
        result: 재시뮬로 확정된 결과.
    """
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO run_result"
            " (submission_id, outcome, ticks, player_hp, verdict, detail)"
            " VALUES (%s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (submission_id) DO NOTHING",
            (
                result.submission_id,
                result.outcome,
                result.ticks,
                result.player_hp,
                result.verdict,
                result.detail,
            ),
        )
