"""몬스터별 드롭 표 관리 (설계/4_아이템 §15.6 D3).

`test_api_catalog_admin.py` 에서 갈라 둔 이유는 책임이 다르기 때문이다 — 저쪽은 아이템
종류가 무엇인가이고, 이쪽은 **누가 그것을 떨구는가**다.

여기서 지키는 것은 셋이다.

1. **소스별 표가 있으면 `ANY` 를 안 본다.** 두 표를 합치면 "이 몬스터만 떨군다" 가
   성립하지 않고, 도감이 표적 목록이 되는 근거가 그 배타성이다.
2. **가중치 0 은 지우는 것이 아니라 안 나오게 하는 것이다.**
3. **없는 아이템은 표에 못 올린다.** 올리면 굴림이 그 등급에서 아무것도 못 뽑는다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)

REASON = "검사용 조작"
# **매번 새 id 를 쓴다.** 같은 id 를 쓰면 앞선 실행이 남긴 드롭 표 줄 때문에 "표에
# 올렸는가" 가 코드와 무관하게 통과한다 — 실제로 그렇게 통과했다.
BASE_ITEM = {
    "id": "probe_blade",
    "kind": "EQUIPMENT",
    "label_ko": "표본 검",
    "slot": "WEAPON_MAIN",
    "hands": "ONE",
    "grade": "FINE",
    "min_floor": 2,
    "affixes": [{"stat": "attack", "flat": 3, "label_ko": "표본 날"}],
    "reason": REASON,
}


def build_item(client, token, **patch):
    """이 실행에서만 쓰는 아이템 절을 만든다.

    Args:
        client: 테스트 클라이언트.
        token: 관리자 토큰.
        patch: 덮어쓸 값들.

    Returns:
        아이템 절.
    """
    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    return {**BASE_ITEM, "id": f"probe_blade_{account_id}", **patch}


@pytest.fixture
def client():
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as running:
        yield running


@pytest.fixture
def admin(client):
    """관리자 토큰. 승격은 스크립트와 같은 경로(저장 층)로만 한다."""
    from game.api.deps import get_pool
    from game.app.store.admin import ROLE_OWNER, set_admin_role

    account = client.post("/api/account").json()
    login_id = f"catadmin{account['account_id']}"
    client.post(
        "/api/register",
        json={"login_id": login_id, "password": "probe-password-1"},
        headers=build_headers(account["token"]),
    )
    assert set_admin_role(get_pool(), login_id, ROLE_OWNER)
    return account["token"]


def build_headers(token):
    return {"X-Game-Token": token}


def read_items(client, token):
    return client.get("/api/admin/catalog/items", headers=build_headers(token)).json()


def find_row(body, catalog_id):
    return next((row for row in body["items"] if row["catalog_id"] == catalog_id), None)


def read_drops(client, token, kind_id):
    return client.get(f"/api/admin/drops/{kind_id}", headers=build_headers(token)).json()


def test_a_monster_without_a_table_says_so(client, admin):
    """★ 소스별 표가 없으면 ANY 로 떨어진다 — 그 사실이 화면에 있어야 「왜 다른 게
    나오지」를 안 겪는다."""
    body = read_drops(client, admin, "no_such_kind_probe")
    assert body["uses_default"] is True
    assert body["rows"] == []


def test_setting_a_drop_takes_the_monster_off_the_default(client, admin):
    """★ 첫 줄을 세우는 순간 그 몬스터는 ANY 를 안 본다 (D3).

    두 표를 합치면 "이 몬스터만 떨군다" 가 성립하지 않고, 도감이 표적 목록이 되는 근거가
    그 배타성이다.
    """
    account_id = client.get("/api/account", headers=build_headers(admin)).json()["account_id"]
    kind = f"probe_drop_{account_id}"
    response = client.post(
        "/api/admin/drops",
        json={
            "kind_id": kind,
            "grade": "COMMON",
            "catalog_id": "helm_iron",
            "weight": 7,
            "reason": REASON,
        },
        headers=build_headers(admin),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["uses_default"] is False
    assert [(row["catalog_id"], row["weight"]) for row in body["rows"]] == [("helm_iron", 7)]
    assert body["rows"][0]["label_ko"] != "", "이름이 없으면 관리자가 id 로만 고른다"


def test_a_drop_for_a_missing_item_is_refused(client, admin):
    """★ 없는 아이템을 표에 올리면 굴림이 그 등급에서 아무것도 못 뽑는다."""
    response = client.post(
        "/api/admin/drops",
        json={
            "kind_id": "probe_kind",
            "grade": "COMMON",
            "catalog_id": "no_such_item",
            "weight": 1,
            "reason": REASON,
        },
        headers=build_headers(admin),
    )
    assert response.status_code == 404


def test_a_drop_without_a_reason_is_refused(client, admin):
    """★ 사유 없는 개입은 나중에 아무도 설명할 수 없다."""
    response = client.post(
        "/api/admin/drops",
        json={
            "kind_id": "probe_kind",
            "grade": "COMMON",
            "catalog_id": "helm_iron",
            "weight": 1,
            "reason": "",
        },
        headers=build_headers(admin),
    )
    assert response.status_code == 400


def test_a_zero_weight_keeps_the_row(client, admin):
    """★ 가중치 0 은 지우는 것이 아니라 안 나오게 하는 것이다.

    줄을 지우면 "이 몬스터가 무엇을 떨구기로 되어 있었는가" 를 나중에 못 읽는다.
    """
    account_id = client.get("/api/account", headers=build_headers(admin)).json()["account_id"]
    kind = f"probe_zero_{account_id}"
    client.post(
        "/api/admin/drops",
        json={
            "kind_id": kind,
            "grade": "COMMON",
            "catalog_id": "helm_iron",
            "weight": 5,
            "reason": REASON,
        },
        headers=build_headers(admin),
    )
    response = client.post(
        "/api/admin/drops",
        json={
            "kind_id": kind,
            "grade": "COMMON",
            "catalog_id": "helm_iron",
            "weight": 0,
            "reason": REASON,
        },
        headers=build_headers(admin),
    )
    rows = response.json()["rows"]
    assert [(row["catalog_id"], row["weight"]) for row in rows] == [("helm_iron", 0)]


def test_registering_refreshes_what_the_server_holds(client, admin):
    """★ 등록해도 서버가 모르면 그 아이템은 영영 안 나온다.

    굴림이 보는 것은 기동 시점에 읽은 사본이다. 등록이 그 사본을 갈아 끼우지 않으면
    새 아이템이 드롭 표에는 있는데 카탈로그에는 없는 상태가 되고, 굴림이 그 자리에서
    터진다.
    """
    from game.api.deps import get_item_catalog

    item = build_item(client, admin, id=f"probe_fresh_{REASON and 1}")
    account_id = client.get("/api/account", headers=build_headers(admin)).json()["account_id"]
    item = {**item, "id": f"probe_fresh_{account_id}"}
    assert item["id"] not in get_item_catalog()
    client.post("/api/admin/catalog/item", json=item, headers=build_headers(admin))
    assert item["id"] in get_item_catalog(), "등록했는데 서버가 모른다"
