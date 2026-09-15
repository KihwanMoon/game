"""도플갱어의 목숨 — 몇 번 잡아야 사라지는가 (결정 #35 위에 선다).

`test_doppel_roster.py` 에서 갈라 나왔다. 저쪽은 **자리를 누가 갖는가**(정원·비례·퇴출)
이고 여기는 **선 것이 언제 사라지는가**다. 파일이 400줄 상한을 넘은 것이 계기였을 뿐,
가르는 선은 책임이다 (§4).

**한 번 잡았다고 사라지지 않는다.** 처치가 자리를 비우게 한 직후에 나온 문제다 — 봇들이
쉼 없이 싸우니 그림자가 서자마자 지워져 사람이 만날 새가 없었다. 그렇다고 안 지우면
자리가 굳는다. 목숨 셋이 그 사이를 잡는다: 같은 그림자를 세 번 만나되 만날 때마다 약해진다.

**그리고 지워도 되는 종이다.** 지속 몬스터를 안 지우는 사유(되찾기 동기)가 이 종에는 안
붙는다 — 애초에 아무것도 안 들기 때문이다.
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


def test_a_shadow_survives_two_beatings(client):
    """★ 한 번 잡았다고 사라지지 않는다 — 셋을 견딘다.

    처치가 자리를 비우게 한 직후에 나온 문제다: 봇들이 쉼 없이 싸우니 그림자가 서자마자
    지워져 **사람이 만날 새가 없었다.** 그렇다고 안 지우면 자리가 굳는다 — 그것이 원래
    고치려던 병이다. 목숨 셋이 그 사이를 잡는다.
    """
    from game.api.deps import get_pool
    from game.app.bots.doppel import DOPPEL_LIVES
    from game.app.store.doppels import apply_doppel_defeat, count_doppels, create_doppel

    pool = get_pool()
    record_id = create_doppel(pool, build_bot_account(client), 4, "lives_slot", {"hp_max": 10}, {})

    left = [apply_doppel_defeat(pool, record_id) for _ in range(DOPPEL_LIVES)]

    assert left == [2, 1, 0], f"목숨이 {left} 로 줄었다"
    assert count_doppels(pool) == 0, "다 쓰고도 안 지워졌다"


def test_a_beaten_shadow_still_holds_its_place(client):
    """★ 목숨이 남았으면 그 자리는 아직 그 그림자의 것이다.

    잡혔다고 자리를 놓으면 세 번 만나는 이야기가 성립하지 않는다 — 두 번째로 만나기
    전에 더 깊은 죽음 하나가 밀어내 버린다.
    """
    from game.api.deps import get_pool
    from game.app.store.doppels import apply_doppel_defeat, count_doppels, create_doppel

    pool = get_pool()
    record_id = create_doppel(pool, build_bot_account(client), 4, "held_slot", {"hp_max": 10}, {})

    assert apply_doppel_defeat(pool, record_id) == 2
    assert count_doppels(pool) == 1
    assert read_floors(pool) == [4]


def test_beating_something_that_is_not_a_shadow_changes_nothing(client):
    """★ 목숨을 쓰는 길이 일반 몬스터로 새면 결정 #35 가 뚫린다."""
    from game.api.deps import get_pool
    from game.app.store.doppels import apply_doppel_defeat

    pool = get_pool()
    with pool.connection() as connection:
        record_id = int(
            connection.execute(
                "INSERT INTO entity_record (kind, catalog_id, tier, level, zone_floor)"
                " VALUES ('MONSTER', 'goblin_rusher', 'NORMAL', 1, 2) RETURNING id"
            ).fetchone()[0]
        )

    assert apply_doppel_defeat(pool, record_id) == -1
    with pool.connection() as connection:
        assert (
            connection.execute(
                "SELECT lives FROM entity_record WHERE id = %s", (record_id,)
            ).fetchone()[0]
            == 1
        ), "일반 몬스터의 목숨이 줄었다"
        connection.execute("DELETE FROM entity_record WHERE id = %s", (record_id,))


def test_a_new_shadow_stands_with_its_lives(client):
    """★ 목숨을 갖고 선다 — 기본값 1 로 서면 첫 판에 사라진다."""
    from game.api.deps import get_pool
    from game.app.bots.doppel import DOPPEL_LIVES
    from game.app.store.doppels import create_doppel

    pool = get_pool()
    record_id = create_doppel(pool, build_bot_account(client), 4, "born_slot", {"hp_max": 10}, {})

    with pool.connection() as connection:
        lives = connection.execute(
            "SELECT lives FROM entity_record WHERE id = %s", (record_id,)
        ).fetchone()[0]
    assert lives == DOPPEL_LIVES


# ── 자리 고갈 (알려진 이슈 Z10) ──────────────────────────────────────────
