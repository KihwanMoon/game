"""봇의 리듬 — 시간당 두 판이 상한이다.

**상한을 세우는 이유가 둘이다.** 하나는 부하다: 런 단위 레이트 리밋이 없어(로그인만
`throttle` 이 센다) 봇이 이 API 의 첫 대량 클라이언트가 된다. 다른 하나는 경제다 —
봇이 사람보다 빨리 돌면 전리품과 화폐가 봇 쪽에서 나오고, 시장을 채우려던 것이 시장을
봇의 것으로 만든다.
"""

from game.app.bots.personas import (
    BOT_PERSONAS,
    HOUR,
    MAX_RUNS_PER_HOUR,
    MIN_CADENCE_SEC,
    resolve_cadence,
)


def test_the_names_are_bot1_through_bot10():
    """★ 이름이 `bot1`~`bot10` 이다 — 화면에서 봇임을 바로 알아봐야 한다 (T11).

    성격 이름(「겁쟁이」)은 사람 이름처럼 보여서 그 목적과 어긋난다. 성격은 남기되
    계정 이름은 따로 짓는다.
    """
    from game.app.bots.play import list_persona_specs

    names = [spec[0] for spec in list_persona_specs()]
    assert names == [f"bot{number}" for number in range(1, 11)]


def test_the_cap_is_two_runs_an_hour():
    """★ 상한이 실제로 시간당 둘이다 — 간격을 바꿔도 이 등식이 남는다.

    다섯이던 것을 2026-09-10 에 둘로 낮췄다. 열 명이 합쳐 50판이던 것이 20판이다.
    """
    assert HOUR // MIN_CADENCE_SEC == MAX_RUNS_PER_HOUR
    assert MIN_CADENCE_SEC == 1800


def test_a_faster_cadence_is_pushed_back():
    """★ 더 빠른 값을 넣어도 상한으로 밀린다.

    성격 정의에만 적으면 그건 데이터라 다음 사람이 더 빠른 수를 넣을 수 있고, 그러면
    상한이 있었다는 사실만 남는다.
    """
    assert resolve_cadence(1) == MIN_CADENCE_SEC
    assert resolve_cadence(0) == MIN_CADENCE_SEC
    assert resolve_cadence(-100) == MIN_CADENCE_SEC


def test_a_slower_cadence_is_left_alone():
    """느린 봇은 그대로 둔다 — 상한이지 목표가 아니다."""
    assert resolve_cadence(HOUR * 4) == HOUR * 4


def test_every_persona_respects_the_cap():
    """★ 열 명 전부가 상한 안에 있다."""
    for persona in BOT_PERSONAS:
        assert persona.cadence_sec >= MIN_CADENCE_SEC, persona.label


def test_every_bot_runs_at_the_cap():
    """★ 봇마다 시간당 두 판이다.

    리듬을 갈라 두면 세계가 고르게 움직이지만, 지금은 **세계가 너무 조용한 것**이 더 큰
    문제다 — 경매 등록이 4건이다. 다양성보다 활동량을 택한 자리이며, 조용함이 해결되면
    다시 갈라 볼 값이다.
    """
    for persona in BOT_PERSONAS:
        assert HOUR // persona.cadence_sec == MAX_RUNS_PER_HOUR, persona.label


def test_ten_bots_cannot_exceed_twenty_runs_an_hour():
    """★ 열 명을 합쳐도 시간당 20판이 천장이다 — 부하 상한이 이 수다.

    50 이던 것을 2026-09-10 에 20 으로 낮췄다. 봇은 세계를 혼자 두지 않으려고 있는
    것이지 세계를 채우려고 있는 것이 아니다.
    """
    ceiling = sum(HOUR // persona.cadence_sec for persona in BOT_PERSONAS)
    assert ceiling == MAX_RUNS_PER_HOUR * len(BOT_PERSONAS) == 20


def test_the_store_pushes_back_a_too_fast_bot(monkeypatch):
    """★ 쓰는 자리에서 물린다 — 순수 함수만 맞고 호출부가 안 부르면 상한은 없는 것이다.

    `create_bot` 과 `apply_bot_rest` 가 `next_run_at` 을 정하는 두 자리다. 둘 중 하나라도
    날것의 값을 쓰면 그 길로 상한을 넘긴다.
    """
    from game.app.store import bots as bot_store

    written: list[object] = []

    class FakeConnection:
        def execute(self, _sql, params=None):
            written.append(params)
            return self

        def fetchone(self):
            return None

        def fetchall(self):
            return []

    class FakePool:
        def connection(self):
            from contextlib import nullcontext

            return nullcontext(FakeConnection())

    pool = FakePool()
    bot_store.create_bot(pool, 1, "빠른봇", "g0_kite", 1, 100)
    # INSERT 의 네 번째 자리가 리듬이다. 1초로 넣었는데 상한으로 밀려 있어야 한다.
    assert written[-1][3] == MIN_CADENCE_SEC

    written.clear()
    from datetime import UTC, datetime

    before = datetime.now(UTC)
    bot_store.apply_bot_rest(pool, 1, 1)
    gap = (written[-1][0] - before).total_seconds()
    assert gap >= MIN_CADENCE_SEC - 1


def test_a_bot_account_is_named_like_a_bot(monkeypatch):
    """★ **봇 이름이 `user_` 로 시작하면 안 된다** (2026-09-11, 실제 신고).

    봇은 사람과 같은 익명 계정으로 태어나므로 이름이 `user_xxxx` 다. 그런데 순위표·
    경매·도감이 전부 이 이름만 적어서, 어디에서도 봇인지 알 수 없었다.

    **앞만 바꾼다.** 뒷자리는 이미 유일하므로 이름 충돌이 안 생기고, 같은 계정이 늘
    같은 이름으로 남는다 — 순위표에 적힌 이름이 어느 날 통째로 달라지면 「누가
    누구였지」가 된다.
    """
    from game.app.store.accounts import BOT_HANDLE_PREFIX, HANDLE_PREFIX, apply_bot_handle

    seen: dict[str, str] = {"handle": f"{HANDLE_PREFIX}a1b2c3d4"}

    class FakeCursor:
        def fetchone(self):
            return (seen["handle"],)

    class FakeConnection:
        def execute(self, sql, params=()):
            if sql.startswith("UPDATE"):
                seen["handle"] = params[0]
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class FakePool:
        def connection(self):
            return FakeConnection()

    pool = FakePool()
    assert apply_bot_handle(pool, 1) == f"{BOT_HANDLE_PREFIX}a1b2c3d4"
    # 뒷자리가 그대로다 — 같은 계정이 늘 같은 이름이다.
    assert seen["handle"].endswith("a1b2c3d4")
    # 여러 번 불러도 같다.
    assert apply_bot_handle(pool, 1) == f"{BOT_HANDLE_PREFIX}a1b2c3d4"
