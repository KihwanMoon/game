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


def build_meta_payload(**overrides):
    """메타 세이브 절 하나. 덮어쓸 것만 넘긴다."""
    payload = {
        "format": "v1",
        "best_floor": 0,
        "unlocked_perceptions": [],
        "unlocked_actions": [],
        "bestiary": [],
        "presets": [],
    }
    payload.update(overrides)
    return payload


def test_presets_round_trip(client, token):
    """★ 프리셋은 유저가 지은 것이라 그대로 오간다.

    판정할 것이 없으므로 서버가 내용을 볼 이유도 없다.
    """
    headers = build_headers(token)
    assert client.get("/api/meta", headers=headers).json()["payload"] is None
    preset = {"name": "내 것", "ruleset": {"ruleset_id": "mine", "version": 1, "rules": []}}
    payload = build_meta_payload(presets=[preset])
    assert client.put("/api/meta", json={"payload": payload}, headers=headers).status_code == 200
    stored = client.get("/api/meta", headers=headers).json()["payload"]
    assert [item["name"] for item in stored["presets"]] == ["내 것"]


def test_the_client_cannot_write_achievements(client, token):
    """★ **해금·도감·최고 층은 클라이언트가 쓸 수 없다.**

    이것이 열려 있으면 도감을 다 채우고 층 기록을 올려 규칙 슬롯 상한까지 늘릴 수 있고,
    그러면 이 세이브는 순위의 근거가 될 수 없다. 성취는 `/api/run` 의 재시뮬이 뽑는다.
    """
    headers = build_headers(token)
    payload = build_meta_payload(
        best_floor=99,
        unlocked_actions=["ATTACK", "SUMMON"],
        unlocked_perceptions=["target_distance"],
        bestiary=[{"kind_id": "goblin_rusher", "encounters": 50, "defeats": 50}],
    )
    client.put("/api/meta", json={"payload": payload}, headers=headers)
    stored = client.get("/api/meta", headers=headers).json()["payload"]
    assert stored["best_floor"] == 0
    assert stored["unlocked_actions"] == []
    assert stored["unlocked_perceptions"] == []
    assert stored["bestiary"] == []


def test_rejecting_achievements_does_not_lose_presets(client, token):
    """★ 성취를 버리면서 프리셋까지 버리면 그 사람은 규칙표를 잃는다.

    구버전 클라이언트는 둘을 함께 보낸다 — 400 으로 거절하지 않는 이유가 이것이다.
    """
    headers = build_headers(token)
    preset = {"name": "함께", "ruleset": {"ruleset_id": "mine", "version": 1, "rules": []}}
    payload = build_meta_payload(best_floor=99, presets=[preset])
    client.put("/api/meta", json={"payload": payload}, headers=headers)
    stored = client.get("/api/meta", headers=headers).json()["payload"]
    assert stored["best_floor"] == 0
    assert [item["name"] for item in stored["presets"]] == ["함께"]


def test_broken_meta_is_rejected(client, token):
    response = client.put("/api/meta", json={"payload": {"nope": 1}}, headers=build_headers(token))
    assert response.status_code == 400


def test_practice_ticket_honours_the_requested_seed(client, token):
    """연습 티켓은 시드를 제안받는다 — "이 시드 다시" 가 성립해야 한다."""
    body = client.post(
        "/api/ticket",
        json={"room_id": ROOM_ID, "seed": 4242},
        headers=build_headers(token),
    ).json()
    assert body["seed"] == 4242


def test_ticket_without_a_seed_gets_a_server_one(client, token):
    seeds = {
        client.post("/api/ticket", json={"room_id": ROOM_ID}, headers=build_headers(token)).json()[
            "seed"
        ]
        for _ in range(5)
    }
    # 서버가 정하면 매번 같을 수 없다.
    assert len(seeds) > 1


def test_forced_seed_is_server_authoritative(client, token):
    """★ 서버가 정한 시드와 클라이언트가 제안한 시드를 가른다.

    데일리는 모두가 같은 시드를 받아야 성립하는데, 그것은 클라이언트가 고른 것이 아니라
    서버가 날짜에서 파생한 값이므로 T2 와 무관하다. 둘을 한 인자로 두면 "누가 정했는가"
    가 흐려지고, 그 구분이 이 게이트의 전부다.
    """
    from game.api.deps import get_pool
    from game.app.store.tickets import create_ticket
    from game.schemas.run_ticket import RunMode

    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    # 순위 모드라도 서버가 정한 시드는 그대로 쓴다.
    ranked = create_ticket(
        get_pool(), account_id, ROOM_ID, "b5.v2.e1", mode=RunMode.DAILY, forced_seed=4321
    )
    assert ranked.seed == 4321
    # 클라이언트 제안은 순위 모드에서 무시된다.
    proposed = create_ticket(
        get_pool(), account_id, ROOM_ID, "b5.v2.e1", mode=RunMode.DAILY, wanted_seed=4321
    )
    assert proposed.seed != 4321


def test_the_draft_survives_a_round_trip(client, token):
    """★ 초안을 서버가 버리면 기기를 바꿀 때 규칙이 사라진다.

    올리는 쪽·받는 쪽·화면을 다 고쳐도, 여기서 버리면 아무 소용이 없다 — 실제로 그
    상태였다. 프리셋만 얹고 초안은 버리고 있었다.
    """
    import json

    from game.config import G0_RULESETS_PATH

    raw = json.loads(G0_RULESETS_PATH.read_text(encoding="utf-8"))
    kite = next(item for item in raw["rulesets"] if item["ruleset_id"] == "g0_kite")
    payload = {
        "format": "v1",
        "best_floor": 0,
        "unlocked_perceptions": [],
        "unlocked_actions": [],
        "bestiary": [],
        "presets": [],
        "draft": kite,
    }
    headers = {"X-Game-Token": token}
    assert client.put("/api/meta", json={"payload": payload}, headers=headers).status_code == 200
    stored = client.get("/api/meta", headers=headers).json()["payload"]
    assert stored["draft"] is not None, "서버가 초안을 버렸다"
    assert len(stored["draft"]["rules"]) == len(kite["rules"])


def test_an_achievement_is_still_refused(client, token):
    """★ 초안을 받게 됐다고 해금까지 받으면 안 된다 — 그것이 예전의 구멍이었다."""
    headers = {"X-Game-Token": token}
    payload = {
        "format": "v1",
        "best_floor": 99,
        "unlocked_perceptions": ["self_hp_percent"],
        "unlocked_actions": ["ATTACK"],
        "bestiary": [],
        "presets": [],
        "draft": None,
    }
    client.put("/api/meta", json={"payload": payload}, headers=headers)
    stored = client.get("/api/meta", headers=headers).json()["payload"]
    assert stored["best_floor"] != 99
    assert stored["unlocked_actions"] == []
