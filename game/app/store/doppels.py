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

from game.app.bots.doppel import (
    DOPPEL_KIND_ID,
    DOPPEL_LIVES,
    DOPPELS_PER_SOURCE,
    MAX_DOPPELS_PER_FLOOR,
    compute_doppel_cap,
)
from game.app.monsters.growth import compute_level_xp
from game.app.monsters.tiers import MonsterTier
from game.app.store.doppel_quota import (
    count_doppel_sources,
    count_doppels_on_floor,
    count_own_doppels,
    find_crowded_doppel,
    find_oldest_doppel_on_floor,
    find_own_doppel_on_floor,
    find_own_oldest_doppel,
)
from game.app.store.letters import apply_doppel_settlement


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


def remove_doppel(pool: ConnectionPool, record_id: int) -> bool:
    """그림자 하나를 세계에서 지운다.

    **지워도 되는 종이다.** 지속 몬스터를 안 지우는 이유는 되찾기 동기가 함께 사라지기
    때문인데(결정 #35), 도플갱어는 **애초에 아무것도 안 든다** — 되찾기가 코드로 막혀
    있으므로 그 사유가 이 종에는 안 붙는다.

    **물러나는 자리에서 활자를 정산한다** (2026-09-15). 그림자가 사라지는 길은 둘이다 —
    목숨을 다 썼거나 정원에 밀렸거나. 둘 다 이 함수를 지나므로 여기 하나만 걸면 새는 길이
    없다. 정산을 부르는 쪽에 두었더니 정원 퇴출 경로가 조용히 빠졌었다.

    Args:
        pool: 연결 풀.
        record_id: 지울 개체.

    Returns:
        지웠으면 참. 이미 없었으면 거짓.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "DELETE FROM entity_record WHERE id = %s AND is_doppel"
            " RETURNING id, coalesce(origin_account_id, 0)",
            (record_id,),
        ).fetchone()
    if row is None:
        return False
    apply_doppel_settlement(pool, record_id, int(row[1]))
    return True


def apply_doppel_defeat(pool: ConnectionPool, record_id: int) -> int:
    """그림자를 한 번 잡은 것을 반영한다.

    **목숨을 하나 쓴다.** 다 쓰면 지운다 — 한 번에 지우면 봇들이 쉼 없이 싸우는 세계에서
    그림자가 서자마자 사라져 사람이 만날 새가 없고, 안 지우면 자리가 굳는다.

    **레벨 감쇠는 부르는 쪽이 한다.** 여기서 함께 하면 목숨과 감쇠가 한 덩이가 되어,
    여느 몬스터의 감쇠와 다른 길이 하나 더 생긴다.

    Args:
        pool: 연결 풀.
        record_id: 잡힌 개체.

    Returns:
        남은 목숨. 0 이면 지워졌다. 그림자가 아니거나 이미 없으면 -1.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "UPDATE entity_record SET lives = lives - 1, updated_at = now()"
            " WHERE id = %s AND is_doppel RETURNING lives",
            (record_id,),
        ).fetchone()
    if row is None:
        return -1
    left = max(0, int(row[0]))
    if left <= 0:
        remove_doppel(pool, record_id)
    return left


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

    **정원을 장마다 잰다** (개정 2026-09-15). 예전에는 세계 상한 하나였고 그것이 깊이로
    줄을 세웠다 — 「가장 깊은 스물을 남긴다」. 그래서 실측으로 **스물 중 열아홉이 9장에
    몰렸고 주인은 셋뿐**이었다. 한 장이 도는 방이 다섯이고 `build_room_doppels` 가 방마다
    하나씩 세우므로, 9장에 닿은 사람은 **다섯 방이 전부 그림자**였고 2~8장에서는 하나도
    못 만났다. 깊이로 줄을 세우면 얕은 장이 영원히 진다.

    이제 셋을 함께 본다 (`doppel_quota`).

    1. **한 원천은 한 장에 하나.** 같은 사람의 새 죽음은 제 옛 그림자를 **물려받는다** —
       자리까지 함께. 없으면 한 사람이 그 장의 정원을 통째로 가져가 다섯 방에서 같은
       빌드를 두 번 만나게 된다.
    2. **한 원천은 세계에 둘까지.** 넘으면 제 것 중 가장 오래된 것이 물러난다. 세계
       상한이 **원천 수에 비례**하는 것은 이 규칙의 결과다 — 총량에만 걸면 계정 둘이
       아홉 장을 나눠 차지해도 통과한다.
    3. **한 장에 둘까지.** 넘으면 — 또는 방 배치에 빈 자리가 없으면 — 그 장에서 가장
       오래된 것이 나가고 새 그림자가 **그 자리를 물려받는다**.
    4. **마지막으로 세계 상한(원천 수 × 2)을 한 번 더 잰다.** 넘으면 **가장 붐비는
       장**에서 가장 오래된 것이 나간다 — 가장 얕은 것이 아니다.

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
    # **제 그림자를 먼저 물려받는다.** 이것을 뒤로 미루면 아래 정원 검사가 제 것을 남의
    # 것으로 세어, 같은 사람이 그 장을 둘 다 차지하는 길이 열린다.
    own, own_slot = find_own_doppel_on_floor(pool, origin_account_id, floor)
    if own != 0:
        remove_doppel(pool, own)
        slot = slot or own_slot
    # **비례는 여기서 걸린다.** 세계 총량에만 상한을 두면 계정 둘이 아홉 장을 하나씩
    # 차지해도 통과한다 — 세계는 안 덮였는데 만나는 빌드는 둘뿐이다. 넘치면 **제 것 중
    # 가장 오래된 것**이 물러난다; 남의 것을 밀어내면 「내가 깊이 갔다」가 남의 자리를
    # 빼앗는 일이 된다.
    if count_own_doppels(pool, origin_account_id) >= DOPPELS_PER_SOURCE:
        retired = find_own_oldest_doppel(pool, origin_account_id)
        if retired == 0:
            return 0
        remove_doppel(pool, retired)
    # **자리 고갈도 같은 문으로 들어온다** (Z10). 정원이 남았는데 자리가 없는 경우가
    # 있다 — 방 배치의 자리 이름은 여느 지속 몬스터와 나눠 쓰기 때문이다. 예전에는 그때
    # 그냥 0 을 돌려줬고, 그래서 4층 자리 열하나가 찬 뒤 봇이 4층을 115번 깼는데 새
    # 그림자가 하나도 안 섰다. 둘 다 「그 층의 가장 오래된 것이 비켜 준다」로 푼다.
    if count_doppels_on_floor(pool, floor) >= MAX_DOPPELS_PER_FLOOR or not slot:
        evicted, evicted_slot = find_oldest_doppel_on_floor(pool, floor)
        if evicted == 0:
            return 0
        remove_doppel(pool, evicted)
        slot = slot or evicted_slot
    if not slot:
        return 0
    if count_doppels(pool) >= compute_doppel_cap(count_doppel_sources(pool)):
        crowded = find_crowded_doppel(pool)
        if crowded == 0:
            return 0
        remove_doppel(pool, crowded)
    level = max(1, floor)
    # **키트도 함께 얼린다** (개정 2026-09-04). 예전에는 스탯 셋만 담아서, 장궁 든 봇의
    # 그림자가 사거리 1 근접으로 싸웠다 — 빌드에서 가장 그 빌드다운 것이 빠진 채 숫자만
    # 큰 몹이 됐다. 사거리·스킬·물약은 장비가 주는 것 중 **숫자로 안 녹는 부분**이고,
    # 그것이 빠지면 어떤 그림자를 만나도 싸움이 똑같아진다.
    stats = {
        "hp_max": int(loadout.get("hp_max", 0)),
        "attack": int(loadout.get("attack", 0)),
        "defense": int(loadout.get("defense", 0)),
        "attack_range": int(loadout.get("attack_range", 0)),
        # 정렬해서 담는다 — 순회 순서가 세계 상태에 새면 두 코어가 갈린다 (R5).
        "skills": sorted(str(one) for one in loadout.get("skills") or ()),
        "potions": int((loadout.get("consumables") or {}).get("POTION", 0)),
    }
    with pool.connection() as connection:
        row = connection.execute(
            "INSERT INTO entity_record"
            " (kind, catalog_id, tier, persistence, level, total_xp, stat_json, ruleset_json,"
            "  zone_floor, entity_slot, is_doppel, origin_account_id, loadout_json,"
            "  rule_slots, cpu_budget, lives)"
            " VALUES ('MONSTER', %s, %s, 'PERSISTENT', %s, %s, %s, %s, %s, %s, TRUE, %s, %s,"
            "  %s, %s, %s)"
            # **경합은 예외가 아니라 0 이다.** 위의 정원 검사와 이 INSERT 는 한
            # 트랜잭션이 아니라, 봇 열이 한꺼번에 죽으면 같은 사람의 그림자가 한 장에
            # 둘 설 수 있다. 인덱스가 그것을 막고 여기서는 「안 섰다」로 떨어진다 —
            # 예외로 터지면 제출 전체가 500 이 된다.
            " ON CONFLICT (origin_account_id, zone_floor)"
            "  WHERE is_doppel AND alive AND origin_account_id IS NOT NULL DO NOTHING"
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
                # **목숨을 갖고 선다.** 한 번에 지워지면 서자마자 사라져 아무도 못 만난다.
                DOPPEL_LIVES,
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


def check_doppel_opt_in(pool: ConnectionPool, account_id: int) -> bool:
    """이 계정이 자기 그림자를 세우기로 했는가 (2026-09-06).

    **기본은 꺼져 있다.** 그림자는 원본의 규칙표로 싸우므로, 관전하며 행동을 보면 남의
    해답이 어느 정도 역산된다 — 그러면 베끼는 것이 최선이 되고 P1(실패는 정보다)이
    죽는다. 켜는 사람이 알고 켜야 하는 대가다.

    Args:
        pool: 연결 풀.
        account_id: 볼 계정.

    Returns:
        켰으면 True. 없는 계정도 False.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT doppel_opt_in FROM account WHERE id = %s", (account_id,)
        ).fetchone()
    return bool(row[0]) if row else False


def apply_doppel_opt_in(pool: ConnectionPool, account_id: int, is_on: bool) -> bool:
    """자기 그림자를 세울지 정한다.

    **이미 선 그림자는 안 지운다.** 끄는 것은 「앞으로 안 세운다」이고, 지우는 것은 남의
    던전에서 개체가 사라지는 일이라 뜻이 다르다 — 목숨을 다 쓰면 저절로 사라진다.

    Args:
        pool: 연결 풀.
        account_id: 대상 계정.
        is_on: 켤지.

    Returns:
        바뀐 계정이 있으면 True.
    """
    with pool.connection() as connection:
        cursor = connection.execute(
            "UPDATE account SET doppel_opt_in = %s WHERE id = %s", (is_on, account_id)
        )
    return cursor.rowcount == 1
