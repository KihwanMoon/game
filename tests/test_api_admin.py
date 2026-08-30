"""관리자 경로 — 세계를 보고 손대는 유일한 문.

**여기가 이 서버에서 가장 위험한 자리다.** 나머지 경로는 뚫려도 한 계정이 손해를 보지만,
관리자 경로가 뚫리면 세계 전체가 뚫린다. 그래서 검사도 기능보다 **차단**을 먼저 본다.

세 가지를 지킨다.

1. **관리자가 아니면 404 다.** 403 은 "여기 뭔가 있는데 너는 못 본다" 를 알려 주고,
   그것은 경로의 존재 자체를 노출한다.
2. **승격은 API 로 불가능하다.** 길은 `scripts/grant_admin.py` 하나이며 DB 접속이 있어야
   돈다. 익명 계정은 관리자가 될 수 없다 — 토큰 하나가 곧 세계 전체가 된다.
3. **개입은 반드시 원장에 남는다.**
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

fastapi_testclient = pytest.importorskip("fastapi.testclient")

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)

PASSWORD = "correct horse battery"


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


def build_admin(client):
    """가입한 계정 하나를 만들어 관리자로 올린다. **스크립트와 같은 경로를 쓴다.**"""
    from game.api.deps import get_pool
    from game.app.store.admin import set_admin

    account = client.post("/api/account").json()
    login_id = f"admin{account['account_id']}"
    client.post(
        "/api/register",
        json={"login_id": login_id, "password": PASSWORD},
        headers=build_headers(account["token"]),
    )
    assert set_admin(get_pool(), login_id, True)
    return account["token"]


# ── 차단 ─────────────────────────────────────────────────────────────────


def test_a_normal_account_sees_nothing(client, token):
    """★ 관리자가 아니면 **404** 다 — 403 은 경로의 존재를 알려 준다."""
    assert client.get("/api/admin/overview", headers=build_headers(token)).status_code == 404


def test_no_token_sees_nothing(client):
    """★ 토큰 없이 열려 있으면 그 자체로 끝이다."""
    assert client.get("/api/admin/overview").status_code in {401, 403, 404, 422}


def test_a_normal_account_cannot_change_a_monster(client, token):
    """★ 읽기만 막고 쓰기를 열어 두면 막은 뜻이 없다."""
    response = client.put(
        "/api/admin/monster/level",
        json={"record_id": 1, "level": 5},
        headers=build_headers(token),
    )
    assert response.status_code == 404


def test_there_is_no_route_that_grants_admin(client):
    """★ **승격 엔드포인트가 있으면 안 된다.**

    그 하나가 뚫리는 순간 세계 전체가 뚫린다. 길은 스크립트뿐이다.
    """
    from game.api.main import create_app

    paths = [route.path for route in create_app().routes]
    assert not [path for path in paths if "grant" in path or "promote" in path]
    # 관리자 경로는 조회와 개입뿐이다.
    assert sorted(path for path in paths if "/admin/" in path) == [
        "/api/admin/monster/level",
        "/api/admin/overview",
    ]


def test_an_anonymous_account_cannot_be_promoted(client, token):
    """★ 익명은 관리자가 될 수 없다 — 토큰 하나가 곧 세계 전체가 된다."""
    from game.api.deps import get_pool
    from game.app.store.admin import set_admin

    handle = client.get("/api/account", headers=build_headers(token)).json()["handle"]
    assert not set_admin(get_pool(), handle, True)


# ── 조회 ─────────────────────────────────────────────────────────────────


def test_an_admin_sees_the_world(client):
    """★ 지금까지 세계 상태를 볼 방법이 아예 없었다."""
    body = client.get("/api/admin/overview", headers=build_headers(build_admin(client))).json()
    assert body["accounts"] >= 1
    assert body["catalog_items"] >= 1
    assert body["core_version"]


def test_the_overview_counts_items_held_by_monsters(client):
    """★ 남의 장비를 들고 있는 몬스터가 World Loop 의 동기다 (`설계/6_몬스터` §5).

    그것을 세지 않으면 이 표가 세계를 설명하지 못한다.
    """
    body = client.get("/api/admin/overview", headers=build_headers(build_admin(client))).json()
    assert "items_held_by_monsters" in body
    assert body["items_held_by_monsters"] >= 0


def test_monster_rows_carry_the_level_cap(client):
    """★ 상한 없이 레벨만 보면 그것이 높은 값인지 알 수 없다."""
    body = client.get("/api/admin/overview", headers=build_headers(build_admin(client))).json()
    for row in body["monsters"]:
        assert row["level_cap"] >= row["level"]


# ── 개입 ─────────────────────────────────────────────────────────────────


def test_changing_a_level_is_recorded(client):
    """★ **개입은 반드시 남는다.**

    남지 않으면 "이 몬스터 레벨이 왜 이렇지" 를 나중에 아무도 답할 수 없다.
    """
    from game.api.deps import get_pool
    from game.app.monsters.tiers import MonsterTier
    from game.app.store.monsters import create_monster

    admin = build_admin(client)
    record = create_monster(get_pool(), "goblin_rusher", MonsterTier.ELITE, 1, "admin_probe")
    if record is None:
        pytest.skip("그 자리에 이미 개체가 있다")
    body = client.put(
        "/api/admin/monster/level",
        json={"record_id": record.record_id, "level": 3},
        headers=build_headers(admin),
    ).json()
    changed = [row for row in body["monsters"] if row["record_id"] == record.record_id]
    assert changed[0]["level"] == 3
    assert any(item["action"] == "monster.level" for item in body["recent_actions"])


def test_a_level_over_the_cap_is_rejected(client):
    """★ 관리자라도 층 상한을 넘길 수 없다.

    넘기면 폭주 방지(결정 #35)가 뚫리고, 그 개체를 만난 플레이어는 이길 수 없는 판을
    받는다.
    """
    from game.api.deps import get_pool
    from game.app.monsters.tiers import MonsterTier
    from game.app.store.monsters import create_monster

    admin = build_admin(client)
    record = create_monster(get_pool(), "goblin_rusher", MonsterTier.ELITE, 1, "admin_cap_probe")
    if record is None:
        pytest.skip("그 자리에 이미 개체가 있다")
    response = client.put(
        "/api/admin/monster/level",
        json={"record_id": record.record_id, "level": 999},
        headers=build_headers(admin),
    )
    assert response.status_code == 409


def test_a_missing_monster_is_a_404(client):
    """없는 개체에 손대면 조용히 넘어가지 않는다."""
    response = client.put(
        "/api/admin/monster/level",
        json={"record_id": 999999999, "level": 2},
        headers=build_headers(build_admin(client)),
    )
    assert response.status_code == 404
