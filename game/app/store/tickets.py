"""런 티켓 발급과 소비 — **시드의 유일한 출처** (docs/설계/7_변조방지 T2·T6).

클라이언트가 시드를 정하면 유리한 시드가 나올 때까지 돌려 보고 그것만 제출할 수 있다.
그래서 시드는 여기서만 나오고, 예측 불가능해야 하며(`secrets`), 티켓 하나는 한 번만
쓰인다.

만료를 두는 이유는 골라 담기를 좁히기 위해서다. 티켓을 여러 개 받아 유리한 것만 완주하고
나머지를 버리는 것까지는 막지 못하지만(§5 의 남는 문제), 무한히 쌓아 두는 것은 막는다.
"""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from psycopg_pool import ConnectionPool

from game.schemas.run_ticket import MAX_SEED, RunMode

# 티켓 유효 기간. 짧으면 정상 플레이가 끊기고 길면 골라 담기가 열린다.
# 런 목표 시간이 15~25분이므로(GDD §1) 그 두 배로 잡았다 (결정/1_결정대기목록 #46).
TICKET_TTL = timedelta(minutes=50)

# 티켓 id 의 무작위 길이. 서버 발급 티켓은 로컬 것(`local:` 접두어)과 구분된다.
TICKET_ID_BYTES = 12


@dataclass(frozen=True)
class IssuedTicket:
    """발급된 티켓 하나."""

    ticket_id: str
    seed: int
    room_id: str
    floor: int
    mode: str
    core_version: str


def create_seed() -> int:
    """예측 불가능한 시드를 만든다.

    상한은 `MAX_SEED` 다. 넘기면 TypeScript 코어가 그 값을 담지 못해 클라이언트가 다른
    판을 돈다 (docs/설계/3 §10-2 의 이식 제약).

    Returns:
        0 이상 MAX_SEED 이하의 정수.
    """
    return secrets.randbelow(MAX_SEED + 1)


def create_ticket(
    pool: ConnectionPool,
    account_id: int,
    room_id: str,
    core_version: str,
    floor: int = 1,
    mode: RunMode = RunMode.PRACTICE,
    wanted_seed: int | None = None,
    forced_seed: int | None = None,
    ttl: timedelta = TICKET_TTL,
) -> IssuedTicket:
    """티켓을 발급한다.

    Args:
        pool: 연결 풀.
        account_id: 발급 대상 계정.
        room_id: 방 id.
        core_version: 이 서버가 도는 코어 버전.
        floor: 층.
        mode: 런 모드.
        wanted_seed: **클라이언트가** 제안한 시드. 연습 모드에서만 반영한다 — 순위에
            반영되는 판에서 받으면 유리한 시드를 골라 담을 수 있다 (T2).
        forced_seed: **서버가** 정한 시드. 모드와 무관하게 그대로 쓴다. 데일리가 이것을
            쓴다 — 모두가 같은 시드를 받아야 성립하는데, 그것은 클라이언트가 고른 것이
            아니라 서버가 날짜에서 파생한 값이므로 T2 와 무관하다. 둘을 한 인자로 두면
            "누가 정했는가" 가 흐려지고, 그 구분이 이 게이트의 전부다.
        ttl: 유효 기간. 데일리는 짧게 잡는다 — "받아 두고 연습한 뒤 제출" 을 좁힌다.

    Returns:
        발급된 티켓.

    Raises:
        RuntimeError: 삽입이 실패한 경우.
    """
    ticket_id = secrets.token_urlsafe(TICKET_ID_BYTES)
    if forced_seed is not None:
        seed = forced_seed
    elif mode is RunMode.PRACTICE and wanted_seed is not None:
        seed = wanted_seed
    else:
        seed = create_seed()
    if not 0 <= seed <= MAX_SEED:
        raise ValueError(f"시드가 이식 범위를 벗어났다: {seed}")
    expires_at = datetime.now(UTC) + ttl
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO run_ticket"
            " (id, account_id, seed, room_id, floor, mode, core_version, expires_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (ticket_id, account_id, seed, room_id, floor, str(mode), core_version, expires_at),
        )
    return IssuedTicket(
        ticket_id=ticket_id,
        seed=seed,
        room_id=room_id,
        floor=floor,
        mode=str(mode),
        core_version=core_version,
    )


def find_open_ticket(pool: ConnectionPool, ticket_id: str, account_id: int) -> IssuedTicket | None:
    """아직 쓰지 않았고 만료되지 않은 티켓을 찾는다.

    **계정을 함께 본다.** 남의 티켓으로 제출하는 것을 막는다.

    Args:
        pool: 연결 풀.
        ticket_id: 티켓 id.
        account_id: 제출한 계정.

    Returns:
        쓸 수 있는 티켓. 없거나 이미 썼거나 만료됐으면 None.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT id, seed, room_id, floor, mode, core_version FROM run_ticket"
            " WHERE id = %s AND account_id = %s"
            " AND consumed_at IS NULL AND expires_at > now()",
            (ticket_id, account_id),
        ).fetchone()
    if row is None:
        return None
    return IssuedTicket(
        ticket_id=str(row[0]),
        seed=int(row[1]),
        room_id=str(row[2]),
        floor=int(row[3]),
        mode=str(row[4]),
        core_version=str(row[5]),
    )


def mark_ticket_consumed(pool: ConnectionPool, ticket_id: str) -> bool:
    """티켓을 쓴 것으로 표시한다.

    조건부 갱신이다 — 이미 쓴 티켓이면 아무 행도 바뀌지 않는다. 같은 티켓으로 두 번
    제출하는 경쟁 상태를 여기서 끊는다 (T6).

    Args:
        pool: 연결 풀.
        ticket_id: 티켓 id.

    Returns:
        이번 호출이 실제로 소비했으면 True.
    """
    with pool.connection() as connection:
        cursor = connection.execute(
            "UPDATE run_ticket SET consumed_at = now() WHERE id = %s AND consumed_at IS NULL",
            (ticket_id,),
        )
        return cursor.rowcount == 1
