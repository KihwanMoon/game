"""도플갱어를 세운다 (T11, 결정 #35 위에 선다).

**빌드를 든 정예다.** 봇이 깊은 층에서 죽으면 그 자리에 그림자가 선다 — 스탯은 그 봇이
쓰던 로드아웃에서 나오고, 규칙표는 기록에 남는다(도감이 그것을 편다). 그래서 5층에서
만나는 도플갱어는 「운 좋게 레벨이 오른 것」이 아니라 **거기까지 실제로 내려간 빌드**다.

**실제 플레이어의 규칙표를 복사하지 않는다.** 봇의 것만 쓰므로 공개·소유 문제가 없다.

**전리품을 만들지 않는다** (결정 #02). 봇의 장비에서 나온 개체라 무엇이든 떨어지면
봇이 벌어 둔 것을 사람에게 건네는 통로가 된다 — 막는 세 자리는 `bots/doppel.py` 에 있고,
그 판정이 `doppelganger` 라는 종 id 하나에 걸려 있다. 그래서 여기서 세울 때 그 종으로
세우는 것이 안전장치의 일부다.
"""

import json

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from game.app.bots.doppel import DOPPEL_KIND_ID, MAX_DOPPELS
from game.app.monsters.growth import compute_level_xp
from game.app.monsters.tiers import MonsterTier


def count_doppels(pool: ConnectionPool) -> int:
    """살아 있는 도플갱어 수.

    Args:
        pool: 연결 풀.

    Returns:
        마릿수.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT count(*) FROM entity_record WHERE kind = 'MONSTER' AND is_doppel AND alive"
        ).fetchone()
    return int(row[0]) if row else 0


def find_shallowest_doppel(pool: ConnectionPool) -> tuple[int, int]:
    """가장 얕은 그림자. 같은 깊이면 가장 오래된 것.

    **밀어낼 하나를 고르는 자리다.** 얕은 것부터 내보내야 남는 것이 「가장 깊은 스물」이
    된다. 같은 깊이가 여럿이면 오래된 것을 내보낸다 — 그래야 같은 깊이가 계속 나올 때도
    보토가 돌고, 하루 종일 같은 그림자를 만나지 않는다.

    Args:
        pool: 연결 풀.

    Returns:
        (개체 id, 그 층). 하나도 없으면 (0, 0).
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT id, zone_floor FROM entity_record"
            " WHERE kind = 'MONSTER' AND is_doppel AND alive"
            " ORDER BY zone_floor ASC, id ASC LIMIT 1"
        ).fetchone()
    return (int(row[0]), int(row[1] or 0)) if row else (0, 0)


def remove_doppel(pool: ConnectionPool, record_id: int) -> bool:
    """그림자 하나를 세계에서 지운다.

    **지워도 되는 종이다.** 지속 몬스터를 안 지우는 이유는 되찾기 동기가 함께 사라지기
    때문인데(결정 #35), 도플갱어는 **애초에 아무것도 안 든다** — 되찾기가 코드로 막혀
    있으므로 그 사유가 이 종에는 안 붙는다.

    Args:
        pool: 연결 풀.
        record_id: 지울 개체.

    Returns:
        지웠으면 참. 이미 없었으면 거짓.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "DELETE FROM entity_record WHERE id = %s AND is_doppel RETURNING id", (record_id,)
        ).fetchone()
    return row is not None


def find_free_slot(pool: ConnectionPool, floor: int, slots: tuple[str, ...]) -> str:
    """그 층에서 아직 아무도 안 앉은 자리를 찾는다.

    **템플릿의 자리여야 한다.** 방 배치에 없는 이름으로 세우면 스냅샷이 아무에게도
    안 붙어서, 개체는 있는데 아무도 못 만나는 상태가 된다.

    Args:
        pool: 연결 풀.
        floor: 세울 층.
        slots: 그 층 방들의 스폰 자리 이름들. 순서가 곧 우선순위다.

    Returns:
        빈 자리 이름. 없으면 빈 문자열.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT entity_slot FROM entity_record"
            " WHERE kind = 'MONSTER' AND zone_floor = %s AND entity_slot IS NOT NULL",
            (floor,),
        ).fetchall()
    taken = {str(row[0]) for row in rows}
    return next((slot for slot in slots if slot not in taken), "")


