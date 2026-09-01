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
    """★ 이미 나온 것에 소급하지 않는 것은 고칠 수 있어야 한다.

    **화면이 실제로 보내는 절로 부른다.** 예전 검사는 전체 절을 되풀이해 보냈고, 그래서
    화면이 접사를 안 실어 보내 이름 바꾸기가 전부 거절되던 것을 못 봤다 — 검사가 진짜
    클라이언트가 안 쓰는 모양을 쓰고 있었다.
    """
    item = build_item(client, admin)
    client.post("/api/admin/catalog/item", json=item, headers=build_headers(admin))
    response = client.post(
        "/api/admin/catalog/edit",
        json={
            "catalog_id": item["id"],
            "label_ko": "고친 이름",
            "min_floor": 5,
            "reason": REASON,
        },
        headers=build_headers(admin),
    )
    assert response.status_code == 200
    row = find_row(response.json(), item["id"])
    assert row is not None and row["label_ko"] == "고친 이름" and row["min_floor"] == 5


def test_editing_cannot_touch_the_slot(client, admin):
    """★ 분류·슬롯·손 규격은 **이미 착용된 자리**를 가리킨다 (개정: §15.11).

    투구를 갑옷으로 바꾸면 누군가의 머리 칸에 갑옷이 들어 있게 되고, 그 상태를 어느
    화면도 설명하지 못한다. 접사·등급은 인스턴스가 자기 것을 갖게 된 뒤로 열렸다.
    """
    from game.api.view_schemas import CatalogEditRequest

    fields = set(CatalogEditRequest.model_fields)
    assert "kind" not in fields
    assert "slot" not in fields
    assert "hands" not in fields
    assert {"affixes", "grade"} <= fields


def test_editing_the_affixes_changes_what_drops_next(client, admin):
    """★ 접사를 고칠 수 있어야 밸런스가 손에 잡힌다 — 그것이 §15.11 이 연 것이다."""
    item = build_item(client, admin)
    client.post("/api/admin/catalog/item", json=item, headers=build_headers(admin))
    response = client.post(
        "/api/admin/catalog/edit",
        json={
            "catalog_id": item["id"],
            "label_ko": "표본 검",
            "min_floor": 2,
            "grade": "RELIC",
            "affixes": [{"stat": "attack", "flat": 12, "label_ko": "다시 벼림"}],
            "reason": REASON,
        },
        headers=build_headers(admin),
    )
    assert response.status_code == 200
    row = find_row(response.json(), item["id"])
    assert row is not None
    assert row["grade"] == "RELIC"
    assert row["affixes"] == ["다시 벼림 +12"]


def test_an_edit_does_not_reach_into_a_bag(client, admin):
    """★ 카탈로그를 고쳐도 이미 나온 아이템은 안 바뀐다 (§15.11).

    인스턴스가 자기 접사를 갖는 것이 그 근거다. 이 성질이 깨지면 접사 편집을 다시
    통째로 막아야 한다.
    """
    from game.api.deps import get_item_catalog, get_pool
    from game.app.store.accounts import find_player_entity
    from game.app.store.items import create_item, find_item

    item = build_item(client, admin)
    client.post("/api/admin/catalog/item", json=item, headers=build_headers(admin))
    account_id = client.get("/api/account", headers=build_headers(admin)).json()["account_id"]
    entity_id = find_player_entity(get_pool(), account_id)
    held = create_item(get_pool(), entity_id, item["id"], get_item_catalog()[item["id"]].affixes)
    before = find_item(get_pool(), entity_id, held)
    client.post(
        "/api/admin/catalog/edit",
        json={
            "catalog_id": item["id"],
            "label_ko": "표본 검",
            "min_floor": 2,
            "affixes": [{"stat": "attack", "flat": 99, "label_ko": "소급 시도"}],
            "reason": REASON,
        },
        headers=build_headers(admin),
    )
    after = find_item(get_pool(), entity_id, held)
    assert after is not None and before is not None
    assert after.affixes == before.affixes, "카탈로그 수정이 가방까지 닿았다"


def test_an_empty_affix_list_keeps_the_current_ones(client, admin):
    """★ 빈 목록을 「지운다」로 읽으면 이름만 고치려던 요청이 아이템을 맹탕으로 만든다."""
    item = build_item(client, admin)
    client.post("/api/admin/catalog/item", json=item, headers=build_headers(admin))
    before = find_row(read_items(client, admin), item["id"])
    response = client.post(
        "/api/admin/catalog/edit",
        json={
            "catalog_id": item["id"],
            "label_ko": "이름만",
            "min_floor": 2,
            "reason": REASON,
        },
        headers=build_headers(admin),
    )
    after = find_row(response.json(), item["id"])
    assert before is not None and after is not None
    assert after["affixes"] == before["affixes"]


def test_an_item_keeps_its_affixes_after_a_rename(client, admin):
    """★ 이름만 고쳤는데 접사가 사라지면 그 아이템이 성능을 잃는다."""
    item = build_item(client, admin)
    client.post("/api/admin/catalog/item", json=item, headers=build_headers(admin))
    before = find_row(read_items(client, admin), item["id"])
    response = client.post(
        "/api/admin/catalog/edit",
        json={
            "catalog_id": item["id"],
            "label_ko": "이름만 바꿈",
            "min_floor": 2,
            "reason": REASON,
        },
        headers=build_headers(admin),
    )
    after = find_row(response.json(), item["id"])
    assert before is not None and after is not None
    assert after["affixes"] == before["affixes"]
    assert after["grade"] == before["grade"]


def test_registering_an_existing_id_says_where_to_go(client, admin):
    """★ 있는 id 로 등록하려는 것은 십중팔구 「고치려던 것」이다."""
    item = build_item(client, admin)
    client.post("/api/admin/catalog/item", json=item, headers=build_headers(admin))
    response = client.post("/api/admin/catalog/item", json=item, headers=build_headers(admin))
    assert response.status_code == 409
    assert "고치기" in response.json()["detail"]


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


def read_drops(client, token, kind_id):
    return client.get(f"/api/admin/drops/{kind_id}", headers=build_headers(token)).json()
