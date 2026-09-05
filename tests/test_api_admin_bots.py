"""봇 관리 라우트 (T11, 결정 #48 준비).

**우리가 들인 봇은 우리가 볼 수 있어야 한다.** 표시만 하고 보는 자리가 없으면 「몇
마리가 무엇을 하고 있는지」를 DB 로만 알 수 있고, 그러면 실질적으로 아무도 안 본다.
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
    """관리자 토큰 하나를 만든다.

    Args:
        client: 테스트 클라이언트.

    Returns:
        관리자 토큰.
    """
    from game.api.deps import get_pool

    token = client.post("/api/account").json()["token"]
    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    with get_pool().connection() as connection:
        connection.execute("UPDATE account SET admin_role = 'owner' WHERE id = %s", (account_id,))
    return token


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
    create_bot(get_pool(), account_id, "검사봇", "g0_kite", 720, 60)
    return account_id


def test_a_plain_account_cannot_see_the_bots(client):
    """★ 관리자만 본다. 관리자가 아니면 404 다 — 경로의 존재도 알리지 않는다."""
    token = client.post("/api/account").json()["token"]
    assert client.get("/api/admin/bots", headers=build_headers(token)).status_code == 404


def test_the_overview_carries_the_cap(client):
    """★ 상한을 서버가 싣는다 — 화면이 제 값으로 적으면 서버가 물리는 값과 갈린다."""
    body = client.get("/api/admin/bots", headers=build_headers(build_admin(client))).json()
    assert body["max_runs_per_hour"] == 5
    assert body["min_cadence_sec"] == 720


def test_a_bot_row_carries_its_results(client):
    """★ 성격만이 아니라 **결과**를 싣는다.

    규칙표와 실력은 우리가 정해 준 값이라 화면에 적어도 새 사실이 없다. 승리가 0이면
    그 봇은 세계에 아무것도 안 남긴다 — 그 사실이 보여야 늘릴지 줄일지 정할 수 있다.
    """
    account_id = build_bot(client)
    body = client.get("/api/admin/bots", headers=build_headers(build_admin(client))).json()
    found = next(row for row in body["bots"] if row["account_id"] == account_id)
    for key in ("runs", "wins", "best_floor", "balance", "items", "due_in_sec"):
        assert key in found, key
    assert found["handle"] != ""
    assert found["is_active"] is True


def test_stopping_a_bot_takes_it_out_of_the_queue(client):
    """★ 멈추면 차례에서 빠진다 — 화면의 스위치가 실제로 러너를 막아야 한다."""
    from game.api.deps import get_pool
    from game.app.store.bots import list_due_bots

    account_id = build_bot(client)
    admin = build_admin(client)
    client.put(
        "/api/admin/bot",
        json={
            "account_id": account_id,
            "ruleset_id": "g0_kite",
            "skill_pct": 60,
            "cadence_sec": 720,
            "is_active": False,
        },
        headers=build_headers(admin),
    )
    assert account_id not in {bot.account_id for bot in list_due_bots(get_pool())}


def test_the_server_still_pins_the_cadence(client):
    """★ 화면이 더 빠른 값을 보내도 상한으로 밀린다 — 상한은 서버가 물린다."""
    account_id = build_bot(client)
    admin = build_admin(client)
    response = client.put(
        "/api/admin/bot",
        json={
            "account_id": account_id,
            "ruleset_id": "g0_kite",
            "skill_pct": 60,
            "cadence_sec": 1,
            "is_active": True,
        },
        headers=build_headers(admin),
    )
    # 스키마가 먼저 막는다. 뚫려도 저장 계층이 다시 민다 — 두 겹이다.
    assert response.status_code == 422


def test_changing_a_bot_is_recorded(client):
    """★ 개입은 남는다 — 「이 봇이 왜 멈춰 있지」를 나중에 답할 수 있어야 한다."""
    account_id = build_bot(client)
    admin = build_admin(client)
    client.put(
        "/api/admin/bot",
        json={
            "account_id": account_id,
            "ruleset_id": "sniper",
            "skill_pct": 90,
            "cadence_sec": 900,
            "is_active": True,
        },
        headers=build_headers(admin),
    )
    body = client.get("/api/admin/overview", headers=build_headers(admin)).json()
    assert any(item["action"] == "bot.settings" for item in body["recent_actions"])


def test_a_missing_bot_is_a_404(client):
    """없는 봇에 손대면 조용히 넘어가지 않는다."""
    response = client.put(
        "/api/admin/bot",
        json={
            "account_id": 999999999,
            "ruleset_id": "g0_kite",
            "skill_pct": 60,
            "cadence_sec": 720,
            "is_active": True,
        },
        headers=build_headers(build_admin(client)),
    )
    assert response.status_code == 404
