"""되찾기 — 빼앗긴 것을 잡아서 돌려받는다 (`설계/6_몬스터` §5, M1).

`test_api_monsters.py` 에서 갈라 둔 이유는 책임이 다르기 때문이다 — 저쪽은 "몬스터가
어떻게 크고 무엇을 가져가는가" 이고, 이쪽은 "그것을 어떻게 돌려받는가" 다.

여기서 지키는 것은 셋이다.

1. **잡으면 돌려받는다.** 도감이 "내 아이템을 들고 있다" 고 말해 놓고 잡아도 못
   돌려받으면, World Loop 의 동기가 화면에만 있고 세계에는 없다.
2. **내 것만 돌려받는다** (M1). 처치 보상을 "그 몬스터가 들고 있던 것 중 자기 것" 으로
   한정하는 것이 동시 처치의 보상 복제를 막는 방식이다.
3. **되찾은 것은 귀속된다.** 사본이라 총량이 이미 한 번 늘었고, 그것이 경매로 흘러들면
   사망이 화폐 발행이 된다 (결정 #07·#34).
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

fastapi_testclient = pytest.importorskip("fastapi.testclient")

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)

# corridor 의 첫 배치. 방 배치가 `{kind}_{index}` 로 붙인다.
SLOT = "goblin_rusher_0"


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


@pytest.fixture
def monster(client):
    """층 1 에 지속 엘리트를 하나 놓는다. 이미 있으면 그것을 쓴다."""
    from game.api.deps import get_pool
    from game.app.monsters.tiers import MonsterTier
    from game.app.store.monsters import create_monster, list_monsters

    pool = get_pool()
    create_monster(pool, "goblin_rusher", MonsterTier.ELITE, 1, SLOT)
    return next(item for item in list_monsters(pool, 1) if item.entity_slot == SLOT)


def build_taken_item(client, token, monster, catalog_id="helm_iron"):
    """내 아이템 하나를 몬스터에게 빼앗긴 상태를 만든다.

    Args:
        client: 테스트 클라이언트.
        token: 기기 토큰.
        monster: 가져갈 몬스터.
        catalog_id: 빼앗길 아이템.

    Returns:
        (계정 id, 개체 id).
    """
    from game.api.deps import get_pool
    from game.api.monster_service import apply_trophy_transfer
    from game.app.store.accounts import find_player_entity
    from game.app.store.items import create_item

    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    entity_id = find_player_entity(get_pool(), account_id)
    create_item(get_pool(), entity_id, catalog_id, ())
    apply_trophy_transfer(account_id, monster.record_id)
    return account_id, entity_id


def test_defeating_it_takes_my_item_back(client, token, monster):
    """★ 잡아도 못 돌려받으면 도감의 「내 것을 들고 있다」 가 빈말이 된다 (§5)."""
    from game.api.deps import get_pool
    from game.app.store.items import list_inventory
    from game.app.store.trophies import apply_recovery, list_trophies

    account_id, entity_id = build_taken_item(client, token, monster)
    taken = apply_recovery(get_pool(), monster.record_id, account_id, entity_id)
    assert "helm_iron" in taken
    # 몬스터의 손에서 없어지고 내 가방에 들어와야 한다. 한쪽만 맞으면 복제거나 증발이다.
    # (같은 개체가 다른 계정의 것도 들고 있으므로 **내 것만** 본다.)
    assert not [
        item
        for item in list_trophies(get_pool(), monster.record_id)
        if item["taken_from"] == account_id
    ]
    bag = list_inventory(get_pool(), entity_id)
    assert any(entry.item is not None and entry.item.catalog_id == "helm_iron" for entry in bag)


def test_a_recovered_item_is_bound(client, token, monster):
    """★ 사본이라 총량이 이미 늘었다. 경매로 흘러들면 사망이 화폐 발행이 된다."""
    from game.api.deps import get_pool
    from game.app.store.items import list_inventory
    from game.app.store.trophies import apply_recovery

    account_id, entity_id = build_taken_item(client, token, monster)
    apply_recovery(get_pool(), monster.record_id, account_id, entity_id)
    recovered = next(
        entry.item
        for entry in list_inventory(get_pool(), entity_id)
        if entry.item is not None and entry.item.is_recovered
    )
    assert recovered.is_bound


def test_i_cannot_take_someone_elses_item(client, token, monster):
    """★ "그 몬스터가 들고 있던 것 중 자기 것" 이 동시 처치의 보상 복제를 막는다 (M1)."""
    from game.api.deps import get_pool
    from game.app.store.accounts import find_player_entity
    from game.app.store.trophies import apply_recovery, list_trophies

    account_id, _ = build_taken_item(client, token, monster)
    other_token = client.post("/api/account").json()["token"]
    other_id = client.get("/api/account", headers=build_headers(other_token)).json()["account_id"]
    other_entity = find_player_entity(get_pool(), other_id)
    assert apply_recovery(get_pool(), monster.record_id, other_id, other_entity) == ()
    # 남의 것은 그 자리에 그대로 남아 있어야 한다.
    assert any(
        item["taken_from"] == account_id for item in list_trophies(get_pool(), monster.record_id)
    )
