"""랭킹·데일리·경매장 흐름 (F단계).

여기서 지키는 것은 다섯이다.

1. **경험치는 검증된 런에서만 오른다.** 순위의 근거가 누적 경험치이므로, 클라이언트
   보고로 오르면 순위표가 곧 거짓이 된다.
2. **랭킹은 코어 버전별로 갈린다** (결정 #06). 섞으면 재현되지 않는 기록이 상위에 남는다.
3. **데일리는 하루 한 번, 모두 같은 시드.**
4. **수수료가 화폐를 태운다.** 이 게임의 유일한 배출구다.
5. **자기 매물은 못 산다.** 막지 않으면 원장이 자전거래로 찬다.
"""

import os
from datetime import date

import pytest

from game.app.store.connection import DATABASE_URL_ENV

fastapi_testclient = pytest.importorskip("fastapi.testclient")

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)

ROOM_ID = "corridor"

# 매물 조회 상한. 화면은 50줄만 보여주지만 검사는 "걸렸는가" 를 봐야 하므로 넉넉히 둔다.
LISTING_PROBE_LIMIT = 10000


@pytest.fixture
def client():
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as running:
        yield running


@pytest.fixture
def token(client):
    return client.post("/api/account").json()["token"]


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


# ── 성장·랭킹 ────────────────────────────────────────────────────────────


def test_progress_starts_at_level_one(client, token):
    body = client.get("/api/progress", headers=build_headers(token)).json()
    assert body["level"] == 1
    assert body["total_xp"] == 0
    assert set(body["stat_keys"]) == {"str", "dex", "int"}


def test_a_verified_run_grants_xp(client, token):
    """★ 경험치는 검증된 런에서만 오른다."""
    body = run_once(client, token)
    assert body["verdict"] == "verified"
    assert "경험치" in body["reward"]
    assert client.get("/api/progress", headers=build_headers(token)).json()["total_xp"] > 0


def test_leaderboard_scores_by_total_xp(client, token):
    """★ 점수는 누적 경험치다 — 한 판의 성적이 아니라 얼마나 멀리 왔는가."""
    headers = build_headers(token)
    account_id = client.get("/api/account", headers=headers).json()["account_id"]
    run_once(client, token)
    total = client.get("/api/progress", headers=headers).json()["total_xp"]
    # 순위표는 상위 N 만 준다. 계정이 많으면 새 계정이 거기 없는 것이 정상이므로,
    # 저장된 값을 직접 본다 — 목록에 있는지로 검사하면 계정 수에 따라 흔들린다.
    from game.api.deps import get_pool

    with get_pool().connection() as connection:
        row = connection.execute(
            "SELECT score FROM leaderboard WHERE account_id = %s", (account_id,)
        ).fetchone()
    assert row is not None
    assert int(row[0]) == total


def test_leaderboard_is_seasoned_by_core_version(client, token):
    """★ 결정 #06 — 섞으면 재현되지 않는 기록이 상위에 남는다."""
    body = client.get("/api/leaderboard", headers=build_headers(token)).json()
    health = client.get("/api/health").json()
    assert body["core_version"] == health["core_version"]


def test_allocation_persists(client, token):
    from game.api.deps import get_pool
    from game.app.store.accounts import find_player_entity
    from game.app.store.progress import add_player_xp

    headers = build_headers(token)
    account_id = client.get("/api/account", headers=headers).json()["account_id"]
    add_player_xp(get_pool(), find_player_entity(get_pool(), account_id), 100_000)

    body = client.put("/api/progress/stats", json={"stats": {"str": 3}}, headers=headers).json()
    assert body["stats"]["str"] == 3
    assert body["spent_points"] == 3


def test_over_allocation_is_rejected(client, token):
    """레벨 1 은 포인트가 없다."""
    response = client.put(
        "/api/progress/stats", json={"stats": {"str": 99}}, headers=build_headers(token)
    )
    assert response.status_code == 400


# ── 데일리 ───────────────────────────────────────────────────────────────


def test_daily_is_once_per_day(client, token):
    """★ 두 번 받아도 같은 티켓이다."""
    headers = build_headers(token)
    first = client.post("/api/daily", headers=headers).json()
    second = client.post("/api/daily", headers=headers).json()
    assert first["ticket_id"] == second["ticket_id"]
    assert first["mode"] == "DAILY"


def test_daily_seed_is_the_same_for_everyone(client, token):
    """★ 모두 같은 시드를 받아야 데일리가 성립한다."""
    other = client.post("/api/account").json()["token"]
    mine = client.post("/api/daily", headers=build_headers(token)).json()
    theirs = client.post("/api/daily", headers=build_headers(other)).json()
    assert mine["seed"] == theirs["seed"]
    assert mine["ticket_id"] != theirs["ticket_id"]


def test_daily_seed_is_derived_from_the_day():
    from game.api.routes.world import build_daily_seed
    from game.schemas.run_ticket import MAX_SEED

    seed = build_daily_seed(date(2026, 8, 30), "b5.v2.e1")
    assert seed == build_daily_seed(date(2026, 8, 30), "b5.v2.e1")
    assert seed != build_daily_seed(date(2026, 8, 31), "b5.v2.e1")
    # 밸런스가 바뀌면 같은 날짜라도 다른 판이어야 한다.
    assert seed != build_daily_seed(date(2026, 8, 30), "b6.v2.e1")
    assert 0 <= seed <= MAX_SEED


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
    listed = client.post(
        "/api/auction/list", json={"item_id": item_id, "price": 100}, headers=headers
    ).json()
    listing_id = next(i["listing_id"] for i in listed["listings"] if i["item_id"] == item_id)
    response = client.post("/api/auction/buy", json={"listing_id": listing_id}, headers=headers)
    assert response.status_code == 409


def test_buying_moves_money_and_ownership(client, token):
    headers = build_headers(token)
    grant_currency(client, token, 5000)
    item_id = grant_item(client, token)
    listed = client.post(
        "/api/auction/list", json={"item_id": item_id, "price": 300}, headers=headers
    ).json()
    listing_id = next(i["listing_id"] for i in listed["listings"] if i["item_id"] == item_id)

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
    listing_id = next(i["listing_id"] for i in listed["listings"] if i["item_id"] == item_id)
    after_list = listed["balance"]
    body = client.post(
        "/api/auction/cancel", json={"listing_id": listing_id}, headers=headers
    ).json()
    assert body["balance"] == after_list
    assert compute_fee(400) > 0
    slots = client.get("/api/inventory", headers=headers).json()["slots"]
    assert any((slot["item"] or {}).get("item_id") == item_id for slot in slots)
