"""관리자 등급과 개입 기록.

**권한은 이분법이 아니다** (2026-09-05, 설계/9_에이전트_운영 §3.1). 예전에는 불리언
하나가 콘텐츠 발행·아이템 지급·회수·카탈로그 편집·몬스터 레벨을 전부 열었다. 에이전트를
붙이려면 그것으로는 안 된다 — CS 에이전트가 콘텐츠를 발행할 수 있으면 안 되고, 밸런스
에이전트가 아이템을 지급할 수 있으면 안 된다.

**발행은 어느 등급에도 안 딸려 있지 않다.** `owner` 만 가지며 `owner` 는 사람만 받는다.

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

# 관리자 등급 (설계/9_에이전트_운영 §3.1). **정본이 여기 하나다** — DB 의 CHECK 제약이
# 같은 목록을 들고 있고, 둘이 어긋나면 세우는 순간 터진다.
ROLE_OBSERVER = "observer"
ROLE_AUTHOR = "author"
ROLE_OPERATOR = "operator"
ROLE_OWNER = "owner"

# 넓은 것부터 적는다 — 화면과 도움말이 이 순서로 보여 준다.
ADMIN_ROLES = (ROLE_OWNER, ROLE_OPERATOR, ROLE_AUTHOR, ROLE_OBSERVER)


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


def read_admin_role(pool: ConnectionPool, account_id: int) -> str:
    """이 계정의 관리자 등급.

    Args:
        pool: 연결 풀.
        account_id: 볼 계정.

    Returns:
        등급 문자열. 관리자가 아니거나 없는 계정이면 **빈 문자열**이다 — None 을 돌려주면
        부르는 쪽마다 None 검사를 다시 쓰게 되고, 한 곳이 빠지면 그 자리가 열린다.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT admin_role FROM account WHERE id = %s", (account_id,)
        ).fetchone()
    return str(row[0]) if row and row[0] else ""


def check_role_allows(role: str, wanted: str) -> bool:
    """이 등급이 원하는 등급의 일을 할 수 있는가.

    **사다리가 아니다.** `author` 와 `operator` 는 서로를 포함하지 않는다 — 콘텐츠를 쓰는
    에이전트가 아이템을 회수할 수 있으면 등급을 나눈 뜻이 없다. `owner` 만 전부 덮고,
    읽기(`observer`)는 누구나 한다.

    Args:
        role: 가진 등급.
        wanted: 그 일에 필요한 등급.

    Returns:
        할 수 있으면 True.
    """
    if role not in ADMIN_ROLES:
        return False
    if role == ROLE_OWNER or wanted == ROLE_OBSERVER:
        return True
    return role == wanted


def set_admin_role(pool: ConnectionPool, login_id: str, role: str) -> bool:
    """계정의 관리자 등급을 세우거나 내린다.

    **라우트에서 부르지 않는다.** `scripts/grant_admin.py` 만 부른다. 승격이 엔드포인트로
    열려 있으면 그 하나가 뚫리는 순간 세계 전체가 뚫린다.

    `login_id` 로 찾는 이유는 익명 계정을 관리자로 만들 수 없게 하려는 것이다 — 익명은
    토큰만 있으면 되므로, 그 계정이 관리자면 토큰 하나가 곧 세계 전체다.

    Args:
        pool: 연결 풀.
        login_id: 대상 계정의 로그인 id.
        role: 세울 등급. 빈 문자열이면 권한을 내린다.

    Returns:
        바뀐 계정이 있으면 True.

    Raises:
        ValueError: 모르는 등급인 경우. 오타를 조용히 「권한 없음」으로 만들면, 막힌
            것인지 이름을 틀린 것인지 화면에서 구별되지 않는다.
    """
    if role and role not in ADMIN_ROLES:
        raise ValueError(f"모르는 등급이다: {role}")
    with pool.connection() as connection:
        cursor = connection.execute(
            "UPDATE account SET admin_role = %s WHERE lower(login_id) = lower(%s)",
            (role or None, login_id),
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
