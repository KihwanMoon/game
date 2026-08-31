"""드롭 표 저장 — 등급 가중치·아이템 가중치·천장·굴림 기록 (설계/4_아이템 §15).

**두 표로 갈라 둔 것이 이 설계의 전부다.** 등급 분포(`drop_grade_weight`)와 등급 안의
아이템 비율(`drop_item_weight`)을 한 표에 섞으면, 보통 등급에 아이템 하나를 더하는 순간
유물 등급의 확률까지 내려간다 — 콘텐츠를 늘리는 일이 밸런스를 흔드는 일이 된다.

여기 있는 값은 **자리를 잡아 둔 것**이지 밸런스가 아니다. 확률 수식은 나중에 정한다.
"""

from psycopg_pool import ConnectionPool

from game.app.items.drops import GRADE_MISS
from game.schemas.item import GRADE_COMMON, GRADE_FINE, GRADE_RELIC, ItemCatalogEntry

# 소스 갈래. 소스별 표가 없으면 `ANY` 로 떨어진다.
SOURCE_ANY = "ANY"
SOURCE_MONSTER = "MONSTER_KIND"

# 등급 가중치의 출발값. **밸런스가 아니라 자리다** (§15.6). 처치마다 굴리므로 런당
# 60% 이던 예전보다 훨씬 낮아야 하고, 한 방에 넷을 잡는다고 보면 굴림당 1/4 쯤이 된다.
# `GRADE_MISS` 는 아무것도 안 나오는 몫이다 — 등급과 같은 저울에 올려야 "안 나옴" 도
# 분포의 일부가 된다.
DEFAULT_GRADE_WEIGHTS: tuple[tuple[str, int, int], ...] = (
    (GRADE_MISS, 820, 0),
    (GRADE_COMMON, 150, 0),
    (GRADE_FINE, 27, 6),
    (GRADE_RELIC, 3, 4),
)


def find_source(pool: ConnectionPool, kind: str, ref_id: str = "") -> int | None:
    """드롭 소스의 id 를 찾는다.

    Args:
        pool: 연결 풀.
        kind: 소스 갈래.
        ref_id: 소스 식별자. `ANY` 는 빈 문자열이다.

    Returns:
        소스 id. 없으면 None.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT id FROM drop_source WHERE kind = %s AND ref_id = %s", (kind, ref_id)
        ).fetchone()
    return None if row is None else int(row[0])


def save_source(pool: ConnectionPool, kind: str, ref_id: str = "") -> int:
    """드롭 소스를 만들거나 찾는다.

    Args:
        pool: 연결 풀.
        kind: 소스 갈래.
        ref_id: 소스 식별자.

    Returns:
        소스 id.
    """
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO drop_source (kind, ref_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (kind, ref_id),
        )
    found = find_source(pool, kind, ref_id)
    if found is None:
        raise RuntimeError(f"드롭 소스를 만들지 못했다: {kind}/{ref_id}")
    return found


def read_grade_weights(pool: ConnectionPool, source_id: int) -> tuple[tuple[str, int, int], ...]:
    """이 소스의 등급 가중치를 읽는다.

    Args:
        pool: 연결 풀.
        source_id: 소스 id.

    Returns:
        (등급, 가중치, 레벨당 배율%) 들. 등급 이름 순.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT grade, weight, level_scale_pct FROM drop_grade_weight"
            " WHERE source_id = %s ORDER BY grade",
            (source_id,),
        ).fetchall()
    return tuple((str(row[0]), int(row[1]), int(row[2])) for row in rows)


