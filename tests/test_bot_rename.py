"""관리자가 봇에게 이름을 지어 준다 (U3, 2026-09-18).

**손잡이가 화면에 없어서 서버 셸을 열어야 했다.** `BotEditor` 는 내력·실력%·간격초를
고치고 아이템까지 넘기는데 바로 그 위의 이름만 읽기 전용이었고, 바꾸려면
`scripts/rename_bot_handles.py` 를 돌려야 했다 — 그것은 한 번 돌리고 끝나는 소급
스크립트지 봇 하나를 골라 고치는 자리가 아니다.

지키는 것은 셋이다.

1. **사람이 쓰는 길을 그대로 쓴다.** `display_name.apply_nickname` 하나가 규칙과 중복
   검사를 든다 — 처음에 봇 전용 규칙을 따로 짰다가 되돌렸다. 사본은 한쪽만 고쳐진다.
2. **`nickname` 에 적는다.** 표시 이름이 `COALESCE(nickname, login_id, handle)` 이므로
   순위표·경매·도감·둔갑이 전부 그 이름을 쓴다 — 이름이 화면마다 달라지지 않는 유일한
   방법이다. `handle` 은 계정이 태어날 때 받는 내부 이름이라 안 건드린다.
3. **「이것이 봇이다」는 이름이 아니라 다른 채널이 싣는다.** 예전에는 `bot_` 접두어가 그
   일을 했는데, 그러면 봇 이름이 영영 id 처럼 보인다 — 색·글리프·명도 셋으로 적는 디자인
   규율과도 어긋난다. 화면은 `is_bot` 을 받아 표시한다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV
from game.app.store.display_name import NICKNAME_MAX

needs_db = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)


@pytest.fixture
def pool():
    """연결 풀. 스키마를 먼저 올린다 — 검사용 DB 는 백엔드가 뜨는 자리가 아니다."""
    from game.app.store.connection import apply_schema, create_pool

    running = create_pool(os.environ[DATABASE_URL_ENV])
    apply_schema(running)
    yield running
    running.close()


@pytest.fixture
def bot(pool):
    """검사용 봇 하나. 쓰고 지운다."""
    from game.app.store.accounts import apply_bot_handle, create_account

    account, _ = create_account(pool)
    apply_bot_handle(pool, account.account_id)
    with pool.connection() as connection:
        connection.execute("UPDATE account SET is_bot = true WHERE id = %s", (account.account_id,))
    yield pool, account.account_id
    with pool.connection() as connection:
        connection.execute("DELETE FROM account WHERE id = %s", (account.account_id,))


@needs_db
def test_the_name_lands_in_the_nickname(bot):
    """★ **`nickname` 에 적힌다** — 표시 이름이 그것을 먼저 보기 때문이다.

    `handle` 에 적으면 계정이 태어날 때 받은 내부 이름을 덮게 되고, 무엇보다 화면이
    닉네임을 먼저 보므로 지어 준 이름이 안 뜬다.
    """
    from game.app.store.bots import rename_bot
    from game.app.store.display_name import read_display_name

    pool, account_id = bot
    assert rename_bot(pool, account_id, "고블린사냥꾼") == "고블린사냥꾼"
    assert read_display_name(pool, account_id) == "고블린사냥꾼"
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT nickname, handle FROM account WHERE id = %s", (account_id,)
        ).fetchone()
    assert str(row[0]) == "고블린사냥꾼"
    # 내부 이름은 그대로다 — 계정을 가리키는 키라 바뀌면 안 된다.
    assert str(row[1]).startswith("bot_")


@needs_db
def test_the_same_rules_as_people(bot):
    """★ 사람 닉네임과 **같은 규칙**을 쓴다 — 봇만 다른 규칙을 두면 사본이 된다."""
    from game.app.store.bots import rename_bot

    pool, account_id = bot
    with pytest.raises(ValueError, match="자다"):
        rename_bot(pool, account_id, "가")
    with pytest.raises(ValueError, match="자다"):
        rename_bot(pool, account_id, "가" * (NICKNAME_MAX + 1))
    # 자동으로 붙는 이름과 겹치는 머리말은 사람도 못 쓴다.
    with pytest.raises(ValueError, match="머리말"):
        rename_bot(pool, account_id, "bot_사냥꾼")
    with pytest.raises(ValueError, match="쓸 수 있다"):
        rename_bot(pool, account_id, "고블린 사냥꾼")


@needs_db
def test_taken_name_is_refused(bot):
    """★ 겹치면 거절한다 — 조용히 딴 이름을 주면 지은 이름과 뜨는 이름이 갈린다.

    사람이 쓰는 이름과도 겹치면 안 된다. 순위표에서 남을 흉내 낼 수 있기 때문이고,
    그 규칙은 `apply_nickname` 하나가 든다.
    """
    from game.app.store.accounts import apply_bot_handle, create_account
    from game.app.store.bots import rename_bot

    pool, account_id = bot
    rename_bot(pool, account_id, "먼저온놈")
    other, _ = create_account(pool)
    apply_bot_handle(pool, other.account_id)
    with pool.connection() as connection:
        connection.execute("UPDATE account SET is_bot = true WHERE id = %s", (other.account_id,))
    try:
        with pytest.raises(ValueError, match="이미 쓰는"):
            rename_bot(pool, other.account_id, "먼저온놈")
        # 대소문자만 다른 것도 같은 이름으로 친다.
        with pytest.raises(ValueError, match="이미 쓰는"):
            rename_bot(pool, other.account_id, "먼저온놈".upper())
    finally:
        with pool.connection() as connection:
            connection.execute("DELETE FROM account WHERE id = %s", (other.account_id,))


@needs_db
def test_people_are_not_bots(pool):
    """★ 봇이 아닌 계정은 이 문으로 못 고친다 — 사람 이름은 사람이 짓는다."""
    from game.app.store.accounts import create_account
    from game.app.store.bots import rename_bot

    account, _ = create_account(pool)
    try:
        with pytest.raises(ValueError, match="봇이 아니다"):
            rename_bot(pool, account.account_id, "사람이름")
    finally:
        with pool.connection() as connection:
            connection.execute("DELETE FROM account WHERE id = %s", (account.account_id,))
