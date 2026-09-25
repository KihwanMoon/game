"""알림함 (2026-09-25).

여기서 지키는 것은 넷이다.

1. **제출이 알림을 남긴다.** 보상 줄이 다음 판에 덮여도 알림은 읽을 때까지 남는다.
2. **본문은 서버가 확정한 보상 줄 그대로다** — 화면이 다시 짜면 실제와 다른 말을 한다.
3. **읽음은 id 로 끊는다.** 알림함을 여는 사이 도착한 것까지 읽음이 되면 안 된다.
4. **내 것만 본다.**
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

fastapi_testclient = pytest.importorskip("fastapi.testclient")

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)

EMPTY_RULESET = {"ruleset_id": "empty", "version": 1, "rules": []}


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


def submit_losing_run(client, token):
    """규칙이 없는 표로 판 하나를 내고 진다.

    Args:
        client: 테스트 클라이언트.
        token: 기기 토큰.

    Returns:
        제출 응답 절.
    """
    ticket = client.post(
        "/api/ticket", json={"room_id": "open_field"}, headers=build_headers(token)
    ).json()
    answer = client.post(
        "/api/run",
        json={
            "ticket_id": ticket["ticket_id"],
            "ruleset": EMPTY_RULESET,
            "core_version": ticket["core_version"],
            "floor": 1,
        },
        headers=build_headers(token),
    )
    assert answer.status_code == 200, answer.text
    return answer.json()


def test_a_submission_leaves_an_unread_notice(client, token):
    """★ 판이 끝나면 알림 한 건이 안 읽은 채로 남고, 본문은 응답의 보상 줄 그대로다."""
    answer = submit_losing_run(client, token)

    board = client.get("/api/notices", headers=build_headers(token)).json()

    assert board["unread"] == 1
    notice = board["notices"][0]
    assert notice["is_read"] is False
    assert notice["kind"] == "run"
    assert "1장" in notice["title"]
    assert notice["body"] == answer["reward"]


def test_reading_stops_at_the_id_the_screen_saw(client, token):
    """★ 화면이 본 id 까지만 읽음이 된다 — 그 뒤에 온 것은 안 읽은 채다."""
    submit_losing_run(client, token)
    seen = client.get("/api/notices", headers=build_headers(token)).json()["notices"][0]["id"]
    submit_losing_run(client, token)

    board = client.post(
        "/api/notices/read", json={"up_to_id": seen}, headers=build_headers(token)
    ).json()

    assert board["unread"] == 1
    assert [row["is_read"] for row in board["notices"]] == [False, True]


def test_notices_are_mine_only(client, token):
    """★ 남의 알림이 보이면 알림함이 아니라 남의 기록이다."""
    submit_losing_run(client, token)
    other = client.post("/api/account").json()["token"]

    board = client.get("/api/notices", headers=build_headers(other)).json()

    assert board == {"unread": 0, "total": 0, "offset": 0, "notices": []}


def test_reading_someone_elses_ids_touches_nothing(client, token):
    """★ 남의 id 를 적어 보내도 내 것만 건드린다."""
    submit_losing_run(client, token)
    other = client.post("/api/account").json()["token"]

    client.post("/api/notices/read", json={"up_to_id": 10**9}, headers=build_headers(other))

    assert client.get("/api/notices", headers=build_headers(token)).json()["unread"] == 1


def test_notices_come_ten_to_a_page(client, token):
    """★ 한 쪽에 열 건이고, 쪽을 넘기면 그다음 것이 온다 (2026-09-25 요청).

    안 읽은 수와 전체 수는 쪽과 무관하게 전체를 센다 — 쪽 수를 화면이 이것으로 센다.
    """
    from game.api.deps import get_pool
    from game.app.store.notices import KIND_FLOOR, save_notice

    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    for step in range(12):
        save_notice(get_pool(), account_id, KIND_FLOOR, f"{step + 1}장 돌파", "")

    first = client.get("/api/notices", headers=build_headers(token)).json()
    second = client.get("/api/notices", params={"offset": 10}, headers=build_headers(token)).json()

    assert [len(first["notices"]), len(second["notices"])] == [10, 2]
    assert first["notices"][0]["title"] == "12장 돌파"
    assert second["notices"][-1]["title"] == "1장 돌파"
    assert (first["total"], first["unread"], second["offset"]) == (12, 12, 10)
