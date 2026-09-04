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


@dataclass(frozen=True)
class RunRecord:
    """지나간 판 하나. **결과는 서버가 재시뮬해서 만든 값이다** (§4)."""

    submission_id: int
    room_id: str
    floor: int
    seed: int
    outcome: str
    ticks: int
    player_hp: int
    verdict: str
    submitted_at: str


def list_recent_runs(pool: ConnectionPool, account_id: int, limit: int) -> tuple[RunRecord, ...]:
    """이 계정이 최근에 돈 판들을 새것부터 읽는다.

    **이벤트 로그는 없다.** 저장하는 것은 제출(규칙표)과 판정(결과)뿐이라, 여기서 낼 수
    있는 것은 「어떤 판을 돌았고 어떻게 끝났는가」까지다 — 「그 판이 어떻게 돌았는가」는
    시드와 규칙표로 다시 돌려야 나온다.

    **판정이 없는 제출도 낸다.** 검증 전인 것과 없는 것이 같아 보이면, 서버가 밀렸을 때
    화면이 「안 돌았다」로 읽힌다.

    Args:
        pool: 연결 풀.
        account_id: 대상 계정.
        limit: 몇 개까지.

    Returns:
        새것부터의 판들.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT s.id, t.room_id, t.floor, t.seed,"
            " COALESCE(r.outcome, ''), COALESCE(r.ticks, 0), COALESCE(r.player_hp, 0),"
            " COALESCE(r.verdict, ''), s.submitted_at"
            " FROM run_submission s"
            " JOIN run_ticket t ON t.id = s.ticket_id"
            " LEFT JOIN run_result r ON r.submission_id = s.id"
            " WHERE t.account_id = %s"
            " ORDER BY s.submitted_at DESC, s.id DESC"
            " LIMIT %s",
            (account_id, limit),
        ).fetchall()
    return tuple(
        RunRecord(
            submission_id=int(row[0]),
            room_id=str(row[1] or ""),
            floor=int(row[2] or 0),
            seed=int(row[3] or 0),
            outcome=str(row[4] or ""),
            ticks=int(row[5] or 0),
            player_hp=int(row[6] or 0),
            verdict=str(row[7] or ""),
            submitted_at=row[8].isoformat() if row[8] is not None else "",
        )
        for row in rows
    )
