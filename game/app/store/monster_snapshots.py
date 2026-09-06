"""스냅샷 — 개체 하나를 티켓에 얼려 넣는다 (docs/설계/7_변조방지 T8).

`monsters.py` 에서 갈라 나왔다. 저쪽은 **세계에 사는 개체를 보관하는 일**(레코드·경험치·
감쇠)이고 여기는 **그 개체를 런 하나에 얼려 넣는 일**이다 — 파일이 400줄 상한을 넘은
것이 계기였지만, 가르는 선은 책임이다 (§4).

**스냅샷은 서버가 조회한다.** 클라이언트가 되보내면 약한 스냅샷으로 바꿔 제출할 수 있다.

**스탯을 직접 담는다.** 레벨과 곡선만 담고 클라이언트가 계산하게 하면, 곡선을 고치는
순간 이미 발급된 티켓들이 다른 몬스터를 가리키게 된다.
"""

import json

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from game.app.bots.doppel import check_is_doppel
from game.app.monsters.affixes import compute_affixed_stat, list_monster_affixes
from game.app.monsters.growth import build_growth
from game.app.monsters.tiers import MonsterTier, compute_tier_stat
from game.app.store.monsters import MonsterRecord
from game.app.store.spoils import compute_spoiled_stat
from game.schemas.monster_snapshot import (
    MonsterSnapshot,
    build_snapshot_payload,
    parse_snapshot,
    sort_snapshots,
)

# 퍼센트 기준. 100 이 1.0배다.
PERCENT_BASE = 100


def resolve_frozen_stat(frozen: dict, name: str, computed: int) -> int:
    """얼려 둔 빌드가 그 값을 갖고 있으면 그것을 쓴다.

    **덮는 것이지 얹는 것이 아니다.** 등급·성장을 곱하면 같은 개체가 볼 때마다 다른 값을
    갖게 되어 「그 빌드로 여기까지 왔다」가 뜻을 잃는다 — 전투 쪽이 층 스케일을 대체하는
    것과 같은 규율이다 (`services/run_battle`).

    Args:
        frozen: 얼려 둔 빌드. 비어 있으면 아무것도 안 덮는다.
        name: 볼 스탯 이름.
        computed: 카탈로그·등급·성장으로 계산한 값.

    Returns:
        실제로 쓸 값. 얼려 둔 것이 없거나 0 이면 계산한 값이다 — 0 은 「안 실렸다」다.
    """
    value = int(frozen.get(name) or 0)
    return value if value > 0 else computed


def build_monster_snapshot(
    record: MonsterRecord, base: dict, spoils: dict[str, tuple[int, int]] | None = None
) -> MonsterSnapshot:
    """레코드와 카탈로그 값으로 스냅샷 한 줄을 만든다.

    **스탯을 직접 담는다.** 레벨과 곡선만 담고 클라이언트가 계산하게 하면, 곡선을 고치는
    순간 이미 발급된 티켓들이 다른 몬스터를 가리키게 된다.

    Args:
        record: 몬스터 레코드.
        base: balance.json 의 그 적 절.
        spoils: 뺏어 든 장비의 보정. 없으면 안 건다 — 도감처럼 전투가 아닌 자리는
            굳이 조회하지 않는다.

    Returns:
        만들어진 스냅샷.
    """
    tier = MonsterTier(record.tier)
    taken = spoils or {}
    growth = build_growth(record.level)
    # **얼려 둔 빌드가 있으면 그것이 이 개체다** (도플갱어). 안 읽던 시절에는 카탈로그
    # (hp 100)로만 세워져 **그림자가 원본 봇보다 약했다** — 7층 그림자가 공격 24 대 70,
    # 방어 7 대 42 였다. 빌드를 얼려 두고 안 쓰면 이름뿐인 말이 된다.
    frozen = record.stat_json or {}
    # 엘리트 접사는 spawn_seed 에서 파생한다 — 조회할 때마다 굴리면 도감과 전투가 다른
    # 적을 보게 된다 (docs/설계/6_몬스터 §1).
    affixes = list_monster_affixes(record.spawn_seed, tier)
    return MonsterSnapshot(
        entity_id=record.entity_slot,
        zone_floor=int(record.zone_floor or 0),
        record_id=record.record_id,
        kind_id=record.catalog_id,
        tier=record.tier,
        level=record.level,
        # **뺏은 장비를 맨 뒤에 건다.** 등급 → 레벨 → 정예 접사 → 뺏은 것 순이다.
        # 가장 나중이어야 「그 장비 덕에 이만큼 더 단단하다」가 그대로 읽힌다.
        hp_max=resolve_frozen_stat(
            frozen,
            "hp_max",
            compute_spoiled_stat(
                compute_affixed_stat(
                    compute_tier_stat(int(base["hp_max"]), tier)
                    * growth.stat_percent
                    // PERCENT_BASE,
                    "hp_max",
                    affixes,
                ),
                "hp_max",
                taken,
            ),
        ),
        attack=resolve_frozen_stat(
            frozen,
            "attack",
            compute_spoiled_stat(
                compute_affixed_stat(
                    compute_tier_stat(int(base["attack"]), tier)
                    * growth.stat_percent
                    // PERCENT_BASE,
                    "attack",
                    affixes,
                ),
                "attack",
                taken,
            ),
        ),
        defense=resolve_frozen_stat(
            frozen,
            "defense",
            compute_spoiled_stat(
                compute_affixed_stat(
                    compute_tier_stat(int(base["defense"]), tier), "defense", affixes
                ),
                "defense",
                taken,
            ),
        ),
        rule_slots=resolve_frozen_stat(
            frozen, "rule_slots", int(base.get("rule_slots", 0)) + growth.bonus_rule_slots
        ),
        cpu_budget=resolve_frozen_stat(
            frozen, "cpu_budget", int(base.get("cpu_budget", 0)) + growth.bonus_cpu
        ),
        # 키트. 카탈로그에는 없는 축이라 얼려 둔 것이 없으면 「안 실렸다」로 둔다 —
        # 전투 쪽이 그때 종의 값을 쓴다.
        attack_range=int(frozen.get("attack_range") or 0),
        skills=tuple(sorted(str(one) for one in frozen.get("skills") or ())),
        # **그림자는 물약을 안 쓴다** (2026-09-06). 원본 봇이 들고 다니던 것이 그대로
        # 얼어붙어 있었는데, 그림자는 목숨 셋을 쓰며 세 번 만나는 개체다 — 거기에 회복까지
        # 붙으면 한 판이 아니라 소모전이 된다. 잡을 수 있어야 「끝내 지웠다」가 성립한다.
        potions=(
            0
            if check_is_doppel(record.catalog_id)
            else (int(frozen["potions"]) if "potions" in frozen else -1)
        ),
        # 개체 전용 규칙표. 여느 몬스터는 None 이라 종의 표를 쓴다.
        ruleset=record.ruleset_json,
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
