"""도플갱어 자리 정책 — 누가 서고 누가 밀려나는가 (결정 #35 위에 선다).

`test_api_doppel.py` 에서 갈라 나왔다. 저쪽은 **그림자가 서는 조건**(깊은 봇 죽음)과
**무엇을 들고 서는가**(규칙표·얼린 장비·아이템 없음)이고, 여기는 **자리를 누가 갖는가**다.

가르는 선은 책임이다 (§4). 파일이 400줄 상한을 넘은 것이 계기였을 뿐이다.

**정원이 셋으로 늘었다** (개정 2026-09-15). 예전에는 세계 상한 하나였고 그것이 깊이로
줄을 세웠다 — 그래서 실측으로 **스물 중 열아홉이 9장에 몰렸고 주인은 세 계정뿐**이었다.
한 장이 도는 방이 다섯이고 `build_room_doppels` 가 방마다 하나씩 세우므로, 9장에 닿은
사람은 다섯 방이 전부 그림자였고 2~8장에서는 하나도 못 만났다.

여기서 지키는 것은 넷이다.

1. **한 원천은 한 장에 하나.** 없으면 다섯 방을 돌며 같은 빌드를 두 번 만난다 —
   「누구의 그림자인가」가 뜻을 잃는다.
2. **한 원천은 세계에 둘까지.** 세계 상한이 원천 수에 비례하는 것은 이 규칙의 결과다 —
   총량에만 걸면 계정 둘이 아홉 장을 하나씩 차지해도 통과한다.
3. **한 장에 둘까지.** 그 장의 그림자 수가 곧 「다섯 방 중 몇 방에서 만나는가」다.
4. **잡으면 사라진다.** 지속 몬스터를 안 지우는 사유(되찾기 동기)가 이 종에는 안 붙는다 —
   애초에 아무것도 안 들기 때문이다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

fastapi_testclient = pytest.importorskip("fastapi.testclient")

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)


@pytest.fixture
def client():
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as running:
        yield running


def build_headers(token):
    return {"X-Game-Token": token}


@pytest.fixture(autouse=True)
def clean_doppels(client):
    """검사 사이에 그림자를 지운다.

    **상한이 있어서 안 지우면 뒤의 검사가 전부 건너뛰어진다** — 건너뛴 검사는 없는
    검사다. 검사용 DB 의 도플갱어는 검사가 만든 것뿐이라 지워도 잃을 것이 없다.
    """
    from game.api.deps import get_pool

    def wipe():
        with get_pool().connection() as connection:
            connection.execute("DELETE FROM entity_record WHERE kind = 'MONSTER' AND is_doppel")

    wipe()
    yield
    wipe()


def build_bot_account(client):
    """봇 계정 하나를 세운다.

    Args:
        client: 테스트 클라이언트.

    Returns:
        봇의 계정 id.
    """
    from game.api.deps import get_pool
    from game.app.store.bots import create_bot

    token = client.post("/api/account").json()["token"]
    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    create_bot(get_pool(), account_id, "그림자봇", "g0_kite", 720, 60)
    return account_id


def read_floors(pool):
    """지금 선 그림자들의 층. 정렬해서 돌려준다.

    Args:
        pool: 연결 풀.

    Returns:
        층 목록.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT zone_floor FROM entity_record"
            " WHERE kind = 'MONSTER' AND is_doppel AND alive ORDER BY zone_floor"
        ).fetchall()
    return [int(row[0]) for row in rows]


def test_the_cap_follows_the_source_count():
    """★ 세계 상한은 원천 수에 비례한다 — 고정값은 적은 사람의 빌드로 세계를 채운다.

    실측이 그 병이었다 (2026-09-15): 계정 셋이 그림자 스물을 쥐고 있었다. 세계의 크기가
    아니라 **얼마나 여러 사람이 있는가**가 그림자의 다양성을 정한다.
    """
    from game.app.bots.doppel import DOPPELS_PER_SOURCE, compute_doppel_cap

    assert compute_doppel_cap(0) == 0, "원천이 없는 세계에 그림자가 서면 안 된다"
    assert compute_doppel_cap(1) == DOPPELS_PER_SOURCE, "한 사람이 곧 제 몫이다"
    assert compute_doppel_cap(3) == 3 * DOPPELS_PER_SOURCE
    assert compute_doppel_cap(11) > compute_doppel_cap(3), "사람이 늘어도 안 늘면 비례가 아니다"


