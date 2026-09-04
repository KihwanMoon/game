"""도플갱어 자리 정책 — 누가 서고 누가 밀려나는가 (결정 #35 위에 선다).

`test_api_doppel.py` 에서 갈라 나왔다. 저쪽은 **그림자가 서는 조건**(깊은 봇 죽음)과
**무엇을 들고 서는가**(규칙표·얼린 장비·아이템 없음)이고, 여기는 **자리를 누가 갖는가**다.

가르는 선은 책임이다 (§4). 파일이 400줄 상한을 넘은 것이 계기였을 뿐이다.

여기서 지키는 것은 셋이다.

1. **상한을 넘기지 않는다.** 세계가 그림자로 덮이면 「가끔 만나는 것」이 아니게 된다.
2. **자리가 아니라 순위표다.** 남는 것은 가장 깊은 것들이어야 한다 — 예전에는 선착순에
   비우는 길이 없어서, 가장 흔한 2층 죽음이 자리를 영구히 점유했다.
3. **잡으면 사라진다.** 지속 몬스터를 안 지우는 사유(되찾기 동기)가 이 종에는 안 붙는다 —
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


def test_the_ceiling_holds(client):
    """★ 상한을 넘기지 않는다 — 세계가 그림자로 덮이면 「가끔 만나는 것」이 아니게 된다."""
    from game.api.deps import get_pool
    from game.app.bots.doppel import MAX_DOPPELS
    from game.app.store.doppels import count_doppels, create_doppel

    pool = get_pool()
    account_id = build_bot_account(client)
    for step in range(MAX_DOPPELS + 3):
        create_doppel(pool, account_id, 2 + (step % 4), f"probe_slot_{step}", {"hp_max": 10}, {})
    assert count_doppels(pool) <= MAX_DOPPELS


def fill_doppels(pool, account_id, floor):
    """상한까지 그 층 그림자로 채운다.

    Args:
        pool: 연결 풀.
        account_id: 원본 계정.
        floor: 세울 층.
    """
    from game.app.bots.doppel import MAX_DOPPELS
    from game.app.store.doppels import create_doppel

    for step in range(MAX_DOPPELS):
        create_doppel(pool, account_id, floor, f"fill_slot_{step}", {"hp_max": 10}, {})


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


def test_a_deeper_death_pushes_out_the_shallowest(client):
    """★ 자리가 아니라 순위표다 — 남는 것이 「가장 깊은 스물」이어야 한다.

    예전에는 선착순이었고 비우는 길이 없었다. 2층 죽음이 가장 흔하므로 자리가 2층으로
    차는 순간 그 뒤의 모든 죽음이 조용히 버려졌고 — 실제로 하루에 1,170판이 그렇게
    버려졌다 — **가장 얕은 빌드가 자리를 영구히 점유**했다. 「거기까지 실제로 내려간
    빌드」라는 이 기제의 전제와 정반대다.
    """
    from game.api.deps import get_pool
    from game.app.bots.doppel import MAX_DOPPELS
    from game.app.store.doppels import count_doppels, create_doppel

    pool = get_pool()
    account_id = build_bot_account(client)
    fill_doppels(pool, account_id, 2)

    record_id = create_doppel(pool, account_id, 7, "deep_slot", {"hp_max": 10}, {})

    assert record_id != 0, "더 깊은데 못 섰다"
    assert count_doppels(pool) == MAX_DOPPELS, "밀어내지 않고 늘렸다"
    assert 7 in read_floors(pool)
    assert read_floors(pool).count(2) == MAX_DOPPELS - 1


def test_a_shallower_death_does_not_push_anyone_out(client):
    """★ 얕은 것이 깊은 것을 밀어내면 순위표가 아니다."""
    from game.api.deps import get_pool
    from game.app.store.doppels import create_doppel

    pool = get_pool()
    account_id = build_bot_account(client)
    fill_doppels(pool, account_id, 5)

    assert create_doppel(pool, account_id, 3, "shallow_slot", {"hp_max": 10}, {}) == 0
    assert set(read_floors(pool)) == {5}


def test_the_same_depth_goes_to_the_newer_one(client):
    """★ 같은 깊이면 새 것이 이긴다.

    더 깊을 때만 밀어내게 하면 봇이 한 깊이에서 평평해지는 순간 보토가 다시 굳는다 —
    하루 종일 같은 그림자를 만나게 된다. 밀려나는 것은 그 깊이에서 가장 오래된 것이다.
    """
    from game.api.deps import get_pool
    from game.app.bots.doppel import MAX_DOPPELS
    from game.app.store.doppels import count_doppels, create_doppel

    pool = get_pool()
    account_id = build_bot_account(client)
    fill_doppels(pool, account_id, 4)
    with pool.connection() as connection:
        oldest = int(
            connection.execute(
                "SELECT id FROM entity_record WHERE kind = 'MONSTER' AND is_doppel"
                " ORDER BY id ASC LIMIT 1"
            ).fetchone()[0]
        )

    record_id = create_doppel(pool, account_id, 4, "same_slot", {"hp_max": 10}, {})

    assert record_id != 0
    assert count_doppels(pool) == MAX_DOPPELS
    with pool.connection() as connection:
        assert (
            connection.execute("SELECT id FROM entity_record WHERE id = %s", (oldest,)).fetchone()
            is None
        ), "가장 오래된 것이 아니라 다른 것을 밀어냈다"


def test_beating_a_doppel_frees_its_place(client):
    """★ 잡으면 사라진다 — 그래야 이긴 것이 세계에 남고 자리가 돈다.

    지속 몬스터를 안 지우는 이유는 되찾기 동기가 함께 사라지기 때문인데(결정 #35),
    도플갱어는 애초에 아무것도 안 들어 되찾을 것이 없다 — 그 사유가 이 종에는 안 붙는다.
    """
    from game.api.deps import get_pool
    from game.app.store.doppels import count_doppels, create_doppel, remove_doppel

    pool = get_pool()
    record_id = create_doppel(pool, build_bot_account(client), 4, "beat_slot", {"hp_max": 10}, {})
    assert count_doppels(pool) == 1

    assert remove_doppel(pool, record_id) is True
    assert count_doppels(pool) == 0
    # 두 번 지워도 조용하다 — 같은 판이 두 번 정산되는 길이 있다.
    assert remove_doppel(pool, record_id) is False


def test_removal_only_touches_shadows(client):
    """★ 지우는 길이 일반 몬스터로 새면 결정 #35 가 통째로 뚫린다."""
    from game.api.deps import get_pool
    from game.app.store.doppels import remove_doppel

    pool = get_pool()
    with pool.connection() as connection:
        record_id = int(
            connection.execute(
                "INSERT INTO entity_record (kind, catalog_id, tier, level, zone_floor)"
                " VALUES ('MONSTER', 'goblin_rusher', 'NORMAL', 1, 2) RETURNING id"
            ).fetchone()[0]
        )

    assert remove_doppel(pool, record_id) is False
    with pool.connection() as connection:
        assert (
            connection.execute(
                "SELECT id FROM entity_record WHERE id = %s", (record_id,)
            ).fetchone()
            is not None
        ), "일반 몬스터가 지워졌다"
        connection.execute("DELETE FROM entity_record WHERE id = %s", (record_id,))
