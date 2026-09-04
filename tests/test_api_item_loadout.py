"""장비가 티켓과 아이템 뷰에 실리는 길 (결정 #13, §15.11).

`test_api_items.py` 에서 갈라 나왔다. 저쪽은 **아이템이 저장소에서 어떻게 다뤄지는가**
(발급·요구조건·봉인·해제·사망 손실)이고, 여기는 **낀 것이 밖으로 어떻게 나가는가**다 —
티켓이 싣는 로드아웃과 화면이 읽는 아이템 뷰.

가르는 선은 책임이다 (§4). 파일이 400줄 상한을 넘은 것이 계기였을 뿐이다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV
from game.schemas.item import Affix

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


def grant_item(client, token, catalog_id, affixes=None):
    """검사용으로 아이템 하나를 직접 넣는다. API 에는 이런 문이 없다.

    **접사를 안 주면 카탈로그의 것을 실어 준다.** 실제 발급 경로(`create_kill_drop`)가
    그렇게 하기 때문이다 — 인스턴스가 자기 접사를 갖는 것이 §15.11 의 전부이고, 검사가
    빈 접사로 만들면 진짜 아이템이 아닌 것을 놓고 보게 된다.
    """
    from game.api.deps import get_item_catalog, get_pool
    from game.app.store.accounts import find_player_entity
    from game.app.store.items import create_item

    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    entity_id = find_player_entity(get_pool(), account_id)
    rolled = get_item_catalog()[catalog_id].affixes if affixes is None else tuple(affixes)
    return create_item(get_pool(), entity_id, catalog_id, rolled)


# ── 장비 → 티켓 (결정 #13) ───────────────────────────────────────────────


def apply_equip_via_api(client, token, item_id, slot):
    """착용하고 **성공했는지 확인한다.**

    응답 코드를 안 보면 422·409 로 조용히 실패한 것이 뒤따르는 단언에서 "장비가 반영되지
    않았다" 로 둔갑한다. 실제로 한 번 그렇게 읽었다.
    """
    body = {"item_id": item_id, "slot": slot}
    response = client.post("/api/equip", headers=build_headers(token), json=body)
    assert response.status_code == 200, response.text
    return response


def request_loadout(client, token):
    """티켓을 하나 받아 그 안의 로드아웃을 돌려준다."""
    body = {"room_id": ROOM_ID, "seed": 42}
    return client.post("/api/ticket", headers=build_headers(token), json=body).json()["loadout"]


def test_ticket_carries_loadout(client, token):
    """★ 맨몸이어도 티켓은 로드아웃을 싣는다.

    브라우저가 전투를 돌리므로 서버만 아는 장비를 티켓에 얼려 보내야 한다. 이 절이 없으면
    클라이언트는 기본값으로 떨어지고, 서버는 장비를 낀 채로 재시뮬해 정상 제출이 전부
    반려된다.
    """
    loadout = request_loadout(client, token)
    assert loadout["attack_range"] >= 1
    assert "ATTACK" in loadout["skills"]


def test_equipping_changes_the_issued_loadout(client, token):
    """★ 여기가 실제로 비어 있던 자리다 — 부품은 다 있고 배선이 없었다.

    장비를 끼면 티켓이 싣는 값이 바뀌어야 한다. 안 바뀌면 인벤토리는 화면 장식이다.
    """
    before = request_loadout(client, token)
    item_id = grant_item(client, token, "bow_long")
    apply_equip_via_api(client, token, item_id, "WEAPON_MAIN")
    after = request_loadout(client, token)
    assert after["attack_range"] > before["attack_range"]


def test_equipping_opens_a_skill(client, token):
    """★ 장비가 스킬을 연다 — 규칙표 재설계로 이어지는 지점이다 (결정 #13)."""
    item_id = grant_item(client, token, "shield_buckler")
    apply_equip_via_api(client, token, item_id, "WEAPON_OFF")
    assert "GUARD_BRACE" in request_loadout(client, token)["skills"]


def test_broken_gear_grants_nothing(client, token):
    """★ 파손은 그 자리가 비어 있는 것과 같다 (결정 #34).

    파손된 장비가 계속 스탯을 주면 사망 대가가 사라진다.
    """
    from game.api.deps import get_pool
    from game.app.store.accounts import find_player_entity
    from game.app.store.equipment import mark_item_broken

    item_id = grant_item(client, token, "bow_long")
    apply_equip_via_api(client, token, item_id, "WEAPON_MAIN")
    geared = request_loadout(client, token)
    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    mark_item_broken(get_pool(), find_player_entity(get_pool(), account_id), item_id)
    assert request_loadout(client, token)["attack_range"] < geared["attack_range"]


def test_instance_affixes_beat_catalog_defaults(client, token):
    """★ 같은 이름의 아이템이 조금씩 다르게 나와야 파밍이 성립한다.

    인스턴스가 굴린 접사를 안 쓰면 모든 롱보우가 똑같아진다.
    """
    plain_id = grant_item(client, token, "helm_iron")
    apply_equip_via_api(client, token, plain_id, "HEAD")
    plain = request_loadout(client, token)
    unequip = {"item_id": plain_id, "slot": "HEAD"}
    client.post("/api/unequip", headers=build_headers(token), json=unequip)
    rolled_id = grant_item(client, token, "helm_iron", (Affix(stat="hp_max", flat=40),))
    apply_equip_via_api(client, token, rolled_id, "HEAD")
    assert request_loadout(client, token)["hp_max"] > plain["hp_max"]


def test_the_item_view_shows_what_it_actually_gives(client, token):
    """★ 카탈로그 기본 접사를 가진 아이템도 효과가 보여야 한다.

    인스턴스가 굴린 접사만 보내면, 기본 접사로만 이루어진 아이템이 화면에서 "아무 효과
    없음" 으로 보인다 — 로드아웃 계산은 카탈로그 것을 쓰는데 화면만 모르는 상태가 된다.
    """
    item_id = grant_item(client, token, "helm_iron")
    slots = client.get("/api/inventory", headers=build_headers(token)).json()["slots"]
    view = next(s["item"] for s in slots if (s["item"] or {}).get("item_id") == item_id)
    assert view["affixes"] != []
    assert any(a["stat"] == "hp_max" for a in view["affixes"])


def test_rolled_affixes_replace_the_catalog_ones_in_the_view(client, token):
    """★ 화면이 로드아웃 계산과 같은 규칙을 보여야 한다.

    인스턴스가 굴린 접사가 카탈로그 기본값을 **대체한다** — 화면만 둘을 합쳐 보여주면
    유저가 본 것과 전투가 쓰는 것이 달라진다.
    """
    item_id = grant_item(client, token, "helm_iron", (Affix(stat="hp_max", flat=40),))
    slots = client.get("/api/inventory", headers=build_headers(token)).json()["slots"]
    view = next(s["item"] for s in slots if (s["item"] or {}).get("item_id") == item_id)
    assert [a["flat"] for a in view["affixes"]] == [40]
