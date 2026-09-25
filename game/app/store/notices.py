"""알림 (2026-09-25) — 판을 넘어 쌓이는 것과 없는 동안 생긴 일을 한 곳에 둔다.

**문구는 부르는 쪽이 서버에서 확정한 것만 넘긴다.** 이 모듈은 받은 것을 적고 읽을 뿐이다.
"""

from dataclasses import dataclass
from datetime import datetime

from psycopg_pool import ConnectionPool

# 한 번에 싣는 알림 수. 알림함은 기록장이 아니라 「요즘 무슨 일이 있었나」다 — 쉰 건이면
# 며칠치가 들어가고, 그보다 오래된 것은 각 패널(지나간 판·내 둔갑·경매)에 남아 있다.
NOTICE_LIMIT = 50

# 알림 종류. 화면이 글리프·색을 고르는 열쇠이고, 문구를 짜는 데는 안 쓴다.
KIND_RUN = "run"
KIND_FLOOR = "floor"
KIND_RECORD = "record"
KIND_DOPPEL = "doppel"
KIND_AUCTION = "auction"
KIND_REJECTED = "rejected"


@dataclass(frozen=True)
class Notice:
    """알림 한 건."""

    notice_id: int
    kind: str
    title: str
    body: str
    created_at: datetime
    is_read: bool


def save_notice(pool: ConnectionPool, account_id: int, kind: str, title: str, body: str) -> int:
    """알림 한 건을 적는다.

    Args:
        pool: 연결 풀.
        account_id: 받을 계정.
        kind: 알림 종류 (`KIND_*`).
        title: 한 줄 제목.
        body: 서버가 확정한 본문. 항목은 `·` 로 잇는다 — 화면이 그것으로 끊는다.

    Returns:
        새 알림 id.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "INSERT INTO notice (account_id, kind, title, body) VALUES (%s, %s, %s, %s)"
            " RETURNING id",
            (account_id, kind, title, body),
        ).fetchone()
    return int(row[0]) if row is not None else 0


def list_notices(
    pool: ConnectionPool, account_id: int, limit: int = NOTICE_LIMIT
) -> tuple[Notice, ...]:
    """최근 알림을 새것부터 읽는다.

    Args:
        pool: 연결 풀.
        account_id: 대상 계정.
        limit: 최대 건수.

    Returns:
        알림들. id 내림차순이다 — 시각은 같을 수 있지만 id 는 안 겹친다 (R5 와 같은 규율).
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT id, kind, title, body, created_at, read_at IS NOT NULL FROM notice"
            " WHERE account_id = %s ORDER BY id DESC LIMIT %s",
            (account_id, limit),
        ).fetchall()
    return tuple(
        Notice(
            notice_id=int(row[0]),
            kind=str(row[1]),
            title=str(row[2]),
            body=str(row[3]),
            created_at=row[4],
            is_read=bool(row[5]),
        )
        for row in rows
    )


def count_unread_notices(pool: ConnectionPool, account_id: int) -> int:
    """안 읽은 알림 수. **싣는 쉰 건 밖의 것도 센다** — 숫자가 목록보다 작으면 거짓말이다.

    Args:
        pool: 연결 풀.
        account_id: 대상 계정.

    Returns:
        건수.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT count(*) FROM notice WHERE account_id = %s AND read_at IS NULL",
            (account_id,),
        ).fetchone()
    return int(row[0]) if row is not None else 0


def apply_notices_read(pool: ConnectionPool, account_id: int, up_to_id: int) -> int:
    """그 id 까지의 알림을 읽음으로 적는다.

    **id 로 끊는다.** 「전부 읽음」으로 적으면 알림함을 여는 사이에 도착한 것까지 읽은
    것이 된다 — 본 적 없는 것이 읽음이 되는 자리다.

    Args:
        pool: 연결 풀.
        account_id: 대상 계정. 남의 알림은 못 건드린다.
        up_to_id: 화면이 본 가장 새 알림 id.

    Returns:
        새로 읽음이 된 건수.
    """
    with pool.connection() as connection:
        cursor = connection.execute(
            "UPDATE notice SET read_at = now()"
            " WHERE account_id = %s AND id <= %s AND read_at IS NULL",
            (account_id, up_to_id),
        )
    return cursor.rowcount
