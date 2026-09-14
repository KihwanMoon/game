"""DB 카탈로그가 저장소의 씨앗과 어디서 갈렸는지 본다.

**게이트는 이것을 못 본다.** 카탈로그 불변 조건 검사(`tests/test_catalog_ladder.py`)는
`items.json` 만 읽는데, 정본은 DB 다(§15.7) — 그래서 **DB 에만 있는 행은 어떤 검사도
안 거친다.** 2026-09-01 에 들어온 `sword_great_fine` 이 그랬다: 무기인데 사거리가 없고
이름이 `sword_great` 와 겹친 채 열흘 넘게 드롭됐고, 봇 일곱과 사람 둘이 끼고 있었다.
아무도 못 본 이유는 **아무 검사도 DB 를 안 봤기 때문**이다.

씨앗에 없는 행을 나무라지 않는다 — 관리자가 화면에서 더한 것은 정상이다. 나무라는 것은
**그 행이 깨져 있을 때**다.

    GAME_DATABASE_URL=... uv run python -m scripts.report_catalog_drift
"""

import json
import os
import sys
from pathlib import Path

from psycopg_pool import ConnectionPool

from game.app.store.connection import DATABASE_URL_ENV, create_pool

# 씨앗 파일. 여기 있는 id 는 「저장소가 아는 것」이고, 나머지는 DB 에서 자란 것이다.
SEED_PATH = Path("game/resources/balance/items.json")
# 사거리를 반드시 정해야 하는 자리. 주무기가 사거리를 안 정하면 맨손 사거리로 떨어져,
# 활을 껴도 1칸이 된다 (`items/loadout.apply_weapon_range`).
RANGE_REQUIRED_SLOT = "WEAPON_MAIN"


def read_seed_ids() -> frozenset[str]:
    """씨앗 파일이 아는 종류 id 들.

    Returns:
        id 집합. 파일이 없으면 빈 집합.
    """
    if not SEED_PATH.exists():
        return frozenset()
    raw = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    return frozenset(str(item["id"]) for item in raw.get("items", ()))


def list_broken_weapons(pool: ConnectionPool) -> tuple[tuple[str, str], ...]:
    """사거리 없는 주무기들.

    Args:
        pool: 연결 풀.

    Returns:
        (id, 이름) 튜플들. 없으면 빈 튜플.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT catalog_id, label_ko FROM item_catalog"
            " WHERE slot = %s AND attack_range IS NULL AND NOT is_retired"
            " ORDER BY catalog_id",
            (RANGE_REQUIRED_SLOT,),
        ).fetchall()
    return tuple((str(row[0]), str(row[1])) for row in rows)


def list_duplicate_labels(pool: ConnectionPool) -> tuple[tuple[str, str], ...]:
    """같은 이름을 쓰는 살아 있는 종류들.

    **폐기된 것은 안 센다.** 드롭에서 빠진 이름은 가방에서만 보이고, 그때 같은 이름이
    둘인 것은 옛 물건과 새 물건을 가르는 정보다.

    Args:
        pool: 연결 풀.

    Returns:
        (이름, 겹친 id 들) 튜플들.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT label_ko, string_agg(catalog_id, ', ' ORDER BY catalog_id)"
            " FROM item_catalog WHERE NOT is_retired"
            " GROUP BY label_ko HAVING count(*) > 1 ORDER BY label_ko"
        ).fetchall()
    return tuple((str(row[0]), str(row[1])) for row in rows)


def list_extra_rows(pool: ConnectionPool, seed_ids: frozenset[str]) -> tuple[tuple[str, str], ...]:
    """씨앗에 없는 살아 있는 종류들.

    Args:
        pool: 연결 풀.
        seed_ids: 씨앗이 아는 id 들.

    Returns:
        (id, 이름) 튜플들.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT catalog_id, label_ko FROM item_catalog WHERE NOT is_retired ORDER BY catalog_id"
        ).fetchall()
    return tuple((str(row[0]), str(row[1])) for row in rows if str(row[0]) not in seed_ids)


def main(argv: list[str]) -> int:
    """스크립트 진입점.

    Args:
        argv: 프로그램 이름을 뺀 인자들. 받는 것은 없다.

    Returns:
        종료 코드. 깨진 행이 있으면 1.
    """
    del argv
    url = os.environ.get(DATABASE_URL_ENV, "")
    if not url:
        print(f"{DATABASE_URL_ENV} 가 없다", file=sys.stderr)
        return 1
    pool = create_pool(url)
    broken = list_broken_weapons(pool)
    duplicates = list_duplicate_labels(pool)
    extra = list_extra_rows(pool, read_seed_ids())
    for catalog_id, label in extra:
        print(f"  씨앗에 없음: {catalog_id} — 「{label}」 (관리자가 더한 것일 수 있다)")
    for label, ids in duplicates:
        print(f"  ✘ 이름이 겹친다: 「{label}」 — {ids}")
    for catalog_id, label in broken:
        print(f"  ✘ 주무기인데 사거리가 없다: {catalog_id} — 「{label}」")
    if broken or duplicates:
        print(f"깨진 행 {len(broken) + len(duplicates)}건. **드롭표에 살아 있다**")
        return 1
    print(f"깨진 행 없음. 씨앗에 없는 행 {len(extra)}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
