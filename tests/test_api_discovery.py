"""도감 해금 — 얻은 것이 밝혀진다 (요구: 등록된 것을 조회하고, 획득한 것은 해금).

여기서 지키는 것은 넷이다.

1. **미해금도 목록에 있다.** 안 밝힌 것을 빼면 도감이 "내가 가진 것 목록" 이 되고,
   무엇을 더 찾아야 하는지가 화면에서 사라진다.
2. **속살은 밝힌 뒤에만.** 안 밝힌 것의 성능이 다 보이면 도감이 상점이 된다.
3. **소유가 아니라 이력이다.** 팔거나 잃어도 해금은 남는다.
4. **얻는 길이 셋이다** — 보상 발급·되찾기·경매 구매. 하나만 기록하면 "왜 저건 도감에
   안 뜨지" 가 된다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

fastapi_testclient = pytest.importorskip("fastapi.testclient")

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)

PROBE_ITEM = "helm_iron"


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


def read_discovery(client, token):
    return client.get("/api/discovery", headers=build_headers(token)).json()


def find_row(body, kind, ref_id):
    key = "items" if kind == "ITEM" else "skills"
    return next(row for row in body[key] if row["ref_id"] == ref_id)


def test_an_untouched_account_still_sees_the_whole_list(client, token):
    """★ 안 밝힌 것을 목록에서 빼면 무엇을 더 찾아야 하는지가 사라진다."""
    body = read_discovery(client, token)
    assert body["total"] > 0
    assert body["found"] == 0
    # 아이템도 스킬도 자리는 다 있어야 한다.
    assert body["items"]
    assert body["skills"]


def test_an_unfound_row_hides_its_numbers(client, token):
    """★ 안 밝힌 것의 성능이 다 보이면 도감이 상점이 된다."""
    body = read_discovery(client, token)
    hidden = [row for row in body["items"] if not row["is_found"]]
    assert hidden
    assert all(row["detail"] == "" for row in hidden)
    # 이름과 분류는 가리지 않는다 — 목표가 안 보이면 찾아갈 이유도 안 생긴다.
    assert all(row["label_ko"] != "" for row in hidden)


def test_getting_an_item_unlocks_it(client, token):
    """★ 얻은 것이 안 밝혀지면 해금이라는 말이 아무 뜻도 없다."""
    from game.api.discovery_service import record_item_discovery

    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    record_item_discovery(account_id, PROBE_ITEM)
    row = find_row(read_discovery(client, token), "ITEM", PROBE_ITEM)
    assert row["is_found"]
    assert row["detail"] != ""


def test_an_item_also_unlocks_the_skill_it_grants(client, token):
    """★ 장비가 스킬을 여는 구조에서 아이템만 밝히면, 그 검을 찾는 이유가 안 보인다."""
    from game.api.deps import get_item_catalog
    from game.api.discovery_service import record_item_discovery

    catalog = get_item_catalog()
    granting = next(entry for entry in catalog.values() if entry.grants_skill)
    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    record_item_discovery(account_id, granting.catalog_id)
    row = find_row(read_discovery(client, token), "SKILL", granting.grants_skill)
    assert row["is_found"]


def test_losing_it_does_not_lock_it_again(client, token):
    """★ 소유로 계산하면 판 순간 도감이 잠긴다 — 그러면 「본 것」이 아니라 「가진 것」이다."""
    from game.api.deps import get_pool
    from game.api.discovery_service import record_item_discovery
    from game.app.store.accounts import find_player_entity
    from game.app.store.equipment import remove_item
    from game.app.store.items import create_item

    headers = build_headers(token)
    account_id = client.get("/api/account", headers=headers).json()["account_id"]
    entity_id = find_player_entity(get_pool(), account_id)
    item_id = create_item(get_pool(), entity_id, PROBE_ITEM, ())
    record_item_discovery(account_id, PROBE_ITEM)
    remove_item(get_pool(), entity_id, item_id)
    assert find_row(read_discovery(client, token), "ITEM", PROBE_ITEM)["is_found"]


def test_buying_unlocks_it_for_the_buyer(client, token):
    """★ 경매로만 구할 수 있는 것이 영영 안 열리면 도감이 절반만 산다."""
    from game.api.deps import get_pool
    from game.app.store.accounts import find_player_entity
    from game.app.store.auction import list_open
    from game.app.store.equipment import add_currency
    from game.app.store.items import create_item

    seller = client.post("/api/account").json()["token"]
    seller_headers = build_headers(seller)
    seller_id = client.get("/api/account", headers=seller_headers).json()["account_id"]
    add_currency(get_pool(), seller_id, 1000)
    item_id = create_item(get_pool(), find_player_entity(get_pool(), seller_id), PROBE_ITEM, ())
    client.post("/api/auction/list", json={"item_id": item_id, "price": 10}, headers=seller_headers)
    listing_id = next(
        row.listing_id
        for row in list_open(get_pool(), seller_id, limit=100_000)
        if row.item_id == item_id
    )

    buyer_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    add_currency(get_pool(), buyer_id, 1000)
    assert not find_row(read_discovery(client, token), "ITEM", PROBE_ITEM)["is_found"]
    response = client.post(
        "/api/auction/buy", json={"listing_id": listing_id}, headers=build_headers(token)
    )
    assert response.status_code == 200
    assert find_row(read_discovery(client, token), "ITEM", PROBE_ITEM)["is_found"]
