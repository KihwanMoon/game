"""카탈로그 관리 — 조회·등록·폐기 (설계/4_아이템 §15.7).

여기서 지키는 것은 여섯이다.

1. **삭제가 없다.** 인스턴스·원장·경매가 catalog_id 를 가리킨다.
2. **제자리 수정이 제한된다.** 접사·등급·분류를 고치면 이미 나온 아이템이 소급해 바뀐다 —
   인스턴스가 굴린 접사가 없으면 카탈로그 기본값을 쓰기 때문이다.
3. **모든 변경이 세대를 올린다.** 아이템을 고치는 것은 시즌을 가르는 일이다.
4. **등록하면 드롭 표에도 오른다.** 안 올리면 등록해도 굴려서 안 나오고, 그 답은 화면
   어디에도 없다.
5. **사유 없는 개입이 없다.** 되돌릴 수 없는 조작이다.
6. **관리자가 아니면 404 다.** 존재 자체를 흘리지 않는다.
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
    from game.app.store.admin import set_admin

    account = client.post("/api/account").json()
    login_id = f"catadmin{account['account_id']}"
    client.post(
        "/api/register",
        json={"login_id": login_id, "password": "probe-password-1"},
        headers=build_headers(account["token"]),
    )
    assert set_admin(get_pool(), login_id, True)
    return account["token"]


def build_headers(token):
    return {"X-Game-Token": token}


def read_items(client, token):
    return client.get("/api/admin/catalog/items", headers=build_headers(token)).json()


def find_row(body, catalog_id):
    return next((row for row in body["items"] if row["catalog_id"] == catalog_id), None)


def test_a_stranger_gets_404(client):
    """★ 403 이면 「거기 뭔가 있다」를 알려 준다."""
    token = client.post("/api/account").json()["token"]
    assert client.get("/api/admin/catalog/items", headers=build_headers(token)).status_code == 404


def test_the_list_shows_retired_items_too(client, admin):
    """★ 폐기는 「없다」가 아니라 「새로 안 나온다」다 — 관리자가 되살릴 수 있어야 한다."""
    client.post(
        "/api/admin/catalog/retire",
        json={"catalog_id": "helm_iron", "is_retired": True, "reason": REASON},
        headers=build_headers(admin),
    )
    try:
        row = find_row(read_items(client, admin), "helm_iron")
        assert row is not None and row["is_retired"]
    finally:
        client.post(
            "/api/admin/catalog/retire",
            json={"catalog_id": "helm_iron", "is_retired": False, "reason": REASON},
            headers=build_headers(admin),
        )


def test_registering_an_item_puts_it_on_the_drop_table(client, admin):
    """★ 드롭 표에 안 올리면 등록해도 굴려서 안 나온다 — 그 답이 화면 어디에도 없다."""
    item = build_item(client, admin)
    response = client.post("/api/admin/catalog/item", json=item, headers=build_headers(admin))
    assert response.status_code == 200
    row = find_row(response.json(), item["id"])
    assert row is not None
    assert row["grade"] == "FINE"
    assert row["min_floor"] == 2
    assert row["drop_weight"] > 0, "드롭 표에 안 올랐다"


def test_a_write_moves_the_generation(client, admin):
    """★ 아이템을 고치는 것은 순위표 시즌을 가르는 일이다."""
    before = read_items(client, admin)["generation"]
    client.post(
        "/api/admin/catalog/retire",
        json={"catalog_id": "helm_iron", "is_retired": False, "reason": REASON},
        headers=build_headers(admin),
    )
    assert read_items(client, admin)["generation"] > before


def test_a_retroactive_edit_is_refused(client, admin):
    """★ 접사를 고치면 남의 가방에 있는 아이템의 성능이 바뀐다 (§15.7).

    인스턴스가 굴린 접사가 없으면 카탈로그 기본값을 쓴다. 그래서 이런 수정은 "새 id
    등록 + 옛 id 폐기" 로만 해야 하고, 그 규율을 사람의 기억이 아니라 서버가 지킨다.
    """
    item = build_item(client, admin)
    client.post("/api/admin/catalog/item", json=item, headers=build_headers(admin))
    changed = {**item, "affixes": [{"stat": "attack", "flat": 99, "label_ko": "표본 날"}]}
    response = client.post("/api/admin/catalog/item", json=changed, headers=build_headers(admin))
    assert response.status_code == 409
    assert "새 id" in response.json()["detail"]


def test_the_name_and_floor_can_be_fixed_in_place(client, admin):
    """★ 이미 나온 것에 소급하지 않는 것은 고칠 수 있어야 한다 — 오타까지 새 id 를
    요구하면 아무도 안 고친다."""
    item = build_item(client, admin)
    client.post("/api/admin/catalog/item", json=item, headers=build_headers(admin))
    renamed = {**item, "label_ko": "고친 이름", "min_floor": 5}
    response = client.post("/api/admin/catalog/item", json=renamed, headers=build_headers(admin))
    assert response.status_code == 200
    row = find_row(response.json(), item["id"])
    assert row is not None and row["label_ko"] == "고친 이름" and row["min_floor"] == 5


def test_a_write_without_a_reason_is_refused(client, admin):
    """★ 사유 없는 개입은 나중에 아무도 설명할 수 없다."""
    response = client.post(
        "/api/admin/catalog/item",
        json={**build_item(client, admin), "reason": ""},
        headers=build_headers(admin),
    )
    assert response.status_code == 400


def test_a_broken_item_is_refused(client, admin):
    """★ 장비인데 슬롯이 없으면 착용 판정이 영영 성립하지 않는다."""
    response = client.post(
        "/api/admin/catalog/item",
        json={"id": "probe_bad", "kind": "EQUIPMENT", "reason": REASON},
        headers=build_headers(admin),
    )
    assert response.status_code == 400


def test_there_is_no_delete_route(client, admin):
    """★ 지우면 과거 기록을 못 읽는다 — 원장이 그 id 를 가리킨다."""
    from game.api.main import create_app

    for route in create_app().routes:
        if "/admin/catalog" in getattr(route, "path", ""):
            assert "DELETE" not in set(getattr(route, "methods", set()))
