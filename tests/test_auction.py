"""경매장의 경제 규칙 (결정 #20).

**DB 없이 도는 것만** 여기 둔다 — 수수료 계산과 상한. 흐름은 `test_api_auction.py` 다.

수수료가 이 게임의 **유일한 화폐 배출구**다. 없으면 화폐가 단조 증가해 몇 주 만에
가격이 무의미해진다.
"""

from game.app.store.auction import (
    LISTING_FEE_PERCENT,
    LISTING_TTL,
    MAX_PRICE,
    compute_fee,
)


def test_fee_is_a_percentage():
    assert compute_fee(1000) == 1000 * LISTING_FEE_PERCENT // 100


def test_fee_is_never_zero():
    """★ 0 이면 배출구가 막힌다. 싼 물건을 무한히 걸어 수수료를 피할 수 있다."""
    assert compute_fee(1) >= 1
    assert compute_fee(10) >= 1


def test_fee_floors_down():
    """정수 나눗셈이며 내림이다 — 부동소수를 쓰면 잔액이 소수점으로 갈라진다."""
    assert isinstance(compute_fee(333), int)
    assert compute_fee(333) == max(1, 333 * LISTING_FEE_PERCENT // 100)


def test_price_has_a_ceiling():
    """★ 상한이 없으면 자전거래로 임의의 금액을 한 번에 옮길 수 있다."""
    assert MAX_PRICE > 0
    assert compute_fee(MAX_PRICE) > 0


def test_listings_expire():
    """안 팔린 물건이 영원히 걸려 있으면 호가가 굳는다."""
    assert LISTING_TTL.total_seconds() > 0
