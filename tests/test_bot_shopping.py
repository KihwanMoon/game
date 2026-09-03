"""봇의 경매 구매 (T11, 결정 #02·#07).

지키는 것이 셋이다.

1. **봇은 사기만 한다.** 걸면 「봇이 파밍해서 사람에게 넘기는」 통로가 열린다.
2. **봇은 마지막 구매자다.** 열리자마자 채가면 시장을 채우려던 것이 시장을 봇의 것으로
   만든다.
3. **한 번에 하나만 산다.** 열 봇이 한 바퀴에 시장을 비우면 그것은 유동성이 아니라 청소다.
"""

from pathlib import Path

from game.app.bots.shopping import (
    FIRST_LOOK_MINUTES,
    LISTING_TTL_MINUTES,
    Listing,
    check_is_open_to_bots,
    find_purchase,
    resolve_budget,
)


def build_listing(listing_id, price, age_minutes=FIRST_LOOK_MINUTES, is_mine=False):
    """매물 하나를 짠다.

    Args:
        listing_id: 매물 id.
        price: 호가.
        age_minutes: 걸린 지 지난 시간(분).
        is_mine: 내가 건 것인가.

    Returns:
        매물.
    """
    return Listing(
        listing_id=listing_id,
        price=price,
        is_mine=is_mine,
        expires_in_minutes=LISTING_TTL_MINUTES - age_minutes,
    )


