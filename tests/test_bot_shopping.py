"""봇의 경매 구매 (T11, 결정 #02·#07).

지키는 것이 셋이다.

1. **봇은 사기만 한다.** 걸면 「봇이 파밍해서 사람에게 넘기는」 통로가 열린다.
2. **봇은 마지막 구매자다.** 열리자마자 채가면 시장을 채우려던 것이 시장을 봇의 것으로
   만든다.
3. **한 번에 하나만 산다.** 열 봇이 한 바퀴에 시장을 비우면 그것은 유동성이 아니라 청소다.
4. **넘치는 것만 산다.** 앞의 셋을 다 지켜도 열 봇이 시간당 쉰 번을 훑으면 매물 둘은
   여섯 시간을 넘긴 그 순간 사라진다 — 실측 경매 열림이 0 이었다. 규칙 하나하나가
   아니라 **총량**이 시장을 비웠다.
"""

from pathlib import Path

from game.app.bots.shopping import (
    FIRST_LOOK_MINUTES,
    LISTING_TTL_MINUTES,
    MIN_OPEN_LISTINGS,
    BagItem,
    Listing,
    check_is_open_to_bots,
    find_purchase,
    list_repairable,
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


def build_stocked(*listings: Listing) -> tuple[Listing, ...]:
    """봇이 손댈 수 있을 만큼 재고가 있는 시장을 만든다.

    봇은 **넘치는 것만** 산다. 그래서 다른 규칙(싼 것부터·동점 처리·예산)을 재려면
    먼저 재고 하한을 넘겨 둬야 한다 — 안 그러면 전부 「재고가 적다」로 0 이 나온다.

    Args:
        listings: 실제로 재는 매물들.

    Returns:
        하한을 넘긴 시장. 채움용 매물은 비싸서 후보가 되지 않는다.

    """
    filler = tuple(build_listing(900 + index, 100_000) for index in range(MIN_OPEN_LISTINGS + 1))
    return listings + filler


def test_the_cheapest_affordable_one_wins():
    """★ 싼 것부터 **하나만** 산다 — 한 바퀴에 시장을 비우면 청소다."""
    listings = build_stocked(build_listing(1, 90), build_listing(2, 30), build_listing(3, 50))
    assert find_purchase(listings, 100) == 2


def test_a_tie_breaks_on_listing_id():
    """값이 같으면 순서가 정해져야 한다 — 흔들리면 같은 상황에서 다른 일이 벌어진다."""
    assert find_purchase(build_stocked(build_listing(9, 30), build_listing(4, 30)), 100) == 4


def test_nothing_over_budget():
    """★ 잔액을 넘는 것은 안 산다 — 서버가 거절할 요청을 보내지 않는다."""
    assert find_purchase(build_stocked(build_listing(1, 90)), 100) == 0


def test_a_thin_market_is_left_alone():
    """★ **봇은 넘치는 것만 산다.**

    규칙 하나하나는 지켜지고 있었다 — 여섯 시간을 기다리고, 한 번에 하나만 사고, 잔액을
    남겼다. 그런데 열 봇이 시간당 다섯 판을 돌면 기회가 시간당 쉰 번이라, 매물 둘은
    여섯 시간을 넘긴 그 순간 사라진다. **실측 경매 열림이 0 이었다.** 총량이 시장을
    비운 것이며, 「사람이 열어 봤을 때 아무것도 없다」가 이 시스템의 실패 모습이다.
    """
    thin = tuple(build_listing(index, 10) for index in range(1, MIN_OPEN_LISTINGS + 1))
    assert len(thin) == MIN_OPEN_LISTINGS
    assert find_purchase(thin, 10_000) == 0
    # 한 건만 더 있으면 산다. 하한은 「이하」이지 「미만」이 아니다.
    assert find_purchase((*thin, build_listing(99, 10)), 10_000) != 0


def test_two_listings_survive_a_bot_pass():
    """★ **매물 둘짜리 시장은 봇이 손대지 않는다.**

    수를 상수에서 뽑지 않고 손으로 적는다 — 상수로 적으면 상수를 0 으로 바꿔도 검사가
    같이 움직여 아무것도 못 잡는다. 실제로 그렇게 지나갔다.

    둘은 실측값이다. 사람 둘이 하나씩 건 시장이 여섯 시간을 넘긴 순간 비었다.
    """
    market = (build_listing(1, 10), build_listing(2, 20))
    assert find_purchase(market, 10_000) == 0


def test_a_thin_market_counts_what_people_can_see():
    """★ 재고는 **사람이 볼 수 있는 전량**이지 봇이 살 수 있는 것이 아니다.

    봇이 못 사는 매물(너무 비싸다·아직 안 묵었다)도 사람에게는 재고다. 살 수 있는 것만
    세면 「사람 눈에는 스무 건인데 봇은 텅 빈 시장이라 판단」하는 일이 생긴다.
    """
    fresh = tuple(
        build_listing(index, 10, age_minutes=0) for index in range(1, MIN_OPEN_LISTINGS + 3)
    )
    # 아무것도 안 묵어서 살 것은 없지만, 재고가 적어서가 아니라 묵지 않아서다.
    assert find_purchase(fresh, 10_000) == 0
    aged = (*fresh, build_listing(50, 10, age_minutes=FIRST_LOOK_MINUTES))
    assert find_purchase(aged, 10_000) == 50


def test_my_own_listings_are_not_stock():
    """제 물건은 재고로 세지 않는다 — 세면 봇이 제 매물로 하한을 채우고 남의 것을 산다."""
    mine = tuple(
        build_listing(index, 10, is_mine=True) for index in range(1, MIN_OPEN_LISTINGS + 3)
    )
    assert find_purchase((*mine, build_listing(50, 10)), 10_000) == 0


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


def build_bag_item(item_id, slot="BODY", can_equip=True, is_broken=True):
    """수리 후보 하나를 짠다.

    Args:
        item_id: 아이템 id.
        slot: 장비 자리.
        can_equip: 낄 수 있는가.
        is_broken: 부서졌는가.

    Returns:
        가방 속 물건.
    """
    return BagItem(item_id=item_id, slot=slot, can_equip=can_equip, is_broken=is_broken)


def test_a_bot_repairs_what_it_can_wear():
    """★ **안 고치면 장비가 한 방향으로만 준다.**

    사망 페널티가 장착 중인 것을 부수는데(결정 #34), 아무도 안 고치면 봇의 장비는 죽을
    때마다 줄기만 하고 절대 늘지 않는다 — 「끼는 것이 지키는 것이다」의 뒷부분(복구
    가능)이 봇에게는 거짓이 되고, 몬스터가 뺏어 갈 것도 사라진다.
    """
    # 자리 이름 순이다 — 순서가 흔들리면 잔액이 빠듯할 때 같은 가방에서 다른 것이 고쳐진다.
    bag = (build_bag_item(2, slot="HEAD"), build_bag_item(1, slot="BODY"))
    assert [item.item_id for item in list_repairable(bag, 1000, 120)] == [1, 2]


def test_a_bot_leaves_what_is_not_broken():
    """멀쩡한 것을 고치면 화폐만 나간다."""
    assert list_repairable((build_bag_item(1, is_broken=False),), 1000, 120) == ()


def test_a_bot_leaves_what_it_cannot_wear():
    """★ 못 끼는 것은 안 고친다 — 고쳐도 아무것도 안 바뀌고 값만 나간다."""
    assert list_repairable((build_bag_item(1, can_equip=False),), 1000, 120) == ()
    assert list_repairable((build_bag_item(1, slot=""),), 1000, 120) == ()


def test_a_bot_repairs_only_what_it_can_pay_for():
    """★ 낼 수 있는 만큼만 고른다 — 잔액을 넘겨 보내면 서버가 거절하고 로그만 는다."""
    bag = tuple(build_bag_item(index, slot=f"S{index}") for index in range(1, 6))
    assert len(list_repairable(bag, 250, 120)) == 2
    assert list_repairable(bag, 119, 120) == ()


def test_a_free_repair_is_not_assumed():
    """값이 0 이면 나눗셈이 터지므로 아무것도 안 고른다 — 공짜 수리는 이 게임에 없다."""
    assert list_repairable((build_bag_item(1),), 1000, 0) == ()
