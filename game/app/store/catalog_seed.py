"""카탈로그 시딩 — 파일에서 DB 로 한 번 옮긴다 (설계/4_아이템 §15.7).

**빈 표일 때만 옮긴다.** 서버가 뜰 때마다 파일로 덮으면 관리자가 DB 에서 고친 것이
배포 한 번에 사라진다 — 그러면 정본이 DB 라는 말이 거짓이 된다.

시딩이 끝난 뒤로 `items.json` 은 파생물이다. `scripts/export_items.py` 가 DB 에서 그
파일을 다시 만든다.
"""

from psycopg_pool import ConnectionPool

from game.app.items.catalog import load_item_catalog
from game.app.store.item_catalog import apply_grade_seed, save_catalog_entry
from game.config import ITEMS_PATH


def count_catalog(pool: ConnectionPool) -> int:
    """카탈로그에 몇 줄이 있는지 센다.

    Args:
        pool: 연결 풀.

    Returns:
        줄 수.
    """
    with pool.connection() as connection:
        row = connection.execute("SELECT count(*) FROM item_catalog").fetchone()
    return 0 if row is None else int(row[0])


def apply_catalog_seed(pool: ConnectionPool) -> int:
    """비어 있으면 파일의 카탈로그를 DB 로 옮긴다.

    Args:
        pool: 연결 풀.

    Returns:
        옮긴 줄 수. 이미 있었으면 0.
    """
    apply_grade_seed(pool)
    if count_catalog(pool) > 0:
        return 0
    catalog = load_item_catalog(ITEMS_PATH)
    for entry in catalog.values():
        save_catalog_entry(pool, entry)
    return len(catalog)
