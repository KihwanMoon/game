"""아이템 카탈로그 정본 — DB (설계/4_아이템 §15.7).

**파일에서 DB 로 옮겨 왔다.** 관리자가 종류를 조회·등록·폐기할 수 있어야 하고, 아이템은
브라우저 코어가 읽지 않는 유일한 자산이라 런타임 이관이 가능한 유일한 것이기도 하다.

`resources/balance/items.json` 은 이제 **파생물**이다. `scripts/export_items.py` 가 여기서
내보내고, 코어와 골든은 그 스냅샷을 읽는다 — 골든 재현이 DB 상태에 묶이지 않게 하려는
배치다.

**삭제 함수가 없다.** 인스턴스·원장·경매가 `catalog_id` 를 가리키므로 지우면 과거 기록을
못 읽는다. `apply_retire` 가 "새로 안 나온다" 만 표시한다 (§15.7).
"""

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from game.schemas.item import GRADE_SEALED_SLOTS, ItemCatalogEntry, parse_item

# 등급 기본 정의 (결정 #42). **표시용이다** — 등급이 성능에 하는 일인 봉인 칸 수는
# 코드의 `GRADE_SEALED_SLOTS` 하나가 정하고 여기는 그것을 옮겨 적는다.
DEFAULT_GRADES: tuple[tuple[str, int, str], ...] = (
    ("COMMON", 1, "보통"),
    ("FINE", 2, "상급"),
    ("RELIC", 3, "유물"),
)


def apply_grade_seed(pool: ConnectionPool) -> None:
    """등급 정의를 채운다. 이미 있으면 두고 넘어간다.

    Args:
        pool: 연결 풀.
    """
    with pool.connection() as connection:
        for code, rank, label in DEFAULT_GRADES:
            connection.execute(
                "INSERT INTO item_grade (code, rank, label_ko, sealed_slots)"
                " VALUES (%s, %s, %s, %s) ON CONFLICT (code)"
                " DO UPDATE SET sealed_slots = EXCLUDED.sealed_slots",
                (code, rank, label, GRADE_SEALED_SLOTS.get(code, 0)),
            )
        connection.execute(
            "INSERT INTO catalog_generation (id, generation) VALUES (1, 1)"
            " ON CONFLICT (id) DO NOTHING"
        )


def save_catalog_entry(pool: ConnectionPool, entry: ItemCatalogEntry) -> None:
    """카탈로그 한 줄을 쓴다. 같은 id 가 있으면 갱신한다.

    **세대를 올리지 않는다.** 시딩이 한 줄마다 세대를 올리면 서버가 뜰 때마다 코어
    버전이 바뀐다 — 세대는 부르는 쪽이 한 번에 올린다 (`apply_generation_bump`).

    Args:
        pool: 연결 풀.
        entry: 쓸 항목.
    """
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO item_catalog (catalog_id, kind, slot, hands, grade, label_ko,"
            " tags, affixes, requirements, grants_skill, min_floor, is_retired, attack_range,"
            " use_tag, stack_max)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (catalog_id) DO UPDATE SET"
            " kind = EXCLUDED.kind, slot = EXCLUDED.slot, hands = EXCLUDED.hands,"
            " grade = EXCLUDED.grade, label_ko = EXCLUDED.label_ko, tags = EXCLUDED.tags,"
            " affixes = EXCLUDED.affixes, requirements = EXCLUDED.requirements,"
            " grants_skill = EXCLUDED.grants_skill, min_floor = EXCLUDED.min_floor,"
            " is_retired = EXCLUDED.is_retired, attack_range = EXCLUDED.attack_range,"
            " use_tag = EXCLUDED.use_tag, stack_max = EXCLUDED.stack_max,"
            " updated_at = now()",
            (
                entry.catalog_id,
                str(entry.kind.value),
                str(entry.slot.value) if entry.slot else None,
                str(entry.hands.value) if entry.hands else None,
                entry.grade,
                entry.label_ko,
                Jsonb(list(entry.tags)),
                Jsonb(
                    [
                        {
                            "stat": a.stat,
                            "flat": a.flat,
                            "percent": a.percent,
                            "label_ko": a.label_ko,
                        }
                        for a in entry.affixes
                    ]
                ),
                Jsonb([{"stat": r.stat, "min": r.minimum} for r in entry.requirements]),
                entry.grants_skill,
                entry.min_floor,
                entry.is_retired,
                entry.attack_range,
                entry.use_tag,
                entry.stack_max,
            ),
        )


