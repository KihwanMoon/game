"""둔갑이 돌려주는 것 — 제 그림자를 안 만나고, 물러날 때 활자를 남긴다 (2026-09-15).

여기서 지키는 것은 셋이다.

1. **제 그림자는 제 판에 안 선다.** 내 규칙표가 내 앞에 서면 새로 알 것이 없고, 이겨도
   져도 전적에 안 적힌다(`record_bout` 이 자기 그림자를 건너뛴다) — 정예 자리 하나가
   통째로 버려지는 셈이다.
2. **물러날 때 평생 승수만큼 활자가 들어온다.** 이긴 그 순간이 아니다 — 판마다 주면 또
   하나의 노가다 지표가 되고, 그러면 푼과 둘로 가른 뜻이 없다.
3. **사라지는 길이 둘인데 둘 다 정산한다.** 목숨을 다 썼거나 정원에 밀렸거나 —
   `remove_doppel` 하나를 지나므로 새는 길이 없다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)


@pytest.fixture
def client():
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as running:
        yield running


def build_headers(token):
    return {"X-Game-Token": token}


@pytest.fixture(autouse=True)
def clean_doppels(client):
    """검사 사이에 그림자와 전적을 지운다 — 정원이 있어서 안 지우면 뒤가 건너뛰어진다."""
    from game.api.deps import get_pool

    def wipe():
        with get_pool().connection() as connection:
            connection.execute("DELETE FROM entity_record WHERE kind = 'MONSTER' AND is_doppel")
            connection.execute("DELETE FROM doppel_bout")

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
    create_bot(get_pool(), account_id, "정산봇", "g0_kite", 720, 60)
    return account_id


def build_shadow(client, floor=4):
    """그림자 하나를 세운다.

    Args:
        client: 테스트 클라이언트.
        floor: 세울 층.

    Returns:
        (주인 계정 id, 개체 id).
    """
    from game.api.deps import get_pool
    from game.app.store.doppels import create_doppel

    account_id = build_bot_account(client)
    record_id = create_doppel(
        get_pool(), account_id, floor, f"reward_slot_{floor}", {"hp_max": 10}, {}
    )
    assert record_id != 0
    return account_id, record_id


def test_my_own_shadow_does_not_stand_in_my_run(client):
    """★ 제 그림자는 제 판에 안 선다 — 만나 봐야 전적에도 안 적힌다."""
    from game.api.doppel_pick import build_room_doppels
    from game.app.store.monsters import MonsterRecord

    mine = MonsterRecord(
        record_id=1,
        catalog_id="doppelganger",
        tier="ELITE",
        zone_floor=1,
        entity_slot="doppel_1",
        total_xp=0,
        level=1,
        alive=True,
        origin_account_id=7,
    )
    theirs = MonsterRecord(**{**vars(mine), "record_id": 2, "origin_account_id": 9})
    rooms = ("a", "b", "c", "d", "e")

    picked = build_room_doppels([mine, theirs], rooms, 5, 1, lambda n: 0, 7)

    origins = {one.origin_account_id for one in picked}
    assert 7 not in origins, "내 그림자가 내 판에 섰다"
    assert 9 in origins, "남의 그림자까지 빠졌다"


def test_someone_elses_shadow_still_stands(client):
    """★ 거르는 것은 **내 것 하나**다 — 계정을 안 넘기면 아무것도 안 걸러진다."""
    from game.api.doppel_pick import build_room_doppels
    from game.app.store.monsters import MonsterRecord

    shadow = MonsterRecord(
        record_id=1,
        catalog_id="doppelganger",
        tier="ELITE",
        zone_floor=1,
        entity_slot="doppel_1",
        total_xp=0,
        level=1,
        alive=True,
        origin_account_id=7,
    )

    assert len(build_room_doppels([shadow], ("a",), 1, 1, lambda n: 0, 0)) == 1


def test_a_retiring_shadow_pays_its_wins_in_letters(client):
    """★ 이긴 판은 물러날 때 활자가 된다 — 이긴 그 순간이 아니다."""
    from game.api.deps import get_pool
    from game.app.store.doppel_bouts import record_bout
    from game.app.store.doppels import remove_doppel
    from game.app.store.letters import read_letters

    pool = get_pool()
    account_id, record_id = build_shadow(client)
    rival = build_bot_account(client)
    record_bout(pool, record_id, rival, 4, True)
    record_bout(pool, record_id, rival, 4, True)
    record_bout(pool, record_id, rival, 4, False)

    assert read_letters(pool, account_id) == 0, "서 있는 동안 들어왔다"

    remove_doppel(pool, record_id)

    assert read_letters(pool, account_id) == 2, "이긴 판 수와 다르다"


def test_a_shadow_that_never_won_pays_nothing(client):
    """★ 지는 판은 세지 않는다 — 세면 모든 둔갑이 같은 값을 받는다."""
    from game.api.deps import get_pool
    from game.app.store.doppel_bouts import record_bout
    from game.app.store.doppels import remove_doppel
    from game.app.store.letters import read_letters

    pool = get_pool()
    account_id, record_id = build_shadow(client)
    record_bout(pool, record_id, build_bot_account(client), 4, False)

    remove_doppel(pool, record_id)

    assert read_letters(pool, account_id) == 0


def test_being_pushed_out_settles_too(client):
    """★ 정원에 밀려 사라질 때도 정산한다 — 새는 길이 있으면 이긴 것이 사라진다."""
    from game.api.deps import get_pool
    from game.app.bots.doppel import MAX_DOPPELS_PER_FLOOR
    from game.app.store.doppel_bouts import record_bout
    from game.app.store.doppels import create_doppel
    from game.app.store.letters import read_letters

    pool = get_pool()
    account_id, record_id = build_shadow(client, floor=6)
    record_bout(pool, record_id, build_bot_account(client), 6, True)

    # 그 장을 남들로 채워 가장 오래된 것(내 것)을 밀어낸다.
    for step in range(MAX_DOPPELS_PER_FLOOR + 1):
        create_doppel(pool, build_bot_account(client), 6, f"push_slot_{step}", {"hp_max": 10}, {})

    assert read_letters(pool, account_id) == 1, "밀려난 그림자의 승리가 사라졌다"
