"""방별 상시 기록 (2026-09-25).

여기서 지키는 것은 넷이다.

1. **같은 방은 같은 싸움이다.** 누가 받든 시드·몸·방이 같아야 기록이 비교된다.
2. **값은 전부 서버가 낸다** (설계/7_변조방지 §4). CPU·줄 수는 검증기를 지난 규칙표에서,
   틱은 재시뮬에서 — 제출에는 결과를 받을 칸이 없다.
3. **더 나은 기록만 덮는다.** 순서는 CPU → 틱 → 줄 수. 진 판은 아무것도 안 적는다.
4. **세계에 아무것도 안 남긴다.** 시드가 고정이라 보상을 주면 그것이 곧 파밍 고리다.
"""

import json
import os

import pytest

from game.api.record_service import build_record_seed
from game.app.simulation.phases import OUTCOME_PLAYER_WIN
from game.app.store.connection import DATABASE_URL_ENV
from game.app.store.runs import VERDICT_VERIFIED
from game.config import BENCHMARK_RULESETS_PATH, G0_RULESETS_PATH
from game.schemas.run_ticket import MAX_SEED

ROOM_ID = "open_field"
FIELDS = ("ruleset_id", "version", "rules")


def test_the_record_seed_is_the_same_for_everyone():
    """★ 방과 코어 버전이 같으면 같은 시드다 — 모두가 같은 판을 받아야 비교가 된다."""
    assert build_record_seed(ROOM_ID, "b1.v1") == build_record_seed(ROOM_ID, "b1.v1")
    assert 0 <= build_record_seed(ROOM_ID, "b1.v1") <= MAX_SEED


def test_the_record_seed_moves_with_the_room_and_the_core():
    """★ 방이 다르거나 밸런스가 바뀌면 다른 판이다."""
    base = build_record_seed(ROOM_ID, "b1.v1")
    assert build_record_seed("corridor", "b1.v1") != base
    assert build_record_seed(ROOM_ID, "b1.v2") != base


needs_database = pytest.mark.skipif(
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


def load_payloads():
    """출고 규칙표들을 제출 절 모양으로 읽는다.

    Returns:
        (id, 절) 쌍들.
    """
    payloads = []
    for path in (G0_RULESETS_PATH, BENCHMARK_RULESETS_PATH):
        for raw in json.loads(path.read_text(encoding="utf-8"))["rulesets"]:
            payloads.append((raw["ruleset_id"], {key: raw[key] for key in FIELDS}))
    return payloads


def submit_record(client, token, payload):
    """기록 도전 하나를 받고 낸다.

    Args:
        client: 테스트 클라이언트.
        token: 기기 토큰.
        payload: 규칙표 절.

    Returns:
        (티켓 절, 응답 절).
    """
    ticket = client.post(
        "/api/record/ticket", json={"room_id": ROOM_ID}, headers=build_headers(token)
    ).json()
    answer = client.post(
        "/api/run",
        json={
            "ticket_id": ticket["ticket_id"],
            "ruleset": payload,
            "core_version": ticket["core_version"],
        },
        headers=build_headers(token),
    )
    assert answer.status_code == 200, answer.text
    return ticket, answer.json()


def read_board(client, token):
    return client.get(
        "/api/records", params={"room_id": ROOM_ID}, headers=build_headers(token)
    ).json()


@needs_database
def test_two_people_get_the_same_fight(client, token):
    """★ 누가 받든 방 하나·같은 시드·같은 몸·그림자 없음이다."""
    other = client.post("/api/account").json()["token"]
    mine = client.post(
        "/api/record/ticket", json={"room_id": ROOM_ID}, headers=build_headers(token)
    ).json()
    theirs = client.post(
        "/api/record/ticket", json={"room_id": ROOM_ID}, headers=build_headers(other)
    ).json()

    assert mine["seed"] == theirs["seed"]
    assert mine["mode"] == "RECORD"
    assert mine["room_ids"] == [ROOM_ID]
    assert mine["rooms_per_floor"] == 0
    assert mine["monster_snapshot"] == []
    # **몸도 같다.** 비워 두면 브라우저가 검증 안 된 로컬 경로로 돌므로 명시해서 싣는다.
    assert mine["loadout"] is not None
    assert mine["loadout"] == theirs["loadout"]


@needs_database
def test_the_board_keeps_only_the_best_winning_run(client, token):
    """★ 여러 표를 내면 이긴 것 중 CPU → 틱 → 줄 수가 가장 작은 것 하나만 남는다.

    **값을 제출에서 안 읽는다** — 응답의 틱은 재시뮬 값이고, CPU 는 규칙표에서 센다.
    """
    wins = []
    for _name, payload in load_payloads():
        _ticket, body = submit_record(client, token, payload)
        if body["verdict"] == VERDICT_VERIFIED and body["outcome"] == OUTCOME_PLAYER_WIN:
            cpu = sum(rule["cpu_cost"] for rule in payload["rules"])
            wins.append((cpu, body["ticks"], len(payload["rules"])))
        else:
            assert "새 기록" not in body["reward"]
    assert wins, "출고 규칙표 중 하나는 너른 마당을 이겨야 이 검사가 볼 것이 생긴다"

    # **내 줄만 본다.** 검사 DB 는 세션 처음에만 비워지므로 윗자리에는 다른 검사의 기록이 있다.
    mine = read_board(client, token)["mine"]

    assert (mine["cpu"], mine["ticks"], mine["rule_count"]) == min(wins)


@needs_database
def test_a_losing_run_writes_nothing(client, token):
    """★ 규칙이 없는 표는 진다 — 진 판은 「적게 써서 풀었다」가 아니다."""
    _ticket, body = submit_record(client, token, {"ruleset_id": "empty", "version": 1, "rules": []})

    assert body["outcome"] != OUTCOME_PLAYER_WIN
    assert read_board(client, token)["mine"] is None


@needs_database
def test_a_record_run_leaves_nothing_in_the_world(client, token):
    """★ 기록 도전은 푼·경험치를 안 준다 — 고정 시드에 보상을 주면 파밍 고리다."""
    headers = build_headers(token)
    before = client.get("/api/wallet", headers=headers).json()["balance"]
    for _name, payload in load_payloads():
        submit_record(client, token, payload)

    assert client.get("/api/progress", headers=headers).json()["total_xp"] == 0
    assert client.get("/api/wallet", headers=headers).json()["balance"] == before
