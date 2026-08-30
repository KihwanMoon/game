"""관리자 권한과 개입 기록.

**승격은 API 로 하지 않는다.** 이 모듈에 승격 함수를 두되 라우트에서 부르지 않으며,
부르는 곳은 `scripts/grant_admin.py` 하나다 — DB 접속이 있어야 돈다. 관리자 승격이
엔드포인트로 열려 있으면 그 하나가 뚫리는 순간 세계 전체가 뚫리고, 이 저장소는
클라이언트를 적대적이라고 전제한다(CLAUDE.md).

**개입은 반드시 남는다.** 남지 않으면 "이 몬스터 레벨이 왜 이렇지" 를 나중에 아무도
답할 수 없다. 경매 원장이 있는 이유와 같다.
"""

from dataclasses import dataclass
from datetime import datetime

from psycopg_pool import ConnectionPool


@dataclass(frozen=True)
class AdminAction:
    """관리자가 세계에 손댄 기록 한 줄."""

    action_id: int
    account_id: int
    handle: str
    action: str
    target: str
    detail: str
    created_at: datetime


def check_is_admin(pool: ConnectionPool, account_id: int) -> bool:
    """이 계정이 관리자인가.

    Args:
        pool: 연결 풀.
        account_id: 볼 계정.

    Returns:
        관리자면 True. 없는 계정도 False 다.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT is_admin FROM account WHERE id = %s", (account_id,)
        ).fetchone()
    return bool(row[0]) if row else False


def set_admin(pool: ConnectionPool, login_id: str, is_admin: bool) -> bool:
    """계정의 관리자 권한을 세우거나 내린다.

    **라우트에서 부르지 않는다.** `scripts/grant_admin.py` 만 부른다.

    `login_id` 로 찾는 이유는 익명 계정을 관리자로 만들 수 없게 하려는 것이다 — 익명은
    토큰만 있으면 되므로, 그 계정이 관리자면 토큰 하나가 곧 세계 전체다.

    Args:
        pool: 연결 풀.
        login_id: 대상 계정의 로그인 id.
        is_admin: 세울 값.

    Returns:
        바뀐 계정이 있으면 True.
    """
    with pool.connection() as connection:
        cursor = connection.execute(
            "UPDATE account SET is_admin = %s WHERE lower(login_id) = lower(%s)",
            (is_admin, login_id),
        )
    return cursor.rowcount == 1


def record_admin_action(
    pool: ConnectionPool, account_id: int, action: str, target: str = "", detail: str = ""
) -> None:
    """개입 하나를 기록한다.

    Args:
        pool: 연결 풀.
        account_id: 손댄 관리자.
        action: 무엇을 했는가.
        target: 무엇에 했는가.
        detail: 값이 어떻게 바뀌었는가.
    """
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO admin_action (account_id, action, target, detail) VALUES (%s, %s, %s, %s)",
            (account_id, action, target, detail),
        )


def list_admin_actions(pool: ConnectionPool, limit: int = 50) -> tuple[AdminAction, ...]:
    """최근 개입 기록을 읽는다.

    Args:
        pool: 연결 풀.
        limit: 최대 줄 수.

    Returns:
        최신순 기록들.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT a.id, a.account_id, c.handle, a.action, a.target, a.detail, a.created_at"
            " FROM admin_action a JOIN account c ON c.id = a.account_id"
            " ORDER BY a.created_at DESC, a.id DESC LIMIT %s",
            (limit,),
        ).fetchall()
    return tuple(
        AdminAction(
            action_id=int(row[0]),
            account_id=int(row[1]),
            handle=str(row[2]),
            action=str(row[3]),
            target=str(row[4]),
            detail=str(row[5]),
            created_at=row[6],
        )
        for row in rows
    )
