"""지속 몬스터 보관 — 레코드·스냅샷·경험치·전리품 (docs/설계/6_몬스터).

**성장은 검증된 런에서만 일어난다.** 클라이언트가 "내가 졌다" 고 보고해서 몬스터가 크는
구조면, 자기 몬스터를 키우려고 일부러 지는 어뷰징이 열린다.

**스냅샷은 서버가 조회한다.** 클라이언트가 되보내면 약한 스냅샷으로 바꿔 제출할 수
있다 (docs/설계/7_변조방지 T8).
"""

import json
import secrets
from dataclasses import dataclass

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from game.app.monsters.growth import (
    compute_cap_xp,
    compute_defeat_xp,
    compute_level,
    compute_level_xp,
)
from game.app.monsters.tiers import MonsterTier

# 플레이어를 잡았을 때 얻는 경험치. 처치한 플레이어의 레벨·장비에 비례시키지 않는다 —
# 비례시키면 강한 캐릭터로 일부러 죽어 주는 것이 가장 빠른 육성법이 된다 (T9).
# 퍼센트 기준. 100 이 1.0배다.
PERCENT_BASE = 100

XP_PER_PLAYER = 60

# 스폰 시드 상한. 엘리트 접사 굴림의 재현 근거이며, 예측 불가능해야 어느 개체가 어떤
# 접사를 갖는지 미리 계산해 그것만 노리는 일이 막힌다.
MAX_SPAWN_SEED = 1 << 40

# 조회 결과에서의 자리. SELECT 목록과 함께 고쳐야 한다 — 어긋나면 접사와 규칙표가
# 조용히 비고, 그것이 "엘리트인데 접사가 없다" 로 나타난다.
COLUMN_SPAWN_SEED = 8
COLUMN_RULESET = 9
COLUMN_STATS = 10


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
    # 엘리트 접사 굴림의 재현 근거. 같은 개체는 언제 조회해도 같은 접사를 낸다.
    spawn_seed: int = 0
    # 이 개체 전용 규칙표. None 이면 카탈로그 기본표를 쓴다 — 레벨별 규칙표(#36)의 자리다.
    ruleset_json: dict | None = None
    # 얼려 둔 빌드. **도플갱어의 것이다** — 카탈로그가 아니라 그 봇이 쓰던 값이 이 개체의
    # 바탕이다. 비어 있으면 여느 몬스터처럼 카탈로그를 바탕으로 쓴다.
    #
    # 안 읽던 시절에는 카탈로그(hp 100)로만 세워져서, **그림자가 원본 봇보다 약했다** —
    # 실측으로 7층 그림자가 공격 24 대 70, 방어 7 대 42 였다. 빌드를 얼려 두고 안 쓰면
    # 「그 빌드로 여기까지 왔다」가 이름뿐인 말이 된다.
    stat_json: dict | None = None


def create_monster(
    pool: ConnectionPool,
    catalog_id: str,
    tier: MonsterTier,
    zone_floor: int,
    entity_slot: str,
    spawn_seed: int | None = None,
    ruleset_json: dict | None = None,
) -> MonsterRecord | None:
    """지속 몬스터를 세계에 놓는다. 그 자리에 이미 있으면 아무것도 하지 않는다.

    Args:
        pool: 연결 풀.
        catalog_id: 적 종류 id.
        tier: 등급.
        zone_floor: 사는 층.
        entity_slot: 방 배치에서의 엔티티 id.
        spawn_seed: 굴림의 재현 근거. 생략하면 서버가 만든다 — 엘리트 접사가 이것에서
            나오므로, 같은 개체는 언제 조회해도 같은 접사를 낸다.
        ruleset_json: 이 개체 전용 규칙표. 없으면 카탈로그 기본표를 쓴다 — 레벨별
            규칙표(#36)가 정해지면 여기 들어온다.

    Returns:
        만들어진 레코드. 이미 있으면 None.
    """
    # **층이 곧 레벨이다** (난이도 개편). 깊은 층의 지속 몬스터가 레벨 1 로 태어나면
    # 층 스케일과 무관하게 도감·스냅샷 성장이 1층과 같다. 경험치도 함께 맞춘다 —
    # 레벨만 세우면 다음 경험치 한 점에 되돌아간다.
    born_level = max(1, int(zone_floor))
    with pool.connection() as connection:
        row = connection.execute(
            "INSERT INTO entity_record"
            " (kind, catalog_id, tier, zone_floor, entity_slot, spawn_seed, ruleset_json,"
            " level, total_xp)"
            " VALUES ('MONSTER', %s, %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (zone_floor, entity_slot) DO NOTHING"
            " RETURNING id, catalog_id, tier, zone_floor, entity_slot, total_xp, level, alive,"
            " spawn_seed, ruleset_json",
            (
                catalog_id,
                str(tier),
                zone_floor,
                entity_slot,
                spawn_seed if spawn_seed is not None else secrets.randbelow(MAX_SPAWN_SEED),
                Jsonb(ruleset_json) if ruleset_json is not None else None,
                born_level,
                compute_level_xp(born_level),
            ),
        ).fetchone()
    return None if row is None else _build_record(row)


