"""메타 세이브 서버 보관 (docs/설계/1_통합시스템설계 §5).

**통째로 갈아 끼운다.** 부분 갱신이 아니라 새 세이브를 통으로 쓴다 — 저장 도중 예외가
나도 이전 세이브가 그대로 남으며, `manage_meta.py` 가 파일에 대해 쓰는 규약과 같다.

여기서 검증하지 않는다. 검증은 `apply_run_result` 를 거친 값만 들어오도록 API 층이
보장하며, 그러지 않으면 클라이언트가 보낸 세이브를 그대로 믿는 셈이 된다.
"""

from typing import Any

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool


def load_meta_payload(pool: ConnectionPool, account_id: int) -> dict[str, Any] | None:
    """계정의 메타 세이브 절을 읽는다.

    Args:
        pool: 연결 풀.
        account_id: 계정 id.

    Returns:
        저장돼 있던 절. 없으면 None.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT payload FROM meta_save WHERE account_id = %s", (account_id,)
        ).fetchone()
    return dict(row[0]) if row is not None else None


def save_meta_payload(
    pool: ConnectionPool, account_id: int, payload: dict[str, Any], core_version: str
) -> None:
    """계정의 메타 세이브를 통째로 쓴다.

    Args:
        pool: 연결 풀.
        account_id: 계정 id.
        payload: 저장할 절.
        core_version: 이 세이브를 만든 코어 버전.
    """
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO meta_save (account_id, payload, core_version, updated_at)"
            " VALUES (%s, %s, %s, now())"
            " ON CONFLICT (account_id) DO UPDATE"
            " SET payload = EXCLUDED.payload,"
            "     core_version = EXCLUDED.core_version,"
            "     updated_at = now()",
            (account_id, Jsonb(payload), core_version),
        )