def read_item_weights(
    pool: ConnectionPool, source_id: int, grade: str, floor: int
) -> tuple[tuple[str, int], ...]:
    """그 등급 안의 아이템 가중치를 읽는다. 폐기·미개방 층은 빠진다.

    Args:
        pool: 연결 풀.
        source_id: 소스 id.
        grade: 등급.
        floor: 지금 층. `min_floor` 가 이보다 높으면 아직 안 나온다 (D1).

    Returns:
        (catalog_id, 가중치) 들. id 순.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT w.catalog_id, w.weight FROM drop_item_weight w"
            " JOIN item_catalog c ON c.catalog_id = w.catalog_id"
            " WHERE w.source_id = %s AND w.grade = %s AND NOT c.is_retired AND c.min_floor <= %s"
            " ORDER BY w.catalog_id",
            (source_id, grade, floor),
        ).fetchall()
    return tuple((str(row[0]), int(row[1])) for row in rows)


def apply_drop_seed(pool: ConnectionPool, catalog: dict[str, ItemCatalogEntry]) -> int:
    """`ANY` 소스의 기본 표를 채운다. 이미 있으면 두고 넘어간다.

    아이템 가중치는 등급 안에서 모두 1 이다 — 아이템별 차등은 밸런스이고, 그것은
    나중에 정한다. 지금 필요한 것은 **두 단계가 실제로 도는 것**이다.

    Args:
        pool: 연결 풀.
        catalog: 아이템 카탈로그.

    Returns:
        채운 아이템 가중치 줄 수. 이미 있었으면 0.
    """
    source_id = save_source(pool, SOURCE_ANY)
    if read_grade_weights(pool, source_id):
        return 0
    with pool.connection() as connection:
        for grade, weight, scale in DEFAULT_GRADE_WEIGHTS:
            if grade == GRADE_MISS:
                continue
            connection.execute(
                "INSERT INTO drop_grade_weight (source_id, grade, weight, level_scale_pct)"
                " VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (source_id, grade, weight, scale),
            )
    filled = 0
    with pool.connection() as connection:
        for entry in sorted(catalog.values(), key=lambda item: item.catalog_id):
            if entry.is_retired:
                continue
            connection.execute(
                "INSERT INTO drop_item_weight (source_id, grade, catalog_id, weight)"
                " VALUES (%s, %s, %s, 1) ON CONFLICT DO NOTHING",
                (source_id, entry.grade, entry.catalog_id),
            )
            filled += 1
    return filled


def read_pity(pool: ConnectionPool, account_id: int) -> dict[str, int]:
    """이 계정의 연속 미획득 수를 읽는다 (D2).

    Args:
        pool: 연결 풀.
        account_id: 대상 계정.

    Returns:
        등급에서 연속 미획득 수로.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT grade, misses FROM drop_pity WHERE account_id = %s", (account_id,)
        ).fetchall()
    return {str(row[0]): int(row[1]) for row in rows}


def apply_pity(pool: ConnectionPool, account_id: int, grade: str, is_hit: bool) -> None:
    """천장 카운터를 올리거나 되돌린다.

    Args:
        pool: 연결 풀.
        account_id: 대상 계정.
        grade: 등급.
        is_hit: 그 등급이 나왔는가. 나왔으면 0 으로 되돌린다.
    """
    statement = (
        "INSERT INTO drop_pity (account_id, grade, misses) VALUES (%s, %s, 0)"
        " ON CONFLICT (account_id, grade) DO UPDATE SET misses = 0"
        if is_hit
        else "INSERT INTO drop_pity (account_id, grade, misses) VALUES (%s, %s, 1)"
        " ON CONFLICT (account_id, grade) DO UPDATE SET misses = drop_pity.misses + 1"
    )
    with pool.connection() as connection:
        connection.execute(statement, (account_id, grade))


def record_roll(pool: ConnectionPool, account_id: int, fields: dict) -> None:
    """굴림 한 번을 원장에 남긴다 (D4).

    **입력까지 남긴다.** 결과만 남기면 확률이 맞는지 사후에 증명할 수 없다. 안 나온
    굴림도 남긴다 — 안 나온 것이 데이터다.

    Args:
        pool: 연결 풀.
        account_id: 굴린 계정.
        fields: 소스·레벨·층·세대·등급·결과.
    """
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO item_roll_log (account_id, submission_id, source_kind, source_ref,"
            " monster_level, floor, generation, grade, catalog_id, detail)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                account_id,
                fields.get("submission_id"),
                fields.get("source_kind", SOURCE_ANY),
                fields.get("source_ref", ""),
                int(fields.get("monster_level", 0)),
                int(fields.get("floor", 1)),
                int(fields.get("generation", 0)),
                fields.get("grade"),
                fields.get("catalog_id"),
                fields.get("detail", ""),
            ),
        )
