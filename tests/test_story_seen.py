"""장 카드를 본 기록 — 계정에 붙는다 (2026-09-16).

**세션 안에서만 기억하던 때는 새로고침하면 1장 카드가 다시 떴다.** 이야기는 한 번 읽는
것이라 두 번째부터는 방해다.

여기서 지키는 것은 넷이다.

1. **계정에 붙는다.** 기기가 아니라 계정이라, 옮겨도 다시 안 뜬다.
2. **두 번 와도 한 줄이다.** 같은 카드를 두 번 닫아도 충돌하지 않는다.
3. **카드 id 를 검사하지 않는다.** 이야기 목록의 정본은 화면이고, 서버가 그것을 알면
   이야기를 하나 더할 때마다 양쪽을 고쳐야 한다.
4. **남의 기록을 안 본다.** 토큰이 가리키는 계정의 것만 나온다.
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


def build_token(client):
    return client.post("/api/account").json()["token"]


def test_a_fresh_account_has_read_nothing(client):
    """★ 처음 온 사람에게는 전부 새 이야기다."""
    token = build_token(client)

    response = client.get("/api/story/seen", headers=build_headers(token))

    assert response.status_code == 200
    assert response.json()["seen"] == []


def test_a_card_stays_read(client):
    """★ 한 번 읽으면 계속 읽은 것이다 — 새로고침해도 다시 안 뜬다."""
    token = build_token(client)

    client.post("/api/story/seen", json={"card_id": "floor:1"}, headers=build_headers(token))
    again = client.get("/api/story/seen", headers=build_headers(token))

    assert again.json()["seen"] == ["floor:1"]


def test_reading_twice_keeps_one_row(client):
    """★ 같은 카드를 두 번 닫아도 한 줄이다 — 두 화면이 동시에 닫을 수 있다."""
    token = build_token(client)

    for _step in range(3):
        client.post("/api/story/seen", json={"card_id": "shadow"}, headers=build_headers(token))

    assert client.get("/api/story/seen", headers=build_headers(token)).json()["seen"] == ["shadow"]


def test_an_unknown_card_is_kept(client):
    """★ 모르는 카드 id 도 담는다.

    이야기 목록의 정본은 화면이다. 서버가 그것을 검사하면 이야기를 하나 더할 때마다 양쪽을
    고쳐야 하고, 담기는 것은 판정에 아무 영향이 없는 문자열 하나다.
    """
    token = build_token(client)

    client.post("/api/story/seen", json={"card_id": "floor:99"}, headers=build_headers(token))

    assert "floor:99" in client.get("/api/story/seen", headers=build_headers(token)).json()["seen"]


def test_one_account_does_not_see_another(client):
    """★ 남의 읽음이 내 것이 되면 안 된다 — 첫 장을 못 읽고 지나간다."""
    mine = build_token(client)
    theirs = build_token(client)
    client.post("/api/story/seen", json={"card_id": "floor:4"}, headers=build_headers(theirs))

    assert client.get("/api/story/seen", headers=build_headers(mine)).json()["seen"] == []


def test_it_needs_a_token(client):
    """★ 계정에 붙는 기록이라 토큰 없이는 못 본다."""
    assert client.get("/api/story/seen").status_code in (401, 422)
