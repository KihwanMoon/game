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


def list_catalog_ids(pool: ConnectionPool) -> set[str]:
    """카탈로그에 이미 있는 id 를 모은다.

    Args:
        pool: 연결 풀.

    Returns:
        catalog_id 들. 비어 있으면 빈 집합.
    """
    with pool.connection() as connection:
        rows = connection.execute("SELECT catalog_id FROM item_catalog").fetchall()
    return {str(row[0]) for row in rows}


def apply_catalog_seed(pool: ConnectionPool) -> int:
    """파일에 있는데 DB 에 없는 줄만 심는다.

    **이미 있는 줄은 손대지 않는다.** 서버가 뜰 때마다 파일로 덮으면 관리자가 DB 에서
    고친 것이 배포 한 번에 사라지고, 그러면 정본이 DB 라는 말이 거짓이 된다. 폐기한
    아이템이 되살아나는 것도 같은 사고다.

    **한 번 채우고 끝내지도 않는다.** 예전에는 표가 비어 있을 때만 돌아서, 콘텐츠를 파일에
    더해도 이미 돌고 있는 서버에는 영영 안 들어갔다 — 드롭 표에서 겪은 것과 같은 구멍이다.

    Args:
        pool: 연결 풀.

    Returns:
        새로 심은 줄 수. 심을 것이 없었으면 0.
    """
    apply_grade_seed(pool)
    known = list_catalog_ids(pool)
    catalog = load_item_catalog(ITEMS_PATH)
    fresh = [entry for key, entry in sorted(catalog.items()) if key not in known]
    for entry in fresh:
        save_catalog_entry(pool, entry)
    return len(fresh)