def test_one_source_holds_one_place_per_floor(client):
    """★ 한 원천은 한 장에 하나 — 같은 빌드를 한 장에서 두 번 만나면 안 된다.

    한 장이 도는 방이 다섯이고 방마다 그림자가 하나씩 서므로(`build_room_doppels`),
    같은 사람이 그 장에 둘 서면 **다섯 방 중 둘이 같은 사람**이 된다.

    새로 죽은 쪽이 이긴다 — 같은 사람의 더 최근 빌드가 더 그 사람답다.
    """
    from game.api.deps import get_pool
    from game.app.store.doppels import create_doppel

    pool = get_pool()
    account_id = build_bot_account(client)

    first = create_doppel(pool, account_id, 4, "first_slot", {"hp_max": 10}, {})
    second = create_doppel(pool, account_id, 4, "second_slot", {"hp_max": 10}, {})

    assert first != 0 and second != 0, "제 옛 그림자 때문에 못 섰다"
    assert read_floors(pool) == [4], "같은 사람이 한 장에 둘 섰다"
    with pool.connection() as connection:
        assert (
            connection.execute("SELECT id FROM entity_record WHERE id = %s", (first,)).fetchone()
            is None
        ), "옛 그림자가 남았다 — 새 것이 이겨야 한다"


def test_one_source_holds_only_two_places(client):
    """★ 한 원천은 세계에 둘까지 — 비례가 실제로 걸리는 자리다.

    총량에만 상한을 두면 계정 **둘**이 아홉 장을 하나씩 차지해도 통과한다. 세계는 안
    덮였는데 만나는 빌드는 둘뿐이다 — 실측이 그 모양이었다 (주인 셋이 그림자 스물).

    넘치면 **제 것 중 가장 오래된 것**이 물러난다. 남의 것을 밀어내면 「내가 깊이 갔다」가
    남의 자리를 빼앗는 일이 되고, 그것이 이 정원이 막으려던 쏠림이다.
    """
    from game.api.deps import get_pool
    from game.app.bots.doppel import DOPPELS_PER_SOURCE
    from game.app.store.doppel_quota import count_own_doppels
    from game.app.store.doppels import create_doppel

    pool = get_pool()
    account_id = build_bot_account(client)
    oldest = create_doppel(pool, account_id, 2, "slot_2", {"hp_max": 10}, {})
    for floor in range(3, 3 + DOPPELS_PER_SOURCE + 1):
        create_doppel(pool, account_id, floor, f"slot_{floor}", {"hp_max": 10}, {})

    assert count_own_doppels(pool, account_id) == DOPPELS_PER_SOURCE
    with pool.connection() as connection:
        assert (
            connection.execute("SELECT id FROM entity_record WHERE id = %s", (oldest,)).fetchone()
            is None
        ), "제 것 중 가장 오래된 것이 아니라 다른 것이 물러났다"


def test_a_floor_holds_only_its_quota(client):
    """★ 한 장에 둘까지 — 그 수가 곧 「다섯 방 중 몇 방에서 만나는가」다.

    다섯이면 모든 방이 그림자가 되어 「가끔 만나는 것」이 아니게 된다. 넘치면 그 장에서
    가장 오래된 것이 나간다 — 그래야 붐빌 때도 보토가 돈다.
    """
    from game.api.deps import get_pool
    from game.app.bots.doppel import MAX_DOPPELS_PER_FLOOR
    from game.app.store.doppel_quota import count_doppels_on_floor
    from game.app.store.doppels import create_doppel

    pool = get_pool()
    oldest = create_doppel(pool, build_bot_account(client), 5, "slot_a", {"hp_max": 10}, {})
    for step in range(MAX_DOPPELS_PER_FLOOR + 2):
        create_doppel(pool, build_bot_account(client), 5, f"slot_{step}", {"hp_max": 10}, {})

    assert count_doppels_on_floor(pool, 5) == MAX_DOPPELS_PER_FLOOR
    with pool.connection() as connection:
        assert (
            connection.execute("SELECT id FROM entity_record WHERE id = %s", (oldest,)).fetchone()
            is None
        ), "가장 오래된 것이 아니라 다른 것을 밀어냈다"


