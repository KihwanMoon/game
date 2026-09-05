"""사람이 봇에게 아이템을 넘긴다 — 한 방향 (T11, 결정 #02·#07).

**돌아오는 길이 없어야 성립한다.** 봇에게 간 물건이 사람에게 돌아올 수 있으면 이것은
「사람이 봇에게 준다」가 아니라 「봇을 거쳐 사람끼리 주고받는다」가 되고, 귀속으로 막아
둔 자전거래가 그 길로 되살아난다.

아이템이 봇을 거쳐 사람에게 갈 수 있는 길은 넷이고 셋은 이미 막혀 있다 — 도플갱어 드롭·
전리품 강탈·되찾기. 넷째가 경매이며, 그것은 **귀속**이 막는다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

fastapi_testclient = pytest.importorskip("fastapi.testclient")

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)


@pytest.fixture
def client():
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as running:
        yield running


def build_headers(token):
    return {"X-Game-Token": token}


def build_admin(client):
    """관리자 토큰 하나. **아이템을 주는 쪽이 이 계정이다.**

    Args:
        client: 테스트 클라이언트.

    Returns:
        (토큰, 계정 id).
    """
    from game.api.deps import get_pool

    token = client.post("/api/account").json()["token"]
    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    with get_pool().connection() as connection:
        connection.execute("UPDATE account SET admin_role = 'owner' WHERE id = %s", (account_id,))
    return token, account_id


def build_bot(client):
    """봇 하나를 세운다.

    Args:
        client: 테스트 클라이언트.

    Returns:
        봇의 계정 id.
    """
    from game.api.deps import get_pool
    from game.app.store.bots import create_bot

    token = client.post("/api/account").json()["token"]
    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    create_bot(get_pool(), account_id, "받는봇", "g0_kite", 720, 60)
    return account_id


def build_item(account_id):
    """그 계정의 가방에 아이템 하나를 넣는다.

    Args:
        account_id: 받을 계정.

    Returns:
        아이템 id.
    """
    from game.api.deps import get_item_catalog, get_pool
    from game.app.store.accounts import find_player_entity
    from game.app.store.inventory_slots import find_empty_slot

    pool = get_pool()
    entity_id = find_player_entity(pool, account_id)
    index = find_empty_slot(pool, entity_id)
    with pool.connection() as connection:
        # **서버가 든 카탈로그에서 고른다.** DB 표에는 다른 검사가 남긴 id 가 있는데
        # 그것들은 메모리 카탈로그에 없어서 가방 조회가 그 줄에서 터진다.
        row = connection.execute(
            "INSERT INTO item_instance (catalog_id, owner_entity_id) VALUES (%s, %s) RETURNING id",
            (sorted(get_item_catalog())[0], entity_id),
        ).fetchone()
        connection.execute(
            "INSERT INTO inventory_slot (entity_id, slot_index, item_id) VALUES (%s, %s, %s)",
            (entity_id, index, int(row[0])),
        )
    return int(row[0])


def read_owner(item_id):
    """지금 그 아이템을 누가 들고 있는가.

    Args:
        item_id: 볼 아이템.

    Returns:
        (소유 개체 id, 귀속 여부).
    """
    from game.api.deps import get_pool

    with get_pool().connection() as connection:
        row = connection.execute(
            "SELECT owner_entity_id, is_bound FROM item_instance WHERE id = %s", (item_id,)
        ).fetchone()
    return int(row[0]), bool(row[1])


def test_a_gift_reaches_the_bot_and_binds(client):
    """★ 넘어가고, 도착하는 순간 귀속된다.

    귀속이 「돌아오지 않는다」를 만든다 — 귀속된 물건은 경매에 못 걸린다 (결정 #07).
    """
    from game.api.deps import get_pool
    from game.app.store.accounts import find_player_entity

    token, admin_id = build_admin(client)
    bot_id = build_bot(client)
    item_id = build_item(admin_id)
    response = client.post(
        "/api/admin/bot/gift",
        json={"account_id": bot_id, "item_id": item_id},
        headers=build_headers(token),
    )
    assert response.status_code == 200
    owner, is_bound = read_owner(item_id)
    assert owner == find_player_entity(get_pool(), bot_id)
    assert is_bound is True


def test_a_bound_gift_cannot_be_listed_back(client):
    """★ **돌아오는 길이 실제로 막혀 있다.**

    귀속을 박는 것만으로는 부족하고, 그것이 경매를 실제로 거절해야 한다.
    """
    from game.api.deps import get_pool
    from game.app.store.accounts import find_player_entity
    from game.app.store.auction import create_listing

    token, admin_id = build_admin(client)
    bot_id = build_bot(client)
    item_id = build_item(admin_id)
    client.post(
        "/api/admin/bot/gift",
        json={"account_id": bot_id, "item_id": item_id},
        headers=build_headers(token),
    )
    pool = get_pool()
    with pytest.raises(ValueError, match="귀속"):
        create_listing(pool, bot_id, find_player_entity(pool, bot_id), item_id, 10)


def test_a_person_cannot_receive_a_gift(client):
    """★ **봇에게만 준다.**

    사람에게 줄 수 있으면 이것은 관리자가 중개하는 사람↔사람 이관이고, 귀속으로 막아 둔
    자전거래가 그 길로 되살아난다.
    """
    token, admin_id = build_admin(client)
    person = client.post("/api/account").json()["token"]
    person_id = client.get("/api/account", headers=build_headers(person)).json()["account_id"]
    item_id = build_item(admin_id)
    response = client.post(
        "/api/admin/bot/gift",
        json={"account_id": person_id, "item_id": item_id},
        headers=build_headers(token),
    )
    assert response.status_code == 409
    assert "봇에게만" in response.json()["detail"]


def test_an_item_i_do_not_have_is_refused(client):
    """★ 남의 물건을 넘길 수 없다 — 관리자라도 원장을 손으로 옮기지 않는다."""
    token, _admin_id = build_admin(client)
    other = client.post("/api/account").json()["token"]
    other_id = client.get("/api/account", headers=build_headers(other)).json()["account_id"]
    bot_id = build_bot(client)
    item_id = build_item(other_id)
    response = client.post(
        "/api/admin/bot/gift",
        json={"account_id": bot_id, "item_id": item_id},
        headers=build_headers(token),
    )
    assert response.status_code == 409


def test_a_plain_account_cannot_give(client):
    """★ 관리자만 준다. 아니면 404 — 경로의 존재도 알리지 않는다."""
    token = client.post("/api/account").json()["token"]
    response = client.post(
        "/api/admin/bot/gift",
        json={"account_id": 1, "item_id": 1},
        headers=build_headers(token),
    )
    assert response.status_code == 404


def test_the_gift_is_recorded(client):
    """★ 개입은 남는다 — 「이 봇이 이걸 어디서 났지」를 나중에 답할 수 있어야 한다."""
    token, admin_id = build_admin(client)
    bot_id = build_bot(client)
    item_id = build_item(admin_id)
    client.post(
        "/api/admin/bot/gift",
        json={"account_id": bot_id, "item_id": item_id},
        headers=build_headers(token),
    )
    body = client.get("/api/admin/overview", headers=build_headers(token)).json()
    assert any(item["action"] == "bot.gift" for item in body["recent_actions"])


def test_there_is_no_route_that_takes_from_a_bot(client):
    """★ **되받는 경로가 없다.**

    주는 길만 있고 받는 길이 없어야 한 방향이다. 다음 사람이 대칭을 맞추려고 반대편을
    만드는 것을 여기서 막는다 — 그 순간 봇이 파밍 도구가 된다 (T11).
    """
    from game.api.main import create_app

    paths = [route.path for route in create_app().routes]
    assert not [path for path in paths if "bot" in path and ("take" in path or "claim" in path)]


def test_the_bot_bag_is_readable(client):
    """★ 봇이 무엇을 가졌는지 관리 화면이 본다.

    id 를 손으로 적게 하면 그 화면은 안 쓰인다 — 무엇이 있는지 모르는 채로 숫자를 적을
    수는 없다.
    """
    token, admin_id = build_admin(client)
    bot_id = build_bot(client)
    item_id = build_item(admin_id)
    client.post(
        "/api/admin/bot/gift",
        json={"account_id": bot_id, "item_id": item_id},
        headers=build_headers(token),
    )
    body = client.get(
        "/api/admin/bot/bag", params={"account_id": bot_id}, headers=build_headers(token)
    ).json()
    held = [slot["item"]["item_id"] for slot in body["slots"] if slot["item"] is not None]
    assert item_id in held


def test_only_a_bot_bag_can_be_opened(client):
    """★ **봇만 본다.**

    아무 계정이나 열리면 이것은 관리자가 남의 가방을 들여다보는 길이 된다 — 봇을
    관리하려고 연 창이 그것이어서는 안 된다.
    """
    token, _admin_id = build_admin(client)
    person = client.post("/api/account").json()["token"]
    person_id = client.get("/api/account", headers=build_headers(person)).json()["account_id"]
    response = client.get(
        "/api/admin/bot/bag", params={"account_id": person_id}, headers=build_headers(token)
    )
    assert response.status_code == 404


def test_a_plain_account_cannot_open_a_bot_bag(client):
    """관리자가 아니면 404 — 경로의 존재도 알리지 않는다."""
    token = client.post("/api/account").json()["token"]
    response = client.get(
        "/api/admin/bot/bag", params={"account_id": 1}, headers=build_headers(token)
    )
    assert response.status_code == 404
