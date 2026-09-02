"""충전을 깎는 셈 (설계/4_아이템 §5).

`test_consumable_slots.py` 에서 갈라 나왔다. 저쪽은 **칸이 무엇인가**를 보고 여기는
**정산이 얼마를 깎는가**를 본다 — 파일이 400줄 상한을 넘은 것이 계기였지만, 가르는 선은
책임이다 (§4).

깎는 셈에는 함정이 둘 있고 둘 다 조용하다.

* **층마다 처음부터 다시 도므로 「쓴 수」는 누적이다.** 이미 깎은 만큼을 안 빼면 3층을
  청구할 때 1·2층에서 쓴 것이 또 깎인다.
* **공짜분도 누적에서 한 번만 뺀다.** 정산마다 빼면 층을 깰 때마다 공짜 충전이 새로
  생긴다 — 실제로 그렇게 돌았다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

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
def test_a_settlement_spends_what_the_resim_used(client, token):
    """★ 정산이 안 깎으면 물약은 무한이다 — 한도도 보충비도 뜻을 잃는다.

    쓴 수는 **티켓이 실은 수 − 재시뮬이 남긴 수**로 나온다. 클라이언트가 「세 개 썼다」고
    보고할 자리를 만들지 않는다 (T9).

    빈 물약 칸 하나가 공짜 1을 주므로, 그것을 넘겨 쓴 만큼만 끼운 칸에서 빠진다.
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

    before = [s for s in list_consumable_slots(pool, entity_id) if s.catalog_id][0].charges
    carried = dict(parse_loadout(ticket.loadout).consumables)["POTION"]
    apply_charge_spend(
        account_id,
        ticket,
        VerifiedRun(
            outcome="PLAYER_WIN",
            ticks=1,
            player_hp=1,
            verdict=VERDICT_VERIFIED,
            remaining_consumables=(("POTION", 1),),
        ),
    )
    after = [s for s in list_consumable_slots(pool, entity_id) if s.catalog_id][0].charges
    # 실은 것 중 하나만 남겼으니 `carried - 1` 개를 썼고, 그중 공짜 1개는 깎을 자리가
    # 없으므로 칸에서는 `carried - 2` 개가 빠진다.
    assert after == before - (carried - 2)
    assert after < before, "재시뮬이 쓴 만큼 안 깎였다"


@pytestmark_db
def test_a_rejected_submission_spends_nothing(client, token):
    """★ 반려된 제출이 충전을 깎으면, 코어 버전 시차 한 번이 물약을 태운다."""
    from game.api.deps import get_pool
    from game.api.floor_service import apply_charge_spend
    from game.app.services.verify_run import VerifiedRun
    from game.app.store.accounts import find_player_entity
    from game.app.store.consumables import list_consumable_slots
    from game.app.store.runs import VERDICT_REJECTED
    from game.app.store.tickets import find_open_ticket

    load_potion(client, token, slot_index=0)
    headers = build_headers(token)
    account_id = client.get("/api/account", headers=headers).json()["account_id"]
    pool = get_pool()
    entity_id = find_player_entity(pool, account_id)
    issued = client.post("/api/ticket", json={"room_id": "open_field"}, headers=headers).json()
    ticket = find_open_ticket(pool, issued["ticket_id"], account_id)
    assert ticket is not None

    before = [s for s in list_consumable_slots(pool, entity_id) if s.catalog_id][0].charges
    apply_charge_spend(
        account_id,
        ticket,
        VerifiedRun(outcome="", ticks=0, player_hp=0, verdict=VERDICT_REJECTED),
    )
    after = [s for s in list_consumable_slots(pool, entity_id) if s.catalog_id][0].charges
    assert after == before


