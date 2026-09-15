"""재주조 — 연 봉인을 활자로 다시 찍는다 (설계/4_아이템 §17, 신설 2026-09-15).

`test_item_unseal.py` 에서 갈라 두었다. 저쪽은 **여는 일**(푼)이고 여기는 **연 것을 다시
찍는 일**(활자)이다. 재화가 다르고 막으려는 것이 다르다.

**여는 것과 다시 찍는 것이 같은 재화면 봉인이 아무것도 막지 않는다.** 푼만 모으면 원하는
값이 나올 때까지 돌릴 수 있기 때문이다 — 열기 전에 모르는 것이 이 기제의 전부다. 활자는
내 둔갑이 남의 장에서 이겨야 들어오므로 그렇게 못 돈다.

여기서 지키는 것은 넷이다.

1. **봉인에서 나온 줄만 바꾼다.** 드롭이 달고 나온 접사까지 바꾸면 활자가 「모든 접사를
   고르는 값」이 되어 드롭의 운이 통째로 사라진다.
2. **칸을 안 늘린다.** 자리에 있는 값을 갈아 끼울 뿐이다 — 이것이 「전투력 천장을 안
   올린다」의 실제 내용이다.
3. **활자를 먼저 뺀다.** 굴린 뒤에 빼면 굴림은 성공하고 차감이 실패하는 창이 생긴다.
4. **모자라면 거절한다.** 음수 활자를 만드는 것보다 거절이 낫다.
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


def build_opened_item(client, token, drop_affixes=()):
    """봉인 한 칸을 연 유물 하나를 만든다.

    Args:
        client: 테스트 클라이언트.
        token: 토큰.
        drop_affixes: 드롭이 달고 나온 접사들. 이것들은 다시 찍을 수 없어야 한다.

    Returns:
        (계정 id, 개체 id, 아이템 id).
    """
    from game.api.deps import get_pool
    from game.app.store.accounts import find_player_entity
    from game.app.store.equipment import add_currency
    from game.app.store.items import create_item
    from game.schemas.item import GRADE_SEALED_SLOTS

    pool = get_pool()
    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    entity_id = find_player_entity(pool, account_id)
    item_id = create_item(
        pool,
        entity_id,
        "helm_iron",
        tuple(drop_affixes),
        None,
        "RELIC",
        GRADE_SEALED_SLOTS["RELIC"],
    )
    add_currency(pool, account_id, 10_000)
    assert (
        client.post(
            "/api/item/unseal", json={"item_id": item_id}, headers=build_headers(token)
        ).status_code
        == 200
    )
    return account_id, entity_id, item_id


def read_item(entity_id, item_id):
    from game.api.deps import get_pool
    from game.app.store.items import find_item

    return find_item(get_pool(), entity_id, item_id)


def test_recasting_replaces_the_line_without_adding_a_slot(client, token):
    """★ 칸을 안 늘린다 — 자리에 있는 값을 갈아 끼울 뿐이다."""
    from game.api.deps import get_pool
    from game.app.store.letters import add_letters, read_letters

    account_id, entity_id, item_id = build_opened_item(client, token)
    add_letters(get_pool(), account_id, 5)
    before = read_item(entity_id, item_id)

    response = client.post(
        "/api/item/recast",
        json={"item_id": item_id, "affix_index": len(before.affixes) - 1},
        headers=build_headers(token),
    )

    assert response.status_code == 200, response.text
    after = read_item(entity_id, item_id)
    assert len(after.affixes) == len(before.affixes), "줄 수가 바뀌었다"
    assert after.sealed_slots == before.sealed_slots, "칸이 늘거나 줄었다"
    assert read_letters(get_pool(), account_id) == 4, "활자가 안 나갔다"


def test_a_drop_affix_is_not_recastable(client, token):
    """★ 봉인에서 나온 줄만 바꾼다.

    드롭이 달고 나온 접사까지 바꾸면 활자가 「모든 접사를 고르는 값」이 되어, 무엇이
    떨어졌는가가 뜻을 잃는다.
    """
    from game.api.deps import get_pool
    from game.app.store.letters import add_letters, read_letters
    from game.schemas.item import Affix

    account_id, _entity_id, item_id = build_opened_item(
        client, token, (Affix(stat="attack", flat=3, label_ko="드롭 옵션"),)
    )
    add_letters(get_pool(), account_id, 5)

    response = client.post(
        "/api/item/recast",
        json={"item_id": item_id, "affix_index": 0},
        headers=build_headers(token),
    )

    assert response.status_code == 409
    assert read_letters(get_pool(), account_id) == 5, "거절했는데 활자가 나갔다"


def test_running_out_of_letters_is_a_refusal(client, token):
    """★ 모자라면 거절한다 — 음수 활자를 만드는 것보다 거절이 낫다."""
    _account_id, entity_id, item_id = build_opened_item(client, token)
    index = len(read_item(entity_id, item_id).affixes) - 1

    response = client.post(
        "/api/item/recast",
        json={"item_id": item_id, "affix_index": index},
        headers=build_headers(token),
    )

    assert response.status_code == 409
    assert "활자" in response.json()["detail"]


def test_letters_go_first(client, token):
    """★ 굴린 뒤에 빼면 굴림은 성공하고 차감이 실패하는 창이 생긴다."""
    import inspect

    from game.api.routes import unseal as module

    source = inspect.getsource(module.create_recast)
    spend = source.index("add_letters(pool, account.account_id, -RECAST_COST)")
    roll = source.index("create_sealed_affix(")
    assert spend < roll, "굴린 뒤에 뺀다 — 공짜 재주조의 창이다"


def test_the_request_carries_no_result(client, token):
    """★ 결과를 받을 자리가 있으면 원하는 값을 적어 보내는 것이 최적이 된다."""
    from game.api.schemas_item import AffixRecastRequest

    assert set(AffixRecastRequest.model_fields) == {"item_id", "affix_index"}
