"""지킴이가 남긴 것 (설계/9_에이전트_운영 §4.1, 알려진이슈 Z1).

**로그에서 죽고 있었다.** 5분마다 정확히 판단해 컨테이너 로그에 뱉었고, 컨테이너 로그를
읽는 사람은 없다.

여기서 지키는 것은 둘이다.

1. **등급이 바뀔 때만 이력을 쌓는다.** 매 틱을 다 쌓으면 하루 2천 줄이 되고, 그 안에서
   「언제부터 틀렸나」를 찾는 것이 다시 일이 된다.
2. **등급이 그대로면 「언제부터」를 안 밀어낸다.** 밀면 그 값이 매 틱 지금이 되어 뜻을
   잃고, 지킴이를 붙인 이유(그날 안에 드러난다)가 화면에서 사라진다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV
from game.app.watch.checks import LEVEL_ALARM, LEVEL_OK, LEVEL_WARN, build_finding

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)

KEY = "표본지표"


@pytest.fixture
def pool():
    from game.app.store.connection import create_pool

    running = create_pool(os.environ[DATABASE_URL_ENV])
    with running.connection() as connection:
        connection.execute("DELETE FROM watch_state WHERE key = %s", (KEY,))
        connection.execute("DELETE FROM watch_event WHERE key = %s", (KEY,))
    yield running
    with running.connection() as connection:
        connection.execute("DELETE FROM watch_state WHERE key = %s", (KEY,))
        connection.execute("DELETE FROM watch_event WHERE key = %s", (KEY,))


def build_probe(level, detail="0 / 10"):
    return build_finding(KEY, level, "표본 소견", detail)


def find_row(pool, key):
    from game.app.store.watch_log import list_watch_state

    return next((row for row in list_watch_state(pool) if row.key == key), None)


def count_events(pool, key):
    from game.app.store.watch_log import list_watch_events

    return len([one for one in list_watch_events(pool, 100) if one.key == key])


def test_the_first_look_is_written(pool):
    from game.app.store.watch_log import save_watch_findings

    assert save_watch_findings(pool, (build_probe(LEVEL_OK),)) == 1
    row = find_row(pool, KEY)
    assert row is not None and row.level == LEVEL_OK


def test_the_same_grade_does_not_pile_up(pool):
    """★ 매 틱을 다 쌓으면 하루 2천 줄이 되고, 그 안에서 「언제부터」를 찾는 것이 일이 된다."""
    from game.app.store.watch_log import save_watch_findings

    save_watch_findings(pool, (build_probe(LEVEL_OK),))
    assert save_watch_findings(pool, (build_probe(LEVEL_OK),)) == 0
    assert save_watch_findings(pool, (build_probe(LEVEL_OK),)) == 0
    assert count_events(pool, KEY) == 1


def test_a_changed_grade_is_recorded(pool):
    from game.app.store.watch_log import save_watch_findings

    save_watch_findings(pool, (build_probe(LEVEL_OK),))
    assert save_watch_findings(pool, (build_probe(LEVEL_ALARM),)) == 1
    assert count_events(pool, KEY) == 2
    row = find_row(pool, KEY)
    assert row is not None and row.level == LEVEL_ALARM


def test_the_since_stamp_holds_while_the_grade_holds(pool):
    """★ **이것이 이 표의 전부다.** 「어제 낮부터 틀렸다」가 여기서 읽힌다.

    등급이 그대로인데 `changed_at` 을 밀면 그 값이 매 틱 지금이 되어 뜻을 잃는다.
    """
    from game.app.store.watch_log import save_watch_findings

    save_watch_findings(pool, (build_probe(LEVEL_ALARM, "1 / 10"),))
    first = find_row(pool, KEY)
    # 수치만 움직인다 — 판단은 그대로다.
    save_watch_findings(pool, (build_probe(LEVEL_ALARM, "4 / 10"),))
    later = find_row(pool, KEY)
    assert first is not None and later is not None
    assert later.changed_at == first.changed_at, "등급이 그대로인데 「언제부터」가 밀렸다"
    # 마지막으로 본 때와 실측은 따라 움직인다.
    assert later.detail == "4 / 10"


def test_the_since_stamp_moves_when_the_grade_moves(pool):
    from game.app.store.watch_log import save_watch_findings

    save_watch_findings(pool, (build_probe(LEVEL_OK),))
    before = find_row(pool, KEY)
    save_watch_findings(pool, (build_probe(LEVEL_WARN),))
    after = find_row(pool, KEY)
    assert before is not None and after is not None
    assert after.changed_at >= before.changed_at


def test_the_worst_comes_first(pool):
    """★ 여덟 줄이 등급 없이 늘어서면 무엇을 먼저 볼지가 안 정해지고, 결국 안 읽힌다."""
    from game.app.store.watch_log import list_watch_state, save_watch_findings

    save_watch_findings(
        pool,
        (
            build_finding(f"{KEY}", LEVEL_ALARM, "틀렸다", ""),
            build_finding("정상표본", LEVEL_OK, "괜찮다", ""),
        ),
    )
    levels = [row.level for row in list_watch_state(pool)]
    if LEVEL_ALARM in levels and LEVEL_OK in levels:
        assert levels.index(LEVEL_ALARM) < levels.index(LEVEL_OK)
    with pool.connection() as connection:
        connection.execute("DELETE FROM watch_state WHERE key = '정상표본'")
        connection.execute("DELETE FROM watch_event WHERE key = '정상표본'")
