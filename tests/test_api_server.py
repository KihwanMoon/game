"""검증 서버를 실제 DB 에 붙여 끝까지 돌린다 (B단계).

**연결이 없으면 건너뛴다.** 로컬에서 맨손으로 `pytest` 를 돌릴 때 DB 가 없다고 게이트가
막히면, 사람은 검사를 지우는 쪽을 택한다. 컨테이너 게이트(`docker compose run --rm test`)
가 DB 를 띄우고 이 검사를 실제로 돌린다.

여기서 보는 것은 계약이 아니라 **흐름**이다 — 티켓을 받아 제출하면 서버가 재시뮬해서
결과를 확정하는가, 같은 티켓을 두 번 쓸 수 있는가, 남의 티켓으로 제출할 수 있는가.
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


@pytest.fixture
def client():
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as running:
        yield running


@pytest.fixture
def token(client):
    response = client.post("/api/account")
    assert response.status_code == 200
    return response.json()["token"]


def build_headers(token):
    return {"X-Game-Token": token}


def test_health_reports_core_version(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["core_version"].startswith("b")


def test_account_token_is_returned_only_once(client, token):
    """평문 토큰은 만들 때만 나온다. 서버는 해시만 갖는다."""
    body = client.get("/api/account", headers=build_headers(token)).json()
    assert body["token"] is None


def test_unknown_token_is_rejected(client):
    assert client.get("/api/account", headers=build_headers("nope")).status_code == 401


def test_missing_token_is_rejected(client):
    assert client.get("/api/account").status_code == 401


def test_ticket_carries_a_server_seed(client, token):
    """★ 시드는 서버가 정한다. 요청에 시드가 없다."""
    body = client.post(
        "/api/ticket", json={"room_id": ROOM_ID}, headers=build_headers(token)
    ).json()
    assert body["seed"] >= 0
    assert body["room_id"] == ROOM_ID
    assert body["mode"] == "PRACTICE"


def test_unknown_room_is_rejected(client, token):
    response = client.post("/api/ticket", json={"room_id": "nope"}, headers=build_headers(token))
    assert response.status_code == 400


def test_submission_is_resimulated(client, token):
    """★ 서버가 결과를 만든다. 제출에는 결과가 없다."""
    headers = build_headers(token)
    ticket = client.post("/api/ticket", json={"room_id": ROOM_ID}, headers=headers).json()
    response = client.post(
        "/api/run",
        json={
            "ticket_id": ticket["ticket_id"],
            "ruleset": {"ruleset_id": "empty", "version": 1, "rules": []},
            "core_version": ticket["core_version"],
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "verified"
    # 빈 규칙표는 폴백으로 돈다. 무엇이 나오든 서버가 정한 값이어야 한다.
    assert body["ticks"] > 0


def test_a_ticket_cannot_be_used_twice(client, token):
    """★ 같은 티켓으로 두 번 제출할 수 없다 (T6)."""
    headers = build_headers(token)
    ticket = client.post("/api/ticket", json={"room_id": ROOM_ID}, headers=headers).json()
    payload = {
        "ticket_id": ticket["ticket_id"],
        "ruleset": {"ruleset_id": "empty", "version": 1, "rules": []},
        "core_version": ticket["core_version"],
    }
    assert client.post("/api/run", json=payload, headers=headers).status_code == 200
    assert client.post("/api/run", json=payload, headers=headers).status_code == 409


def test_another_account_cannot_use_the_ticket(client, token):
    """★ 남의 티켓으로 제출할 수 없다."""
    ticket = client.post(
        "/api/ticket", json={"room_id": ROOM_ID}, headers=build_headers(token)
    ).json()
    other = client.post("/api/account").json()["token"]
    response = client.post(
        "/api/run",
        json={
            "ticket_id": ticket["ticket_id"],
            "ruleset": {"ruleset_id": "empty", "version": 1, "rules": []},
            "core_version": ticket["core_version"],
        },
        headers=build_headers(other),
    )
    assert response.status_code == 409


def test_version_mismatch_is_rejected_not_simulated(client, token):
    headers = build_headers(token)
    ticket = client.post("/api/ticket", json={"room_id": ROOM_ID}, headers=headers).json()
    body = client.post(
        "/api/run",
        json={
            "ticket_id": ticket["ticket_id"],
            "ruleset": {"ruleset_id": "empty", "version": 1, "rules": []},
            "core_version": "b99.v99.e99",
        },
        headers=headers,
    ).json()
    assert body["verdict"] == "rejected"
    assert "코어 버전" in body["detail"]


def test_broken_ruleset_is_rejected(client, token):
    headers = build_headers(token)
    ticket = client.post("/api/ticket", json={"room_id": ROOM_ID}, headers=headers).json()
    body = client.post(
        "/api/run",
        json={
            "ticket_id": ticket["ticket_id"],
            "ruleset": {"nope": True},
            "core_version": ticket["core_version"],
        },
        headers=headers,
    ).json()
    assert body["verdict"] == "rejected"


def test_meta_round_trips(client, token):
    headers = build_headers(token)
    assert client.get("/api/meta", headers=headers).json()["payload"] is None
    payload = {
        "format": "v1",
        "best_floor": 3,
        "unlocked_perceptions": ["target_distance"],
        "unlocked_actions": ["ATTACK"],
        "bestiary": [],
        "presets": [],
    }
    assert client.put("/api/meta", json={"payload": payload}, headers=headers).status_code == 200
    assert client.get("/api/meta", headers=headers).json()["payload"]["best_floor"] == 3


def test_broken_meta_is_rejected(client, token):
    response = client.put("/api/meta", json={"payload": {"nope": 1}}, headers=build_headers(token))
    assert response.status_code == 400
