"""관리자 경로 — 세계를 보고 손대는 유일한 문.

**여기가 이 서버에서 가장 위험한 자리다.** 나머지 경로는 뚫려도 한 계정이 손해를 보지만,
관리자 경로가 뚫리면 세계 전체가 뚫린다. 그래서 검사도 기능보다 **차단**을 먼저 본다.

세 가지를 지킨다.

1. **관리자가 아니면 404 다.** 403 은 "여기 뭔가 있는데 너는 못 본다" 를 알려 주고,
   그것은 경로의 존재 자체를 노출한다.
2. **승격은 API 로 불가능하다.** 길은 `scripts/grant_admin.py` 하나이며 DB 접속이 있어야
   돈다. 익명 계정은 관리자가 될 수 없다 — 토큰 하나가 곧 세계 전체가 된다.
3. **개입은 반드시 원장에 남는다.**
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

fastapi_testclient = pytest.importorskip("fastapi.testclient")

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)

PASSWORD = "correct horse battery"


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


def build_admin(client):
    """가입한 계정 하나를 만들어 관리자로 올린다. **스크립트와 같은 경로를 쓴다.**"""
    from game.api.deps import get_pool
    from game.app.store.admin import ROLE_OWNER, set_admin_role

    account = client.post("/api/account").json()
    login_id = f"admin{account['account_id']}"
    client.post(
        "/api/register",
        json={"login_id": login_id, "password": PASSWORD},
        headers=build_headers(account["token"]),
    )
    assert set_admin_role(get_pool(), login_id, ROLE_OWNER)
    return account["token"]


# ── 조회 ─────────────────────────────────────────────────────────────────


def test_an_admin_sees_the_world(client):
    """★ 지금까지 세계 상태를 볼 방법이 아예 없었다."""
    body = client.get("/api/admin/overview", headers=build_headers(build_admin(client))).json()
    assert body["accounts"] >= 1
    assert body["catalog_items"] >= 1
    assert body["core_version"]


def test_the_overview_counts_items_held_by_monsters(client):
    """★ 남의 장비를 들고 있는 몬스터가 World Loop 의 동기다 (`설계/6_몬스터` §5).

    그것을 세지 않으면 이 표가 세계를 설명하지 못한다.
    """
    body = client.get("/api/admin/overview", headers=build_headers(build_admin(client))).json()
    assert "items_held_by_monsters" in body
    assert body["items_held_by_monsters"] >= 0


def test_monster_rows_carry_the_level_cap(client):
    """★ 상한 없이 레벨만 보면 그것이 높은 값인지 알 수 없다."""
    body = client.get("/api/admin/overview", headers=build_headers(build_admin(client))).json()
    for row in body["monsters"]:
        assert row["level_cap"] >= row["level"]


# ── 개입 ─────────────────────────────────────────────────────────────────


def test_changing_a_level_is_recorded(client):
    """★ **개입은 반드시 남는다.**

    남지 않으면 "이 몬스터 레벨이 왜 이렇지" 를 나중에 아무도 답할 수 없다.
    """
    from game.api.deps import get_pool
    from game.app.monsters.tiers import MonsterTier
    from game.app.store.monsters import create_monster

    admin = build_admin(client)
    record = create_monster(get_pool(), "goblin_rusher", MonsterTier.ELITE, 1, "admin_probe")
    if record is None:
        pytest.skip("그 자리에 이미 개체가 있다")
    body = client.put(
        "/api/admin/monster/level",
        json={"record_id": record.record_id, "level": 3},
        headers=build_headers(admin),
    ).json()
    changed = [row for row in body["monsters"] if row["record_id"] == record.record_id]
    assert changed[0]["level"] == 3
    assert any(item["action"] == "monster.level" for item in body["recent_actions"])


def test_a_level_over_the_cap_is_rejected(client):
    """★ 관리자라도 층 상한을 넘길 수 없다.

    넘기면 폭주 방지(결정 #35)가 뚫리고, 그 개체를 만난 플레이어는 이길 수 없는 판을
    받는다.
    """
    from game.api.deps import get_pool
    from game.app.monsters.tiers import MonsterTier
    from game.app.store.monsters import create_monster

    admin = build_admin(client)
    record = create_monster(get_pool(), "goblin_rusher", MonsterTier.ELITE, 1, "admin_cap_probe")
    if record is None:
        pytest.skip("그 자리에 이미 개체가 있다")
    response = client.put(
        "/api/admin/monster/level",
        json={"record_id": record.record_id, "level": 999},
        headers=build_headers(admin),
    )
    assert response.status_code == 409


def test_a_missing_monster_is_a_404(client):
    """없는 개체에 손대면 조용히 넘어가지 않는다."""
    response = client.put(
        "/api/admin/monster/level",
        json={"record_id": 999999999, "level": 2},
        headers=build_headers(build_admin(client)),
    )
    assert response.status_code == 404


# ── 개입 2단계 — 사유가 없으면 아무것도 못 한다 ──────────────────────────


def build_listing(client, admin):
    """관리자 계정으로 매물 하나를 건다. 강제 취소 대상이다."""
    from game.api.deps import get_pool
    from game.app.store.accounts import find_player_entity
    from game.app.store.auction import create_listing
    from game.app.store.equipment import add_currency
    from game.app.store.items import create_item

    account_id = client.get("/api/account", headers=build_headers(admin)).json()["account_id"]
    entity_id = find_player_entity(get_pool(), account_id)
    add_currency(get_pool(), account_id, 5000)
    item_id = create_item(get_pool(), entity_id, "sword_short", ())
    listing_id = create_listing(get_pool(), account_id, entity_id, item_id, 100)
    return listing_id, item_id


def test_an_intervention_without_a_reason_is_rejected(client):
    """★ **사유가 비면 거절한다.**

    무엇을 했는지만 남으면 "왜 그랬지" 를 나중에 아무도 답할 수 없고, 그때 원장은
    기록이 아니라 알리바이가 된다.
    """
    admin = build_admin(client)
    listing_id, item_id = build_listing(client, admin)
    for path, target in (
        ("/api/admin/auction/cancel", listing_id),
        ("/api/admin/item/recall", item_id),
    ):
        response = client.post(
            path, json={"target_id": target, "reason": "  "}, headers=build_headers(admin)
        )
        assert response.status_code == 400, path


def test_a_normal_account_cannot_intervene(client, token):
    """★ 조회만 막고 개입을 열어 두면 막은 뜻이 없다."""
    for path in ("/api/admin/auction/cancel", "/api/admin/item/recall"):
        response = client.post(
            path, json={"target_id": 1, "reason": "정상 사유"}, headers=build_headers(token)
        )
        assert response.status_code == 404, path


def test_cancelling_a_listing_records_the_reason(client):
    """★ 개입과 사유가 함께 남는다."""
    admin = build_admin(client)
    listing_id, _ = build_listing(client, admin)
    body = client.post(
        "/api/admin/auction/cancel",
        json={"target_id": listing_id, "reason": "가격 오기입 신고"},
        headers=build_headers(admin),
    ).json()
    logged = [row for row in body["recent_actions"] if row["action"] == "auction.cancel"]
    assert logged
    assert logged[0]["detail"] == "가격 오기입 신고"


def test_recalling_an_item_keeps_the_row(client):
    """★ **지우지 않는다.**

    원장이 이 id 를 가리키므로 지우면 "이 아이템이 어디로 갔나" 를 추적할 수 없다.
    """
    from game.api.deps import get_pool

    admin = build_admin(client)
    _, item_id = build_listing(client, admin)
    client.post(
        "/api/admin/item/recall",
        json={"target_id": item_id, "reason": "복제 버그로 나온 것"},
        headers=build_headers(admin),
    )
    with get_pool().connection() as connection:
        row = connection.execute(
            "SELECT is_broken FROM item_instance WHERE id = %s", (item_id,)
        ).fetchone()
    assert row is not None, "행이 지워졌다 — 원장이 가리키는 것이 사라지면 조사가 끊긴다"
    assert bool(row[0])


def test_there_is_no_item_grant_route(client):
    """★ **발급하는 짝을 만들지 않았다.**

    서버가 검증된 런의 결과로만 아이템을 만든다는 결정 #02 가 관리자 경로 하나로
    뚫리면, 그 뒤로는 어떤 아이템도 "정상적으로 나온 것" 이라고 말할 수 없다.
    """
    from game.api.main import create_app

    paths = [route.path for route in create_app().routes]
    assert not [path for path in paths if "/admin/" in path and ("grant" in path or "give" in path)]


def test_held_items_show_who_they_were_taken_from(client):
    """★ 되찾으러 갈 동기가 World Loop 의 전부다 (`설계/6_몬스터` §5).

    원주인을 모르면 이 표가 무엇을 설명하는지 알 수 없다.
    """
    body = client.get("/api/admin/overview", headers=build_headers(build_admin(client))).json()
    assert "held_items" in body
    for row in body["held_items"]:
        assert "taken_from_handle" in row
        assert row["catalog_id"]


# ── 카탈로그 (읽기 전용) ─────────────────────────────────────────────────


def test_a_normal_account_cannot_read_the_catalog(client, token):
    """★ 카탈로그도 관리자 경로다 — 404 여야 한다."""
    assert client.get("/api/admin/catalog", headers=build_headers(token)).status_code == 404


def test_the_catalog_shows_what_the_game_reads(client):
    """★ **게임이 읽는 그대로 보여준다.**

    별도 표를 만들어 두면 화면에 적힌 값과 전투가 쓰는 값이 갈라지고, 그때 이 뷰어는
    도움이 아니라 오해의 근원이 된다.
    """
    from game.api.deps import get_context, get_item_catalog

    body = client.get("/api/admin/catalog", headers=build_headers(build_admin(client))).json()
    assert len(body["items"]) == len(get_item_catalog())
    assert len(body["enemies"]) == len(get_context().balance["enemies"])


def test_only_the_item_catalog_is_writable(client):
    """★ 브라우저 코어가 읽는 자산에는 런타임 쓰기 경로가 없다 (개정 2026-08-31).

    예전에는 카탈로그 전체가 읽기 전용이었다. 아이템 카탈로그만 DB 로 옮겼는데
    (설계/4_아이템 §15.7), 그것이 **브라우저 코어가 읽지 않는 유일한 자산**이기 때문이다 —
    아이템은 로드아웃으로 합산돼 티켓에 얼려 들어간다.

    스킬·블록·밸런스·룸·적 규칙표는 두 코어가 함께 읽으므로 런타임에 바꾸면 브라우저와
    서버가 다른 게임을 돈다 (결정 #06, R5). 그쪽 쓰기 경로가 생기면 여기서 걸린다.
    """
    from game.api.main import create_app

    banned = ("skill", "block", "balance", "room", "enemy")
    for route in create_app().routes:
        path = getattr(route, "path", "")
        methods = set(getattr(route, "methods", set()))
        if "/admin/" not in path or methods <= {"GET", "HEAD"}:
            continue
        assert not [word for word in banned if word in path], f"{path} 에 런타임 쓰기가 생겼다"


def test_every_catalog_write_moves_the_generation(client):
    """★ 아이템을 고치는 것은 시즌을 가르는 일이다 (§15.8).

    세대를 안 올리면 관리자가 조용히 과거 기록을 무효로 만든다 — 저장된 리플레이가
    거짓이 되는데 코어 버전은 그대로다.
    """
    import inspect

    from game.api.routes import catalog_admin

    for name in ("create_catalog_item", "create_catalog_retire"):
        source = inspect.getsource(getattr(catalog_admin, name))
        assert "apply_generation_bump" in source, f"{name} 이 세대를 안 올린다"


def test_the_level_curve_carries_the_real_distribution(client):
    """★ **곡선만 보면 튜닝할 수 없다.**

    사람들이 실제로 어디서 멈추는지가 보여야 "이 구간이 너무 긴가" 를 물을 수 있다.
    """
    # **실제 값을 본다.** 열쇠가 있는지만 보면 늘 0 을 보내도 통과한다 — 처음 쓴 검사가
    # 그랬고, 반증에서 드러났다.
    admin = build_admin(client)
    body = client.get("/api/admin/catalog", headers=build_headers(admin)).json()
    curve = body["level_curve"]
    assert curve
    # 방금 만든 관리자 계정이 레벨 1 개체를 하나 갖는다. 그것이 안 세어지면 이 곡선은
    # 세계를 보고 있지 않다.
    first = next(row for row in curve if row["level"] == 1)
    assert first["players"] >= 1, curve[:3]
    # 누적 경험치는 단조 증가한다 — 아니면 곡선이 곡선이 아니다.
    totals = [row["total_xp"] for row in curve]
    assert totals == sorted(totals)


def test_the_curve_shows_where_expressiveness_stops(client):
    """★ 표현력 상한을 함께 보낸다 — 없으면 그 값이 계속 오르는지 알 수 없다."""
    body = client.get("/api/admin/catalog", headers=build_headers(build_admin(client))).json()
    caps = body["caps"]
    assert caps["max_bonus_cpu"] > 0
    assert max(row["bonus_cpu"] for row in body["level_curve"]) <= caps["max_bonus_cpu"]
