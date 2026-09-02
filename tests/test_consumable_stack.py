"""가방의 소모품 (설계/4_아이템 §5).

**소모품은 인스턴스가 아니라 스택이다.** 가방을 세는 쪽(`count_consumables`)이 스택만
보므로, 인스턴스로 넣으면 물약을 여섯 개 들고도 전투에는 기본 지급 두 개만 나간다 —
「가방에 있는 소모품을 쓰는 게 잘 안 된다」의 정체다.

`test_item_drops.py` 에서 갈라 나왔다. 저쪽은 **무엇이 나오는가**이고 여기는 **나온 것이
가방에 어떻게 들어가는가**다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)


@pytest.fixture
def client():
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as running:
        yield running


@pytest.fixture
def token(client):
    return client.post("/api/account").json()["token"]


def build_headers(token):
    return {"X-Game-Token": token}


def test_a_dropped_consumable_stacks_instead_of_taking_a_slot(client, token):
    """★ **소모품이 인스턴스로 들어가면 세는 쪽이 못 본다.**

    가방을 세는 쪽(`count_consumables`)은 스택만 본다. 인스턴스로 넣으면 물약을 여섯 개
    들고도 전투에는 기본 지급 두 개만 나가고, 사람 눈에는 「가방에 있는데 못 쓴다」로
    보인다 — 실제로 그렇게 신고됐다.
    """
    from game.api.deps import get_pool
    from game.api.loot_service import create_issued_item
    from game.app.store.accounts import find_player_entity
    from game.app.store.items import list_inventory

    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    entity_id = find_player_entity(get_pool(), account_id)
    for _step in range(3):
        create_issued_item(
            get_pool(), entity_id, "potion_heal", {"grade": "COMMON", "submission_id": None}
        )
    bag = list_inventory(get_pool(), entity_id)
    stacked = [entry for entry in bag if entry.stack_catalog_id == "potion_heal"]
    assert len(stacked) == 1, "칸마다 하나씩 흩어졌다"
    assert stacked[0].stack_count == 3
    assert [entry for entry in bag if entry.item is not None] == []


def test_a_stacked_consumable_reaches_the_battle(client, token):
    """★ 쌓아 둔 것이 전투 입력에 실려야 「들고 있는 것을 쓴다」가 성립한다."""
    from game.api.deps import get_item_catalog, get_pool
    from game.api.loadout_service import count_consumables
    from game.api.loot_service import create_issued_item
    from game.app.store.accounts import find_player_entity

    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    entity_id = find_player_entity(get_pool(), account_id)
    create_issued_item(
        get_pool(), entity_id, "potion_heal", {"grade": "COMMON", "submission_id": None}
    )
    create_issued_item(
        get_pool(), entity_id, "scroll_shield", {"grade": "COMMON", "submission_id": None}
    )
    counted = count_consumables(get_pool(), entity_id, get_item_catalog())
    assert counted.get("POTION") == 1
    assert counted.get("SCROLL") == 1
