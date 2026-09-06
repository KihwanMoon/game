"""유저 도플갱어 — 켠 사람만 (2026-09-06).

**기본은 꺼져 있다.** 그림자는 원본의 규칙표로 싸우므로, 관전하며 행동을 보면 남의 해답이
어느 정도 역산된다 — 그러면 베끼는 것이 최선이 되고 P1(실패는 정보다)이 죽는다.

봇은 이 칸을 안 본다. 우리가 들인 것이라 동의를 물을 상대가 없다.
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


def test_it_is_off_by_default(client):
    """★ 켜는 사람이 알고 켜야 한다 — 기본이 켜져 있으면 아무도 안 고른 것이다."""
    account = client.post("/api/account").json()
    body = client.get("/api/account", headers=build_headers(account["token"])).json()
    assert body["doppel_opt_in"] is False


def test_a_person_can_turn_it_on_and_off(client):
    token = client.post("/api/account").json()["token"]
    on = client.put(
        "/api/account/doppel", json={"is_on": True}, headers=build_headers(token)
    ).json()
    assert on["doppel_opt_in"] is True
    off = client.put(
        "/api/account/doppel", json={"is_on": False}, headers=build_headers(token)
    ).json()
    assert off["doppel_opt_in"] is False


def test_it_needs_a_token(client):
    """남의 설정을 바꿀 수 있으면 동의가 동의가 아니다."""
    assert client.put("/api/account/doppel", json={"is_on": True}).status_code in {401, 403, 422}


def test_a_bot_does_not_need_it(client):
    """★ 봇은 이 칸을 안 본다 — 우리가 들인 것이라 동의를 물을 상대가 없다."""
    from pathlib import Path

    source = Path("game/api/doppel_service.py").read_text(encoding="utf-8")
    # 봇이면 통과, 아니면 켰는지 본다. 순서가 뒤집히면 봇이 꺼진 채로 안 서게 된다.
    assert "check_is_bot(pool, account_id) and not check_doppel_opt_in" in source


def test_turning_it_off_does_not_erase_what_already_stands(client):
    """★ 끄는 것은 「앞으로 안 세운다」다.

    지우는 것은 남의 던전에서 개체가 사라지는 일이라 뜻이 다르다 — 목숨을 다 쓰면
    저절로 사라진다.
    """
    from pathlib import Path

    source = Path("game/app/store/doppels.py").read_text(encoding="utf-8")
    body = source[source.index("def apply_doppel_opt_in") :]
    assert "DELETE" not in body.upper().split("def ")[0].upper() or "DELETE" not in body[:900]
