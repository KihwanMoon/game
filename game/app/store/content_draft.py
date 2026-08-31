"""콘텐츠 초안 — 편집과 발행을 가른다.

**초안은 아직 게임이 아니다.** 스킬·블록·밸런스·룸·적 규칙표는 두 코어가 함께 읽는
실행 자산이고, 브라우저는 빌드 시점에 번들로 인라인한다. 런타임에 DB 를 보게 만들면
서버가 없을 때 게임이 안 돌고, 그것은 이 저장소가 지키는 전제다.

그래서 편집·검증·발행이 갈린다. 발행이 사람 손을 타는 것이 설계다 — 자동으로 반영되면
순위표 시즌이 아무도 모르게 갈린다.
"""

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from game.config import (
    BALANCE_PATH,
    BLOCKS_PATH,
    ENEMY_RULESETS_PATH,
    ROOM_TEMPLATES_PATH,
    SKILLS_PATH,
)

# 편집할 수 있는 자산과 그 파일. **아이템은 여기 없다** — 아이템 카탈로그만 DB 가
# 정본이고 런타임에 바뀐다 (설계/4_아이템 §15.7). 이쪽은 전부 파일이 정본이다.
DRAFT_ASSETS: dict[str, tuple[str, str]] = {
    "skills": (str(SKILLS_PATH), "skill_list_version"),
    "blocks": (str(BLOCKS_PATH), "block_list_version"),
    "balance": (str(BALANCE_PATH), "balance_version"),
    "rooms": (str(ROOM_TEMPLATES_PATH), "room_list_version"),
    "enemies": (str(ENEMY_RULESETS_PATH), "enemy_list_version"),
}


def save_draft(pool: ConnectionPool, asset: str, payload: dict, note: str, account_id: int) -> None:
    """초안을 저장한다. 같은 자산이 있으면 덮어쓴다.

    **게임에는 아무 영향이 없다.** 반영은 발행이 한다.

    Args:
        pool: 연결 풀.
        asset: 자산 이름.
        payload: 파일 전체 내용.
        note: 무엇을 왜 고쳤는가.
        account_id: 고친 관리자.
    """
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO content_draft (asset, payload, note, updated_by)"
            " VALUES (%s, %s, %s, %s)"
            " ON CONFLICT (asset) DO UPDATE SET payload = EXCLUDED.payload,"
            " note = EXCLUDED.note, updated_by = EXCLUDED.updated_by, updated_at = now()",
            (asset, Jsonb(payload), note, account_id),
        )


def read_draft(pool: ConnectionPool, asset: str) -> dict | None:
    """초안 하나를 읽는다.

    Args:
        pool: 연결 풀.
        asset: 자산 이름.

    Returns:
        초안 절. 없으면 None.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT payload FROM content_draft WHERE asset = %s", (asset,)
        ).fetchone()
    return None if row is None else dict(row[0])


def list_drafts(pool: ConnectionPool) -> tuple[tuple[str, str, str], ...]:
    """초안 목록을 읽는다. 본문은 담지 않는다 — 목록은 목록이다.

    Args:
        pool: 연결 풀.

    Returns:
        (자산, 사유, 고친 시각) 들.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT asset, note, to_char(updated_at, 'YYYY-MM-DD HH24:MI')"
            " FROM content_draft ORDER BY asset"
        ).fetchall()
    return tuple((str(row[0]), str(row[1]), str(row[2])) for row in rows)


def remove_draft(pool: ConnectionPool, asset: str) -> None:
    """초안을 버린다. **파일은 안 건드린다** — 발행 전이라 게임에 없던 것이다.

    Args:
        pool: 연결 풀.
        asset: 자산 이름.
    """
    with pool.connection() as connection:
        connection.execute("DELETE FROM content_draft WHERE asset = %s", (asset,))
