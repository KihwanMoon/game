"""카탈로그 초안 — 아이템 편집과 발행을 가른다 (설계/9_에이전트_운영 §3.2).

**아이템만 초안을 안 거치고 있었다.** 스킬·블록·밸런스·룸·적 규칙표는 사람이 발행을
눌러야 반영되는데, 카탈로그는 정본이 DB 라 등록·수정·폐기가 **즉시** 세계를 바꿨다.
다른 넷은 문이 있고 아이템만 열려 있었다는 뜻이고, 아이템 에이전트를 붙이면 그 문으로
검토 없이 세계가 바뀐다.

**초안은 아직 아이템이 아니다.** 여기 있는 것은 게임이 안 읽는다 — 카탈로그를 읽는
`list_catalog` 는 `item_catalog` 만 본다. 발행이 그것을 옮긴다.

**세대는 발행이 한 번만 올린다.** 예전에는 조작마다 올라서, 아이템 열 개를 손보면 시즌
경계가 열 번 그였다 (§15.8). 한 번 발행이 한 번 경계다.
"""

from dataclasses import dataclass

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

# 초안이 담을 수 있는 조작. **정본이 여기 하나다** — DB 의 CHECK 제약이 같은 목록을 들고
# 있고, 둘이 어긋나면 초안을 올리는 순간 터진다.
ACTION_ITEM = "item"
ACTION_EDIT = "edit"
ACTION_RETIRE = "retire"
ACTION_RESTORE = "restore"

DRAFT_ACTIONS = (ACTION_ITEM, ACTION_EDIT, ACTION_RETIRE, ACTION_RESTORE)


@dataclass(frozen=True)
class CatalogDraft:
    """쌓여 있는 조작 하나."""

    catalog_id: str
    action: str
    payload: dict
    reason: str
    handle: str
    updated_at: str


def save_catalog_draft(
    pool: ConnectionPool,
    catalog_id: str,
    action: str,
    payload: dict,
    reason: str,
    account_id: int,
) -> None:
    """초안 하나를 쌓는다. 같은 아이템이 있으면 덮어쓴다.

    **게임에는 아무 영향이 없다.** 반영은 발행이 한다.

    덮어쓰는 이유는 순서 때문이다. 같은 아이템에 조작을 쌓아 두면 발행할 때 어느 것을
    먼저 먹일지가 문제가 되고, 그 순서는 아무도 안 정했다 — 마지막 뜻만 남기면 그
    질문이 생기지 않는다.

    Args:
        pool: 연결 풀.
        catalog_id: 대상 아이템.
        action: 무슨 조작인가.
        payload: 조작에 필요한 절. 폐기·복구는 빈 절이어도 된다.
        reason: 왜 하는가.
        account_id: 올린 계정.

    Raises:
        ValueError: 모르는 조작인 경우.
    """
    if action not in DRAFT_ACTIONS:
        raise ValueError(f"모르는 조작이다: {action}")
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO catalog_draft (catalog_id, action, payload, reason, updated_by)"
            " VALUES (%s, %s, %s, %s, %s)"
            " ON CONFLICT (catalog_id) DO UPDATE SET action = EXCLUDED.action,"
            " payload = EXCLUDED.payload, reason = EXCLUDED.reason,"
            " updated_by = EXCLUDED.updated_by, updated_at = now()",
            (catalog_id, action, Jsonb(payload), reason, account_id),
        )


def list_catalog_drafts(pool: ConnectionPool) -> tuple[CatalogDraft, ...]:
    """쌓여 있는 조작을 오래된 것부터 읽는다.

    **누가 올렸는지 함께 준다.** 에이전트가 올린 것과 사람이 올린 것을 화면에서 못
    가르면, 검토한다는 것이 무엇을 보는 일인지가 흐려진다.

    Args:
        pool: 연결 풀.

    Returns:
        조작들. 없으면 빈 튜플.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT d.catalog_id, d.action, d.payload, d.reason,"
            " COALESCE(a.handle, ''), to_char(d.updated_at, 'YYYY-MM-DD HH24:MI')"
            " FROM catalog_draft d"
            " LEFT JOIN account a ON a.id = d.updated_by"
            " ORDER BY d.updated_at, d.catalog_id"
        ).fetchall()
    return tuple(
        CatalogDraft(
            catalog_id=str(row[0]),
            action=str(row[1]),
            payload=dict(row[2]),
            reason=str(row[3]),
            handle=str(row[4]),
            updated_at=str(row[5]),
        )
        for row in rows
    )


def remove_catalog_draft(pool: ConnectionPool, catalog_id: str) -> bool:
    """초안 하나를 버린다.

    Args:
        pool: 연결 풀.
        catalog_id: 버릴 아이템.

    Returns:
        버린 것이 있으면 True.
    """
    with pool.connection() as connection:
        cursor = connection.execute(
            "DELETE FROM catalog_draft WHERE catalog_id = %s", (catalog_id,)
        )
    return cursor.rowcount == 1


def clear_catalog_drafts(pool: ConnectionPool) -> int:
    """쌓인 것을 전부 비운다 — 발행이 끝난 뒤에 부른다.

    Args:
        pool: 연결 풀.

    Returns:
        비운 줄 수.
    """
    with pool.connection() as connection:
        cursor = connection.execute("DELETE FROM catalog_draft")
    return cursor.rowcount
