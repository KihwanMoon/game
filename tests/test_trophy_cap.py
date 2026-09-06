"""전리품 상한 (결정 #34, 2026-09-06 개정).

**상한이 없어서 무한히 쌓였다.** 패배마다 사본 하나가 들어오는데 봇이 쉼 없이 죽으므로,
1층 고블린 하나가 **696개**를 들고 있었다 — 도감이 못 읽을 화면이 되고 「저 놈이 내 걸
들고 있다」가 목록에 묻힌다.

다섯까지만 들고, **더 강해질 때만** 받는다. 그래서 개체가 「지금까지 본 것 중 가장 좋은
다섯」으로 수렴한다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV
from game.app.store.trophies import MAX_TROPHIES, compute_affix_score

# ── 값어치 매기기 — DB 없이 돈다 ─────────────────────────────────────────


def test_a_bigger_affix_scores_higher():
    assert compute_affix_score([{"stat": "attack", "flat": 9}]) > compute_affix_score(
        [{"stat": "attack", "flat": 3}]
    )


def test_more_affixes_score_higher():
    both = [{"stat": "attack", "flat": 3}, {"stat": "defense", "flat": 3}]
    assert compute_affix_score(both) > compute_affix_score([{"stat": "attack", "flat": 3}])


def test_a_string_payload_is_read():
    """DB 가 절을 문자열로 줄 수 있다. 0 으로 떨어지면 좋은 것이 약한 것으로 읽힌다."""
    assert compute_affix_score('[{"stat": "attack", "flat": 7}]') == 7


def test_a_broken_payload_scores_nothing():
    """절이 아니면 0 이다 — 터지면 그 판의 결산이 통째로 죽는다."""
    assert compute_affix_score(None) == 0
    assert compute_affix_score("이건 절이 아니다") == 0
    assert compute_affix_score([]) == 0


# ── 실제로 막히는가 — DB 가 필요하다 ─────────────────────────────────────

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)


@pytest.fixture
def probe():
    """빈 몬스터 개체 하나."""
    from game.app.store.connection import create_pool

    pool = create_pool(os.environ[DATABASE_URL_ENV])
    with pool.connection() as connection:
        row = connection.execute(
            "INSERT INTO entity_record (kind, catalog_id, zone_floor)"
            " VALUES ('MONSTER', 'goblin_rusher', 99) RETURNING id"
        ).fetchone()
    record_id = int(row[0])
    yield pool, record_id
    with pool.connection() as connection:
        connection.execute("DELETE FROM item_instance WHERE owner_entity_id = %s", (record_id,))
        connection.execute("DELETE FROM entity_record WHERE id = %s", (record_id,))


def count_held(pool, record_id):
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT count(*) FROM item_instance WHERE owner_entity_id = %s", (record_id,)
        ).fetchone()
    return int(row[0])


def take(pool, record_id, flat):
    from game.app.store.trophies import create_trophy

    return create_trophy(pool, record_id, "armor_plate", [{"stat": "defense", "flat": flat}], 1)


def test_the_first_five_all_go_in(probe):
    pool, record_id = probe
    for step in range(MAX_TROPHIES):
        assert take(pool, record_id, step + 1) is True
    assert count_held(pool, record_id) == MAX_TROPHIES


def test_a_weaker_take_is_refused_once_full(probe):
    """★ **이것이 이 변경의 전부다.** 다섯이 차면 더 강한 것만 들어온다."""
    pool, record_id = probe
    for step in range(MAX_TROPHIES):
        take(pool, record_id, 10 + step)
    assert take(pool, record_id, 1) is False
    assert count_held(pool, record_id) == MAX_TROPHIES


def test_a_stronger_take_replaces_the_weakest(probe):
    """★ 가장 약한 것을 밀어낸다 — 개체가 「본 것 중 가장 좋은 다섯」으로 수렴한다."""
    pool, record_id = probe
    for flat in (10, 11, 12, 13, 14):
        take(pool, record_id, flat)
    assert take(pool, record_id, 99) is True
    assert count_held(pool, record_id) == MAX_TROPHIES
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT affixes FROM item_instance WHERE owner_entity_id = %s", (record_id,)
        ).fetchall()
    scores = sorted(compute_affix_score(row[0]) for row in rows)
    assert scores == [11, 12, 13, 14, 99], "가장 약한 것이 안 밀려났다"


def test_it_never_grows_past_the_cap(probe):
    """★ 봇이 쉼 없이 죽어도 목록이 안 자란다 — 696개가 그렇게 쌓였다."""
    pool, record_id = probe
    for step in range(40):
        take(pool, record_id, step)
    assert count_held(pool, record_id) == MAX_TROPHIES
