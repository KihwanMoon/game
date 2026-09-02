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

    소모품을 다루는 쪽은 스택만 본다. 인스턴스로 넣으면 물약을 여섯 개 들고도 칸에
    끼울 후보로 안 뜨고, 사람 눈에는 「가방에 있는데 못 쓴다」로 보인다 — 실제로 그렇게
    신고됐다.
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


def test_a_stacked_consumable_can_be_loaded_into_a_slot(client, token):
    """★ 주운 것이 칸에 끼울 후보로 떠야 「주운 것을 들고 간다」가 성립한다.

    **전투에 실리는 것은 가방이 아니라 칸이다** (§5). 예전에는 가방을 통째로 세서
    들고 갔고, 그래서 「몇 개를 들고 갈까」가 선택이 아니었다.
    """
    from game.api.deps import get_pool
    from game.api.loot_service import create_issued_item
    from game.app.store.accounts import find_player_entity

    headers = build_headers(token)
    account_id = client.get("/api/account", headers=headers).json()["account_id"]
    entity_id = find_player_entity(get_pool(), account_id)
    create_issued_item(
        get_pool(), entity_id, "potion_heal", {"grade": "COMMON", "submission_id": None}
    )
    offered = client.get("/api/consumables", headers=headers).json()["options"]
    assert [option["catalog_id"] for option in offered] == ["potion_heal"]
    assert offered[0]["use_tag"] == "POTION"
    assert offered[0]["charges"] > 1, "카탈로그의 칸 용량이 안 실렸다"
