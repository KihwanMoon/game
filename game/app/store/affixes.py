"""봉인 옵션을 붙이고 다시 찍는다 (설계/4_아이템 §17).

`items.py` 에서 갈라 나왔다. 저쪽은 **아이템이 누구 것이고 어디 있는가**이고 여기는
**그 아이템에 어떤 줄이 박히는가**다. 파일이 400줄 상한에 닿은 것이 계기였을 뿐, 가르는
선은 책임이다 (§4).

**여는 것과 다시 찍는 것은 값이 다르다.** 봉인을 여는 것은 푼이고(`compute_unseal_cost`),
연 것을 다시 찍는 것은 활자다(`letters.py`). 하나로 두면 푼만 모으면 원하는 옵션이 나올
때까지 돌릴 수 있고, 그러면 봉인이 아무것도 막지 않는다 — 열기 전에 모르는 것이 이
기제의 전부다.
"""

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from game.app.store.items import build_affix_payload
from game.schemas.item import GRADE_SEALED_SLOTS, Affix


def list_affix_pool(pool: ConnectionPool) -> tuple[tuple[str, str, int, int, int, int, int], ...]:
    """옵션 풀을 읽는다. 폐기된 줄은 빠진다.

    Args:
        pool: 연결 풀.

    Returns:
        (stat, label_ko, flat_min, flat_max, percent_min, percent_max, weight) 들.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT stat, label_ko, flat_min, flat_max, percent_min, percent_max, weight"
            " FROM affix_pool WHERE NOT is_retired ORDER BY id"
        ).fetchall()
    return tuple(
        (str(r[0]), str(r[1]), int(r[2]), int(r[3]), int(r[4]), int(r[5]), int(r[6])) for r in rows
    )


def apply_unseal(pool: ConnectionPool, item_id: int, affix: Affix) -> bool:
    """봉인 한 칸을 열고 옵션을 붙인다.

    **조건부 갱신이다.** 남은 칸이 있을 때만 바뀌므로, 같은 요청이 두 번 와도 한 번만
    열린다 — 푼은 부르는 쪽이 이미 뺐다.

    Args:
        pool: 연결 풀.
        item_id: 대상 아이템.
        affix: 붙일 옵션.

    Returns:
        실제로 열렸으면 True.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT affixes FROM item_instance WHERE id = %s AND sealed_slots > 0", (item_id,)
        ).fetchone()
        if row is None:
            return False
        merged = list(row[0] or []) + build_affix_payload((affix,))
        cursor = connection.execute(
            "UPDATE item_instance SET affixes = %s, sealed_slots = sealed_slots - 1"
            " WHERE id = %s AND sealed_slots > 0",
            (Jsonb(merged), item_id),
        )
    return cursor.rowcount == 1


def apply_recast(pool: ConnectionPool, item_id: int, affix_index: int, affix: Affix) -> bool:
    """이미 연 칸의 옵션 하나를 다시 찍는다.

    **봉인에서 나온 줄만 바꾼다.** 정예 드롭이 달고 나온 접사까지 다시 찍게 하면, 활자가
    「봉인을 다시 여는 값」이 아니라 「모든 접사를 고르는 값」이 된다 — 드롭의 운이 통째로
    사라지는 자리다. `apply_unseal` 이 **뒤에 붙이므로** 봉인에서 나온 것은 언제나 꼬리
    쪽이고, 그래서 연 칸 수만큼의 꼬리가 곧 바꿀 수 있는 범위다.

    **칸을 안 늘린다.** 자리에 있는 값을 갈아 끼울 뿐이라 `sealed_slots` 를 안 건드린다 —
    이것이 활자가 전투력 천장을 안 올린다는 말의 실제 내용이다.

    Args:
        pool: 연결 풀.
        item_id: 대상 아이템.
        affix_index: 바꿀 자리. `affixes` 배열의 첨자다.
        affix: 새로 박을 옵션.

    Returns:
        실제로 바뀌었으면 True. 봉인에서 나온 자리가 아니면 False.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT affixes, coalesce(grade, ''), sealed_slots FROM item_instance WHERE id = %s",
            (item_id,),
        ).fetchone()
        if row is None:
            return False
        current = list(row[0] or [])
        opened = max(0, GRADE_SEALED_SLOTS.get(str(row[1]), 0) - int(row[2] or 0))
        first = len(current) - opened
        if opened <= 0 or affix_index < first or affix_index >= len(current):
            return False
        current[affix_index] = build_affix_payload((affix,))[0]
        cursor = connection.execute(
            "UPDATE item_instance SET affixes = %s WHERE id = %s", (Jsonb(current), item_id)
        )
    return cursor.rowcount == 1
