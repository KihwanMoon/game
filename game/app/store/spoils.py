"""뺏어 든 장비가 몬스터를 세게 만든다 (결정 #34).

**예전에는 표식일 뿐이었다.** 도감이 「내 것을 들고 있다」고 말할 수는 있었지만 그
몬스터가 세지지는 않았고, 그러면 되찾으러 갈 이유가 감정뿐이다. 붙으면 「저놈이 내 갑옷
때문에 단단하다」가 되고, 그것이 World Loop 의 동기다.

**몬스터도 사람과 같은 여섯 칸을 쓴다.** 예전에는 뺏은 것을 전부 더했다 — 칸 상한이
어디에도 없어서, 같은 개체에게 열일곱 번 죽으면 열일곱 벌이 한꺼번에 붙었다. 실제로
1층 `goblin_rusher_0` 이 hp 49→275 · 공격 9→66 · 방어 2→52 가 되어 있었다. 사람은 여섯
칸뿐인데 몬스터만 무제한이면 그것은 성장이 아니라 구멍이다.

그래서 칸마다 하나만 든다. **가장 최근에 뺏은 것이 그 칸을 차지한다** — 몬스터는 값을
매기지 않고 방금 뜯어낸 것을 걸친다. 「더 좋은 것을 고른다」로 하지 않은 이유는 무엇이
더 좋은가를 정하려면 세기 지표를 새로 만들어야 하고, 그것이 곧 밸런스 결정 하나가
늘어나는 일이기 때문이다.

합산은 `items/stats.py` 의 사람 쪽 함수를 그대로 부른다. 양손무기가 보조 칸을 봉인하는
규칙까지 같아야, 같은 장비가 사람에게 붙을 때와 몬스터에게 붙을 때 다른 값을 내지 않는다.

몬스터 저장소에서 갈라 둔 이유는 책임이 다르기 때문이다 — 저쪽은 개체를 읽고 쓰고,
여기는 **든 것이 스탯에 얼마나 붙는가**만 안다 (§4 의 400줄 상한에 걸린 자리이기도 하다).
"""

import json
from dataclasses import replace

from psycopg_pool import ConnectionPool

from game.app.items.stats import StatDelta
from game.app.store.item_catalog import list_catalog
from game.schemas.item import COMBAT_STATS, Affix, ItemCatalogEntry

# 퍼센트의 분모. 100 이 1.0배다.
PERCENT_BASE = 100


def read_affixes(raw: object) -> tuple[Affix, ...]:
    """저장된 접사 절을 접사로 읽는다.

    **`COMBAT_STATS` 로 거르지 않는다.** 거르는 자리는 합산이며(`merge_stat_deltas`),
    여기서 한 번 더 거르면 두 곳이 서로 다른 목록을 들 수 있다.

    Args:
        raw: DB 가 준 값. 문자열이거나 이미 풀린 목록이다.

    Returns:
        접사들. 절이 아니면 빈 튜플.
    """
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, list):
        return ()
    return tuple(
        Affix(
            stat=str(item.get("stat", "")),
            flat=int(item.get("flat", 0)),
            percent=int(item.get("percent", 0)),
        )
        for item in raw
        if isinstance(item, dict)
    )


