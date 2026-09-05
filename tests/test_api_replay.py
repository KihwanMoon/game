"""내 판을 다시 돌린다 (결정 #09).

여기서 지키는 것은 셋이다.

1. **내 것만 본다.** 제출 id 를 훑어 남의 규칙표를 읽는 길이 되면 안 된다.
2. **없는 것과 남의 것이 같아 보인다.** 404 가 갈리면 그 차이만으로 남의 제출 범위를
   알아낼 수 있다.
3. **나가는 값은 전부 티켓의 것이다** (설계/7_변조방지 §4). 제출이 실어 온 것은 규칙표
   하나뿐이고, 재생이 재생이려면 나머지가 전부 서버가 얼려 둔 값이어야 한다.
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
    return client.post("/api/account").json()["token"]


def build_headers(token):
    return {"X-Game-Token": token}


def build_submission(client, token):
    """판 하나를 제출하고 그 제출 id 를 낸다.

    Args:
        client: 테스트 클라이언트.
        token: 기기 토큰.

    Returns:
        (제출 id, 티켓 절).
    """
    ticket = client.post(
        "/api/ticket", json={"room_id": ROOM_ID}, headers=build_headers(token)
    ).json()
    answer = client.post(
        "/api/run",
        json={
            "ticket_id": ticket["ticket_id"],
            "ruleset": {"ruleset_id": "probe", "version": 1, "rules": []},
            "core_version": ticket["core_version"],
        },
        headers=build_headers(token),
    )
    assert answer.status_code == 200, answer.text
    return int(answer.json()["submission_id"]), ticket


def test_the_history_lists_my_runs(client, token):
    """★ 돈 판이 목록에 남아야 다시 볼 수 있다."""
    submission_id, _ticket = build_submission(client, token)

    body = client.get("/api/runs", headers=build_headers(token)).json()

    assert [row["submission_id"] for row in body["runs"]] == [submission_id]
    assert body["runs"][0]["room_id"] == ROOM_ID


def test_the_history_shows_only_mine(client, token):
    """★ 남의 판이 섞이면 목록이 아니라 남의 기록이다."""
    build_submission(client, token)
    other = client.post("/api/account").json()["token"]

    body = client.get("/api/runs", headers=build_headers(other)).json()

    assert body["runs"] == []


def test_the_replay_carries_the_ticket_inputs(client, token):
    """★ 결과가 아니라 **입력**을 준다 — 그것으로 다시 돌려야 재생이다."""
    submission_id, ticket = build_submission(client, token)

    body = client.get(
        f"/api/replay?submission_id={submission_id}", headers=build_headers(token)
    ).json()

    assert body["submission_id"] == submission_id
    # 전부 티켓이 얼려 둔 값이다. 하나라도 클라이언트에서 오면 재생이 재생이 아니다.
    assert body["seed"] == ticket["seed"]
    assert body["room_id"] == ticket["room_id"]
    assert body["floor"] == ticket["floor"]
    assert body["room_ids"] == ticket["room_ids"]
    # 규칙표는 제출이 실어 온 유일한 값이다.
    assert body["ruleset"]["ruleset_id"] == "probe"


def test_i_cannot_replay_someone_elses_run(client, token):
    """★ 제출 id 를 훑어 남의 규칙표를 읽는 길이 되면 안 된다.

    **없는 것과 같은 응답이어야 한다.** 404 가 갈리면 그 차이만으로 남의 제출 범위를
    알아낼 수 있다.
    """
    submission_id, _ticket = build_submission(client, token)
    other = client.post("/api/account").json()["token"]

    stolen = client.get(f"/api/replay?submission_id={submission_id}", headers=build_headers(other))
    missing = client.get("/api/replay?submission_id=999999999", headers=build_headers(other))

    assert stolen.status_code == 404
    assert missing.status_code == 404
    assert stolen.json()["detail"] == missing.json()["detail"].replace(
        "999999999", str(submission_id)
    )


def test_the_replay_needs_a_token(client, token):
    """★ 토큰 없이 열려 있으면 그 자체로 끝이다."""
    submission_id, _ticket = build_submission(client, token)

    assert client.get(f"/api/replay?submission_id={submission_id}").status_code in {401, 403, 422}
    assert client.get("/api/runs").status_code in {401, 403, 422}
