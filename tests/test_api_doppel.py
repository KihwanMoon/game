"""도플갱어는 전리품을 만들지 않는다 — DB 가 필요한 두 길목 (결정 #02·#34, T11).

종 판정과 드롭 굴림은 `test_doppel_loot` 가 본다. 여기는 **강탈과 되찾기** 다 — 둘 다
지속 몬스터 상태를 읽으므로 DB 가 있어야 돈다.

아이템이 도플갱어를 거쳐 사람에게 갈 수 있는 길이 셋이고, 하나라도 열려 있으면 봇을
여럿 돌려 죽이는 것이 최적 파밍이 된다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

fastapi_testclient = pytest.importorskip("fastapi.testclient")

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)

ROOM_ID = "corridor"


@pytest.fixture
def client():
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as running:
        yield running


@pytest.fixture
def token(client):
    return client.post("/api/account").json()["token"]


def build_headers(token):
    return {"X-Game-Token": token}


def build_doppel_pair():
    """도플갱어 하나와 일반 몬스터 하나를 스냅샷으로 짠다.

    Returns:
        (도플갱어, 일반) 순의 스냅샷들. **도플갱어를 첫 자리에 둔다** — 강탈이 첫 개체를
        고르므로, 뒤에 두면 건너뛰는지 아닌지가 드러나지 않는다.
    """
    from game.app.bots.doppel import DOPPEL_KIND_ID
    from game.schemas.monster_snapshot import MonsterSnapshot

    def build(record_id, kind_id, tier):
        return MonsterSnapshot(
            entity_id=f"{kind_id}_{record_id}",
            record_id=record_id,
            kind_id=kind_id,
            tier=tier,
            level=3,
            hp_max=10,
            attack=1,
            defense=0,
            rule_slots=0,
            cpu_budget=0,
        )

    return (build(9001, DOPPEL_KIND_ID, "ELITE"), build(9002, "goblin_rusher", "NORMAL"))


def build_probe_ticket():
    """검사용 티켓 하나.

    Returns:
        1층짜리 티켓.
    """
    from game.app.store.tickets import IssuedTicket

    return IssuedTicket(
        ticket_id="doppel-probe",
        seed=1,
        room_id=ROOM_ID,
        floor=1,
        mode="PRACTICE",
        core_version="probe",
    )


def test_a_doppel_never_takes_a_players_gear(client, token, monkeypatch):
    """★ 길 2 — 전리품 강탈. 도플갱어는 사람의 장비 사본을 갖지 않는다.

    들면 그 순간 「내 것을 들고 있는 개체」가 되고, 되찾기(길 3)가 그 위에 길을 낸다 —
    봇이 벌어 둔 장비가 사람에게 흘러가는 통로이며, 봇을 죽이는 것이 최적 파밍이 된다.
    """
    from game.api import monster_service
    from game.app.services.verify_run import VERDICT_VERIFIED, VerifiedRun

    holders = []
    monkeypatch.setattr(monster_service, "load_snapshots", lambda *_a, **_k: build_doppel_pair())
    monkeypatch.setattr(
        monster_service,
        "apply_trophy_transfer",
        lambda _account, record_id: holders.append(record_id) or "",
    )
    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    monster_service.apply_monster_outcome(
        build_probe_ticket(),
        1,
        VerifiedRun("PLAYER_LOSS", 10, 0, VERDICT_VERIFIED, ""),
        account_id,
    )
    # 첫 자리의 도플갱어를 건너뛰고 뒤의 일반 몬스터가 가져갔다.
    assert holders == [9002]


def test_a_doppel_gives_nothing_back(client, token, monkeypatch):
    """★ 길 3 — 되찾기. 도플갱어에서는 아무것도 돌려받지 않는다."""
    from game.api import monster_service
    from game.app.services.verify_run import VERDICT_VERIFIED, VerifiedRun

    asked = []
    monkeypatch.setattr(monster_service, "load_snapshots", lambda *_a, **_k: build_doppel_pair())
    monkeypatch.setattr(
        monster_service,
        "apply_recovery",
        lambda _pool, record_id, *_a: asked.append(record_id) or (),
    )
    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    monster_service.apply_monster_outcome(
        build_probe_ticket(),
        1,
        VerifiedRun("PLAYER_WIN", 10, 50, VERDICT_VERIFIED, ""),
        account_id,
    )
    assert asked == [9002]


@pytest.fixture(autouse=True)
def clean_doppels(client):
    """검사 사이에 그림자를 지운다.

    **상한이 다섯이라 안 지우면 두 번째 실행부터 전부 건너뛴다** — 건너뛴 검사는 없는
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