@pytestmark_db
def test_a_second_claim_does_not_spend_twice(client, token):
    """★ **층마다 처음부터 다시 도므로 「쓴 수」는 누적이다.**

    이미 깎은 만큼을 안 빼면 3층을 청구할 때 1·2층에서 쓴 것이 또 깎인다. 그러면 런
    중에 보충한 사람은 낸 돈이 그 자리에서 사라진다 — 그것을 막으려고 런 중 보충을
    잠갔었고, 그 잠금이 방 사이 편집을 막았다.
    """
    from game.api.deps import get_pool
    from game.api.floor_service import apply_charge_spend
    from game.app.services.verify_run import VERDICT_VERIFIED, VerifiedRun
    from game.app.store.accounts import find_player_entity
    from game.app.store.consumables import list_consumable_slots
    from game.app.store.tickets import find_open_ticket

    load_potion(client, token, slot_index=0)
    headers = build_headers(token)
    account_id = client.get("/api/account", headers=headers).json()["account_id"]
    pool = get_pool()
    entity_id = find_player_entity(pool, account_id)
    issued = client.post("/api/ticket", json={"room_id": "open_field"}, headers=headers).json()
    ticket = find_open_ticket(pool, issued["ticket_id"], account_id)
    assert ticket is not None

    def settle(remaining):
        """같은 티켓으로 한 번 더 정산한다.

        Args:
            remaining: 재시뮬이 남긴 물약 수.
        """
        apply_charge_spend(
            account_id,
            ticket,
            VerifiedRun(
                outcome="PLAYER_WIN",
                ticks=1,
                player_hp=1,
                verdict=VERDICT_VERIFIED,
                remaining_consumables=(("POTION", remaining),),
            ),
        )

    def read_charges():
        """끼운 칸에 남은 충전.

        Returns:
            충전 수.
        """
        return [s for s in list_consumable_slots(pool, entity_id) if s.catalog_id][0].charges

    before = read_charges()
    settle(1)
    once = read_charges()
    assert once < before, "첫 정산이 안 깎였다"
    # 같은 층을 다시 청구하면 「쓴 수」가 같다 — 한 번 더 깎이면 안 된다.
    settle(1)
    assert read_charges() == once, "같은 사용분이 두 번 깎였다"


@pytestmark_db
def test_a_deeper_claim_spends_only_the_difference(client, token):
    """★ 더 깊이 가서 더 쓴 만큼만 깎는다 — 전부 다시 깎으면 충전이 순식간에 마른다."""
    from game.api.deps import get_pool
    from game.api.floor_service import apply_charge_spend
    from game.app.services.verify_run import VERDICT_VERIFIED, VerifiedRun
    from game.app.store.accounts import find_player_entity
    from game.app.store.consumables import list_consumable_slots
    from game.app.store.tickets import find_open_ticket
    from game.schemas.loadout import parse_loadout

    load_potion(client, token, catalog_id="potion_greater", slot_index=0)
    headers = build_headers(token)
    account_id = client.get("/api/account", headers=headers).json()["account_id"]
    pool = get_pool()
    entity_id = find_player_entity(pool, account_id)
    issued = client.post("/api/ticket", json={"room_id": "open_field"}, headers=headers).json()
    ticket = find_open_ticket(pool, issued["ticket_id"], account_id)
    assert ticket is not None
    carried = dict(parse_loadout(ticket.loadout).consumables)["POTION"]

    def settle(remaining):
        """정산 한 번.

        Args:
            remaining: 재시뮬이 남긴 물약 수.
        """
        apply_charge_spend(
            account_id,
            ticket,
            VerifiedRun(
                outcome="PLAYER_WIN",
                ticks=1,
                player_hp=1,
                verdict=VERDICT_VERIFIED,
                remaining_consumables=(("POTION", remaining),),
            ),
        )

    def read_charges():
        """끼운 칸에 남은 충전.

        Returns:
            충전 수.
        """
        return [s for s in list_consumable_slots(pool, entity_id) if s.catalog_id][0].charges

    start = read_charges()
    # 한 개만 썼으면 그것은 빈 칸의 공짜분이다 — 산 충전은 안 줄어야 한다.
    settle(carried - 1)
    assert read_charges() == start, "공짜분보다 적게 썼는데 산 충전이 깎였다"
    # 둘을 썼으면 공짜분 하나를 뺀 하나만 깎인다.
    settle(carried - 2)
    assert read_charges() == start - 1
    # 같은 층을 다시 청구해도 더 안 깎인다.
    settle(carried - 2)
    assert read_charges() == start - 1
