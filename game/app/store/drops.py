"""드롭 표 저장 — 등급 가중치·아이템 가중치·천장·굴림 기록 (설계/4_아이템 §15).

**두 표로 갈라 둔 것이 이 설계의 전부다.** 등급 분포(`drop_grade_weight`)와 등급 안의
아이템 비율(`drop_item_weight`)을 한 표에 섞으면, 보통 등급에 아이템 하나를 더하는 순간
유물 등급의 확률까지 내려간다 — 콘텐츠를 늘리는 일이 밸런스를 흔드는 일이 된다.

여기 있는 값은 **자리를 잡아 둔 것**이지 밸런스가 아니다. 확률 수식은 나중에 정한다.
"""

from psycopg_pool import ConnectionPool

from game.app.items.drops import GRADE_MISS
from game.schemas.item import (
    GRADE_COMMON,
    GRADE_FINE,
    GRADE_RELIC,
    ItemCatalogEntry,
    ItemKind,
    list_grades_above,
)

# 소스 갈래. 소스별 표가 없으면 `ANY` 로 떨어진다.
SOURCE_ANY = "ANY"
SOURCE_MONSTER = "MONSTER_KIND"

# 등급 가중치의 출발값. **밸런스가 아니라 자리다** (§15.6).
#
# 만분율이다. 해상도를 크게 잡은 이유는 유물이 만분의 5 라서다 — 천분율로 두면 유물이
# 1 이 되고, 그러면 천장 한 걸음이 그 등급을 두 배로 만든다.
#
# 실측으로 맞췄다. **한 런의 처치 수는 4가 아니라 16이다** — 소환사가 계속 부르므로
# 방 배치의 적 수와 처치 수가 다르다. 굴림당 3.7% 면 런당 기대 0.6개로, 런당 60% 이던
# 예전과 체감이 같다. 처음에 넷으로 어림잡아 18.9% 로 뒀다가 10판에 가방을 채웠다.
# `GRADE_MISS` 는 아무것도 안 나오는 몫이다 — 등급과 같은 저울에 올려야 "안 나옴" 도
# 분포의 일부가 된다.
DEFAULT_GRADE_WEIGHTS: tuple[tuple[str, int, int], ...] = (
    (GRADE_MISS, 9630, 0),
    (GRADE_COMMON, 310, 0),
    (GRADE_FINE, 55, 6),
    (GRADE_RELIC, 5, 4),
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
        (catalog_id, 가중치) 들. id 순. 퀘스트 아이템은 담기지 않는다 (설계 §4).
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT w.catalog_id, w.weight FROM drop_item_weight w"
            " JOIN item_catalog c ON c.catalog_id = w.catalog_id"
            # **퀘스트 아이템은 읽는 쪽에서도 막는다.** 시딩만 걸러 두면 표에 한 번 들어간
            # 줄이 영원히 남는다 — 실제로 옛 코드가 넣어 둔 줄이 그대로 굴려졌다.
            " WHERE w.source_id = %s AND w.grade = %s AND NOT c.is_retired"
            " AND c.kind <> 'QUEST' AND c.min_floor <= %s"
            " ORDER BY w.catalog_id",
            (source_id, grade, floor),
        ).fetchall()
    return tuple((str(row[0]), int(row[1])) for row in rows)


