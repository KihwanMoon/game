"""관리자 경로의 차단 규율.

`test_api_admin.py` 에서 갈라 둔 이유는 책임이 다르기 때문이다 — 저쪽은 관리자가 무엇을
보고 무엇을 고치는가이고, 이쪽은 **관리자가 아닌 사람이 무엇을 못 하는가**다.

여기서 지키는 것은 셋이다.

1. **404 로 답한다.** 403 이면 "거기 뭔가 있다" 를 알려 준다.
2. **승격 엔드포인트가 없다.** 그 하나가 뚫리면 세계 전체가 뚫린다.
3. **관리자 경로 목록을 못 박는다.** 새 경로가 붙는 순간 그것이 얼마나 위험한지 한 번
   더 보게 한다.
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
    # 관리자 경로는 **조회와 개입뿐**이다. 늘어나면 이 목록을 함께 고치게 해서,
    # 새 경로가 붙는 순간 그것이 얼마나 위험한지 한 번 더 보게 한다.
    assert sorted(path for path in paths if "/admin/" in path) == [
        "/api/admin/auction/cancel",
        "/api/admin/catalog",
        "/api/admin/catalog/item",
        "/api/admin/catalog/items",
        "/api/admin/catalog/retire",
        "/api/admin/content",
        "/api/admin/content/discard",
        "/api/admin/content/draft",
        "/api/admin/content/publish",
        "/api/admin/content/{asset}",
        "/api/admin/drops",
        "/api/admin/drops/{kind_id}",
        "/api/admin/item/recall",
        "/api/admin/monster/level",
        "/api/admin/overview",
    ]


def test_an_anonymous_account_cannot_be_promoted(client, token):
    """★ 익명은 관리자가 될 수 없다 — 토큰 하나가 곧 세계 전체가 된다."""
    from game.api.deps import get_pool
    from game.app.store.admin import set_admin

    handle = client.get("/api/account", headers=build_headers(token)).json()["handle"]
    assert not set_admin(get_pool(), handle, True)