def build_entry_row(row: tuple) -> ItemCatalogEntry:
    """DB 한 줄을 카탈로그 항목으로 만든다.

    파일 파서를 그대로 쓴다 — 파서가 둘이면 규칙이 둘이 되고, 스냅샷과 DB 가 같은 절을
    다르게 읽는 날이 온다.

    Args:
        row: item_catalog 의 한 줄.

    Returns:
        카탈로그 항목.
    """
    raw: dict = {
        "id": row[0],
        "kind": row[1],
        "label_ko": row[5],
        "grade": row[4],
        "tags": row[6] or [],
        "affixes": row[7] or [],
        "requirements": row[8] or [],
        "min_floor": row[10],
        "is_retired": row[11],
    }
    if row[2]:
        raw["slot"] = row[2]
    if row[3]:
        raw["hands"] = row[3]
    if row[9]:
        raw["grants_skill"] = row[9]
    if row[12] is not None:
        raw["attack_range"] = row[12]
    if row[13]:
        raw["use_tag"] = row[13]
    if row[14]:
        raw["stack_max"] = row[14]
    return parse_item(raw)


def list_catalog(pool: ConnectionPool) -> dict[str, ItemCatalogEntry]:
    """카탈로그 전량을 읽는다. 폐기된 것도 담는다.

    폐기는 "새로 안 나온다" 이지 "없다" 가 아니다 — 이미 가방에 있는 것을 읽으려면
    그 정의가 필요하다.

    Args:
        pool: 연결 풀.

    Returns:
        catalog_id 에서 항목으로의 대응표.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT catalog_id, kind, slot, hands, grade, label_ko, tags, affixes,"
            " requirements, grants_skill, min_floor, is_retired, attack_range, use_tag,"
            " stack_max FROM item_catalog"
            " ORDER BY catalog_id"
        ).fetchall()
    return {str(row[0]): build_entry_row(row) for row in rows}


def apply_retire(pool: ConnectionPool, catalog_id: str, is_retired: bool = True) -> None:
    """아이템 종류를 폐기하거나 되살린다. **지우지 않는다** (§15.7).

    Args:
        pool: 연결 풀.
        catalog_id: 대상 종류.
        is_retired: 폐기할지.
    """
    with pool.connection() as connection:
        connection.execute(
            "UPDATE item_catalog SET is_retired = %s, updated_at = now() WHERE catalog_id = %s",
            (is_retired, catalog_id),
        )


def read_generation(pool: ConnectionPool) -> int:
    """카탈로그 세대를 읽는다. core_version 의 `i` 축이다 (§15.8).

    Args:
        pool: 연결 풀.

    Returns:
        세대. 표가 비어 있으면 1.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT generation FROM catalog_generation WHERE id = 1"
        ).fetchone()
    return 1 if row is None else int(row[0])


def apply_generation_bump(pool: ConnectionPool) -> int:
    """카탈로그 세대를 하나 올린다.

    **아이템을 고치는 것은 시즌을 가르는 일이다.** 올리지 않으면 관리자가 조용히 과거
    기록을 무효로 만든다 (§15.8).

    Args:
        pool: 연결 풀.

    Returns:
        올린 뒤의 세대.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "UPDATE catalog_generation SET generation = generation + 1, updated_at = now()"
            " WHERE id = 1 RETURNING generation"
        ).fetchone()
    return 1 if row is None else int(row[0])