def list_origin_gear(pool: ConnectionPool, account_id: int) -> list[dict]:
    """그 계정이 **지금 끼고 있는 것**을 얼려 둘 모양으로 읽는다.

    **아이템을 옮기지 않는다.** 도플갱어는 어떤 아이템도 소유하지 않는다 — 그것이
    전리품 차단의 뿌리다(잡아도 떨어질 것이 없고, 되찾을 것도 없다). 여기서 만드는 것은
    **사본 기록**이라 `item_instance` 행이 늘지 않고, 따라서 세계의 아이템 총량도 그대로다.

    그런데도 기록해 두는 이유는 「그 빌드로 여기까지 왔다」가 이 개체의 뜻이기 때문이다.
    무엇을 끼고 갔는지 볼 수 없으면 그 뜻이 절반만 남는다.

    Args:
        pool: 연결 풀.
        account_id: 원본 계정.

    Returns:
        자리 순의 장비 기록들.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT e.slot, i.catalog_id, i.affixes, i.is_broken"
            " FROM equipment_slot e JOIN item_instance i ON i.id = e.item_id"
            " JOIN entity_record p ON p.id = e.entity_id"
            " WHERE p.kind = 'PLAYER' AND p.owner_account_id = %s"
            " ORDER BY e.slot",
            (account_id,),
        ).fetchall()
    return [
        {
            "slot": str(row[0]),
            "catalog_id": str(row[1]),
            "affixes": row[2] if isinstance(row[2], list) else [],
            "is_broken": bool(row[3]),
        }
        for row in rows
    ]


def read_doppel_gear(pool: ConnectionPool, record_id: int) -> list[dict]:
    """그 도플갱어가 끼고 있던 장비 기록.

    Args:
        pool: 연결 풀.
        record_id: 개체 id.

    Returns:
        장비 기록들. 없으면 빈 목록.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT loadout_json FROM entity_record WHERE id = %s AND is_doppel", (record_id,)
        ).fetchone()
    raw = row[0] if row else None
    if isinstance(raw, str):
        raw = json.loads(raw)
    gear = raw.get("gear") if isinstance(raw, dict) else None
    return [item for item in gear if isinstance(item, dict)] if isinstance(gear, list) else []


def create_doppel(
    pool: ConnectionPool,
    origin_account_id: int,
    floor: int,
    slot: str,
    loadout: dict,
    ruleset: dict,
) -> int:
    """도플갱어 하나를 세운다.

    **자리가 아니라 순위표다** (개정 2026-09-04). 상한에 닿으면 버리는 것이 아니라 **가장
    얕은 그림자와 견준다** — 새 죽음이 그것보다 깊거나 같으면 밀어내고 선다. 예전에는
    선착순이었고 비우는 길이 없어서, 자리가 2층 그림자로 차는 순간 그 뒤의 모든 죽음이
    조용히 버려졌다. 2층 죽음이 가장 흔하므로 **가장 얕은 빌드가 자리를 영구히 점유**했고,
    그것은 「거기까지 실제로 내려간 빌드」라는 이 기제의 전제와 정반대였다.

    **같은 깊이면 새 것이 이긴다.** 더 깊을 때만 밀어내게 하면 봇이 한 깊이에서 평평해지는
    순간 보토가 다시 굳는다 — 밀려나는 것은 그 깊이에서 가장 오래된 그림자다.

    Args:
        pool: 연결 풀.
        origin_account_id: 누구의 그림자인가.
        floor: 세울 층.
        slot: 앉을 자리. 방 템플릿의 스폰 이름이어야 한다.
        loadout: 그 봇이 쓰던 전투 입력.
        ruleset: 그 봇이 쓰던 규칙표. 도감이 이것을 편다.

    Returns:
        만들어진 개체 id. 자리가 없거나 순위에 못 들면 0.
    """
    if not slot:
        return 0
    if count_doppels(pool) >= MAX_DOPPELS:
        record_id, shallowest = find_shallowest_doppel(pool)
        if record_id == 0 or floor < shallowest:
            return 0
        remove_doppel(pool, record_id)
    level = max(1, floor)
    stats = {
        "hp_max": int(loadout.get("hp_max", 0)),
        "attack": int(loadout.get("attack", 0)),
        "defense": int(loadout.get("defense", 0)),
    }
    with pool.connection() as connection:
        row = connection.execute(
            "INSERT INTO entity_record"
            " (kind, catalog_id, tier, persistence, level, total_xp, stat_json, ruleset_json,"
            "  zone_floor, entity_slot, is_doppel, origin_account_id, loadout_json,"
            "  rule_slots, cpu_budget)"
            " VALUES ('MONSTER', %s, %s, 'PERSISTENT', %s, %s, %s, %s, %s, %s, TRUE, %s, %s,"
            "  %s, %s)"
            " RETURNING id",
            (
                DOPPEL_KIND_ID,
                MonsterTier.ELITE,
                level,
                compute_level_xp(level),
                Jsonb(stats),
                Jsonb(ruleset),
                floor,
                slot,
                origin_account_id,
                # **장비를 함께 얼린다.** 아이템을 옮기는 것이 아니라 사본 기록이다 —
                # `item_instance` 가 늘지 않으므로 잡아도 떨어질 것이 없다.
                Jsonb({**loadout, "gear": list_origin_gear(pool, origin_account_id)}),
                int(loadout.get("rule_slots", 0)),
                int(loadout.get("cpu_budget", 0)),
            ),
        ).fetchone()
    return int(row[0]) if row else 0


def read_doppel_ruleset(pool: ConnectionPool, record_id: int) -> dict:
    """그 도플갱어가 들고 있던 규칙표.

    도감이 이것을 그대로 편다 — 「그 빌드로 여기까지 왔다」가 이 개체의 뜻이므로,
    규칙표를 감추면 뜻이 사라진다.

    Args:
        pool: 연결 풀.
        record_id: 개체 id.

    Returns:
        규칙표 절. 없으면 빈 절.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT ruleset_json FROM entity_record WHERE id = %s", (record_id,)
        ).fetchone()
    raw = row[0] if row else None
    if isinstance(raw, str):
        raw = json.loads(raw)
    return dict(raw) if isinstance(raw, dict) else {}