def apply_drop_seed(pool: ConnectionPool, catalog: dict[str, ItemCatalogEntry]) -> int:
    """`ANY` 소스의 표에 **빠진 줄을 채운다.** 이미 있는 줄은 건드리지 않는다.

    **등급마다 한 줄씩 깐다.** 예전에는 아이템을 제 등급 한 칸에만 넣어서, 카탈로그가
    전부 보통이던 프로덕션에서 상급·유물 굴림 26건이 「그 등급에 후보가 없다」로
    증발했다. 카탈로그의 `grade` 는 **이 등급부터** 라는 뜻이고, 같은 단검이 유물로
    나오면 다른 점은 봉인 칸 수다 (§17).

    **한 번 채우고 끝내지 않는다.** 예전에는 등급 가중치가 있으면 곧장 돌아가서, 관리자가
    새로 등록한 아이템이 드롭 표에 영영 안 들어갔다 — 등록은 되는데 나오지는 않았다.
    이미 있는 줄은 `ON CONFLICT DO NOTHING` 이 지키므로 조정한 가중치는 안전하다.

    아이템 가중치는 등급 안에서 모두 1 이다 — 아이템별 차등은 밸런스이고, 그것은
    나중에 정한다.

    Args:
        pool: 연결 풀.
        catalog: 아이템 카탈로그.

    Returns:
        새로 채운 아이템 가중치 줄 수. 채울 것이 없었으면 0.
    """
    source_id = save_source(pool, SOURCE_ANY)
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
            # **퀘스트 아이템은 굴려서 나오지 않는다** (설계/4_아이템 §4). 퀘스트가 주는
            # 것이다. 예전 `list_droppable` 이 걸러 주던 것을 표로 옮기면서 한 번
            # 빠뜨렸고, 프로덕션에서 「봉인된 각인」이 전리품으로 나왔다.
            if entry.is_retired or entry.kind is ItemKind.QUEST:
                continue
            for grade in list_grades_above(entry.grade):
                cursor = connection.execute(
                    "INSERT INTO drop_item_weight (source_id, grade, catalog_id, weight)"
                    " VALUES (%s, %s, %s, 1) ON CONFLICT DO NOTHING",
                    (source_id, grade, entry.catalog_id),
                )
                filled += cursor.rowcount
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


def save_monster_drop(
    pool: ConnectionPool, kind_id: str, grade: str, catalog_id: str, weight: int
) -> int:
    """특정 몬스터 종에게만 걸리는 드롭 줄을 만든다 (D3).

    **소스가 있으면 `ANY` 를 안 본다.** 두 표를 합치면 "이 몬스터만 떨군다" 가 성립하지
    않는다 — 도감이 표적 목록이 되는 근거가 그 배타성이다.

    등급 가중치가 없으면 `ANY` 의 것을 복사해 온다. 소스를 만들자마자 굴림이 통째로
    막히는 것을 피하려는 배치이며, 그 뒤로는 이 소스의 값이 정본이다.

    Args:
        pool: 연결 풀.
        kind_id: 몬스터 종.
        grade: 등급.
        catalog_id: 떨굴 아이템.
        weight: 그 등급 안의 가중치.

    Returns:
        이 소스의 id.
    """
    source_id = save_source(pool, SOURCE_MONSTER, kind_id)
    if not read_grade_weights(pool, source_id):
        base_id = find_source(pool, SOURCE_ANY)
        rows = read_grade_weights(pool, base_id) if base_id is not None else ()
        with pool.connection() as connection:
            for name, base_weight, scale in rows:
                connection.execute(
                    "INSERT INTO drop_grade_weight (source_id, grade, weight, level_scale_pct)"
                    " VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    (source_id, name, base_weight, scale),
                )
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO drop_item_weight (source_id, grade, catalog_id, weight)"
            " VALUES (%s, %s, %s, %s)"
            " ON CONFLICT (source_id, grade, catalog_id) DO UPDATE SET weight = EXCLUDED.weight",
            (source_id, grade, catalog_id, weight),
        )
    return source_id


def list_monster_drops(pool: ConnectionPool, kind_id: str) -> tuple[tuple[str, str, int], ...]:
    """그 몬스터에게만 걸린 드롭 줄들을 읽는다.

    Args:
        pool: 연결 풀.
        kind_id: 몬스터 종.

    Returns:
        (등급, catalog_id, 가중치) 들. 소스가 없으면 빈 튜플.
    """
    source_id = find_source(pool, SOURCE_MONSTER, kind_id)
    if source_id is None:
        return ()
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT grade, catalog_id, weight FROM drop_item_weight"
            " WHERE source_id = %s ORDER BY grade, catalog_id",
            (source_id,),
        ).fetchall()
    return tuple((str(row[0]), str(row[1]), int(row[2])) for row in rows)
