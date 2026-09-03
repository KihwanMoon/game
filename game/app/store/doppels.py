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


def create_doppel(
    pool: ConnectionPool,
    origin_account_id: int,
    floor: int,
    slot: str,
    loadout: dict,
    ruleset: dict,
) -> int:
    """도플갱어 하나를 세운다.

    **다섯을 넘기지 않는다.** 층마다 그림자가 서면 「가끔 만나는 것」이 아니게 된다 —
    정예 승격과 같은 이유로, 사건은 드물어야 사건이다.

    Args:
        pool: 연결 풀.
        origin_account_id: 누구의 그림자인가.
        floor: 세울 층.
        slot: 앉을 자리. 방 템플릿의 스폰 이름이어야 한다.
        loadout: 그 봇이 쓰던 전투 입력.
        ruleset: 그 봇이 쓰던 규칙표. 도감이 이것을 편다.

    Returns:
        만들어진 개체 id. 상한에 걸렸거나 자리가 없으면 0.
    """
    if not slot or count_doppels(pool) >= MAX_DOPPELS:
        return 0
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
                Jsonb(loadout),
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
