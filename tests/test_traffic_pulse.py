"""트래픽 원장과 깔때기 (U2, 2026-09-18).

**두 수가 다른 것을 센다.** 계정 행은 **출격을 누른 사람**이고(`requireAccount` 가
"여는 것만으로는 안 만든다"), `traffic_day` 는 **열어 본 사람**이다. 그동안 명부는
앞엣것을 「다녀간 사람」이라 부르며 뒤엣것인 척했다.

여기서 지키는 것은 셋이다.

1. **비율은 정수다.** 부동소수를 피하는 규율(TDD §1.1)이 화면 수치에도 걸린다.
2. **출처가 값과 함께 남는다.** 계측을 갈아 끼우는 날 같은 날짜에 두 출처가 나란히
   있어야 한다 — 덮어쓰면 그날을 기점으로 선이 점프하고 이유를 아무도 모른다.
3. **봇은 사람이 아니다.** 봇 계정도 `account` 행이라 그동안 「다녀간 사람」에 섞였다.
"""

import os
from datetime import date, timedelta

import pytest

from game.app.store.connection import DATABASE_URL_ENV
from game.app.store.traffic import compute_conversion_pct


class TestConversionPct:
    """전환율은 정수이고, 모르는 것과 0 을 구별할 수 있어야 한다."""

    def test_conversion_is_floor_division(self):
        """★ 내림한 정수를 낸다 — 반올림하면 기기마다 다른 값이 나온다."""
        assert compute_conversion_pct(127, 24) == 18
        assert compute_conversion_pct(3, 1) == 33
        assert compute_conversion_pct(100, 19) == 19

    def test_no_visits_is_zero_not_error(self):
        """★ 들른 사람이 0 이면 0 이다 — 나누다 죽지 않는다.

        **부르는 쪽이 `visits` 를 함께 봐야 한다.** 여기서 낸 0 은 「아무도 안 했다」와
        「아직 계측을 못 받았다」 둘 다일 수 있고, 화면은 그 둘을 달리 적어야 한다.
        """
        assert compute_conversion_pct(0, 0) == 0
        assert compute_conversion_pct(-5, 3) == 0

    def test_everyone_played_is_hundred(self):
        """모두가 판을 내면 100 이다. 넘는 값도 그대로 낸다 — 접으면 이상을 숨긴다.

        들른 사람보다 판을 낸 사람이 많은 날이 실제로 있었다(2026-09-16: 96 대 98).
        고유 방문이 IP 기준이라 같은 집의 기기 둘이 하나로 접히기 때문이며, 그것은
        가려야 할 오류가 아니라 **계측의 성질**이라 화면이 볼 수 있어야 한다.
        """
        assert compute_conversion_pct(50, 50) == 100
        assert compute_conversion_pct(96, 98) == 102


# **모듈 전체에 걸지 않는다.** `pytestmark` 는 적은 위치와 무관하게 파일 전부를 건너뛰어,
# DB 없이도 돌아야 할 순수 검사(전환율)까지 함께 꺼진다.
needs_db = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)


@pytest.fixture
def pool():
    """연결 풀. **스키마를 먼저 올린다.**

    검사용 DB(`game_test`)는 백엔드가 뜨는 자리가 아니라 `apply_schema` 가 저절로
    돌지 않는다. 멱등이므로 매번 불러도 같다.
    """
    from game.app.store.connection import apply_schema, create_pool

    running = create_pool(os.environ[DATABASE_URL_ENV])
    apply_schema(running)
    yield running
    running.close()


@pytest.fixture
def clean_days(pool):
    """검사용 날짜 둘을 쓰고 지운다 — 실제 수치를 건드리지 않는다."""
    far = date(2000, 1, 1)
    days = (far, far + timedelta(days=1))
    yield pool, days
    with pool.connection() as connection:
        for day in days:
            connection.execute("DELETE FROM traffic_day WHERE day = %s", (day,))


