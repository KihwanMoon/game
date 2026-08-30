"""지속 몬스터 보관 — 레코드·스냅샷·경험치·전리품 (docs/설계/6_몬스터).

**성장은 검증된 런에서만 일어난다.** 클라이언트가 "내가 졌다" 고 보고해서 몬스터가 크는
구조면, 자기 몬스터를 키우려고 일부러 지는 어뷰징이 열린다.

**스냅샷은 서버가 조회한다.** 클라이언트가 되보내면 약한 스냅샷으로 바꿔 제출할 수
있다 (docs/설계/7_변조방지 T8).
"""

import json
from dataclasses import dataclass

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from game.app.monsters.growth import (
    build_growth,
    compute_cap_xp,
    compute_defeat_xp,
    compute_level,
)
from game.app.monsters.tiers import MonsterTier, compute_tier_stat
from game.schemas.monster_snapshot import (
    MonsterSnapshot,
    build_snapshot_payload,
    parse_snapshot,
    sort_snapshots,
)

# 플레이어를 잡았을 때 얻는 경험치. 처치한 플레이어의 레벨·장비에 비례시키지 않는다 —
# 비례시키면 강한 캐릭터로 일부러 죽어 주는 것이 가장 빠른 육성법이 된다 (T9).
XP_PER_PLAYER = 60


@dataclass(frozen=True)
class MonsterRecord:
    """지속 몬스터 하나."""

    record_id: int
    catalog_id: str
    tier: str
    zone_floor: int
    entity_slot: str
    total_xp: int
    level: int
    alive: bool


def create_monster(
    pool: ConnectionPool,
    catalog_id: str,
    tier: MonsterTier,
    zone_floor: int,
    entity_slot: str,
) -> MonsterRecord | None:
    """지속 몬스터를 세계에 놓는다. 그 자리에 이미 있으면 아무것도 하지 않는다.

    Args:
        pool: 연결 풀.
        catalog_id: 적 종류 id.
        tier: 등급.
        zone_floor: 사는 층.
        entity_slot: 방 배치에서의 엔티티 id.

    Returns:
        만들어진 레코드. 이미 있으면 None.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "INSERT INTO monster_record (catalog_id, tier, zone_floor, entity_slot)"
            " VALUES (%s, %s, %s, %s) ON CONFLICT (zone_floor, entity_slot) DO NOTHING"
            " RETURNING id, catalog_id, tier, zone_floor, entity_slot, total_xp, level, alive",
            (catalog_id, str(tier), zone_floor, entity_slot),
        ).fetchone()
    return None if row is None else _build_record(row)


def _build_record(row: tuple) -> MonsterRecord:
    """조회 결과 한 줄을 레코드로 만든다.

    Args:
        row: SELECT 결과.

    Returns:
        만들어진 레코드.
    """
    return MonsterRecord(
        record_id=int(row[0]),
        catalog_id=str(row[1]),
        tier=str(row[2]),
        zone_floor=int(row[3]),
        entity_slot=str(row[4]),
        total_xp=int(row[5]),
        level=int(row[6]),
        alive=bool(row[7]),
    )


def list_monsters(pool: ConnectionPool, zone_floor: int) -> tuple[MonsterRecord, ...]:
    """그 층에 사는 지속 몬스터를 읽는다.

    entity_slot 순으로 정렬한다 — 순서가 실행마다 다르면 같은 티켓이 다른 글자로
    저장된다 (R5).

    Args:
        pool: 연결 풀.
        zone_floor: 층.

    Returns:
        정렬된 레코드들. 죽은 것은 빠진다.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT id, catalog_id, tier, zone_floor, entity_slot, total_xp, level, alive"
            " FROM monster_record WHERE zone_floor = %s AND alive = true"
            " ORDER BY entity_slot",
            (zone_floor,),
        ).fetchall()
    return tuple(_build_record(row) for row in rows)


def build_monster_snapshot(record: MonsterRecord, base: dict) -> MonsterSnapshot:
    """레코드와 카탈로그 값으로 스냅샷 한 줄을 만든다.

    **스탯을 직접 담는다.** 레벨과 곡선만 담고 클라이언트가 계산하게 하면, 곡선을 고치는
    순간 이미 발급된 티켓들이 다른 몬스터를 가리키게 된다.

    Args:
        record: 몬스터 레코드.
        base: balance.json 의 그 적 절.

    Returns:
        만들어진 스냅샷.
    """
    tier = MonsterTier(record.tier)
    growth = build_growth(record.level)
    return MonsterSnapshot(
        entity_id=record.entity_slot,
        record_id=record.record_id,
        kind_id=record.catalog_id,
        tier=record.tier,
        level=record.level,
        hp_max=compute_tier_stat(int(base["hp_max"]), tier) * growth.stat_percent // 100,
        attack=compute_tier_stat(int(base["attack"]), tier) * growth.stat_percent // 100,
        defense=compute_tier_stat(int(base["defense"]), tier),
        rule_slots=int(base.get("rule_slots", 0)) + growth.bonus_rule_slots,
        cpu_budget=int(base.get("cpu_budget", 0)) + growth.bonus_cpu,
    )


