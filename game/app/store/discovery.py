"""도감 해금 — 무엇을 처음 손에 넣어 봤는가.

**소유가 아니라 이력을 남긴다.** 지금 가진 것으로 계산하면 아이템을 판 순간 도감이
다시 잠기고, 그러면 도감이 "본 것" 이 아니라 "지금 가진 것" 이 된다.

**결정론과 무관하다.** 코어는 이 표를 모른다 — 여기 있는 것은 화면이 무엇을 밝혀
보여줄지뿐이며, 런 등식의 어느 항도 아니다 (R5).
"""

from psycopg_pool import ConnectionPool

# 해금 갈래. 아이템과 스킬을 한 표에 담되 갈래로 가른다 — 같은 문자열 id 가 양쪽에
# 있어도 서로를 열지 않아야 한다.
KIND_ITEM = "ITEM"
KIND_SKILL = "SKILL"


def record_discovery(pool: ConnectionPool, account_id: int, kind: str, ref_id: str) -> None:
    """해금 한 줄을 남긴다. 이미 있으면 아무 일도 하지 않는다.

    처음 얻은 시각을 덮어쓰지 않는 이유는, 나중에 "언제 처음 봤는가" 를 물을 수 있어야
    하기 때문이다 — 덮어쓰면 마지막으로 얻은 시각이 되어 뜻이 달라진다.

    Args:
        pool: 연결 풀.
        account_id: 해금하는 계정.
        kind: `KIND_ITEM` 또는 `KIND_SKILL`.
        ref_id: 카탈로그 id 또는 스킬 id.
    """
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO account_discovery (account_id, kind, ref_id) VALUES (%s, %s, %s)"
            " ON CONFLICT DO NOTHING",
            (account_id, kind, ref_id),
        )


def list_discovery(pool: ConnectionPool, account_id: int, kind: str) -> frozenset[str]:
    """그 갈래에서 이 계정이 밝힌 것들을 읽는다.

    Args:
        pool: 연결 풀.
        account_id: 대상 계정.
        kind: `KIND_ITEM` 또는 `KIND_SKILL`.

    Returns:
        밝힌 id 들. 없으면 빈 집합.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT ref_id FROM account_discovery WHERE account_id = %s AND kind = %s",
            (account_id, kind),
        ).fetchall()
    return frozenset(str(row[0]) for row in rows)
