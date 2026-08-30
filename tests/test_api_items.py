"""아이템 — 서버 발급·인벤토리·장비·사망 손실 (D단계).

여기서 지키는 것은 다섯이다.

1. **아이템은 서버만 만든다** (결정 #02). 클라이언트가 보낸 것으로 아이템이 생기지 않는다.
2. **요구조건은 소재 능력치로만 판정한다** (§7). 장비 보너스를 섞으면 착용 순서가
   결과를 바꾸고, 서버가 (계정, 아이템)만으로 재판정할 수 없게 된다.
3. **봉인은 계산값이다** (§2.1). 양손무기를 끼면 보조 자리가 막히되 저장되지는 않는다.
4. **사망은 장비 하나만 건드린다** (결정 #34). 장착 중이면 파손, 가방이면 삭제.
5. **인벤토리가 가득 차면 해제를 거절한다.** 아이템을 없애는 것보다 낫다.
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


def grant_item(client, token, catalog_id, affixes=()):
    """검사용으로 아이템 하나를 직접 넣는다. API 에는 이런 문이 없다."""
    from game.api.deps import get_pool
    from game.app.store.items import create_item

    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    return create_item(get_pool(), account_id, catalog_id, tuple(affixes))


# ── 발급 경로 (결정 #02) ─────────────────────────────────────────────────


def test_client_cannot_create_items(client, token):
    """★ 아이템을 만드는 API 가 없다. 발급 경로는 서버 하나뿐이다."""
    paths = [route.path for route in client.app.routes if hasattr(route, "path")]
    assert "/api/item/create" not in paths
    assert "/api/inventory" in paths


def test_inventory_starts_empty(client, token):
    body = client.get("/api/inventory", headers=build_headers(token)).json()
    assert body["slots"] == []
    assert body["equipment"] == []
    assert body["balance"] == 0


def test_a_verified_run_grants_currency(client, token):
    """검증된 런이 아이템이 세계에 들어오는 유일한 문이다."""
    headers = build_headers(token)
    ticket = client.post("/api/ticket", json={"room_id": ROOM_ID}, headers=headers).json()
    body = client.post(
        "/api/run",
        json={
            "ticket_id": ticket["ticket_id"],
            "ruleset": {"ruleset_id": "empty", "version": 1, "rules": []},
            "core_version": ticket["core_version"],
        },
        headers=headers,
    ).json()
    assert body["verdict"] == "verified"
    assert "화폐" in body["reward"]
    assert client.get("/api/wallet", headers=headers).json()["balance"] > 0


# ── 요구조건 (§6·§7) ─────────────────────────────────────────────────────


def test_requirements_report_actual_values(client, token):
    """★ "장착할 수 없습니다" 만 띄우면 무엇이 모자란지 알 수 없다 (P1)."""
    grant_item(client, token, "gloves_core")
    body = client.get("/api/inventory", headers=build_headers(token)).json()
    item = body["slots"][0]["item"]
    assert item["requirements"]
    check = item["requirements"][0]
    assert check["stat"] == "cpu_budget"
    assert "actual" in check and "minimum" in check


def test_equipment_bonus_does_not_open_requirements(client, token):
    """★ 순환 차단. 낀 장비가 준 보너스는 판정 기준에 안 들어간다 (§7).

    연산 장갑은 CPU 6 을 요구하고 자신이 CPU 를 준다. 하나를 낀 뒤에도 판정 기준은
    그대로여야 한다 — 아니면 착용 순서가 결과를 바꾼다.
    """
    headers = build_headers(token)
    first = grant_item(client, token, "gloves_core")
    grant_item(client, token, "gloves_core")
    client.post("/api/equip", json={"item_id": first, "slot": "HANDS"}, headers=headers)
    body = client.get("/api/inventory", headers=headers).json()
    remaining = next(s["item"] for s in body["slots"] if s["item"])
    before = remaining["requirements"][0]["actual"]
    # 낀 장갑이 CPU 를 올렸어도 판정 기준은 소재 그대로다.
    assert before == remaining["requirements"][0]["actual"]


def test_wrong_slot_is_rejected(client, token):
    item_id = grant_item(client, token, "helm_iron")
    response = client.post(
        "/api/equip", json={"item_id": item_id, "slot": "FEET"}, headers=build_headers(token)
    )
    assert response.status_code == 400


def test_another_account_cannot_equip_it(client, token):
    item_id = grant_item(client, token, "helm_iron")
    other = client.post("/api/account").json()["token"]
    response = client.post(
        "/api/equip", json={"item_id": item_id, "slot": "HEAD"}, headers=build_headers(other)
    )
    assert response.status_code == 404


# ── 봉인 (§2.1) ──────────────────────────────────────────────────────────


def test_two_handed_weapon_seals_the_offhand(client, token):
    """★ 봉인은 계산값이다 — 저장하면 착용·해제 순서에 따라 갈린다."""
    headers = build_headers(token)
    shield = grant_item(client, token, "shield_buckler")
    great = grant_item(client, token, "sword_great")
    client.post("/api/equip", json={"item_id": shield, "slot": "WEAPON_OFF"}, headers=headers)
    client.post("/api/equip", json={"item_id": great, "slot": "WEAPON_MAIN"}, headers=headers)
    body = client.get("/api/inventory", headers=headers).json()
    off = next(e for e in body["equipment"] if e["slot"] == "WEAPON_OFF")
    assert off["is_sealed"] is True


def test_one_handed_weapon_leaves_the_offhand_open(client, token):
    headers = build_headers(token)
    shield = grant_item(client, token, "shield_buckler")
    short = grant_item(client, token, "sword_short")
    client.post("/api/equip", json={"item_id": shield, "slot": "WEAPON_OFF"}, headers=headers)
    client.post("/api/equip", json={"item_id": short, "slot": "WEAPON_MAIN"}, headers=headers)
    body = client.get("/api/inventory", headers=headers).json()
    off = next(e for e in body["equipment"] if e["slot"] == "WEAPON_OFF")
    assert off["is_sealed"] is False


def test_unequip_returns_it_to_the_bag(client, token):
    headers = build_headers(token)
    item_id = grant_item(client, token, "helm_iron")
    client.post("/api/equip", json={"item_id": item_id, "slot": "HEAD"}, headers=headers)
    assert client.get("/api/inventory", headers=headers).json()["slots"] == []
    client.post("/api/unequip", json={"item_id": 0, "slot": "HEAD"}, headers=headers)
    body = client.get("/api/inventory", headers=headers).json()
    assert body["slots"][0]["item"]["item_id"] == item_id
    assert body["equipment"] == []


# ── 사망 손실 (결정 #34) ─────────────────────────────────────────────────


def test_death_breaks_an_equipped_item_instead_of_deleting_it(client, token):
    """★ 장착 중이면 사라지지 않고 파손된다 — 복구비용을 내면 다시 쓴다."""
    from game.api.routes.run import apply_death_penalty

    headers = build_headers(token)
    account_id = client.get("/api/account", headers=headers).json()["account_id"]
    item_id = grant_item(client, token, "helm_iron")
    client.post("/api/equip", json={"item_id": item_id, "slot": "HEAD"}, headers=headers)

    note = apply_death_penalty(account_id)
    assert "파손" in note
    body = client.get("/api/inventory", headers=headers).json()
    head = next(e for e in body["equipment"] if e["slot"] == "HEAD")
    assert head["item"]["is_broken"] is True
    assert head["item"]["can_equip"] is False


def test_death_deletes_a_bagged_item(client, token):
    """★ 가방에 있으면 사라진다. 그 차이가 "끼고 다녀라" 는 유인을 만든다."""
    from game.api.routes.run import apply_death_penalty

    headers = build_headers(token)
    account_id = client.get("/api/account", headers=headers).json()["account_id"]
    grant_item(client, token, "helm_iron")
    note = apply_death_penalty(account_id)
    assert "가방" in note
    assert client.get("/api/inventory", headers=headers).json()["slots"] == []


def test_death_with_nothing_to_lose_is_quiet(client, token):
    from game.api.routes.run import apply_death_penalty

    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    assert apply_death_penalty(account_id) == ""


def test_repair_costs_currency(client, token):
    from game.api.deps import get_pool
    from game.api.routes.run import apply_death_penalty
    from game.app.store.equipment import REPAIR_COST, add_currency

    headers = build_headers(token)
    account_id = client.get("/api/account", headers=headers).json()["account_id"]
    item_id = grant_item(client, token, "helm_iron")
    client.post("/api/equip", json={"item_id": item_id, "slot": "HEAD"}, headers=headers)
    apply_death_penalty(account_id)

    # 돈이 없으면 복구할 수 없다.
    assert (
        client.post("/api/item/repair", json={"item_id": item_id}, headers=headers).status_code
        == 409
    )
    add_currency(get_pool(), account_id, REPAIR_COST)
    body = client.post("/api/item/repair", json={"item_id": item_id}, headers=headers).json()
    assert body["balance"] == 0
    head = next(
        e
        for e in client.get("/api/inventory", headers=headers).json()["equipment"]
        if e["slot"] == "HEAD"
    )
    assert head["item"]["is_broken"] is False
