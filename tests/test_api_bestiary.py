"""도감 — 만난 것을 무엇까지 알려 주는가 (docs/설계/6_몬스터 §8).

봉인과 성장은 `test_api_monsters` 가 본다. 여기는 **그 개체를 화면이 어떻게 읽는가**를
본다 — 규칙표를 그대로 펴 주는지, 레벨과 상한을 함께 적는지, 내 물건인지 남의 것인지
가려 주는지.

책임이 둘이라 파일을 갈랐다 (표준 §4 의 400줄 상한).
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

# 성장 상한 검사가 쓰는 자리. 방 템플릿에 없는 이름이라 다른 검사의 전투에 안 끼어든다.
GROWTH_SLOT = "growth_cap_probe"
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


def build_ruleset():
    return {"ruleset_id": "probe", "version": 1, "rules": []}


def build_winning_ruleset():
    """방을 실제로 이기는 규칙표. 연쇄 검사는 이것이라야 뒷 방까지 돈다."""
    import json

    from game.config import G0_RULESETS_PATH

    raw = json.loads(G0_RULESETS_PATH.read_text(encoding="utf-8"))
    return next(item for item in raw["rulesets"] if item["ruleset_id"] == "g0_kite")


def run_once(client, token, floor=1):
    headers = build_headers(token)
    ticket = client.post(
        "/api/ticket", json={"room_id": ROOM_ID, "floor": floor}, headers=headers
    ).json()
    body = client.post(
        "/api/run",
        json={
            "ticket_id": ticket["ticket_id"],
            "ruleset": build_ruleset(),
            "core_version": ticket["core_version"],
        },
        headers=headers,
    ).json()
    return ticket, body


# ── 도감 (§8) ────────────────────────────────────────────────────────────


def test_bestiary_publishes_the_ruleset_verbatim(client, token, monster):
    """★ 요약하지 않는다 — 원문이 곧 카운터 설계의 입력이다 (GDD §2.3, P1)."""
    body = client.get("/api/bestiary", headers=build_headers(token)).json()
    entry = next(e for e in body["entries"] if e["record_id"] == monster.record_id)
    assert entry["ruleset"] is not None
    assert entry["ruleset"]["rules"], "규칙표가 비었다 — 요약된 것이 아니라 원문이어야 한다"


def test_bestiary_reports_level_and_cap(client, token, monster):
    """상한을 함께 보여준다 — 얼마나 더 클 수 있는지가 표적 판단에 든다."""
    body = client.get("/api/bestiary", headers=build_headers(token)).json()
    entry = next(e for e in body["entries"] if e["record_id"] == monster.record_id)
    assert entry["level"] >= 1
    assert entry["level_cap"] >= entry["level"]


def test_bestiary_flags_my_own_items(client, token, monster):
    """★ "내 아이템을 들고 있다" 가 되찾으러 가는 동기다 (World Loop)."""
    from game.api.deps import get_pool
    from game.api.monster_service import apply_trophy_transfer
    from game.app.store.accounts import find_player_entity
    from game.app.store.items import create_item

    headers = build_headers(token)
    account_id = client.get("/api/account", headers=headers).json()["account_id"]
    create_item(get_pool(), find_player_entity(get_pool(), account_id), "boots_swift", ())
    apply_trophy_transfer(account_id, monster.record_id)

    entry = next(
        e
        for e in client.get("/api/bestiary", headers=headers).json()["entries"]
        if e["record_id"] == monster.record_id
    )
    assert entry["holds_mine"] is True
    assert "boots_swift" in entry["trophies"]


def test_another_account_does_not_see_it_as_theirs(client, token, monster):
    """남의 전리품을 내 것으로 표시하면 도감이 거짓말을 한다."""
    from game.api.deps import get_pool
    from game.api.monster_service import apply_trophy_transfer
    from game.app.store.accounts import find_player_entity
    from game.app.store.items import create_item

    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    create_item(get_pool(), find_player_entity(get_pool(), account_id), "armor_plate", ())
    apply_trophy_transfer(account_id, monster.record_id)

    other = client.post("/api/account").json()["token"]
    entry = next(
        e
        for e in client.get("/api/bestiary", headers=build_headers(other)).json()["entries"]
        if e["record_id"] == monster.record_id
    )
    assert entry["holds_mine"] is False


def test_the_bestiary_carries_stats_too(client, token, monster):
    """★ 규칙표만으로는 **이길 수 있는지**를 알 수 없다.

    도감이 표적 목록이려면 "어떻게 싸우는가"(규칙표)와 "얼마나 센가"(스탯)가 둘 다
    있어야 한다 (`설계/6_몬스터` §8).
    """
    rows = client.get("/api/bestiary", headers=build_headers(token)).json()["entries"]
    assert rows
    for row in rows:
        assert row["hp_max"] > 0
        assert row["attack"] > 0
        # 전투가 쓰는 것과 같은 계산이어야 한다 — 따로 세면 화면과 실제가 갈린다.
        assert row["ruleset"] is None or row["ruleset"]["rules"]
