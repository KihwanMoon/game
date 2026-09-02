"""소모품 칸을 읽고 채우고 깎는다 (설계/4_아이템 §5).

**칸은 미리 깔지 않는다.** 계정마다 빈 줄을 만들어 두면 칸 수를 늘릴 때 기존 계정만
안 늘어난다 — 칸 수는 코드가 정하고(`schemas/consumable.py`), 줄이 없는 칸은 빈 칸으로
읽는다.

충전을 깎는 시점은 **층 정산**이다. 서버가 그 층까지 처음부터 다시 돌려 몇 개를 썼는지
알아내고, 그만큼만 깎는다 — 클라이언트가 「세 개 썼다」고 보고할 자리를 만들지 않는다
(T9). 런을 중간에 버려도 청구한 층까지 쓴 것은 이미 깎여 있다.
"""

from dataclasses import dataclass

from psycopg_pool import ConnectionPool

from game.schemas.consumable import FREE_CHARGES, build_slot_rows, list_slot_tags


@dataclass(frozen=True)
class ConsumableSlot:
    """소모품 칸 하나."""

    use_tag: str
    slot_index: int
    # 끼운 소모품. None 이면 빈 칸이고, 출격할 때 공짜로 한 개가 찬다.
    catalog_id: str | None
    charges: int


