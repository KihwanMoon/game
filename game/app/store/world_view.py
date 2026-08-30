"""세계 현황 조회 — 관리자가 무엇이 벌어지는지 보는 창.

**읽기만 한다.** 이 모듈에는 쓰기가 없다. 개입은 별도 경로에서만 하고 반드시 원장에
남는다(`store/admin.py`).

지금까지 세계 상태를 볼 방법이 아예 없었다. 지속 몬스터가 몇이고 누가 남의 장비를 들고
있는지, 화폐가 얼마나 풀렸는지 확인하려면 매번 임시 스크립트를 써야 했다 — 그 상태로는
"세계가 건강한가" 를 아무도 답할 수 없다.
"""

from dataclasses import dataclass

from psycopg_pool import ConnectionPool


@dataclass(frozen=True)
class WorldSummary:
    """세계 한눈에 보기."""

    accounts: int
    registered: int
    entities: int
    monsters_alive: int
    items: int
    items_bound: int
    items_held_by_monsters: int
    listings_open: int
    currency_total: int
    verified_runs: int


@dataclass(frozen=True)
class MonsterRow:
    """지속 몬스터 한 줄 — 보유 아이템 수를 함께 센다.

    엘리트가 남의 장비를 들고 있는 것이 World Loop 의 동기이므로(`설계/6_몬스터` §5),
    그것을 세지 않으면 이 표가 세계를 설명하지 못한다.
    """

    record_id: int
    entity_id: int
    catalog_id: str
    tier: str
    zone_floor: int
    entity_slot: str
    level: int
    total_xp: int
    alive: bool
    held_items: int


def read_world_summary(pool: ConnectionPool) -> WorldSummary:
    """세계 요약을 한 번에 읽는다.

    Args:
        pool: 연결 풀.

    Returns:
        요약 값들.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT"
            " (SELECT count(*) FROM account),"
            " (SELECT count(*) FROM account WHERE login_id IS NOT NULL),"
            " (SELECT count(*) FROM entity_record),"
            " (SELECT count(*) FROM entity_record WHERE kind = 'MONSTER' AND alive),"
            " (SELECT count(*) FROM item_instance),"
            " (SELECT count(*) FROM item_instance WHERE is_bound),"
            " (SELECT count(*) FROM item_instance i JOIN entity_record e"
            "    ON e.id = i.owner_entity_id WHERE e.kind = 'MONSTER'),"
            " (SELECT count(*) FROM auction_listing WHERE state = 'OPEN'),"
            " (SELECT coalesce(sum(balance), 0) FROM wallet),"
            " (SELECT count(*) FROM run_result WHERE verdict = 'verified')"
        ).fetchone()
    values = [int(item) for item in (row or [0] * 10)]
    return WorldSummary(*values)


def list_world_monsters(pool: ConnectionPool, limit: int = 200) -> tuple[MonsterRow, ...]:
    """지속 몬스터를 층·레벨 순으로 읽는다.

    Args:
        pool: 연결 풀.
        limit: 최대 줄 수.

    Returns:
        층 오름차순, 같은 층에서는 레벨 내림차순.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT e.id, e.id, e.catalog_id, e.tier, e.zone_floor, e.entity_slot,"
            " e.level, e.total_xp, e.alive,"
            " (SELECT count(*) FROM item_instance i WHERE i.owner_entity_id = e.id)"
            " FROM entity_record e WHERE e.kind = 'MONSTER'"
            " ORDER BY e.zone_floor ASC, e.level DESC, e.id ASC LIMIT %s",
            (limit,),
        ).fetchall()
    return tuple(
        MonsterRow(
            record_id=int(row[0]),
            entity_id=int(row[1]),
            catalog_id=str(row[2]),
            tier=str(row[3]),
            zone_floor=int(row[4]),
            entity_slot=str(row[5]),
            level=int(row[6]),
            total_xp=int(row[7]),
            alive=bool(row[8]),
            held_items=int(row[9]),
        )
        for row in rows
    )


@dataclass(frozen=True)
class HeldItemRow:
    """몬스터가 들고 있는 아이템 한 줄.

    **누구에게서 빼앗았는지 함께 본다.** 되찾으러 갈 동기가 World Loop 의 전부이므로
    (`설계/6_몬스터` §5), 원주인을 모르면 이 표가 무엇을 설명하는지 알 수 없다.
    """

    item_id: int
    record_id: int
    monster_id: str
    catalog_id: str
    taken_from_handle: str
    is_broken: bool
    is_bound: bool


def list_held_items(pool: ConnectionPool, limit: int = 200) -> tuple[HeldItemRow, ...]:
    """몬스터가 들고 있는 아이템을 전부 읽는다.

    Args:
        pool: 연결 풀.
        limit: 최대 줄 수.

    Returns:
        개체·아이템 순으로 정렬된 줄들.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT i.id, e.id, e.catalog_id, i.catalog_id,"
            " coalesce(a.handle, ''), i.is_broken, i.is_bound"
            " FROM item_instance i"
            " JOIN entity_record e ON e.id = i.owner_entity_id"
            " LEFT JOIN account a ON a.id = i.taken_from"
            " WHERE e.kind = 'MONSTER'"
            " ORDER BY e.id ASC, i.id ASC LIMIT %s",
            (limit,),
        ).fetchall()
    return tuple(
        HeldItemRow(
            item_id=int(row[0]),
            record_id=int(row[1]),
            monster_id=str(row[2]),
            catalog_id=str(row[3]),
            taken_from_handle=str(row[4]),
            is_broken=bool(row[5]),
            is_bound=bool(row[6]),
        )
        for row in rows
    )


def count_levels(pool: ConnectionPool) -> tuple[tuple[int, int], ...]:
    """플레이어 레벨 분포를 센다.

    **분포가 없으면 레벨 곡선을 튜닝할 수 없다** — 평균만 보면 한 사람이 멀리 간 것과
    모두가 조금씩 온 것을 구분하지 못한다.

    Args:
        pool: 연결 풀.

    Returns:
        (레벨, 인원) 쌍들. 레벨 오름차순.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT level, count(*) FROM entity_record WHERE kind = 'PLAYER'"
            " GROUP BY level ORDER BY level ASC"
        ).fetchall()
    return tuple((int(row[0]), int(row[1])) for row in rows)
