"""스킬 세팅 — 장비가 연 스킬을 끌 수 있다 (결정 #13 확장).

**빼기만 한다.** 더하기가 되면 장비 없이 스킬을 켜는 길이 생기고 로드아웃 동결이 뚫린다.

여기서 지키는 것은 넷이다.

1. **기본 공격은 못 끈다.** 끄면 규칙표가 전부 불가일 때 폴백조차 못 때린다.
2. **꺼도 로드아웃에서만 빠진다.** 장비가 안 연 스킬은 꺼짐 목록에 있어도 아무 일 없다.
3. **티켓이 그 결과를 싣는다** — 이번 런은 얼려져 있고 다음 티켓부터다.
4. **기본은 전부 켬이다.**
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
    """서버 하나."""
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as running:
        yield running


@pytest.fixture
def token(client):
    """새 계정의 토큰."""
    return client.post("/api/account").json()["token"]


def build_headers(token):
    """토큰을 헤더로.

    Args:
        token: 계정 토큰.

    Returns:
        요청 헤더.
    """
    return {"X-Game-Token": token}


def test_the_default_is_all_on(client, token):
    """★ 기본이 끔이면 아무도 안 켠 스킬로 첫 판을 돈다."""
    body = client.get("/api/skills", headers=build_headers(token)).json()
    assert body["rows"], "기본 스킬 줄이 비었다"
    assert all(row["is_on"] for row in body["rows"])
    locked = [row for row in body["rows"] if row["is_locked"]]
    assert [row["skill_id"] for row in locked] == ["ATTACK"]


def test_attack_cannot_be_turned_off(client, token):
    """★ 기본 공격을 끄면 폴백조차 못 때려 맨몸으로 서서 죽는다."""
    headers = build_headers(token)
    body = client.put(
        "/api/skills",
        json={"rows": [{"skill_id": "ATTACK", "is_on": False}]},
        headers=headers,
    ).json()
    attack = next(row for row in body["rows"] if row["skill_id"] == "ATTACK")
    assert attack["is_on"], "기본 공격이 꺼졌다"


def test_a_disabled_skill_leaves_the_ticket(client, token):
    """★ 꺼짐이 티켓에 안 실리면 세팅이 화면 장식이다."""
    from game.schemas.loadout import parse_loadout

    headers = build_headers(token)
    client.put(
        "/api/skills",
        json={"rows": [{"skill_id": "SKILL_2", "is_on": False}]},
        headers=headers,
    )
    issued = client.post("/api/ticket", json={"room_id": "open_field"}, headers=headers).json()
    skills = parse_loadout(issued["loadout"]).skills
    assert "SKILL_2" not in skills
    assert "ATTACK" in skills and "SKILL_1" in skills
