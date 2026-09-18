"""관리자가 봇 이름을 고친다 (U3, 2026-09-18).

**손잡이가 화면에 없어서 서버 셸을 열어야 했다.** `BotEditor` 는 내력·실력%·간격초를
고치고 아이템까지 넘기는데 바로 그 위의 이름만 읽기 전용이었고, 바꾸려면
`scripts/rename_bot_handles.py` 를 돌려야 했다 — 그것은 한 번 돌리고 끝나는 소급
스크립트지 봇 하나를 골라 고치는 자리가 아니다.

지키는 것은 셋이다.

1. **`bot_` 접두어는 안 바뀐다.** 그것이 「이것이 봇이다」를 싣는 유일한 채널이다 —
   순위표·경매·도감이 전부 이름만 적으므로, 떼는 순간 세 화면에서 봇이 사람과
   구별되지 않는다 (2026-09-11 실제 신고).
2. **닉네임을 쓰지 않는다.** 표시 이름이 `COALESCE(nickname, login_id, handle)` 이라
   (`display_name.py`), 봇에 닉네임을 주면 `handle` 이 표시에서 밀려나 같은 구멍이 난다.
3. **겹치면 거절한다.** 조용히 딴 이름으로 바꿔 주면 관리자가 지은 이름과 화면에 뜨는
   이름이 갈린다.
"""

import os

import pytest

from game.app.store.accounts import BOT_HANDLE_PREFIX
from game.app.store.bots import MAX_BOT_NAME
from game.app.store.connection import DATABASE_URL_ENV

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
    yield pool, account.account_id
    with pool.connection() as connection:
        connection.execute("DELETE FROM account WHERE id = %s", (account.account_id,))


@needs_db
def test_rename_keeps_the_bot_prefix(bot):
    """★ **접두어는 안 바뀐다.** 이름이 봇임을 싣는 유일한 채널이다."""
    from game.app.store.bots import rename_bot_handle

    pool, account_id = bot
    renamed = rename_bot_handle(pool, account_id, "고블린사냥꾼")
    assert renamed == f"{BOT_HANDLE_PREFIX}고블린사냥꾼"
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT handle FROM account WHERE id = %s", (account_id,)
        ).fetchone()
    assert str(row[0]) == renamed


@needs_db
def test_prefix_in_the_input_is_refused(bot):
    """★ 접두어를 받아서 또 붙이면 `bot_bot_…` 이 된다.

    받은 것을 그대로 쓰면 관리자가 접두어를 지워 봇을 사람처럼 세울 수도 있다.
    """
    from game.app.store.bots import rename_bot_handle

    pool, account_id = bot
    for wanted in (f"{BOT_HANDLE_PREFIX}사냥꾼", "user_사냥꾼", "BOT_사냥꾼"):
        with pytest.raises(ValueError, match="접두어"):
            rename_bot_handle(pool, account_id, wanted)


@needs_db
def test_taken_name_is_refused(bot):
    """★ 겹치면 거절한다 — 조용히 딴 이름을 주면 지은 이름과 뜨는 이름이 갈린다."""
    from game.app.store.accounts import apply_bot_handle, create_account
    from game.app.store.bots import rename_bot_handle

    pool, account_id = bot
    rename_bot_handle(pool, account_id, "먼저온놈")
    other, _ = create_account(pool)
    apply_bot_handle(pool, other.account_id)
    try:
        with pytest.raises(ValueError, match="이미 쓰는"):
            rename_bot_handle(pool, other.account_id, "먼저온놈")
        # 대소문자만 다른 것도 같은 이름으로 친다 — 순위표에서 남을 흉내 낼 수 있다.
        with pytest.raises(ValueError, match="이미 쓰는"):
            rename_bot_handle(pool, other.account_id, "먼저온놈 ".strip().upper())
    finally:
        with pool.connection() as connection:
            connection.execute("DELETE FROM account WHERE id = %s", (other.account_id,))


@needs_db
def test_same_name_again_is_fine(bot):
    """같은 이름을 다시 넣어도 된다 — 저장 버튼을 두 번 눌러도 거절당하면 안 된다."""
    from game.app.store.bots import rename_bot_handle

    pool, account_id = bot
    first = rename_bot_handle(pool, account_id, "그대로")
    assert rename_bot_handle(pool, account_id, "그대로") == first


@needs_db
def test_shape_is_checked(bot):
    """★ 빈 이름·긴 이름·공백 든 이름을 막는다.

    **가운데 공백을 막는 이유**는 한 줄에 적히는 값이라서다 — 이름이 둘로 읽히고, 순위표
    에서 다음 칸과 붙어 보인다.
    """
    from game.app.store.bots import rename_bot_handle

    pool, account_id = bot
    with pytest.raises(ValueError, match="비었다"):
        rename_bot_handle(pool, account_id, "   ")
    with pytest.raises(ValueError, match="넘는다"):
        rename_bot_handle(pool, account_id, "가" * (MAX_BOT_NAME + 1))
    with pytest.raises(ValueError, match="공백"):
        rename_bot_handle(pool, account_id, "고블린 사냥꾼")


@needs_db
def test_people_are_not_bots(pool):
    """★ 봇이 아닌 계정은 못 고친다 — 이 문은 봇 전용이다."""
    from game.app.store.accounts import create_account
    from game.app.store.bots import rename_bot_handle

    account, _ = create_account(pool)
    try:
        with pytest.raises(ValueError, match="봇이 아니다"):
            rename_bot_handle(pool, account.account_id, "사람")
    finally:
        with pool.connection() as connection:
            connection.execute("DELETE FROM account WHERE id = %s", (account.account_id,))
