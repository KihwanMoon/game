"""봇에게 화폐를 넘긴다 (2026-09-06).

**봇에게 밑천을 주는 자리다.** 봇이 경매에서 사려면 화폐가 있어야 하는데, 벌이가 느린
봇은 영영 못 산다 — 그러면 「봇이 아무것도 안 산다」가 봇의 규칙이 아니라 잔액의 문제가
되고, 우리가 보려던 것(봇이 무엇을 고르는가)이 안 보인다.

지키는 것은 셋이다.

1. **화폐를 만들지 않는다.** 주는 쪽에서 빠진 만큼만 들어간다 (결정 #02).
2. **봇에게만 간다.** 사람에게 열면 계정 사이 화폐 이동이 되고, 봇 파밍으로 번 것을
   사람 계정에 모을 수 있다 (T11).
3. **한 방향이다.** 돌려받는 길을 두면 봇을 금고로 쓰는 계정이 생긴다 (결정 #07).
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)


@pytest.fixture
def pool():
    from game.app.store.connection import create_pool

    return create_pool(os.environ[DATABASE_URL_ENV])


@pytest.fixture
def pair(pool):
    """빈 계정 둘과, 첫째에게 100 을 넣어 둔 지갑."""
    from game.app.store.accounts import create_account
    from game.app.store.equipment import add_currency

    giver, _ = create_account(pool)
    taker, _ = create_account(pool)
    add_currency(pool, giver.account_id, 100)
    yield pool, giver.account_id, taker.account_id
    with pool.connection() as connection:
        for account_id in (giver.account_id, taker.account_id):
            connection.execute("DELETE FROM wallet WHERE account_id = %s", (account_id,))


def read_balance(pool, account_id):
    from game.app.store.equipment import read_balance as read

    return read(pool, account_id)


def test_the_coin_moves(pair):
    from game.app.store.gifts import apply_bot_coin_gift

    pool, giver, taker = pair
    assert apply_bot_coin_gift(pool, 30, giver, taker) == 70
    assert read_balance(pool, taker) == 30


def test_the_total_does_not_change(pair):
    """★ 화폐를 만들지 않는다 — 늘리는 문은 검증된 런 하나뿐이다."""
    from game.app.store.gifts import apply_bot_coin_gift

    pool, giver, taker = pair
    before = read_balance(pool, giver) + read_balance(pool, taker)
    apply_bot_coin_gift(pool, 40, giver, taker)
    assert read_balance(pool, giver) + read_balance(pool, taker) == before


def test_more_than_you_have_is_refused(pair):
    """★ 음수 잔액을 만드는 것보다 거절이 낫다."""
    from game.app.store.gifts import apply_bot_coin_gift

    pool, giver, taker = pair
    with pytest.raises(ValueError, match="모자란다"):
        apply_bot_coin_gift(pool, 101, giver, taker)
    # **아무것도 안 움직였다.** 한 트랜잭션이라 반쯤 넘어간 상태가 없다.
    assert read_balance(pool, giver) == 100
    assert read_balance(pool, taker) == 0


def test_zero_or_less_is_refused(pair):
    from game.app.store.gifts import apply_bot_coin_gift

    pool, giver, taker = pair
    for amount in (0, -5):
        with pytest.raises(ValueError, match="0 보다"):
            apply_bot_coin_gift(pool, amount, giver, taker)


def test_giving_to_yourself_is_refused(pair):
    """★ 잔액은 그대로인데 원장에는 오간 것으로 남는다 — 기록이 거짓이 된다."""
    from game.app.store.gifts import apply_bot_coin_gift

    pool, giver, _taker = pair
    with pytest.raises(ValueError, match="자기 자신"):
        apply_bot_coin_gift(pool, 10, giver, giver)
    assert read_balance(pool, giver) == 100


def test_an_empty_wallet_still_receives(pair):
    """받는 쪽에 지갑 행이 없어도 들어간다 — 없으면 만들고 넣는다."""
    from game.app.store.gifts import apply_bot_coin_gift

    pool, giver, taker = pair
    with pool.connection() as connection:
        connection.execute("DELETE FROM wallet WHERE account_id = %s", (taker,))
    apply_bot_coin_gift(pool, 10, giver, taker)
    assert read_balance(pool, taker) == 10
