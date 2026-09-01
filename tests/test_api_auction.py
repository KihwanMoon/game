"""경매장 흐름과 아이템 귀속 (결정 #20, #07).

**수수료가 이 게임의 유일한 화폐 배출구다.** 없으면 화폐가 단조 증가해 몇 주 만에 가격이
무의미해진다. 수식 자체는 `test_auction.py` 가 DB 없이 보고, 여기서는 흐름을 본다.

**거래 후 귀속**(#07)이 여기 함께 있는 이유는 그것이 경제 규칙이기 때문이다. 자유 거래로
두면 같은 아이템을 A→B→A 로 돌려 계정 사이에 화폐를 씻을 수 있고, 봇이 파밍해 파는 것이
최적 전략이 된다.
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

# 매물 조회 상한. 화면은 50줄만 보여주지만 검사는 "걸렸는가" 를 봐야 하므로 넉넉히 둔다.
MINUTES_IN_HOUR = 60
LISTING_PROBE_LIMIT = 10000


@pytest.fixture
def client():
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as running:
        yield running


@pytest.fixture
def token(client):
    return client.post("/api/account").json()["token"]


def find_listing_id(client, token, item_id):
    """방금 건 매물의 id 를 찾는다.

    **응답의 `listings` 를 뒤지지 않는다.** 그것은 싼 것부터 50줄만 보여주는 화면용
    목록이라, 매물이 쌓이면 방금 건 것이 페이지 밖으로 밀린다 — 그것은 화면의 사정이지
    "매물이 안 걸렸다" 가 아니다.
    """
    from game.api.deps import get_pool
    from game.app.store.auction import list_open

    rows = list_open(get_pool(), account_id_of(client, token), limit=LISTING_PROBE_LIMIT)
    return next(row.listing_id for row in rows if row.item_id == item_id)


def account_id_of(client, token):
    """토큰으로 계정 id 를 얻는다."""
    return client.get("/api/account", headers=build_headers(token)).json()["account_id"]


def build_headers(token):
    return {"X-Game-Token": token}


def run_once(client, token):
    headers = build_headers(token)
    ticket = client.post("/api/ticket", json={"room_id": ROOM_ID}, headers=headers).json()
    return client.post(
        "/api/run",
        json={
            "ticket_id": ticket["ticket_id"],
            "ruleset": {"ruleset_id": "p", "version": 1, "rules": []},
            "core_version": ticket["core_version"],
        },
        headers=headers,
    ).json()


def grant_item(client, token, catalog_id="helm_iron"):
    from game.api.deps import get_pool
    from game.app.store.accounts import find_player_entity
    from game.app.store.items import create_item

    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    return create_item(get_pool(), find_player_entity(get_pool(), account_id), catalog_id, ())


def grant_currency(client, token, amount):
    from game.api.deps import get_pool
    from game.app.store.equipment import add_currency

    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    add_currency(get_pool(), account_id, amount)


# ── 경매장 ───────────────────────────────────────────────────────────────


def test_listing_burns_a_fee(client, token):
    """★ 수수료가 이 게임의 유일한 화폐 배출구다."""
    from game.app.store.auction import compute_fee, list_open

    headers = build_headers(token)
    grant_currency(client, token, 1000)
    item_id = grant_item(client, token)
    before = client.get("/api/wallet", headers=headers).json()["balance"]
    body = client.post(
        "/api/auction/list", json={"item_id": item_id, "price": 500}, headers=headers
    ).json()
    assert body["balance"] == before - compute_fee(500)
    # 응답의 `listings` 는 **싼 것부터 50줄**만 보여주는 화면용 목록이라, 매물이 쌓이면
    # 방금 건 것이 페이지 밖으로 밀린다. 그것은 화면의 사정이지 "매물이 안 걸렸다" 가
    # 아니므로, 걸렸는지는 저장 층에 직접 묻는다.
    from game.api.deps import get_pool

    listed = list_open(get_pool(), account_id_of(client, token), limit=LISTING_PROBE_LIMIT)
    assert any(row.item_id == item_id for row in listed)


def test_listing_removes_it_from_the_bag(client, token):
    """★ 걸어 두고 그대로 쓸 수 있으면 하나를 여러 번 팔 수 있다."""
    headers = build_headers(token)
    grant_currency(client, token, 1000)
    item_id = grant_item(client, token)
    client.post("/api/auction/list", json={"item_id": item_id, "price": 100}, headers=headers)
    slots = client.get("/api/inventory", headers=headers).json()["slots"]
    assert all((slot["item"] or {}).get("item_id") != item_id for slot in slots)


def test_cannot_buy_my_own_listing(client, token):
    """★ 자기 것을 사는 것은 수수료만 태우는 자전거래다."""
    headers = build_headers(token)
    grant_currency(client, token, 5000)
    item_id = grant_item(client, token)
    client.post("/api/auction/list", json={"item_id": item_id, "price": 100}, headers=headers)
    listing_id = find_listing_id(client, token, item_id)
    response = client.post("/api/auction/buy", json={"listing_id": listing_id}, headers=headers)
    assert response.status_code == 409


def test_buying_moves_money_and_ownership(client, token):
    headers = build_headers(token)
    grant_currency(client, token, 5000)
    item_id = grant_item(client, token)
    client.post("/api/auction/list", json={"item_id": item_id, "price": 300}, headers=headers)
    listing_id = find_listing_id(client, token, item_id)

    buyer = client.post("/api/account").json()["token"]
    grant_currency(client, buyer, 1000)
    buyer_headers = build_headers(buyer)
    before = client.get("/api/wallet", headers=buyer_headers).json()["balance"]
    client.post("/api/auction/buy", json={"listing_id": listing_id}, headers=buyer_headers)

    assert client.get("/api/wallet", headers=buyer_headers).json()["balance"] == before - 300
    slots = client.get("/api/inventory", headers=buyer_headers).json()["slots"]
    assert any((slot["item"] or {}).get("item_id") == item_id for slot in slots)


def test_broken_items_cannot_be_listed(client, token):
    """★ 팔 수 있으면 복구비용을 남에게 떠넘기는 것이 최적이 된다."""
    from game.api.deps import get_pool
    from game.app.store.accounts import find_player_entity
    from game.app.store.equipment import mark_item_broken

    headers = build_headers(token)
    grant_currency(client, token, 1000)
    item_id = grant_item(client, token)
    account_id = client.get("/api/account", headers=headers).json()["account_id"]
    mark_item_broken(get_pool(), find_player_entity(get_pool(), account_id), item_id)
    response = client.post(
        "/api/auction/list", json={"item_id": item_id, "price": 100}, headers=headers
    )
    assert response.status_code == 409


def test_cancel_returns_it_but_not_the_fee(client, token):
    """★ 수수료를 돌려주면 무료로 시세를 떠볼 수 있다."""
    from game.app.store.auction import compute_fee

    headers = build_headers(token)
    grant_currency(client, token, 1000)
    item_id = grant_item(client, token)
    listed = client.post(
        "/api/auction/list", json={"item_id": item_id, "price": 400}, headers=headers
    ).json()
    listing_id = find_listing_id(client, token, item_id)
    after_list = listed["balance"]
    body = client.post(
        "/api/auction/cancel", json={"listing_id": listing_id}, headers=headers
    ).json()
    assert body["balance"] == after_list
    assert compute_fee(400) > 0
    slots = client.get("/api/inventory", headers=headers).json()["slots"]
    assert any((slot["item"] or {}).get("item_id") == item_id for slot in slots)


# ── 거래 후 귀속 (결정 #07) ──────────────────────────────────────────────


def read_item_view(client, token, item_id):
    """인벤토리에서 그 아이템의 화면용 절을 찾는다."""
    slots = client.get("/api/inventory", headers=build_headers(token)).json()["slots"]
    for slot in slots:
        item = slot["item"] or {}
        if item.get("item_id") == item_id:
            return item
    return None


def test_a_fresh_item_is_not_bound(client, token):
    """★ 주운 것은 팔 수 있다 — 아니면 경매장과 파밍 동기가 함께 죽는다."""
    item_id = grant_item(client, token)
    assert read_item_view(client, token, item_id)["is_bound"] is False


def test_buying_binds_the_item(client, token):
    """★ **여기가 #07 의 전부다.**

    산 물건이 다시 팔리면 같은 아이템을 A→B→A 로 돌려 계정 사이에 화폐를 씻을 수 있고,
    봇이 파밍해 파는 것이 최적 전략이 된다.
    """
    headers = build_headers(token)
    grant_currency(client, token, 5000)
    item_id = grant_item(client, token)
    client.post("/api/auction/list", json={"item_id": item_id, "price": 200}, headers=headers)
    listing_id = find_listing_id(client, token, item_id)

    buyer = client.post("/api/account").json()["token"]
    grant_currency(client, buyer, 5000)
    client.post("/api/auction/buy", json={"listing_id": listing_id}, headers=build_headers(buyer))
    assert read_item_view(client, buyer, item_id)["is_bound"] is True


def test_a_bought_item_cannot_be_relisted(client, token):
    """★ 귀속된 것을 다시 걸 수 있으면 귀속이 표시일 뿐이다."""
    headers = build_headers(token)
    grant_currency(client, token, 5000)
    item_id = grant_item(client, token)
    client.post("/api/auction/list", json={"item_id": item_id, "price": 200}, headers=headers)
    listing_id = find_listing_id(client, token, item_id)

    buyer = client.post("/api/account").json()["token"]
    grant_currency(client, buyer, 5000)
    buyer_headers = build_headers(buyer)
    client.post("/api/auction/buy", json={"listing_id": listing_id}, headers=buyer_headers)
    response = client.post(
        "/api/auction/list", json={"item_id": item_id, "price": 200}, headers=buyer_headers
    )
    assert response.status_code >= 400
    assert "귀속" in response.text


def test_the_seller_can_relist_after_cancelling(client, token):
    """★ 취소는 거래가 아니다 — 취소로 귀속되면 걸어 보는 것 자체가 벌이 된다."""
    headers = build_headers(token)
    grant_currency(client, token, 5000)
    item_id = grant_item(client, token)
    client.post("/api/auction/list", json={"item_id": item_id, "price": 200}, headers=headers)
    listing_id = find_listing_id(client, token, item_id)
    client.post("/api/auction/cancel", json={"listing_id": listing_id}, headers=headers)
    assert read_item_view(client, token, item_id)["is_bound"] is False
    again = client.post(
        "/api/auction/list", json={"item_id": item_id, "price": 300}, headers=headers
    )
    assert again.status_code == 200


def test_the_same_item_cannot_be_listed_twice_at_once(client, token):
    """★ 동시에 두 번 걸리면 하나를 두 사람에게 팔 수 있다.

    취소 뒤 재등록은 열어 주되(위 검사), **열려 있는 동안은 하나뿐**이어야 한다 —
    부분 인덱스가 그 둘을 가른다.
    """
    headers = build_headers(token)
    grant_currency(client, token, 5000)
    item_id = grant_item(client, token)
    first = client.post(
        "/api/auction/list", json={"item_id": item_id, "price": 200}, headers=headers
    )
    assert first.status_code == 200
    second = client.post(
        "/api/auction/list", json={"item_id": item_id, "price": 300}, headers=headers
    )
    assert second.status_code >= 400


def find_listing_row(client, token, item_id):
    """이 아이템의 매물을 **화면이 받는 절 그대로** 만들어 낸다.

    `/api/auction` 응답을 뒤지지 않는다. 그것은 싼 것부터 50줄만 보여주는 화면용
    목록이라 매물이 쌓이면 방금 건 것이 페이지 밖으로 밀린다. 대신 저장 층에서 그 줄을
    꺼내 라우트와 같은 변환 함수에 넣는다 — 검사 대상은 페이지네이션이 아니라 변환이다.

    Args:
        client: 테스트 클라이언트.
        token: 기기 토큰.
        item_id: 대상 아이템.

    Returns:
        매물 절.
    """
    from game.api.deps import get_item_catalog, get_pool
    from game.api.routes.auction import build_listing_view
    from game.app.store.auction import list_open

    rows = list_open(get_pool(), account_id_of(client, token), limit=LISTING_PROBE_LIMIT)
    row = next(entry for entry in rows if entry.item_id == item_id)
    return build_listing_view(row, get_item_catalog())


def test_a_listing_carries_the_affixes_it_actually_rolled(client, token):
    """★ 이름과 값만 보고 사면 저주를 돈 주고 산다.

    접사는 인스턴스마다 다르게 굴린다. 카탈로그 기본값을 보내면 화면이 거짓말을 한다.
    """
    from game.api.deps import get_pool
    from game.app.store.accounts import find_player_entity
    from game.app.store.items import create_item
    from game.schemas.item import Affix

    headers = build_headers(token)
    grant_currency(client, token, 1000)
    entity_id = find_player_entity(get_pool(), account_id_of(client, token))
    rolled = (Affix(stat="attack", flat=7, percent=0, label_ko="날카로움"),)
    item_id = create_item(get_pool(), entity_id, "helm_iron", rolled)
    client.post("/api/auction/list", json={"item_id": item_id, "price": 100}, headers=headers)
    view = find_listing_row(client, token, item_id)
    # 카탈로그의 `helm_iron` 은 이 접사를 갖고 있지 않다. 값이 그대로 나오면 인스턴스가
    # 굴린 것을 실었다는 뜻이고, 다른 값이 나오면 카탈로그 기본값을 실은 것이다.
    assert view.affixes == [
        {
            "stat": "attack",
            "flat": 7,
            "percent": 0,
            "label_ko": "날카로움",
            # 경매장도 능력치의 한글 이름을 받는다. 한 화면만 빠뜨리면 **거기서만**
            # 영어 키가 보이고, 그 사실이 그 화면을 열기 전까지 안 드러난다.
            "stat_label": "공격력",
        }
    ]


def test_a_listing_says_when_it_disappears(client, token):
    """★ 언제 사라지는지 모르면 기다릴지 지금 살지를 정할 수 없다."""
    headers = build_headers(token)
    grant_currency(client, token, 1000)
    item_id = grant_item(client, token)
    client.post("/api/auction/list", json={"item_id": item_id, "price": 100}, headers=headers)
    view = find_listing_row(client, token, item_id)
    # 방금 걸었으므로 만료까지 한 시간 이상 남아 있어야 한다. 0 이면 시계가 아니라
    # 상수를 보내고 있다는 뜻이다.
    assert view.expires_in_minutes > MINUTES_IN_HOUR


def test_a_listing_says_how_much_of_the_fee_is_gone(client, token):
    """★ 내려도 안 돌아오는 돈이다. 그 사실이 화면에 있어야 한다."""
    from game.app.store.auction import compute_fee

    headers = build_headers(token)
    grant_currency(client, token, 2000)
    item_id = grant_item(client, token)
    client.post("/api/auction/list", json={"item_id": item_id, "price": 700}, headers=headers)
    view = find_listing_row(client, token, item_id)
    assert view.fee == compute_fee(700)
    assert view.fee > 0