def list_consumable_slots(
    pool: ConnectionPool, entity_id: int, extra: dict[str, int] | None = None
) -> tuple[ConsumableSlot, ...]:
    """이 개체의 소모품 칸 전부를 정해진 순서로 읽는다.

    저장된 줄이 없는 칸은 **빈 칸으로 채워서** 돌려준다. 없는 것과 비어 있는 것을 화면이
    구분할 필요가 없고, 구분하면 「칸이 아직 안 생겼다」는 상태가 하나 더 생긴다.

    **칸이 줄면 넘치는 줄은 안 읽힌다.** 칸을 늘리던 장비를 빼면 그 칸은 잠기고, 끼워
    둔 것은 지워지지 않은 채 잠들어 있다가 다시 끼우면 돌아온다 — 지우면 장비를 잠깐
    바꿔 낀 것이 물약을 태운다.

    Args:
        pool: 연결 풀.
        entity_id: 대상 개체.
        extra: 장비 접사가 쓰임새마다 더한 칸 수. None 이면 기본 칸만이다.

    Returns:
        칸들. 쓰임새 순, 칸 번호 순이다 (R5).
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT use_tag, slot_index, catalog_id, charges"
            " FROM consumable_slot WHERE entity_id = %s",
            (entity_id,),
        ).fetchall()
    stored = {(str(row[0]), int(row[1])): (row[2], int(row[3])) for row in rows}
    slots: list[ConsumableSlot] = []
    for use_tag in list_slot_tags():
        for index in build_slot_rows(use_tag, (extra or {}).get(use_tag, 0)):
            catalog_id, charges = stored.get((use_tag, index), (None, 0))
            slots.append(
                ConsumableSlot(
                    use_tag=use_tag,
                    slot_index=index,
                    catalog_id=None if catalog_id is None else str(catalog_id),
                    charges=charges,
                )
            )
    return tuple(slots)


def count_slot_charges(slots: tuple[ConsumableSlot, ...]) -> dict[str, int]:
    """칸들이 이번 런에 실어 보내는 충전 수를 쓰임새별로 센다.

    **빈 칸은 공짜로 한 개다** (§5). 안 그러면 새 계정이 물약 없이 시작한다 — 이것이
    예전의 `balance.player.potions` 두 개를 대신하는 자리다.

    Args:
        slots: 읽어 온 칸들.

    Returns:
        쓰임새에서 충전 수로. 0 인 쓰임새는 담지 않는다.
    """
    counts: dict[str, int] = {}
    for slot in slots:
        amount = FREE_CHARGES if slot.catalog_id is None else slot.charges
        if amount > 0:
            counts[slot.use_tag] = counts.get(slot.use_tag, 0) + amount
    return counts


def apply_slot_load(
    pool: ConnectionPool,
    entity_id: int,
    use_tag: str,
    slot_index: int,
    catalog_id: str,
    charges: int,
) -> None:
    """칸에 소모품을 끼운다. 이미 있던 것은 밀려난다.

    Args:
        pool: 연결 풀.
        entity_id: 대상 개체.
        use_tag: 칸의 쓰임새.
        slot_index: 칸 번호.
        catalog_id: 끼울 소모품.
        charges: 가득 찬 충전 수.
    """
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO consumable_slot (entity_id, use_tag, slot_index, catalog_id, charges)"
            " VALUES (%s, %s, %s, %s, %s)"
            " ON CONFLICT (entity_id, use_tag, slot_index) DO UPDATE SET"
            " catalog_id = EXCLUDED.catalog_id, charges = EXCLUDED.charges",
            (entity_id, use_tag, slot_index, catalog_id, charges),
        )


def apply_slot_clear(pool: ConnectionPool, entity_id: int, use_tag: str, slot_index: int) -> None:
    """칸을 비운다. 남은 충전은 **돌려주지 않는다**.

    돌려주면 「끼웠다 빼기」로 보충 없이 물약을 옮길 수 있다.

    Args:
        pool: 연결 풀.
        entity_id: 대상 개체.
        use_tag: 칸의 쓰임새.
        slot_index: 칸 번호.
    """
    with pool.connection() as connection:
        connection.execute(
            "DELETE FROM consumable_slot WHERE entity_id = %s AND use_tag = %s AND slot_index = %s",
            (entity_id, use_tag, slot_index),
        )


def apply_slot_fill(
    pool: ConnectionPool, entity_id: int, use_tag: str, slot_index: int, charges: int
) -> bool:
    """빈 충전을 채운다.

    **끼운 것이 있는 칸만 채운다.** 빈 칸을 채우면 아무 소모품도 안 끼우고 충전만 살 수
    있게 된다.

    Args:
        pool: 연결 풀.
        entity_id: 대상 개체.
        use_tag: 칸의 쓰임새.
        slot_index: 칸 번호.
        charges: 채운 뒤의 충전 수.

    Returns:
        채웠으면 True. 빈 칸이면 False.
    """
    with pool.connection() as connection:
        filled = connection.execute(
            "UPDATE consumable_slot SET charges = %s"
            " WHERE entity_id = %s AND use_tag = %s AND slot_index = %s"
            " AND catalog_id IS NOT NULL",
            (charges, entity_id, use_tag, slot_index),
        )
    return filled.rowcount == 1


def apply_slot_spend(
    pool: ConnectionPool,
    entity_id: int,
    use_tag: str,
    used: int,
    extra: dict[str, int] | None = None,
) -> int:
    """이번 층에서 쓴 만큼 그 쓰임새의 칸에서 깎는다.

    **낮은 칸부터 깎는다.** 어느 칸의 것을 썼는지는 코어가 모른다 — 코어는 「POTION 몇
    개」만 세므로, 여기서 순서를 정해 준다. 정하지 않으면 같은 판이 실행마다 다른 칸을
    비운다 (R5).

    **여기서는 공짜분을 안 뺀다.** 그 셈은 부르는 쪽이 한다 — 층마다 정산이 돌고 이
    함수는 그때마다 불리므로, 여기서 빼면 **정산 한 번마다 공짜 충전이 새로 생긴다.**
    실제로 그렇게 돌아, 층을 깰 때마다 물약이 한 개씩 공짜였다.

    Args:
        pool: 연결 풀.
        entity_id: 대상 개체.
        use_tag: 쓰임새.
        used: 깎을 충전 수. **공짜분을 이미 뺀 값이어야 한다.**
        extra: 장비 접사가 더한 칸 수. **읽을 때와 같은 값이어야 한다** — 다르면 늘어난
            칸에서 쓴 것이 안 깎여 그 칸만 공짜가 된다.

    Returns:
        실제로 깎은 수.
    """
    if used <= 0:
        return 0
    slots = list_consumable_slots(pool, entity_id, extra)
    remaining = used
    taken = 0
    for slot in slots:
        if remaining <= 0:
            break
        if slot.use_tag != use_tag or slot.catalog_id is None or slot.charges <= 0:
            continue
        amount = min(slot.charges, remaining)
        with pool.connection() as connection:
            connection.execute(
                "UPDATE consumable_slot SET charges = charges - %s"
                " WHERE entity_id = %s AND use_tag = %s AND slot_index = %s AND charges >= %s",
                (amount, entity_id, use_tag, slot.slot_index, amount),
            )
        remaining -= amount
        taken += amount
    return taken


def count_free_charges(slots: tuple[ConsumableSlot, ...], use_tag: str) -> int:
    """이 쓰임새의 빈 칸이 출격 때 공짜로 주는 충전 수.

    **깎을 자리가 없는 몫이다.** 정산은 이만큼을 먼저 쓴 것으로 치고 나머지만 칸에서
    깎는다 — 그래야 한 개만 쓴 판에서 산 충전이 안 날아간다.

    Args:
        slots: 읽어 온 칸들.
        use_tag: 쓰임새.

    Returns:
        공짜 충전 수.
    """
    return sum(
        FREE_CHARGES for slot in slots if slot.use_tag == use_tag and slot.catalog_id is None
    )
