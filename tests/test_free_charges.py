"""공짜 충전이 붙는 자리 (설계/4_아이템 §5).

`test_consumable_slots.py` 에서 갈라 나왔다. 저쪽은 **칸이 어떻게 열리고 채워지는가**이고,
여기는 **어느 칸이 공짜를 받는가**다. 파일이 400줄 상한을 넘은 것이 계기였을 뿐, 가르는
선은 책임이다 (§4).

**빈 칸이면 무조건 한 개**이던 때, 칸을 늘리는 접사가 파는 것이 「담을 자리」가 아니라
**공짜 소모품**이었다. 실측으로 공짜 충전 하나는 720런 배치에서 평균 돌파 방 수를
+0.16 올렸다 — 유물 투구가 가진 전부(`hp_max +20`)가 +0.15, 보통 투구(`hp_max +8`)가
+0.07 이다. 접사 한 줄이 유물 한 줄을 넘었고, 저울이 그 축에 준 무게는 1 이라 스무 배에서
예순 배까지 어긋나 있었다.

무게를 정직하게 올리는 길도 있었지만, 그러면 「물약 칸 하나로 무기를 바꾼다」가 일어난다
(`gear_priority.json` 주석이 막으려던 것). **값을 내리는 쪽**을 골랐다.
"""

from game.schemas.consumable import check_is_base_slot


def build_slot(use_tag, slot_index, catalog_id=None, charges=0):
    """칸 하나를 만든다. **실제 배선과 같은 판정을 쓴다.**

    Args:
        use_tag: 쓰임새.
        slot_index: 칸 번호.
        catalog_id: 끼운 것. None 이면 빈 칸.
        charges: 남은 충전.

    Returns:
        칸 하나.
    """
    from game.app.store.consumables import ConsumableSlot

    return ConsumableSlot(
        use_tag=use_tag,
        slot_index=slot_index,
        catalog_id=catalog_id,
        charges=charges,
        is_base=check_is_base_slot(use_tag, slot_index),
    )


def test_the_base_count_decides_which_slots_are_free():
    """★ 기본 칸은 물약 둘·주문서 하나다. 그 뒤는 전부 접사가 연 칸이다."""
    assert [check_is_base_slot("POTION", i) for i in range(4)] == [True, True, False, False]
    assert [check_is_base_slot("SCROLL", i) for i in range(3)] == [True, False, False]


def test_an_affix_slot_gives_no_free_charge():
    """★ **접사가 파는 것은 「담을 자리」이지 소모품이 아니다.**

    주면 그 접사 한 줄이 유물 접사 한 줄을 넘는다 — 실측으로 공짜 충전 하나는 720런
    배치에서 평균 돌파 방 수를 +0.16 올렸고, 예지 투구가 가진 전부(`hp_max +20`)가
    +0.15, 철 투구(`hp_max +8`)가 +0.07 이었다. 저울이 그 축에 준 무게는 1 이라
    스무 배에서 예순 배까지 어긋나 있었다.
    """
    from game.app.store.consumables import count_slot_charges

    base_only = (build_slot("POTION", 0), build_slot("POTION", 1))
    with_affix = (*base_only, build_slot("POTION", 2), build_slot("POTION", 3))
    assert count_slot_charges(base_only)["POTION"] == 2
    assert count_slot_charges(with_affix)["POTION"] == 2, "접사 칸이 공짜 충전을 얹었다"


def test_an_affix_slot_still_carries_what_you_put_in_it():
    """★ 값을 없앤 것이 아니라 **공짜를 없앤 것**이다. 채우면 그대로 실린다."""
    from game.app.store.consumables import count_slot_charges

    slots = (
        build_slot("POTION", 0),
        build_slot("POTION", 1),
        build_slot("POTION", 2, "potion_elixir", 7),
    )
    assert count_slot_charges(slots)["POTION"] == 2 + 7


def test_the_settlement_only_forgives_base_slots():
    """★ 정산도 같은 셈이어야 한다.

    `apply_charge_spend` 가 「공짜분 먼저」로 빼는데 그 수가 실어 보낸 수보다 크면,
    산 충전이 안 깎이고 보충비가 영영 0 이 된다.
    """
    from game.app.store.consumables import count_free_charges

    slots = (build_slot("POTION", 0), build_slot("POTION", 1), build_slot("POTION", 2))
    assert count_free_charges(slots, "POTION") == 2


def test_the_base_free_charge_is_untouched():
    """★ 기본 칸의 공짜는 그대로다 — 없애면 새 계정이 물약 없이 시작한다.

    옛 `balance.player.potions` 두 개를 대신하는 자리다.
    """
    from game.app.store.consumables import count_slot_charges

    counted = count_slot_charges((build_slot("POTION", 0), build_slot("POTION", 1)))
    assert counted["POTION"] == 2