@needs_db
def test_same_day_overwrites(clean_days):
    """★ 같은 날·같은 출처를 다시 적으면 덮어쓴다.

    오늘치는 하루가 끝날 때까지 자라므로, 한 번 적고 마는 구조면 오늘이 늘 모자란 수로
    남는다.
    """
    from game.app.store.traffic import save_traffic_day

    pool, (day, _) = clean_days
    save_traffic_day(pool, day, visits=10, views=20, requests=30)
    save_traffic_day(pool, day, visits=11, views=22, requests=33)
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT visits, views, requests FROM traffic_day WHERE day = %s", (day,)
        ).fetchall()
    assert len(rows) == 1
    assert tuple(rows[0]) == (11, 22, 33)


@needs_db
def test_sources_do_not_overwrite_each_other(clean_days):
    """★ **출처가 다르면 다른 행이다.**

    계측을 갈아 끼우는 날 같은 날짜에 두 값이 나란히 남아야 한다. 덮어쓰면 그날을
    기점으로 선이 점프하는데, 몇 달 뒤에는 그것이 계측 교체 때문인지 사람이 몰린
    것인지 아무도 구별 못 한다.
    """
    from game.app.store.traffic import save_traffic_day

    pool, (day, _) = clean_days
    save_traffic_day(pool, day, visits=10, views=20, requests=30, source="cloudflare")
    save_traffic_day(pool, day, visits=99, views=98, requests=97, source="자체집계")
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT source, visits FROM traffic_day WHERE day = %s ORDER BY source", (day,)
        ).fetchall()
    assert [(str(r[0]), int(r[1])) for r in rows] == [("cloudflare", 10), ("자체집계", 99)]


@needs_db
def test_window_cuts_by_date(clean_days):
    """★ 창은 날짜로 자른다 — 창 밖의 날이 합계에 새면 「이번 주」가 뜻을 잃는다."""
    from game.app.store.traffic import read_traffic_window, save_traffic_day

    pool, (day, _) = clean_days
    before = read_traffic_window(pool, days=7).visits
    # 먼 과거라 7일 창 밖이다. 창이 날짜를 제대로 자르는지도 함께 본다.
    save_traffic_day(pool, day, visits=500, views=500, requests=500)
    assert read_traffic_window(pool, days=7).visits == before


@needs_db
def test_pulse_excludes_bots(pool):
    """★ **봇은 「다녀간 사람」이 아니다.**

    봇 계정도 `account` 행이라 그동안 누적 수치에 섞여 있었다(10/138 = 7%). 순위표·
    경매·도감이 이름만 적으므로 봇을 이름에 싣기로 했고(`BOT_HANDLE_PREFIX`), 세는
    쪽도 같은 규율을 따라야 한다.
    """
    from game.app.store.accounts import BOT_HANDLE_PREFIX
    from game.app.store.world_view import read_world_pulse

    pulse = read_world_pulse(pool)
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT count(*) FROM account WHERE deactivated_at IS NULL AND handle LIKE %s",
            (f"{BOT_HANDLE_PREFIX}%",),
        ).fetchone()
    bots = int(row[0]) if row is not None else 0
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT count(*) FROM account WHERE deactivated_at IS NULL"
        ).fetchone()
    everyone = int(row[0]) if row is not None else 0
    assert pulse.visitors == everyone - bots


@needs_db
def test_pulse_carries_window_and_source(pool):
    """★ 화면이 기간과 출처를 밝힐 수 있어야 한다.

    누적 절대값은 계측을 갈아 끼우는 순간 점프해 예전 값과 이어 붙일 수 없다. 기간이
    안 적혀 있으면 보는 사람이 그것을 알아챌 방법이 없고, 출처가 안 적혀 있으면 수가
    뛴 날을 「갑자기 대박」으로 읽는다.
    """
    from game.app.store.world_view import read_world_pulse

    pulse = read_world_pulse(pool, window_days=7)
    assert pulse.window_days == 7
    assert pulse.traffic_source == "cloudflare"
    assert pulse.conversion_pct == compute_conversion_pct(pulse.window_visits, pulse.window_played)
