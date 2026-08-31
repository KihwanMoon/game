"""전리품 이전 — 몬스터가 플레이어의 장비를 가져간다 (결정 #34, `설계/6_몬스터` §5).

**사본을 만든다.** 원본을 옮기면 플레이어가 그것을 되찾기 전까지 잃은 것이 되고, 사망
대가(장비 하나)와 이중으로 물린다. 사본이라 되찾는 것은 "덤" 이고, 그것이 되찾으러 갈
동기를 만들되 강제하지 않는 방식이다.

몬스터 성장(`store/monsters.py`)과 갈라 둔 이유는 책임이 다르기 때문이다 — 저쪽은 개체가
얼마나 컸는가이고, 이쪽은 무엇을 들고 있는가다.
"""

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from game.app.store.items import find_empty_slot, record_item_event

# 되찾기. `grant` 와 가르는 이유는 원장에서 World Loop 를 셀 수 있어야 하기 때문이다 —
# 발급된 아이템과 돌려받은 아이템은 경제에서 뜻이 다르다.
EVENT_RECOVER = "recover"


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


def apply_recovery(
    pool: ConnectionPool, record_id: int, account_id: int, entity_id: int
) -> tuple[str, ...]:
    """그 몬스터가 들고 있던 것 중 **내 것만** 되찾는다 (`설계/6_몬스터` §5, M1).

    처치 보상을 "아이템" 이 아니라 "그 몬스터가 들고 있던 것 중 자기 것" 으로 한정하는
    것이 동시 처치의 보상 복제를 막는 방식이다 — 두 사람이 같은 개체를 잡아도 각자
    자기 것만 가져간다.

    **되찾은 것은 귀속된다.** 사본이라 아이템 총량이 이미 한 번 늘었고, 그것이 경매에
    흘러들면 사망이 화폐 발행이 된다. 귀속은 그 통로를 막되 쓰는 것은 막지 않는다
    (결정 #07·#34).

    가방이 가득 차면 **거기서 멈춘다.** 소유만 옮기고 칸을 못 주면 어디에도 없는
    아이템이 생긴다 — `create_item` 과 같은 이유다.

    Args:
        pool: 연결 풀.
        record_id: 처치한 몬스터.
        account_id: 되찾는 계정. `taken_from` 과 대조한다.
        entity_id: 그 계정의 개체 id (아이템이 옮겨 갈 자리).

    Returns:
        되찾은 아이템의 카탈로그 id 들. 없으면 빈 튜플.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT id, catalog_id FROM item_instance"
            " WHERE owner_entity_id = %s AND taken_from = %s ORDER BY created_at",
            (record_id, account_id),
        ).fetchall()
    taken: list[str] = []
    for row in rows:
        slot = find_empty_slot(pool, entity_id)
        if slot is None:
            break
        with pool.connection() as connection:
            connection.execute(
                "UPDATE item_instance SET owner_entity_id = %s, is_bound = TRUE WHERE id = %s",
                (entity_id, int(row[0])),
            )
            connection.execute(
                "INSERT INTO inventory_slot (entity_id, slot_index, item_id) VALUES (%s, %s, %s)",
                (entity_id, slot, int(row[0])),
            )
        record_item_event(pool, entity_id, int(row[0]), EVENT_RECOVER, str(row[1]))
        taken.append(str(row[1]))
    return tuple(taken)
