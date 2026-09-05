"""계정 비활성화 — 지우지 않고 끈다.

여기서 지키는 것은 다섯이다.

1. **토큰이 안 통한다.** 통계에서만 빼면 그 계정이 여전히 게임을 돌리고, 관리자였다면
   관리자 권한까지 그대로 쓴다.
2. **순위표에서 빠진다.** 검사가 만든 계정이 1위에 있으면 순위표가 말하는 것이 실력이
   아니라 탐침 횟수다.
3. **세계 현황과 레벨 곡선에서 빠진다.** 섞이면 "사람이 몇인가" 가 거짓이 되고, 그
   숫자로 밸런스를 판단하게 된다.
4. **매물이 안 보인다.** 남겨 두면 사는 사람의 돈이 죽은 지갑으로 들어간다.
5. **되살릴 수 있다.** 되돌릴 수 없으면 그것은 비활성화가 아니라 삭제다.
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


def build_headers(token):
    return {"X-Game-Token": token}


def build_account(client):
    account = client.post("/api/account").json()
    return account["token"], account["account_id"]


def deactivate(account_id, is_active=False):
    from game.api.deps import get_pool
    from game.app.store.accounts import apply_deactivation

    return apply_deactivation(get_pool(), (account_id,), is_active)


def test_a_deactivated_token_stops_working(client):
    """★ 통계에서만 빼면 그 계정이 여전히 게임을 돌린다."""
    token, account_id = build_account(client)
    assert client.get("/api/account", headers=build_headers(token)).status_code == 200
    deactivate(account_id)
    assert client.get("/api/account", headers=build_headers(token)).status_code == 401


def test_a_deactivated_admin_loses_the_admin_path(client):
    """★ 검사가 만든 관리자 계정이 프로덕션에 남아 있었다 — 끄면 그 길도 닫혀야 한다."""
    from game.api.deps import get_pool
    from game.app.store.admin import ROLE_OWNER, set_admin_role

    token, account_id = build_account(client)
    login_id = f"deact{account_id}"
    client.post(
        "/api/register",
        json={"login_id": login_id, "password": "probe-password-1"},
        headers=build_headers(token),
    )
    assert set_admin_role(get_pool(), login_id, ROLE_OWNER)
    assert client.get("/api/admin/overview", headers=build_headers(token)).status_code == 200
    deactivate(account_id)
    # 토큰 자체가 안 통하므로 401 이다. 404 였다면 "관리자가 아니다" 이고, 그것도 막힌
    # 것이지만 여기서 보려는 것은 계정이 통째로 닫히는 것이다.
    assert client.get("/api/admin/overview", headers=build_headers(token)).status_code == 401


def test_a_deactivated_account_leaves_the_leaderboard(client):
    """★ 검사 계정이 1위면 순위표가 말하는 것이 실력이 아니다."""
    from game.api.deps import get_pool
    from game.app.store.accounts import find_player_entity
    from game.app.store.progress import list_leaderboard, save_leaderboard

    token, account_id = build_account(client)
    find_player_entity(get_pool(), account_id)
    save_leaderboard(get_pool(), "PRACTICE", "probe.v1", account_id, 9_999_999, 40)
    ranked = list_leaderboard(get_pool(), "PRACTICE", "probe.v1")
    assert any(row["account_id"] == account_id for row in ranked)
    deactivate(account_id)
    ranked = list_leaderboard(get_pool(), "PRACTICE", "probe.v1")
    assert not [row for row in ranked if row["account_id"] == account_id]


def test_a_deactivated_account_leaves_the_world_counts(client):
    """★ 섞이면 「사람이 몇인가」가 거짓이 되고, 그 숫자로 밸런스를 판단하게 된다."""
    from game.api.deps import get_pool
    from game.app.store.world_view import read_world_summary

    token, account_id = build_account(client)
    before = read_world_summary(get_pool()).accounts
    deactivate(account_id)
    assert read_world_summary(get_pool()).accounts == before - 1


def test_a_deactivated_account_leaves_the_level_curve(client):
    """★ 검사가 만든 레벨 1 수십 개가 곡선 앞머리를 눌러 「다들 초반에 멈춘다」로 읽힌다."""
    from game.api.deps import get_pool
    from game.app.store.accounts import find_player_entity
    from game.app.store.world_view import count_levels

    token, account_id = build_account(client)
    find_player_entity(get_pool(), account_id)
    before = dict(count_levels(get_pool()))
    deactivate(account_id)
    after = dict(count_levels(get_pool()))
    assert after.get(1, 0) == before.get(1, 0) - 1


def test_a_deactivated_seller_disappears_from_the_auction(client):
    """★ 남겨 두면 사는 사람의 돈이 죽은 지갑으로 들어간다."""
    from game.api.deps import get_pool
    from game.app.store.accounts import find_player_entity
    from game.app.store.auction import list_open
    from game.app.store.equipment import add_currency
    from game.app.store.items import create_item

    token, account_id = build_account(client)
    add_currency(get_pool(), account_id, 1000)
    entity_id = find_player_entity(get_pool(), account_id)
    item_id = create_item(get_pool(), entity_id, "helm_iron", ())
    client.post(
        "/api/auction/list",
        json={"item_id": item_id, "price": 10},
        headers=build_headers(token),
    )
    listed = list_open(get_pool(), account_id, limit=100_000)
    assert any(row.item_id == item_id for row in listed)
    deactivate(account_id)
    listed = list_open(get_pool(), account_id, limit=100_000)
    assert not [row for row in listed if row.item_id == item_id]


def test_it_can_be_undone(client):
    """★ 되돌릴 수 없으면 그것은 비활성화가 아니라 삭제다."""
    token, account_id = build_account(client)
    deactivate(account_id)
    assert client.get("/api/account", headers=build_headers(token)).status_code == 401
    deactivate(account_id, is_active=True)
    assert client.get("/api/account", headers=build_headers(token)).status_code == 200


def test_the_records_survive(client):
    """★ 지우면 「이 아이템이 어디서 왔는가」를 나중에 못 읽는다."""
    from game.api.deps import get_pool
    from game.app.store.accounts import find_player_entity
    from game.app.store.items import create_item

    token, account_id = build_account(client)
    entity_id = find_player_entity(get_pool(), account_id)
    item_id = create_item(get_pool(), entity_id, "helm_iron", ())
    deactivate(account_id)
    with get_pool().connection() as connection:
        row = connection.execute(
            "SELECT count(*) FROM item_instance WHERE id = %s", (item_id,)
        ).fetchone()
    assert row is not None and int(row[0]) == 1, "비활성화가 기록을 지웠다"