def test_a_shallow_place_survives_deep_deaths(client):
    """★ 얕은 장이 깊은 죽음에 밀리지 않는다 — 예전에는 그것이 병이었다.

    세계 상한 하나가 깊이로 줄을 세우던 때, 남는 것은 「가장 깊은 스물」이었고 실측으로
    열아홉이 9장에 몰렸다. **닿는 사람이 가장 적은 장에 그림자가 다 모여 있었다.**
    """
    from game.api.deps import get_pool
    from game.app.store.doppels import create_doppel

    pool = get_pool()
    shallow = create_doppel(pool, build_bot_account(client), 2, "shallow_slot", {"hp_max": 10}, {})
    for step in range(8):
        create_doppel(pool, build_bot_account(client), 9, f"deep_slot_{step}", {"hp_max": 10}, {})

    assert 2 in read_floors(pool), "얕은 장이 깊은 죽음에 밀려났다"
    with pool.connection() as connection:
        assert (
            connection.execute("SELECT id FROM entity_record WHERE id = %s", (shallow,)).fetchone()
            is not None
        )


def test_the_world_cap_holds(client):
    """★ 세계가 상한을 넘기지 않는다 — 덮이면 「가끔 만나는 것」이 아니게 된다."""
    from game.api.deps import get_pool
    from game.app.bots.doppel import compute_doppel_cap
    from game.app.store.doppel_quota import count_doppel_sources
    from game.app.store.doppels import count_doppels, create_doppel

    pool = get_pool()
    for step in range(12):
        create_doppel(
            pool,
            build_bot_account(client),
            2 + (step % 9),
            f"probe_slot_{step}",
            {"hp_max": 10},
            {},
        )

    assert count_doppels(pool) <= compute_doppel_cap(count_doppel_sources(pool))


def test_a_full_floor_hands_its_oldest_slot_over(client):
    """★ **자리 고갈은 「순위에 못 듦」과 다르다.**

    예전에는 둘 다 0 을 돌려줘 구분되지 않았고, `apply_doppel_from_death` 가
    `find_free_slot` 을 먼저 부르므로 그 층 자리가 차는 순간 **정원 검사가 한 번도 안
    돌았다.** 실측: 4층 자리 열하나가 다 찬 뒤 봇이 4층을 115번 깼는데 새 그림자가
    하나도 안 섰다 — 「자리가 굳는 것이 원래 고치려던 병」이라고 `create_doppel` 의
    머리말이 적어 둔 그 병이 다른 문으로 돌아와 있었다.
    """
    from game.api.deps import get_pool
    from game.app.store.doppels import count_doppels, create_doppel

    pool = get_pool()
    account_id = build_bot_account(client)
    first = create_doppel(pool, account_id, 4, "only_slot", {"hp_max": 100}, {})
    assert first != 0

    # 자리를 못 찾았다는 뜻으로 빈 문자열을 넘긴다 — `find_free_slot` 이 내는 값이다.
    second = create_doppel(pool, account_id, 4, "", {"hp_max": 110}, {})
    assert second != 0, "자리가 찼다고 새 그림자가 아예 안 서면 보토가 굳는다"
    assert second != first
    assert count_doppels(pool) == 1, "물려받는 것이지 늘어나는 것이 아니다"


def test_the_inherited_slot_is_the_old_one(client):
    """★ 물려받은 자리가 그 층의 자리여야 한다.

    전체에서 가장 얕은 것을 지우면 그것이 **다른 층**일 수 있고, 그러면 지워 봐야 이
    층의 자리는 그대로 차 있다.
    """
    from game.api.deps import get_pool
    from game.app.store.doppels import create_doppel

    pool = get_pool()
    account_id = build_bot_account(client)
    create_doppel(pool, account_id, 4, "taken_slot", {"hp_max": 100}, {})
    heir = create_doppel(pool, account_id, 4, "", {"hp_max": 110}, {})
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT entity_slot, zone_floor FROM entity_record WHERE id = %s", (heir,)
        ).fetchone()
    assert row[0] == "taken_slot"
    assert row[1] == 4


def test_an_empty_floor_still_refuses_without_a_slot(client):
    """★ 물려받을 것이 없으면 안 선다.

    빈 문자열을 그대로 통과시키면 자리 없는 개체가 생기고, 그것은 스냅샷에 안 실려
    **아무도 못 만나는 그림자**가 된다.
    """
    from game.api.deps import get_pool
    from game.app.store.doppels import create_doppel

    assert create_doppel(get_pool(), build_bot_account(client), 7, "", {"hp_max": 100}, {}) == 0