def _build_record(row: tuple) -> MonsterRecord:
    """조회 결과 한 줄을 레코드로 만든다.

    Args:
        row: SELECT 결과.

    Returns:
        만들어진 레코드.
    """
    raw_ruleset = row[COLUMN_RULESET] if len(row) > COLUMN_RULESET else None
    raw_stats = row[COLUMN_STATS] if len(row) > COLUMN_STATS else None
    return MonsterRecord(
        record_id=int(row[0]),
        catalog_id=str(row[1]),
        tier=str(row[2]),
        zone_floor=int(row[3]),
        entity_slot=str(row[4]),
        total_xp=int(row[5]),
        level=int(row[6]),
        alive=bool(row[7]),
        spawn_seed=(
            int(row[COLUMN_SPAWN_SEED])
            if len(row) > COLUMN_SPAWN_SEED and row[COLUMN_SPAWN_SEED] is not None
            else 0
        ),
        ruleset_json=(json.loads(raw_ruleset) if isinstance(raw_ruleset, str) else raw_ruleset),
        stat_json=(json.loads(raw_stats) if isinstance(raw_stats, str) else raw_stats),
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
            "SELECT id, catalog_id, tier, zone_floor, entity_slot, total_xp, level, alive,"
            " spawn_seed, ruleset_json, stat_json"
            " FROM entity_record WHERE kind = 'MONSTER' AND zone_floor = %s AND alive = true"
            " ORDER BY entity_slot",
            (zone_floor,),
        ).fetchall()
    return tuple(_build_record(row) for row in rows)


def find_monster(pool: ConnectionPool, record_id: int) -> MonsterRecord | None:
    """지속 몬스터 하나를 id 로 찾는다.

    Args:
        pool: 연결 풀.
        record_id: 개체 id.

    Returns:
        찾은 레코드. 없으면 None. **죽은 것도 돌려준다** — 관리자는 죽은 개체도 봐야 한다.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT id, catalog_id, tier, zone_floor, entity_slot, total_xp, level, alive,"
            " spawn_seed, ruleset_json, stat_json"
            " FROM entity_record WHERE kind = 'MONSTER' AND id = %s",
            (record_id,),
        ).fetchone()
    return None if row is None else _build_record(row)


def set_monster_level(pool: ConnectionPool, record_id: int, level: int) -> None:
    """지속 몬스터의 레벨을 정한다 (관리자 개입).

    **경험치도 함께 맞춘다.** 레벨만 바꾸면 다음 경험치 한 점에 원래 레벨로 되돌아가고,
    관리자가 손댄 것이 조용히 사라진다.

    Args:
        pool: 연결 풀.
        record_id: 개체 id.
        level: 새 레벨. 상한 판정은 부르는 쪽이 한다.
    """
    with pool.connection() as connection:
        connection.execute(
            "UPDATE entity_record SET level = %s, total_xp = %s, updated_at = now()"
            " WHERE kind = 'MONSTER' AND id = %s",
            (level, compute_level_xp(level), record_id),
        )


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
            "UPDATE entity_record SET total_xp = total_xp + %s, updated_at = now()"
            " WHERE id = %s RETURNING total_xp",
            (amount, record_id),
        ).fetchone()
        if row is None:
            return 0
        level, _ = compute_level(int(row[0]), zone_floor)
        connection.execute("UPDATE entity_record SET level = %s WHERE id = %s", (level, record_id))
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
            "SELECT total_xp, level FROM entity_record WHERE id = %s", (record_id,)
        ).fetchone()
        if row is None:
            return 0
        # 상한으로 먼저 자른다. 상한이 내려갔거나 과거 데이터가 넘치면 감쇠가 아무
        # 효과도 못 내는데, 그러면 처치가 세계에 흔적을 안 남긴다 (결정 #35 방지 3).
        current = min(int(row[0]), compute_cap_xp(zone_floor))
        level, _ = compute_level(current, zone_floor)
        total_xp = compute_defeat_xp(current, level, zone_floor)
        level, _ = compute_level(total_xp, zone_floor)
        # **층이 바닥이다** (난이도 개편: 층 = 최소 레벨). 태어날 때 층만큼 받았는데
        # 죽을 때마다 그 밑으로 깎이면, 몇 번 잡힌 깊은 층 몬스터가 1층 것보다 약해져
        # 「층 = 레벨」이 거짓이 된다. 감쇠는 층 위로 자란 몫에만 닿는다.
        floor_level = max(1, int(zone_floor))
        if level < floor_level:
            level = floor_level
            total_xp = max(total_xp, compute_level_xp(floor_level))
        connection.execute(
            "UPDATE entity_record SET total_xp = %s, level = %s, updated_at = now() WHERE id = %s",
            (total_xp, level, record_id),
        )
    return level
