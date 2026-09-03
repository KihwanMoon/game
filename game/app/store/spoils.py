"""뺏어 든 장비가 몬스터를 세게 만든다 (결정 #34).

**예전에는 표식일 뿐이었다.** 도감이 「내 것을 들고 있다」고 말할 수는 있었지만 그
몬스터가 세지지는 않았고, 그러면 되찾으러 갈 이유가 감정뿐이다. 붙으면 「저놈이 내 갑옷
때문에 단단하다」가 되고, 그것이 World Loop 의 동기다.

몬스터 저장소에서 갈라 둔 이유는 책임이 다르기 때문이다 — 저쪽은 개체를 읽고 쓰고,
여기는 **든 것이 스탯에 얼마나 붙는가**만 안다 (§4 의 400줄 상한에 걸린 자리이기도 하다).
"""

import json

from psycopg_pool import ConnectionPool

# 퍼센트의 분모. 100 이 1.0배다.
PERCENT_BASE = 100


def list_spoil_deltas(pool: ConnectionPool, record_id: int) -> dict[str, tuple[int, int]]:
    """그 몬스터가 **뺏어 든 장비**가 주는 스탯 보정 (결정 #34).

    예전에는 뺏긴 장비가 표식일 뿐이었다 — 도감이 「내 것을 들고 있다」고 말할 수는
    있었지만 그 몬스터가 세지지는 않았다. 그러면 되찾으러 갈 이유가 감정뿐이다. 붙으면
    「저놈이 내 갑옷 때문에 단단하다」가 되고, 그것이 World Loop 의 동기다.

    **파손된 것은 안 붙는다.** 사람에게도 복구해야 쓰이는 것이므로 같은 규칙이다.

    Args:
        pool: 연결 풀.
        record_id: 볼 개체.

    Returns:
        스탯 이름에서 (합계 고정값, 합계 퍼센트) 로의 대응표.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT affixes FROM item_instance"
            " WHERE owner_entity_id = %s AND NOT is_broken ORDER BY id",
            (record_id,),
        ).fetchall()
    totals: dict[str, tuple[int, int]] = {}
    for row in rows:
        raw = row[0]
        if isinstance(raw, str):
            raw = json.loads(raw)
        for affix in raw if isinstance(raw, list) else []:
            if not isinstance(affix, dict):
                continue
            stat = str(affix.get("stat", ""))
            flat, percent = totals.get(stat, (0, 0))
            totals[stat] = (
                flat + int(affix.get("flat", 0)),
                percent + int(affix.get("percent", 0)),
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
