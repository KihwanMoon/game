"""전리품 이전 — 몬스터가 플레이어의 장비를 가져간다 (결정 #34, `설계/6_몬스터` §5).

**사본을 만든다.** 원본을 옮기면 플레이어가 그것을 되찾기 전까지 잃은 것이 되고, 사망
대가(장비 하나)와 이중으로 물린다. 사본이라 되찾는 것은 "덤" 이고, 그것이 되찾으러 갈
동기를 만들되 강제하지 않는 방식이다.

몬스터 성장(`store/monsters.py`)과 갈라 둔 이유는 책임이 다르기 때문이다 — 저쪽은 개체가
얼마나 컸는가이고, 이쪽은 무엇을 들고 있는가다.
"""

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool


def create_trophy(
    pool: ConnectionPool,
    record_id: int,
    catalog_id: str,
    affixes: list[dict],
    taken_from: int,
) -> None:
    """몬스터가 플레이어의 장비 사본을 가져간다 (결정 #34).

    **별도 표가 아니라 그 개체가 소유한 아이템으로 넣는다.** 표를 가르면 "몬스터가 내
    장비를 들고 있다" 가 다시 특수 케이스가 되고, 나중에 몬스터가 그것을 장착하거나
    되찾기가 거래를 타야 할 때 양쪽을 합쳐야 한다.

    Args:
        pool: 연결 풀.
        record_id: 가져간 몬스터의 개체 id.
        catalog_id: 아이템 카탈로그 id.
        affixes: 접사 절.
        taken_from: 누구에게서 가져왔는가.
    """
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO item_instance (owner_entity_id, catalog_id, affixes, taken_from)"
            " VALUES (%s, %s, %s, %s)",
            (record_id, catalog_id, Jsonb(affixes), taken_from),
        )


def list_trophies(pool: ConnectionPool, record_id: int) -> tuple[dict, ...]:
    """그 몬스터가 들고 있는 전리품을 읽는다. 도감이 이것을 보여준다.

    Args:
        pool: 연결 풀.
        record_id: 몬스터 id.

    Returns:
        전리품 절들.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT catalog_id, taken_from FROM item_instance"
            " WHERE owner_entity_id = %s AND taken_from IS NOT NULL"
            " ORDER BY created_at DESC",
            (record_id,),
        ).fetchall()
    return tuple({"catalog_id": str(row[0]), "taken_from": row[1]} for row in rows)