def test_a_deep_bot_death_raises_a_shadow(client, monkeypatch):
    """★ 봇이 깊은 층에서 죽으면 그 자리에 그림자가 선다."""
    from game.api.deps import get_context, get_pool
    from game.api.doppel_service import apply_doppel_from_death
    from game.app.services.verify_run import VERDICT_VERIFIED, VerifiedRun
    from game.app.store.doppels import count_doppels

    pool = get_pool()
    account_id = build_bot_account(client)
    before = count_doppels(pool)
    note = apply_doppel_from_death(
        pool,
        get_context().rooms,
        account_id,
        VerifiedRun("PLAYER_LOSS", 30, 0, VERDICT_VERIFIED, ""),
        3,
        (ROOM_ID,),
        {"hp_max": 130, "attack": 20, "defense": 8, "rule_slots": 5, "cpu_budget": 8},
        {"ruleset_id": "g0_kite", "version": 1, "rules": []},
    )
    assert "3층" in note
    assert count_doppels(pool) == before + 1


def test_a_shallow_death_raises_nothing(client):
    """★ 1층에서 죽은 빌드는 안 선다 — 서면 「못 하는 것들의 모임」이 된다."""
    from game.api.deps import get_context, get_pool
    from game.api.doppel_service import apply_doppel_from_death
    from game.app.services.verify_run import VERDICT_VERIFIED, VerifiedRun
    from game.app.store.doppels import count_doppels

    pool = get_pool()
    before = count_doppels(pool)
    note = apply_doppel_from_death(
        pool,
        get_context().rooms,
        build_bot_account(client),
        VerifiedRun("PLAYER_LOSS", 30, 0, VERDICT_VERIFIED, ""),
        1,
        (ROOM_ID,),
        {"hp_max": 100},
        {},
    )
    assert note == ""
    assert count_doppels(pool) == before


def test_a_person_leaves_no_shadow(client):
    """★ 사람의 죽음은 그림자를 남기지 않는다.

    남기면 그 사람의 빌드가 도감에 공개된다 — 봇의 것만 쓰기로 한 이유가 그것이다.
    """
    from game.api.deps import get_context, get_pool
    from game.api.doppel_service import apply_doppel_from_death
    from game.app.services.verify_run import VERDICT_VERIFIED, VerifiedRun
    from game.app.store.doppels import count_doppels

    pool = get_pool()
    token = client.post("/api/account").json()["token"]
    person_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    before = count_doppels(pool)
    note = apply_doppel_from_death(
        pool,
        get_context().rooms,
        person_id,
        VerifiedRun("PLAYER_LOSS", 30, 0, VERDICT_VERIFIED, ""),
        # **봇이라면 서는 층·방으로 잰다.** 자리가 없는 층에서 재면 「자리가 없어서」
        # 통과하고, 그러면 이 검사는 봇 확인이 사라져도 초록이다.
        3,
        (ROOM_ID,),
        {"hp_max": 100},
        {},
    )
    assert note == ""
    assert count_doppels(pool) == before


def test_a_win_leaves_no_shadow(client):
    """이긴 판은 그림자를 안 남긴다 — 죽은 자리에 서는 것이다."""
    from game.api.deps import get_context, get_pool
    from game.api.doppel_service import apply_doppel_from_death
    from game.app.services.verify_run import VERDICT_VERIFIED, VerifiedRun
    from game.app.store.doppels import count_doppels

    pool = get_pool()
    before = count_doppels(pool)
    note = apply_doppel_from_death(
        pool,
        get_context().rooms,
        build_bot_account(client),
        VerifiedRun("PLAYER_WIN", 30, 50, VERDICT_VERIFIED, ""),
        3,
        (ROOM_ID,),
        {"hp_max": 100},
        {},
    )
    assert note == ""
    assert count_doppels(pool) == before


def test_the_shadow_keeps_the_ruleset(client):
    """★ 규칙표를 들고 선다 — 「그 빌드로 여기까지 왔다」가 이 개체의 뜻이다."""
    from game.api.deps import get_pool
    from game.app.store.doppels import create_doppel, read_doppel_ruleset

    pool = get_pool()
    ruleset = {"ruleset_id": "sniper", "version": 1, "rules": [{"priority": 1}]}
    record_id = create_doppel(
        pool, build_bot_account(client), 3, "keeps_slot", {"hp_max": 120}, ruleset
    )
    assert read_doppel_ruleset(pool, record_id)["ruleset_id"] == "sniper"


