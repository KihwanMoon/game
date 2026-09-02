"""소모품 칸 — 들고 갈 것을 한도 안에서 고른다 (설계/4_아이템 §5).

**예전에는 가방에 든 것을 전부 세서 들고 갔다.** 물약을 많이 주우면 많이 들고 갔고,
거기에 `balance.player.potions` 두 개가 매 판 공짜로 얹혔다. 그래서 「몇 개를 들고
갈까」가 선택이 아니었다 — 주운 만큼이 답이었다.

여기서 지키는 것은 여섯이다.

1. **새 계정이 예전과 같은 손으로 시작한다.** 빈 물약 칸 둘이 옛 기본 지급 둘이다.
2. **끼우면 늘어나고, 공짜분은 그 칸에서 사라진다.** 안 그러면 끼울수록 공짜가 붙는다.
3. **칸과 쓰임새가 맞아야 들어간다.**
4. **공짜분부터 쓴 것으로 친다.** 아니면 한 개 쓴 판에서 산 충전이 날아간다.
5. **깎는 것은 재시뮬이 남긴 수에서 나온다.** 클라이언트 보고를 안 받는다 (T9).
6. **런 중에는 못 채운다.** 로드아웃은 얼려졌는데 정산은 지금 충전에서 깎는다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV
from game.schemas.consumable import (
    FREE_CHARGES,
    check_slot_fit,
    resolve_refill_cost,
    resolve_sell_price,
)


def build_slot(use_tag="POTION", slot_index=0, catalog_id=None, charges=0):
    """검사용 칸 하나를 만든다.

    Args:
        use_tag: 쓰임새.
        slot_index: 칸 번호.
        catalog_id: 끼운 소모품. None 이면 빈 칸이다.
        charges: 남은 충전.

    Returns:
        칸 하나.
    """
    from game.app.store.consumables import ConsumableSlot

    return ConsumableSlot(
        use_tag=use_tag, slot_index=slot_index, catalog_id=catalog_id, charges=charges
    )


def test_an_untouched_account_carries_what_it_used_to():
    """★ 기본 지급을 없앴는데 빈 칸이 안 채우면, 모두가 물약 없이 시작한다.

    옛 `balance.player.potions` 는 2 였다. 빈 물약 칸이 둘이므로 그대로여야 한다.
    """
    from game.app.store.consumables import count_slot_charges
    from game.schemas.consumable import resolve_slot_count

    empty = (build_slot("POTION", 0), build_slot("POTION", 1), build_slot("SCROLL", 0))
    counted = count_slot_charges(empty)
    assert counted["POTION"] == resolve_slot_count("POTION") * FREE_CHARGES == 2


def test_a_loaded_slot_replaces_its_free_charge():
    """★ 끼운 칸에도 공짜분이 붙으면, 채울수록 공짜가 따라 늘어난다."""
    from game.app.store.consumables import count_slot_charges

    slots = (build_slot("POTION", 0, "potion_heal", 2), build_slot("POTION", 1))
    # 끼운 칸 2 + 빈 칸 1 = 3. 4 가 나오면 공짜분이 얹힌 것이다.
    assert count_slot_charges(slots)["POTION"] == 3


def test_an_empty_kind_is_not_carried():
    """★ 0개인 종류를 담으면 티켓이 쓸데없이 길어진다."""
    from game.app.store.consumables import count_slot_charges

    assert "SCROLL" not in count_slot_charges((build_slot("SCROLL", 0, "scroll_shield", 0),))


def test_a_scroll_never_fits_a_potion_slot():
    """★ 칸과 쓰임새가 안 맞으면 못 넣는다 — 넣으면 `USE_ITEM[POTION]` 이 주문서를 마신다."""
    assert check_slot_fit("SCROLL", "POTION") is False
    assert check_slot_fit("POTION", "POTION") is True


def test_a_grade_costs_more_to_refill():
    """★ 등급이 값을 안 가르면 「무엇을 끼울까」가 공짜 선택이 된다."""
    assert resolve_refill_cost("RELIC", 1) > resolve_refill_cost("FINE", 1)
    assert resolve_refill_cost("FINE", 1) > resolve_refill_cost("COMMON", 1)
    # 채울 것이 없으면 값도 없다.
    assert resolve_refill_cost("RELIC", 0) == 0


def test_selling_never_pays_for_a_refill():
    """★ 판 값으로 같은 것을 다시 채울 수 있으면 「끼운다」와 「판다」가 같은 선택이 된다."""
    for grade in ("COMMON", "FINE", "RELIC"):
        assert resolve_sell_price(grade, 3) < resolve_refill_cost(grade, 3)


pytestmark_db = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)


@pytest.fixture
def client():
    """서버 하나."""
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as running:
        yield running


@pytest.fixture
def token(client):
    """새 계정의 토큰."""
    return client.post("/api/account").json()["token"]


def build_headers(token):
    """토큰을 헤더로 만든다.

    Args:
        token: 계정 토큰.

    Returns:
        요청 헤더.
    """
    return {"X-Game-Token": token}


@pytestmark_db
def test_a_new_account_sees_three_empty_slots(client, token):
    """★ 칸이 안 보이면 물약을 끼울 자리가 어디에도 없다.

    줄을 미리 안 깔았으므로, 읽는 쪽이 빈 칸을 만들어 줘야 한다.
    """
    body = client.get("/api/consumables", headers=build_headers(token)).json()
    slots = body["slots"]
    assert [(s["use_tag"], s["slot_index"]) for s in slots] == [
        ("POTION", 0),
        ("POTION", 1),
        ("SCROLL", 0),
    ]
    assert all(s["catalog_id"] is None for s in slots)
    assert body["free_charges"] == FREE_CHARGES


@pytestmark_db
def test_the_ticket_carries_the_free_charges(client, token):
    """★ 아무것도 안 끼운 계정이 빈손으로 나가면, 예전보다 나빠진 것이다."""
    from game.schemas.loadout import parse_loadout

    issued = client.post(
        "/api/ticket", json={"room_id": "open_field"}, headers=build_headers(token)
    ).json()
    carried = dict(parse_loadout(issued["loadout"]).consumables)
    assert carried["POTION"] == 2
    assert carried["SCROLL"] == 1


@pytestmark_db
def test_a_refill_is_allowed_while_a_run_is_open(client, token):
    """★ **런 중 잠금이 이 게임의 고리를 막았다.**

    하강은 서른 방이고 방 사이에서 규칙을 고치는 것이 핵심인데(GDD §2.2), 그 내내 칸이
    잠겼다. 잠근 이유는 「낸 돈이 정산에서 사라진다」였고, 그것은 티켓이 이미 깎은 충전을
    기억하는 것으로 없앴다 — 잠그는 대신 원인을 고친다.

    지금 채운 것이 **이번 런에 실리지는 않는다.** 로드아웃은 얼려져 있고 그것이 T2·T9 가
    서 있는 자리다. 화면은 그 사실을 말하되 막지는 않는다.
    """
    from game.api.deps import get_pool
    from game.app.store.accounts import find_player_entity
    from game.app.store.equipment import add_currency

    headers = build_headers(token)
    load_potion(client, token, slot_index=0)
    account_id = client.get("/api/account", headers=headers).json()["account_id"]
    pool = get_pool()
    entity_id = find_player_entity(pool, account_id)
    add_currency(pool, account_id, 1000)
    # 한 모금 마신 셈으로 두고, 런을 연 뒤 채워 본다.
    from game.app.store.consumables import apply_slot_fill

    apply_slot_fill(pool, entity_id, "POTION", 0, 1)
    client.post("/api/ticket", json={"room_id": "open_field"}, headers=headers)
    body = client.get("/api/consumables", headers=headers).json()
    assert body["is_run_open"], "런이 열렸다는 사실은 여전히 말해야 한다"
    filled = client.post(
        "/api/consumable/refill", json={"use_tag": "POTION", "slot_index": 0}, headers=headers
    )
    assert filled.status_code == 200, filled.text


def load_potion(client, token, catalog_id="potion_heal", use_tag="POTION", slot_index=0):
    """가방에 하나 넣고 칸에 끼운다.

    Args:
        client: 서버.
        token: 계정 토큰.
        catalog_id: 끼울 소모품.
        use_tag: 칸의 쓰임새.
        slot_index: 칸 번호.

    Returns:
        끼운 뒤의 응답 본문.
    """
    from game.api.deps import get_item_catalog, get_pool
    from game.app.store.accounts import find_player_entity
    from game.app.store.inventory_slots import apply_stack_grant

    headers = build_headers(token)
    account_id = client.get("/api/account", headers=headers).json()["account_id"]
    pool = get_pool()
    entity_id = find_player_entity(pool, account_id)
    entry = get_item_catalog()[catalog_id]
    apply_stack_grant(pool, entity_id, catalog_id, max(1, entry.stack_max))
    return client.post(
        "/api/consumable/load",
        json={"use_tag": use_tag, "slot_index": slot_index, "catalog_id": catalog_id},
        headers=headers,
    ).json()


@pytestmark_db
def test_loading_a_slot_takes_one_from_the_bag(client, token):
    """★ 가방에서 안 빼면 물약 하나로 칸을 무한히 채울 수 있다."""
    body = load_potion(client, token)
    loaded = [s for s in body["slots"] if s["catalog_id"] == "potion_heal"]
    assert len(loaded) == 1
    assert loaded[0]["charges"] == loaded[0]["charge_max"] > 0
    # 하나뿐이던 것을 끼웠으니 후보에서 사라진다.
    assert not [o for o in body["options"] if o["catalog_id"] == "potion_heal"]


@pytestmark_db
def test_a_slot_refuses_the_wrong_kind(client, token):
    """★ 주문서 칸에 물약이 들어가면 `USE_ITEM[SCROLL]` 이 물약을 쓴다."""
    from game.api.deps import get_pool
    from game.app.store.accounts import find_player_entity
    from game.app.store.inventory_slots import apply_stack_grant

    headers = build_headers(token)
    account_id = client.get("/api/account", headers=headers).json()["account_id"]
    pool = get_pool()
    apply_stack_grant(pool, find_player_entity(pool, account_id), "potion_heal", 9)
    refused = client.post(
        "/api/consumable/load",
        json={"use_tag": "SCROLL", "slot_index": 0, "catalog_id": "potion_heal"},
        headers=headers,
    )
    assert refused.status_code == 409


@pytestmark_db
def test_the_free_charge_is_spent_first(client, token):
    """★ 산 충전부터 깎으면, 한 개 쓴 판에서 낸 돈이 사라진다.

    물약 칸 둘 중 하나를 채우면 「끼운 칸의 충전 + 빈 칸의 공짜 1」이다. 한 개만 쓴
    판에서는 공짜분이 나간 것으로 봐야 한다.

    **셈은 정산이 한다.** 저장 층(`apply_slot_spend`)은 시키는 만큼 깎기만 한다 — 거기서
    공짜분을 빼면 층마다 정산이 돌 때 공짜 충전이 새로 생긴다.
    """
    from game.api.deps import get_pool
    from game.api.floor_service import apply_charge_spend
    from game.app.services.verify_run import VERDICT_VERIFIED, VerifiedRun
    from game.app.store.accounts import find_player_entity
    from game.app.store.consumables import list_consumable_slots
    from game.app.store.tickets import find_open_ticket
    from game.schemas.loadout import parse_loadout

    load_potion(client, token, slot_index=0)
    headers = build_headers(token)
    account_id = client.get("/api/account", headers=headers).json()["account_id"]
    pool = get_pool()
    entity_id = find_player_entity(pool, account_id)
    issued = client.post("/api/ticket", json={"room_id": "open_field"}, headers=headers).json()
    ticket = find_open_ticket(pool, issued["ticket_id"], account_id)
    assert ticket is not None
    carried = dict(parse_loadout(ticket.loadout).consumables)["POTION"]

    def read_charges():
        """끼운 칸에 남은 충전.

        Returns:
            충전 수.
        """
        return [s for s in list_consumable_slots(pool, entity_id) if s.catalog_id][0].charges

    before = read_charges()
    apply_charge_spend(
        account_id,
        ticket,
        VerifiedRun(
            outcome="PLAYER_WIN",
            ticks=1,
            player_hp=1,
            verdict=VERDICT_VERIFIED,
            remaining_consumables=(("POTION", carried - 1),),
        ),
    )
    assert read_charges() == before, "공짜분보다 적게 썼는데 산 충전이 깎였다"


@pytestmark_db
def test_selling_a_spare_pays_out(client, token):
    """★ 안 팔리면 이미 끼운 종류가 또 나올 때 가방만 찬다 — 드롭이 뜻을 잃는다."""
    from game.api.deps import get_pool
    from game.app.store.accounts import find_player_entity
    from game.app.store.inventory_slots import apply_stack_grant

    headers = build_headers(token)
    account_id = client.get("/api/account", headers=headers).json()["account_id"]
    pool = get_pool()
    apply_stack_grant(pool, find_player_entity(pool, account_id), "potion_heal", 9)
    before = client.get("/api/consumables", headers=headers).json()["balance"]
    body = client.post(
        "/api/consumable/sell", json={"catalog_id": "potion_heal", "count": 1}, headers=headers
    ).json()
    assert body["balance"] > before
    assert not [o for o in body["options"] if o["catalog_id"] == "potion_heal"]


@pytestmark_db
def test_clearing_a_full_slot_returns_the_item(client, token):
    """★ **끼웠다 뺀 것만으로 아이템이 사라졌다** — 실제로 그렇게 신고됐다.

    끼우기는 가방에서 하나를 빼는 조작이므로, 아무것도 안 쓴 채 빼면 그 하나가
    돌아와야 한다.
    """
    headers = build_headers(token)
    load_potion(client, token, slot_index=0)
    body = client.post(
        "/api/consumable/clear",
        json={"use_tag": "POTION", "slot_index": 0},
        headers=headers,
    ).json()
    assert all(s["catalog_id"] is None for s in body["slots"] if s["use_tag"] == "POTION")
    back = [o for o in body["options"] if o["catalog_id"] == "potion_heal"]
    assert back and back[0]["stock"] == 1, "가방으로 안 돌아왔다"


@pytestmark_db
def test_clearing_a_used_slot_returns_nothing(client, token):
    """★ 쓴 칸까지 돌려주면 「뺐다 다시 끼우기」가 가득 찬 새 것이 된다 — 공짜 보충이다."""
    from game.api.deps import get_pool
    from game.app.store.accounts import find_player_entity
    from game.app.store.consumables import apply_slot_fill

    headers = build_headers(token)
    load_potion(client, token, slot_index=0)
    account_id = client.get("/api/account", headers=headers).json()["account_id"]
    apply_slot_fill(get_pool(), find_player_entity(get_pool(), account_id), "POTION", 0, 1)
    body = client.post(
        "/api/consumable/clear",
        json={"use_tag": "POTION", "slot_index": 0},
        headers=headers,
    ).json()
    assert not [o for o in body["options"] if o["catalog_id"] == "potion_heal"]