def save_snapshots(
    pool: ConnectionPool, ticket_id: str, snapshots: tuple[MonsterSnapshot, ...]
) -> None:
    """티켓에 스냅샷을 얼려 넣는다.

    Args:
        pool: 연결 풀.
        ticket_id: 티켓 id.
        snapshots: 얼려 둘 상태들.
    """
    with pool.connection() as connection:
        for item in snapshots:
            connection.execute(
                "INSERT INTO monster_snapshot (ticket_id, record_id, state)"
                " VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                (ticket_id, item.record_id, Jsonb(build_snapshot_payload(item))),
            )


def load_snapshots(pool: ConnectionPool, ticket_id: str) -> tuple[MonsterSnapshot, ...]:
    """티켓이 얼려 둔 상태를 읽는다.

    **클라이언트가 보낸 것을 쓰지 않는다.** 여기가 그 원칙이 코드로 나타나는 자리다.

    Args:
        pool: 연결 풀.
        ticket_id: 티켓 id.

    Returns:
        entity_id 순으로 정렬된 스냅샷들.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT state FROM monster_snapshot WHERE ticket_id = %s", (ticket_id,)
        ).fetchall()
    parsed = tuple(
        parse_snapshot(json.loads(row[0]) if isinstance(row[0], str) else row[0]) for row in rows
    )
    return sort_snapshots(parsed)


def add_monster_xp(
    pool: ConnectionPool,
    record_id: int,
    zone_floor: int,
    victim_kind: str,
    run_result_id: int | None,
    amount: int = XP_PER_PLAYER,
) -> int:
    """몬스터에게 경험치를 준다. 레벨은 층 상한에서 멈춘다.

    Args:
        pool: 연결 풀.
        record_id: 대상 몬스터.
        zone_floor: 사는 층. 상한을 정한다.
        victim_kind: 무엇을 잡았는가.
        run_result_id: 근거가 된 검증 결과.
        amount: 줄 경험치.

    Returns:
        오른 뒤의 레벨.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "UPDATE monster_record SET total_xp = total_xp + %s, last_seen_at = now()"
            " WHERE id = %s RETURNING total_xp",
            (amount, record_id),
        ).fetchone()
        if row is None:
            return 0
        level, _ = compute_level(int(row[0]), zone_floor)
        connection.execute("UPDATE monster_record SET level = %s WHERE id = %s", (level, record_id))
        connection.execute(
            "INSERT INTO monster_kill (record_id, victim_kind, run_result_id, xp_gained)"
            " VALUES (%s, %s, %s, %s)",
            (record_id, victim_kind, run_result_id, amount),
        )
    return level


def apply_monster_defeat(pool: ConnectionPool, record_id: int, zone_floor: int) -> int:
    """처치된 몬스터의 레벨을 감쇠시킨다 (결정 #35).

    죽여도 아무 흔적이 없으면 플레이어의 승리가 세계에 남지 않는다. 지우지는 않는다 —
    개체가 사라지면 되찾기 동기도 함께 사라진다.

    Args:
        pool: 연결 풀.
        record_id: 처치된 몬스터.
        zone_floor: 사는 층.

    Returns:
        감쇠 뒤의 레벨.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT total_xp, level FROM monster_record WHERE id = %s", (record_id,)
        ).fetchone()
        if row is None:
            return 0
        # 상한으로 먼저 자른다. 상한이 내려갔거나 과거 데이터가 넘치면 감쇠가 아무
        # 효과도 못 내는데, 그러면 처치가 세계에 흔적을 안 남긴다 (결정 #35 방지 3).
        current = min(int(row[0]), compute_cap_xp(zone_floor))
        level, _ = compute_level(current, zone_floor)
        total_xp = compute_defeat_xp(current, level, zone_floor)
        level, _ = compute_level(total_xp, zone_floor)
        connection.execute(
            "UPDATE monster_record SET total_xp = %s, level = %s, last_seen_at = now()"
            " WHERE id = %s",
            (total_xp, level, record_id),
        )
    return level


def create_trophy(
    pool: ConnectionPool,
    record_id: int,
    catalog_id: str,
    affixes: list[dict],
    taken_from: int,
) -> None:
    """몬스터가 플레이어의 장비 사본을 가져간다 (결정 #34).

    Args:
        pool: 연결 풀.
        record_id: 가져간 몬스터.
        catalog_id: 아이템 카탈로그 id.
        affixes: 접사 절.
        taken_from: 누구에게서 가져왔는가.
    """
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO monster_trophy (record_id, catalog_id, affixes, taken_from)"
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
            "SELECT catalog_id, taken_from FROM monster_trophy WHERE record_id = %s"
            " ORDER BY taken_at DESC",
            (record_id,),
        ).fetchall()
    return tuple({"catalog_id": str(row[0]), "taken_from": row[1]} for row in rows)