def test_the_shadow_freezes_what_it_wore(client):
    """★ 원본이 끼고 있던 장비를 얼려서 들고 선다.

    「그 빌드로 여기까지 왔다」가 이 개체의 뜻인데, 무엇을 끼고 갔는지 볼 수 없으면 그
    뜻이 절반만 남는다.
    """
    from game.api.deps import get_item_catalog, get_pool
    from game.app.store.accounts import find_player_entity
    from game.app.store.doppels import create_doppel, read_doppel_gear

    pool = get_pool()
    account_id = build_bot_account(client)
    entity_id = find_player_entity(pool, account_id)
    catalog_id = sorted(get_item_catalog())[0]
    with pool.connection() as connection:
        row = connection.execute(
            "INSERT INTO item_instance (catalog_id, owner_entity_id) VALUES (%s, %s) RETURNING id",
            (catalog_id, entity_id),
        ).fetchone()
        connection.execute(
            "INSERT INTO equipment_slot (entity_id, slot, item_id) VALUES (%s, %s, %s)",
            (entity_id, "BODY", int(row[0])),
        )
    record_id = create_doppel(pool, account_id, 3, "wore_slot", {"hp_max": 120}, {})
    gear = read_doppel_gear(pool, record_id)
    assert [item["slot"] for item in gear] == ["BODY"]
    assert gear[0]["catalog_id"] == catalog_id


def test_the_shadow_owns_no_items(client):
    """★ **아이템을 옮기지 않는다.**

    얼린 것은 사본 기록이라 `item_instance` 행이 늘지 않는다 — 그것이 전리품 차단의
    뿌리다. 옮겼다면 원본이 그것을 잃고, 도플갱어를 잡은 사람이 그것을 얻는다.
    """
    from game.api.deps import get_pool
    from game.app.store.doppels import create_doppel

    pool = get_pool()
    with pool.connection() as connection:
        before = int(connection.execute("SELECT count(*) FROM item_instance").fetchone()[0])
    record_id = create_doppel(pool, build_bot_account(client), 3, "owns_slot", {"hp_max": 10}, {})
    with pool.connection() as connection:
        after = int(connection.execute("SELECT count(*) FROM item_instance").fetchone()[0])
        owned = int(
            connection.execute(
                "SELECT count(*) FROM item_instance WHERE owner_entity_id = %s", (record_id,)
            ).fetchone()[0]
        )
    assert after == before
    assert owned == 0


def test_the_gear_route_shows_it(client):
    """★ 관리 화면이 그것을 사람 가방과 **같은 모양**으로 받는다."""
    from game.api.deps import get_pool
    from game.app.store.doppels import create_doppel

    pool = get_pool()
    admin = build_admin_token(client)
    record_id = create_doppel(pool, build_bot_account(client), 3, "route_slot", {"hp_max": 10}, {})
    body = client.get(
        "/api/admin/doppel/gear",
        params={"record_id": record_id},
        headers=build_headers(admin),
    ).json()
    # 가방은 늘 비어 있다 — 도플갱어는 아무것도 들고 다니지 않는다.
    assert body["slots"] == []
    for row in body["equipment"]:
        # **id 가 0 이다.** 가리킬 행이 없다는 뜻이고, 진짜 id 를 지어내면 화면이 그것으로
        # 조작을 걸 수 있다.
        assert row["item"]["item_id"] == 0


def test_a_missing_doppel_is_a_404(client):
    """없는 개체에 손대면 조용히 넘어가지 않는다."""
    response = client.get(
        "/api/admin/doppel/gear",
        params={"record_id": 999999999},
        headers=build_headers(build_admin_token(client)),
    )
    assert response.status_code == 404


def build_admin_token(client):
    """관리자 토큰 하나.

    Args:
        client: 테스트 클라이언트.

    Returns:
        토큰.
    """
    from game.api.deps import get_pool

    token = client.post("/api/account").json()["token"]
    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    with get_pool().connection() as connection:
        connection.execute("UPDATE account SET admin_role = 'owner' WHERE id = %s", (account_id,))
    return token
