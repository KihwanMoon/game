"""봉인된 옵션 — 등급이 칸을 주고 화폐가 그것을 연다 (설계/4_아이템 §17).

여기서 지키는 것은 여섯이다.

1. **등급이 칸 수를 정한다.** 최저 등급은 고정 옵션만 갖는다.
2. **서버가 결과를 부여한다.** 클라이언트가 굴리면 마음에 드는 값이 나올 때까지 다시
   굴릴 수 있고, 그러면 봉인이 아무것도 막지 않는다.
3. **열기 전에는 무엇이 들어올지 모른다.** 미리 정해 두면 그 값이 클라이언트로 새어
   나가고, 그 순간 열 이유가 사라진다.
4. **돈을 먼저 뺀다.** 굴린 뒤에 빼면 굴림은 성공하고 차감이 실패하는 창이 생긴다.
5. **뒤 칸이 비싸다.** 같은 값이면 유물의 두 칸이 상급의 한 칸보다 싸게 먹힌다.
6. **칸이 없으면 못 연다.** 돈만 받고 아무것도 안 주는 길이 있으면 안 된다.
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


def build_item(client, token, grade):
    """그 등급의 아이템 하나를 가방에 넣는다."""
    from game.api.deps import get_pool
    from game.app.items.sealed import GRADE_SEALED_SLOTS
    from game.app.store.accounts import find_player_entity
    from game.app.store.items import create_item

    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    entity_id = find_player_entity(get_pool(), account_id)
    item_id = create_item(
        get_pool(), entity_id, "helm_iron", (), None, grade, GRADE_SEALED_SLOTS[grade]
    )
    return account_id, entity_id, item_id


def read_item(entity_id, item_id):
    from game.api.deps import get_pool
    from game.app.store.items import find_item

    return find_item(get_pool(), entity_id, item_id)


def test_the_grade_decides_how_many_slots(client, token):
    """★ 최저 등급은 고정 옵션만 갖는다 — 등급이 오를수록 하나씩 는다."""
    from game.app.items.sealed import GRADE_SEALED_SLOTS

    assert GRADE_SEALED_SLOTS["COMMON"] == 0
    assert GRADE_SEALED_SLOTS["FINE"] == 1
    assert GRADE_SEALED_SLOTS["RELIC"] == 2
    for grade in ("COMMON", "FINE", "RELIC"):
        _account, entity_id, item_id = build_item(client, token, grade)
        assert read_item(entity_id, item_id).sealed_slots == GRADE_SEALED_SLOTS[grade]


def test_unsealing_adds_an_option_the_server_chose(client, token):
    """★ 서버가 부여한다 — 요청에 결과를 받을 자리가 없다."""
    from game.api.deps import get_pool
    from game.app.store.equipment import add_currency

    account_id, entity_id, item_id = build_item(client, token, "RELIC")
    add_currency(get_pool(), account_id, 10_000)
    before = read_item(entity_id, item_id)
    response = client.post(
        "/api/item/unseal", json={"item_id": item_id}, headers=build_headers(token)
    )
    assert response.status_code == 200
    after = read_item(entity_id, item_id)
    assert after.sealed_slots == before.sealed_slots - 1
    assert len(after.affixes) == len(before.affixes) + 1


def test_the_request_carries_no_result(client, token):
    """★ 결과를 받을 자리가 있으면 원하는 값을 적어 보내는 것이 최적이 된다."""
    from game.api.schemas import ItemActionRequest

    assert set(ItemActionRequest.model_fields) == {"item_id"}


def test_money_goes_first(client, token):
    """★ 굴린 뒤에 빼면 굴림은 성공하고 차감이 실패하는 창이 생긴다."""
    import inspect

    from game.api.routes import unseal as module

    source = inspect.getsource(module.create_unseal)
    spend = source.index("add_currency(pool, account.account_id, -cost)")
    roll = source.index("create_sealed_affix")
    assert spend < roll, "굴림이 차감보다 먼저다"


def test_a_later_slot_costs_more(client, token):
    """★ 같은 값이면 유물의 두 칸이 상급의 한 칸보다 싸게 먹힌다."""
    from game.app.items.sealed import compute_unseal_cost

    assert compute_unseal_cost(1) > compute_unseal_cost(0)
    assert compute_unseal_cost(2) > compute_unseal_cost(1)


def test_a_common_item_cannot_be_unsealed(client, token):
    """★ 칸이 없는데 열리면 돈만 받고 아무것도 안 준다."""
    from game.api.deps import get_pool
    from game.app.store.equipment import add_currency

    account_id, _entity_id, item_id = build_item(client, token, "COMMON")
    add_currency(get_pool(), account_id, 10_000)
    response = client.post(
        "/api/item/unseal", json={"item_id": item_id}, headers=build_headers(token)
    )
    assert response.status_code == 409


def test_a_poor_player_keeps_the_seal(client, token):
    """★ 잔액이 모자라면 칸도 안 열리고 돈도 안 빠진다."""
    from game.api.deps import get_pool
    from game.app.store.equipment import read_balance

    account_id, entity_id, item_id = build_item(client, token, "RELIC")
    before = read_balance(get_pool(), account_id)
    response = client.post(
        "/api/item/unseal", json={"item_id": item_id}, headers=build_headers(token)
    )
    assert response.status_code == 409
    assert read_balance(get_pool(), account_id) == before
    assert read_item(entity_id, item_id).sealed_slots == 2


def test_someone_elses_item_cannot_be_unsealed(client, token):
    """★ 남의 아이템을 열 수 있으면 가방이 공용이 된다."""
    from game.api.deps import get_pool
    from game.app.store.equipment import add_currency

    _owner, _entity, item_id = build_item(client, token, "RELIC")
    other = client.post("/api/account").json()["token"]
    other_id = client.get("/api/account", headers=build_headers(other)).json()["account_id"]
    add_currency(get_pool(), other_id, 10_000)
    response = client.post(
        "/api/item/unseal", json={"item_id": item_id}, headers=build_headers(other)
    )
    assert response.status_code == 404


def test_the_store_itself_refuses_an_empty_seal(client, token):
    """★ 라우트 검사만 있으면 다른 부르는 쪽이 생길 때 그 길이 열린다.

    라우트에서 칸 검사를 지워도 검사가 통과했다 — 저장 층이 이중으로 막고 있었기
    때문이다. 실제로 지키는 것은 이쪽이므로 이쪽을 직접 본다.
    """
    from game.api.deps import get_pool
    from game.app.store.items import apply_unseal
    from game.schemas.item import Affix

    _account, entity_id, item_id = build_item(client, token, "COMMON")
    assert apply_unseal(get_pool(), item_id, Affix(stat="attack", flat=1)) is False
    assert read_item(entity_id, item_id).sealed_slots == 0


def test_a_dropped_item_carries_its_seals(client, token):
    """★ 드롭이 칸을 안 심으면 봉인이 영영 안 생긴다.

    드롭 경로를 안 보면 이 배선이 끊겨도 아무도 모른다 — 실제로 끊고 돌려 봤을 때
    검사가 통과했다.
    """
    from types import SimpleNamespace

    from game.api.deps import get_pool
    from game.api.loot_service import create_run_drops
    from game.app.items.sealed import GRADE_SEALED_SLOTS
    from game.app.store.accounts import find_player_entity
    from game.app.store.drops import save_monster_drop

    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    entity_id = find_player_entity(get_pool(), account_id)
    # **상급이 확실히 나오게 세운다.** 기본 표는 거의 다 보통 등급(칸 0)이라, 배선을
    # 끊어도 "칸 0" 이 맞아떨어져 검사가 통과한다 — 실제로 그렇게 통과했다.
    kind = f"probe_seal_{account_id}"
    source_id = save_monster_drop(get_pool(), kind, "FINE", "helm_iron", 1)
    with get_pool().connection() as connection:
        connection.execute(
            "UPDATE drop_grade_weight SET weight = 1000000 WHERE source_id = %s AND grade = 'FINE'",
            (source_id,),
        )
    verified = SimpleNamespace(summary=SimpleNamespace(defeated_kinds=(kind,) * 5))
    create_run_drops(account_id, None, verified, 1, "no-such-ticket")
    with get_pool().connection() as connection:
        rows = connection.execute(
            "SELECT grade, sealed_slots FROM item_instance WHERE owner_entity_id = %s",
            (entity_id,),
        ).fetchall()
    assert rows, "상급만 나오게 세웠는데 하나도 안 나왔다"
    assert any(str(grade) == "FINE" for grade, _slots in rows), "상급이 하나도 안 나왔다"
    for grade, slots in rows:
        assert int(slots) == GRADE_SEALED_SLOTS.get(str(grade), 0), f"{grade} 의 칸 수가 다르다"