def test_the_ttl_matches_the_auction_store():
    """★ 남은 시간에서 나이를 역산하므로 두 값이 같아야 한다.

    갈리면 봇이 「방금 걸린 것」을 오래된 것으로 알고 채간다.
    """
    from game.app.store.auction import LISTING_TTL

    assert int(LISTING_TTL.total_seconds() // 60) == LISTING_TTL_MINUTES


def test_a_fresh_listing_is_left_to_people():
    """★ 갓 걸린 물건은 안 산다 — 사람이 먼저 볼 시간을 준다."""
    assert not check_is_open_to_bots(build_listing(1, 10, age_minutes=0))
    assert not check_is_open_to_bots(build_listing(1, 10, age_minutes=FIRST_LOOK_MINUTES - 1))


def test_an_unwanted_listing_is_fair_game():
    """아무도 안 가져간 것에는 값을 매긴다 — 그것이 봇을 들인 이유다."""
    assert check_is_open_to_bots(build_listing(1, 10, age_minutes=FIRST_LOOK_MINUTES))


def test_a_bot_does_not_buy_its_own():
    """제 물건을 사면 화폐가 제자리를 돈다."""
    assert not check_is_open_to_bots(build_listing(1, 10, is_mine=True))


def test_a_bot_keeps_some_coin():
    """전부 털어 사면 다음에 더 좋은 것이 떠도 못 산다."""
    assert resolve_budget(100) == 80
    assert resolve_budget(0) == 0


def test_the_cheapest_affordable_one_wins():
    """★ 싼 것부터 **하나만** 산다 — 한 바퀴에 시장을 비우면 청소다."""
    listings = (build_listing(1, 90), build_listing(2, 30), build_listing(3, 50))
    assert find_purchase(listings, 100) == 2


def test_a_tie_breaks_on_listing_id():
    """값이 같으면 순서가 정해져야 한다 — 흔들리면 같은 상황에서 다른 일이 벌어진다."""
    assert find_purchase((build_listing(9, 30), build_listing(4, 30)), 100) == 4


def test_nothing_over_budget():
    """★ 잔액을 넘는 것은 안 산다 — 서버가 거절할 요청을 보내지 않는다."""
    assert find_purchase((build_listing(1, 90),), 100) == 0


def test_an_empty_market_buys_nothing():
    """빈 시장에서 0 을 돌려준다 — 부르는 쪽이 그것으로 「살 것 없음」을 안다."""
    assert find_purchase((), 1000) == 0


def test_the_runner_never_lists_anything():
    """★ **구조로 막는다.** 러너에 거는 길이 아예 없어야 한다.

    봇이 물건을 걸면 「봇이 파밍해서 사람에게 넘기는」 통로가 열리고, 그것이 T11 이자
    아이템의 문을 검증된 런 하나로 묶은 결정 #02 가 막으려던 것이다. 다음 사람이 편의를
    위해 한 줄 넣는 것을 여기서 막는다 — 주석은 안 읽히지만 검사는 걸린다.
    """
    source = "".join(
        Path(name).read_text(encoding="utf-8")
        for name in ("scripts/run_bots.py", "scripts/bot_chores.py", "scripts/bot_client.py")
    )
    assert "auction/list" not in source
    assert "auction/cancel" not in source


def build_bag_item(item_id, slot, can_equip=True, is_broken=False):
    """가방 속 물건 하나.

    Args:
        item_id: 아이템 id.
        slot: 들어갈 자리.
        can_equip: 요구조건을 채웠는가.
        is_broken: 파손됐는가.

    Returns:
        물건.
    """
    from game.app.bots.shopping import BagItem

    return BagItem(item_id=item_id, slot=slot, can_equip=can_equip, is_broken=is_broken)


def test_an_empty_slot_gets_filled():
    """★ **끼는 것이 지키는 것이다.**

    사망 페널티는 장착·가방을 통틀어 하나를 뽑는데, 장착 중이면 파손(복구 가능)이고
    가방에 있으면 삭제다 (결정 #34). 봇이 아무것도 안 끼면 그 유인의 반대편만 받는다 —
    실제로 봇 열이 스무 개를 그렇게 잃었다.
    """
    from game.app.bots.shopping import list_equippable

    picked = list_equippable((build_bag_item(1, "BODY"),), frozenset())
    assert [item.item_id for item in picked] == [1]


def test_a_filled_slot_is_left_alone():
    """★ 차 있는 자리는 안 건드린다.

    갈아 끼우려면 값을 매기는 기준이 필요하고, 기준이 틀리면 봇이 좋은 것을 벗고 나쁜
    것을 낀다. 빈 자리는 그 판단이 필요 없다.
    """
    from game.app.bots.shopping import list_equippable

    assert list_equippable((build_bag_item(1, "BODY"),), frozenset({"BODY"})) == ()


def test_one_per_slot():
    """★ 한 자리에 하나만 고른다 — 둘을 보내면 뒤엣것이 앞엣것을 벗긴다."""
    from game.app.bots.shopping import list_equippable

    picked = list_equippable(
        (build_bag_item(1, "BODY"), build_bag_item(2, "BODY"), build_bag_item(3, "FEET")),
        frozenset(),
    )
    assert sorted(item.slot for item in picked) == ["BODY", "FEET"]


def test_what_cannot_be_worn_is_skipped():
    """★ 요구조건을 못 채웠거나 파손된 것은 안 낀다 — 서버가 거절할 요청을 안 보낸다."""
    from game.app.bots.shopping import list_equippable

    bag = (
        build_bag_item(1, "BODY", can_equip=False),
        build_bag_item(2, "FEET", is_broken=True),
        build_bag_item(3, ""),
    )
    assert list_equippable(bag, frozenset()) == ()


def test_the_order_is_fixed():
    """순서가 흔들리면 같은 가방에서 다른 일이 벌어진다."""
    from game.app.bots.shopping import list_equippable

    bag = (build_bag_item(9, "HEAD"), build_bag_item(4, "BODY"))
    assert [item.slot for item in list_equippable(bag, frozenset())] == ["BODY", "HEAD"]


def test_unspent_points_get_spent():
    """★ **안 쓰면 없는 것과 같다.**

    포인트는 레벨과 함께 쌓이기만 하고 배분해야 몸에 붙는다 — 실제로 열 봇 전부 레벨 4 에
    배분표가 비어 있었고 9점씩 놀고 있었다. 레벨 4 짜리가 레벨 1 의 몸으로 싸운 것이다.
    """
    from game.app.bots.shopping import build_allocation
    from game.app.progression.levels import build_growth, count_spent_points

    stats = build_allocation(4, "g0_pressure", {})
    assert count_spent_points(stats) == build_growth(4).stat_points


def test_the_persona_shapes_the_body():
    """★ 성격을 따른다 — 열이 같은 몸을 가지면 규칙표를 갈라 둔 뜻이 절반 사라진다."""
    from game.app.bots.shopping import build_allocation

    ranged = build_allocation(10, "sniper", {})
    melee = build_allocation(10, "g0_pressure", {})
    assert ranged["dex"] > ranged["str"]
    assert melee["str"] > melee["dex"]


def test_nothing_left_over():
    """★ 나눗셈이 버린 나머지도 쓴다 — 버리면 그 포인트가 영영 안 쓰인다."""
    from game.app.bots.shopping import build_allocation
    from game.app.progression.levels import build_growth, count_spent_points

    for level in range(2, 12):
        stats = build_allocation(level, "focus_lowest", {})
        assert count_spent_points(stats) == build_growth(level).stat_points, level


def test_an_existing_allocation_is_kept():
    """★ 이미 쓴 것은 그대로 둔다 — 통째로 다시 쓰면 사람이 손댄 배분이 조용히 덮인다."""
    from game.app.bots.shopping import build_allocation

    assert build_allocation(4, "sniper", {"str": 9})["str"] == 9


def test_a_full_allocation_changes_nothing():
    """더 쓸 것이 없으면 그대로 둔다 — 서버가 거절할 요청을 안 보낸다."""
    from game.app.bots.shopping import build_allocation

    spent = build_allocation(4, "sniper", {})
    assert build_allocation(4, "sniper", spent) == spent


def test_the_allocation_passes_the_server_check():
    """★ 서버가 받아 주는 배분이어야 한다 — 안 그러면 봇은 영영 안 찍는다."""
    from game.app.bots.shopping import build_allocation
    from game.app.progression.levels import check_allocation

    for level in range(1, 12):
        stats = build_allocation(level, "kite_summoner", {})
        assert check_allocation(stats, level) == "", (level, stats)


def build_slot(use_tag, slot_index, catalog_id=""):
    """소모품 칸 하나.

    Args:
        use_tag: 쓰임새.
        slot_index: 칸 번호.
        catalog_id: 끼워져 있는 것. 비었으면 빈 칸이다.

    Returns:
        칸.
    """
    from game.app.bots.shopping import ConsumableSlot

    return ConsumableSlot(use_tag=use_tag, slot_index=slot_index, catalog_id=catalog_id)


def build_option(catalog_id, use_tag, count=1):
    """가방 속 소모품 하나.

    Args:
        catalog_id: 소모품 id.
        use_tag: 쓰임새.
        count: 가진 수.

    Returns:
        후보.
    """
    from game.app.bots.shopping import ConsumableOption

    return ConsumableOption(catalog_id=catalog_id, use_tag=use_tag, count=count)


def test_an_empty_slot_gets_loaded():
    """★ **끼워야 보충이 돈다.**

    정비의 REFILL 은 이미 끼운 것을 채우기만 한다 — 칸이 비어 있으면 채울 대상이 없어서
    아무 일도 안 일어나고, 주운 소모품은 가방에 쌓이다가 죽을 때 사라진다.
    """
    from game.app.bots.shopping import list_loadable

    picked = list_loadable((build_slot("POTION", 0),), (build_option("potion_heal", "POTION", 3),))
    assert [(slot.use_tag, catalog_id) for slot, catalog_id in picked] == [
        ("POTION", "potion_heal")
    ]


def test_a_loaded_slot_is_left_alone():
    """이미 끼운 칸은 안 건드린다 — 갈아 끼우면 남은 충전이 버려진다."""
    from game.app.bots.shopping import list_loadable

    slots = (build_slot("POTION", 0, "potion_greater"),)
    assert list_loadable(slots, (build_option("potion_heal", "POTION", 3),)) == ()


def test_the_use_tag_must_match():
    """★ POTION 칸에 SCROLL 을 밀어 넣지 않는다 — 서버가 거절할 요청을 안 보낸다."""
    from game.app.bots.shopping import list_loadable

    assert list_loadable((build_slot("POTION", 0),), (build_option("scroll_ward", "SCROLL"),)) == ()


def test_one_stack_does_not_fill_two_slots():
    """★ 하나뿐인 것을 두 칸에 나눠 쓰지 않는다 — 둘째 요청은 「가방에 없다」로 걸린다."""
    from game.app.bots.shopping import list_loadable

    picked = list_loadable(
        (build_slot("POTION", 0), build_slot("POTION", 1)),
        (build_option("potion_heal", "POTION", 1),),
    )
    assert len(picked) == 1


def test_two_stacks_fill_two_slots():
    """넉넉하면 다 채운다."""
    from game.app.bots.shopping import list_loadable

    picked = list_loadable(
        (build_slot("POTION", 0), build_slot("POTION", 1)),
        (build_option("potion_heal", "POTION", 2),),
    )
    assert len(picked) == 2


def test_the_order_is_fixed_for_slots():
    """순서가 흔들리면 같은 가방에서 다른 몸이 나간다."""
    from game.app.bots.shopping import list_loadable

    slots = (build_slot("SCROLL", 0), build_slot("POTION", 1), build_slot("POTION", 0))
    picked = list_loadable(
        slots, (build_option("potion_heal", "POTION", 2), build_option("scroll_ward", "SCROLL", 1))
    )
    assert [(slot.use_tag, slot.slot_index) for slot, _id in picked] == [
        ("POTION", 0),
        ("POTION", 1),
        ("SCROLL", 0),
    ]


def test_an_empty_bag_loads_nothing():
    """가방이 비면 아무것도 안 끼운다 — 지금 봇들이 그 상태다."""
    from game.app.bots.shopping import list_loadable

    assert list_loadable((build_slot("POTION", 0),), ()) == ()
