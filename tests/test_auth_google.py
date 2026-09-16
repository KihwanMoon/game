"""구글 로그인 — 서버가 서명을 직접 본다 (설계/7_변조방지 §4, 신설 2026-09-16).

**진짜 구글에 붙지 않는다.** 검사가 제 RSA 키로 토큰을 서명하고, 서버가 볼 공개키만
갈아 끼운다 — 그래서 네트워크 없이 **검증 논리 전체**가 돈다.

여기서 지키는 것은 여섯이다.

1. **클라이언트가 보낸 것을 안 믿는다.** 요청에 이메일도 계정 id 도 받을 자리가 없다.
2. **남의 서명은 안 통한다.** 다른 키로 서명한 토큰은 떨어진다.
3. **다른 앱의 토큰은 안 통한다** (`aud`).
4. **논스는 한 번만 통한다.** 가로챈 토큰을 그대로 다시 보내는 것이 이것으로 막힌다.
5. **익명 계정이 승격된다.** 계정 id 가 그대로라 진행이 따라온다.
6. **이메일로 계정을 잇지 않는다.** 그렇게 이으면 남의 계정을 가져가는 길이 열린다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)

CLIENT_ID = "test-client.apps.googleusercontent.com"


@pytest.fixture
def keys():
    """검사용 RSA 키 두 벌. 하나는 「구글」, 하나는 남이다."""
    from cryptography.hazmat.primitives.asymmetric import rsa

    return {
        "google": rsa.generate_private_key(public_exponent=65537, key_size=2048),
        "other": rsa.generate_private_key(public_exponent=65537, key_size=2048),
    }


@pytest.fixture
def client(monkeypatch, keys):
    """구글 클라이언트 id 를 켜고, 공개키를 검사용 키로 바꾼 서버."""
    fastapi_testclient = pytest.importorskip("fastapi.testclient")

    from game.api import google_identity
    from game.api.main import create_app

    monkeypatch.setenv(google_identity.CLIENT_ID_ENV, CLIENT_ID)

    class FakeKey:
        def __init__(self, private):
            self.key = private.public_key()

    class FakeKeyClient:
        def __init__(self, private):
            self._private = private

        def get_signing_key_from_jwt(self, _token):
            return FakeKey(self._private)

    monkeypatch.setattr(google_identity, "get_key_client", lambda: FakeKeyClient(keys["google"]))
    with fastapi_testclient.TestClient(create_app()) as running:
        yield running


def build_token(
    private,
    *,
    nonce,
    audience=CLIENT_ID,
    issuer="https://accounts.google.com",
    subject="google-sub-1",
):
    """구글이 준 것처럼 생긴 ID 토큰 하나."""
    import time

    import jwt

    now = int(time.time())
    return jwt.encode(
        {
            "iss": issuer,
            "aud": audience,
            "sub": subject,
            "nonce": nonce,
            "iat": now,
            "exp": now + 600,
        },
        private,
        algorithm="RS256",
    )


def read_nonce(client):
    response = client.get("/api/auth/google/nonce")
    assert response.status_code == 200, response.text
    return response.json()["nonce"]


def test_the_request_carries_no_identity(client):
    """★ 요청에 「나는 누구다」를 적을 자리가 없다 — 있으면 적어 보내는 것이 곧 로그인이다."""
    from game.api.schemas import GoogleAuthRequest

    assert set(GoogleAuthRequest.model_fields) == {"credential", "nonce"}


def test_a_good_token_makes_an_account(client, keys):
    """★ 처음 들어오면 계정이 생기고 기기 토큰을 받는다."""
    nonce = read_nonce(client)
    response = client.post(
        "/api/auth/google",
        json={"credential": build_token(keys["google"], nonce=nonce), "nonce": nonce},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["account_id"] > 0
    assert body["token"]


def test_someone_elses_signature_does_not_pass(client, keys):
    """★ 남이 서명한 토큰은 떨어진다 — 서명을 안 보면 아무나 통과한다."""
    nonce = read_nonce(client)
    response = client.post(
        "/api/auth/google",
        json={"credential": build_token(keys["other"], nonce=nonce), "nonce": nonce},
    )
    assert response.status_code == 401


def test_another_apps_token_does_not_pass(client, keys):
    """★ 다른 앱을 위해 발급된 토큰은 떨어진다 (`aud`).

    이것을 안 보면, 구글로 로그인하는 **아무 서비스**에서 받은 토큰으로 여기 들어올 수 있다.
    """
    nonce = read_nonce(client)
    token = build_token(
        keys["google"], nonce=nonce, audience="someone-else.apps.googleusercontent.com"
    )
    response = client.post("/api/auth/google", json={"credential": token, "nonce": nonce})
    assert response.status_code == 401


def test_a_forged_issuer_does_not_pass(client, keys):
    """★ 발급자가 구글이 아니면 떨어진다."""
    nonce = read_nonce(client)
    token = build_token(keys["google"], nonce=nonce, issuer="https://evil.example")
    response = client.post("/api/auth/google", json={"credential": token, "nonce": nonce})
    assert response.status_code == 401


def test_a_nonce_works_once(client, keys):
    """★ 같은 논스로 두 번은 안 된다 — 가로챈 토큰을 그대로 다시 보내는 것이 이것으로 막힌다."""
    nonce = read_nonce(client)
    token = build_token(keys["google"], nonce=nonce, subject="google-sub-replay")
    assert (
        client.post("/api/auth/google", json={"credential": token, "nonce": nonce}).status_code
        == 200
    )

    again = client.post("/api/auth/google", json={"credential": token, "nonce": nonce})

    assert again.status_code == 400, "같은 논스가 두 번 통했다"


def test_a_mismatched_nonce_does_not_pass(client, keys):
    """★ 토큰 안의 논스가 서버가 낸 것과 다르면 떨어진다."""
    nonce = read_nonce(client)
    token = build_token(keys["google"], nonce="다른-논스")
    response = client.post("/api/auth/google", json={"credential": token, "nonce": nonce})
    assert response.status_code == 401


def test_an_anonymous_account_is_promoted(client, keys):
    """★ 익명 계정이 승격된다 — 계정 id 가 그대로라 지금까지의 진행이 따라온다."""
    anon = client.post("/api/account").json()
    before = client.get("/api/account", headers={"X-Game-Token": anon["token"]}).json()[
        "account_id"
    ]

    nonce = read_nonce(client)
    token = build_token(keys["google"], nonce=nonce, subject="google-sub-promote")
    response = client.post(
        "/api/auth/google",
        json={"credential": token, "nonce": nonce},
        headers={"X-Game-Token": anon["token"]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["account_id"] == before, "계정이 새로 생겼다 — 진행이 날아간다"


def test_coming_back_lands_on_the_same_account(client, keys):
    """★ 같은 구글 계정은 언제나 같은 계정으로 들어온다."""
    subject = "google-sub-return"
    first_nonce = read_nonce(client)
    first = client.post(
        "/api/auth/google",
        json={
            "credential": build_token(keys["google"], nonce=first_nonce, subject=subject),
            "nonce": first_nonce,
        },
    ).json()

    second_nonce = read_nonce(client)
    second = client.post(
        "/api/auth/google",
        json={
            "credential": build_token(keys["google"], nonce=second_nonce, subject=subject),
            "nonce": second_nonce,
        },
    ).json()

    assert second["account_id"] == first["account_id"]
    assert second["token"] != first["token"], "기기 토큰은 매번 새로 나야 한다"


def test_logging_in_cuts_the_other_device(client, keys):
    """★ 한 계정은 한 기기다 — 두 벌이 돌면 나중에 저장한 쪽이 앞의 것을 덮는다."""
    subject = "google-sub-single"
    first_nonce = read_nonce(client)
    first = client.post(
        "/api/auth/google",
        json={
            "credential": build_token(keys["google"], nonce=first_nonce, subject=subject),
            "nonce": first_nonce,
        },
    ).json()

    second_nonce = read_nonce(client)
    client.post(
        "/api/auth/google",
        json={
            "credential": build_token(keys["google"], nonce=second_nonce, subject=subject),
            "nonce": second_nonce,
        },
    )

    bounced = client.get("/api/account", headers={"X-Game-Token": first["token"]})
    assert bounced.status_code == 401, "앞 기기가 안 끊겼다"


def test_it_is_off_without_a_client_id(monkeypatch, keys):
    """★ 설정이 빠진 채로 배포되면 **막힌다** — 조용히 아무나 통과하는 것보다 낫다."""
    fastapi_testclient = pytest.importorskip("fastapi.testclient")

    from game.api import google_identity
    from game.api.main import create_app

    monkeypatch.delenv(google_identity.CLIENT_ID_ENV, raising=False)
    with fastapi_testclient.TestClient(create_app()) as running:
        assert running.get("/api/auth/google/nonce").status_code == 503
        assert (
            running.post("/api/auth/google", json={"credential": "x", "nonce": "y"}).status_code
            == 503
        )
