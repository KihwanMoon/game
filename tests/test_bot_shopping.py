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
    source = Path("scripts/run_bots.py").read_text(encoding="utf-8")
    assert "auction/list" not in source
    assert "auction/cancel" not in source