def build_worn_items(
    rows: list[tuple], catalog: dict[str, ItemCatalogEntry]
) -> tuple[ItemCatalogEntry, ...]:
    """뺏은 것들 중 **스탯에 붙는 것 전부**를 낸다 (개정 2026-09-06).

    예전에는 칸마다 하나씩만 골랐다. 몬스터가 든 것에 상한이 없던 때는 그 골라내기가
    폭주를 막는 유일한 자리였는데(실측으로 한 마리가 696개를 들고 있었다), 이제
    `create_trophy` 가 다섯으로 막는다 — 막는 자리가 둘이면 어느 쪽이 실제 한도인지가
    코드에서 안 읽힌다.

    **칸이 없는 것은 여전히 안 붙는다.** 몬스터가 물약을 마시지는 않는다.

    접사는 카탈로그가 아니라 **그 개체의 것**을 쓴다. 굴림으로 붙은 접사가 카탈로그와
    다르기 때문이다 — 카탈로그에서 가져오는 것은 칸과 손 쓰는 방식뿐이다.

    Args:
        rows: (catalog_id, affixes) 줄들. 최근 것이 앞.
        catalog: 카탈로그. 칸과 손 쓰는 방식의 정본이다.

    Returns:
        붙는 것들. 최근 것이 앞이다.
    """
    return tuple(
        replace(entry, affixes=read_affixes(raw))
        for catalog_id, raw in rows
        for entry in [catalog.get(str(catalog_id))]
        if entry is not None and entry.slot is not None
    )


def list_spoil_deltas(pool: ConnectionPool, record_id: int) -> dict[str, tuple[int, int]]:
    """그 몬스터가 **입고 있는 장비**가 주는 스탯 보정 (결정 #34).

    **파손된 것은 안 붙는다.** 사람에게도 복구해야 쓰이는 것이므로 같은 규칙이다.
    소모품처럼 칸이 없는 것도 안 붙는다 — 몬스터가 물약을 마시지는 않는다.

    Args:
        pool: 연결 풀.
        record_id: 볼 개체.

    Returns:
        스탯 이름에서 (합계 고정값, 합계 퍼센트) 로의 대응표.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT catalog_id, affixes FROM item_instance"
            " WHERE owner_entity_id = %s AND NOT is_broken ORDER BY id DESC",
            (record_id,),
        ).fetchall()
    worn = build_worn_items(rows, list_catalog(pool))
    return {stat: (delta.flat, delta.percent) for stat, delta in merge_spoil_deltas(worn).items()}


def merge_spoil_deltas(items: tuple[ItemCatalogEntry, ...]) -> dict[str, StatDelta]:
    """뺏은 것들의 접사를 스탯별로 합친다.

    **플레이어의 합산과 갈라 둔다.** 저쪽(`merge_stat_deltas`)은 칸 규율을 담는다 —
    양손무기가 보조 칸을 봉인하고, 한 칸에 하나만 든다. 몬스터는 그것을 입은 것이 아니라
    **가진 것**이라 그 규율이 없다: 다섯을 가지면 다섯이 다 붙는다 (2026-09-06 결정).

    같은 함수를 쓰려고 칸 규율을 느슨하게 하면 **사람 쪽이 함께 느슨해진다.**

    Args:
        items: 붙는 것들.

    Returns:
        스탯 이름에서 합계로의 대응표.
    """
    totals: dict[str, StatDelta] = {}
    for entry in items:
        for affix in entry.affixes:
            if affix.stat not in COMBAT_STATS:
                continue
            found = totals.get(affix.stat, StatDelta(flat=0, percent=0))
            totals[affix.stat] = StatDelta(
                flat=found.flat + affix.flat, percent=found.percent + affix.percent
            )
    return totals


def compute_spoiled_stat(base: int, stat: str, spoils: dict[str, tuple[int, int]]) -> int:
    """뺏은 장비를 반영한 스탯 하나.

    정수만 쓴다. 곱한 뒤에 나눈다 — 먼저 나누면 절삭이 두 번 일어난다 (R5).
    **고정값을 먼저 더하고 퍼센트를 건다** — 사람의 장비 합산과 같은 순서여야 같은
    장비가 두 곳에서 다른 값을 내지 않는다.

    Args:
        base: 뺏은 장비 이전 값.
        stat: 볼 스탯 이름.
        spoils: 뺏은 장비의 보정.

    Returns:
        내림 절삭된 값. 0 아래로는 안 내려간다.
    """
    flat, percent = spoils.get(stat, (0, 0))
    return max(0, (base + flat) * (PERCENT_BASE + percent) // PERCENT_BASE)
