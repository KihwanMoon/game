"""가입·로그인과 승격 (인증).

여기서 지키는 것은 넷이다.

1. **익명 계정이 승격된다.** 토큰을 들고 가입하면 계정 id 가 그대로라 진행이 따라온다.
   새 계정을 만들어 옮기는 구조였다면 그 이관이 매번 필요했을 것이다.
2. **한 계정은 한 기기다** (개정 2026-09-01). 다른 기기에서 로그인하면 그 계정을
   불러오고, **기존 기기는 튕긴다** — 상태가 두 벌 돌면 나중에 저장한 쪽이 앞의 것을 덮고,
   쓰는 사람에게 그것은 "규칙이 사라졌다" 로 보인다.
3. **아이디 존재 여부가 새지 않는다.** 모르는 아이디와 틀린 비밀번호가 같은 오류다.
4. **비밀번호 평문이 저장되지 않는다.**
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

fastapi_testclient = pytest.importorskip("fastapi.testclient")

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)

PASSWORD = "correct horse battery"
OTHER_PASSWORD = "another passphrase"


@pytest.fixture
def client():
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as running:
        yield running


def build_headers(token):
    return {"X-Game-Token": token}


def create_login_id(client):
    """검사마다 겹치지 않는 아이디를 만든다."""
    return f"user{client.post('/api/account').json()['account_id']}"


# ── 승격 ─────────────────────────────────────────────────────────────────


def test_anonymous_account_is_promoted_not_replaced(client):
    """★ 가입해도 계정 id 가 바뀌지 않는다 — 진행이 따라온다."""
    anonymous = client.post("/api/account").json()
    token = anonymous["token"]
    login_id = f"promo{anonymous['account_id']}"

    body = client.post(
        "/api/register",
        json={"login_id": login_id, "password": PASSWORD},
        headers=build_headers(token),
    ).json()
    assert body["account_id"] == anonymous["account_id"]
    assert body["login_id"] == login_id
    # 원래 토큰이 그대로 쓰인다.
    assert body["token"] == token


def test_progress_survives_registration(client):
    """★ 승격 전에 쌓은 세이브가 가입 뒤에도 있다."""
    anonymous = client.post("/api/account").json()
    headers = build_headers(anonymous["token"])
    # 성취가 아니라 **프리셋**으로 잰다. 성취는 서버가 재시뮬에서 뽑으므로 PUT 으로
    # 심을 수 없다 — 승계가 되는지는 유저가 지은 것으로 확인해야 한다.
    payload = {
        "format": "v1",
        "best_floor": 0,
        "unlocked_perceptions": [],
        "unlocked_actions": [],
        "bestiary": [],
        "presets": [{"name": "승계", "ruleset": {"ruleset_id": "mine", "version": 1, "rules": []}}],
    }
    client.put("/api/meta", json={"payload": payload}, headers=headers)

    client.post(
        "/api/register",
        json={"login_id": f"keep{anonymous['account_id']}", "password": PASSWORD},
        headers=headers,
    )
    kept = client.get("/api/meta", headers=headers).json()["payload"]["presets"]
    assert [item["name"] for item in kept] == ["승계"]


def test_registering_twice_is_rejected(client):
    anonymous = client.post("/api/account").json()
    headers = build_headers(anonymous["token"])
    first = f"twice{anonymous['account_id']}"
    assert (
        client.post(
            "/api/register", json={"login_id": first, "password": PASSWORD}, headers=headers
        ).status_code
        == 200
    )
    response = client.post(
        "/api/register", json={"login_id": f"{first}b", "password": PASSWORD}, headers=headers
    )
    assert response.status_code == 409


def test_taken_login_id_is_rejected(client):
    login_id = create_login_id(client)
    client.post("/api/register", json={"login_id": login_id, "password": PASSWORD})
    response = client.post("/api/register", json={"login_id": login_id, "password": PASSWORD})
    assert response.status_code == 409


def test_login_id_is_case_folded(client):
    """Alice 와 alice 가 다른 계정이면 사람은 자기 계정에 못 들어간다."""
    login_id = create_login_id(client)
    client.post("/api/register", json={"login_id": login_id, "password": PASSWORD})
    response = client.post(
        "/api/register", json={"login_id": login_id.upper(), "password": PASSWORD}
    )
    assert response.status_code == 409


def test_registration_without_token_creates_an_account(client):
    body = client.post(
        "/api/register", json={"login_id": create_login_id(client), "password": PASSWORD}
    ).json()
    assert body["token"]
    assert client.get("/api/account", headers=build_headers(body["token"])).status_code == 200


@pytest.mark.parametrize(
    ("login_id", "password"),
    [("ab", PASSWORD), ("has space", PASSWORD), ("한글아이디", PASSWORD), ("ok_id", "short")],
)
def test_bad_credentials_are_rejected(client, login_id, password):
    response = client.post("/api/register", json={"login_id": login_id, "password": password})
    assert response.status_code == 400


# ── 로그인 ───────────────────────────────────────────────────────────────


def test_login_from_another_device_loads_the_account(client):
    """★ 다른 기기에서 로그인하면 그 계정과 세이브를 불러온다."""
    first = client.post("/api/account").json()
    login_id = f"device{first['account_id']}"
    client.post(
        "/api/register",
        json={"login_id": login_id, "password": PASSWORD},
        headers=build_headers(first["token"]),
    )
    # 성취가 아니라 프리셋으로 잰다 — 성취는 PUT 으로 심을 수 없다.
    payload = {
        "format": "v1",
        "best_floor": 0,
        "unlocked_perceptions": [],
        "unlocked_actions": [],
        "bestiary": [],
        "presets": [
            {"name": "다른기기", "ruleset": {"ruleset_id": "mine", "version": 1, "rules": []}}
        ],
    }
    client.put("/api/meta", json={"payload": payload}, headers=build_headers(first["token"]))

    second = client.post("/api/login", json={"login_id": login_id, "password": PASSWORD}).json()
    assert second["account_id"] == first["account_id"]
    # 새 기기 토큰이 나온다.
    assert second["token"] != first["token"]
    loaded = client.get("/api/meta", headers=build_headers(second["token"])).json()["payload"]
    assert [item["name"] for item in loaded["presets"]] == ["다른기기"]


def test_a_second_login_kicks_the_first_device(client):
    """★ 한 계정은 한 기기다 (개정 2026-09-01).

    예전에는 반대였다 — 로그인이 토큰을 하나 더 붙였고 두 기기를 함께 쓸 수 있었다.
    그런데 같은 계정의 상태가 두 벌 돌면 나중에 저장한 쪽이 앞의 것을 덮고, 쓰는 사람에게
    그것은 **"규칙이 사라졌다"** 로 보인다. 실제로 그렇게 보고됐다.

    튕긴 기기는 401 을 받는다. 그 기기가 그 사실을 말해야 한다 — 조용히 익명으로
    떨어지면 자기 것이 남의 것처럼 보인다.
    """
    first = client.post("/api/account").json()
    login_id = f"both{first['account_id']}"
    client.post(
        "/api/register",
        json={"login_id": login_id, "password": PASSWORD},
        headers=build_headers(first["token"]),
    )
    second = client.post("/api/login", json={"login_id": login_id, "password": PASSWORD}).json()
    assert client.get("/api/account", headers=build_headers(first["token"])).status_code == 401
    assert client.get("/api/account", headers=build_headers(second["token"])).status_code == 200


def test_logging_out_drops_only_this_device(client):
    """★ 로그아웃은 이 기기가 그 계정을 그만 보는 것이지 계정이 사라지는 것이 아니다."""
    account = client.post("/api/account").json()
    login_id = f"out{account['account_id']}"
    client.post(
        "/api/register",
        json={"login_id": login_id, "password": PASSWORD},
        headers=build_headers(account["token"]),
    )
    assert client.post("/api/logout", headers=build_headers(account["token"])).status_code == 200
    assert client.get("/api/account", headers=build_headers(account["token"])).status_code == 401
    # 계정은 그대로다 — 다시 로그인하면 돌아온다.
    again = client.post("/api/login", json={"login_id": login_id, "password": PASSWORD})
    assert again.status_code == 200
    assert again.json()["account_id"] == account["account_id"]


def test_logout_does_not_hand_back_a_usable_token(client):
    """★ 더 이상 쓸 수 없는 값을 돌려주면 화면이 그것을 저장한다."""
    account = client.post("/api/account").json()
    body = client.post("/api/logout", headers=build_headers(account["token"])).json()
    assert body["token"] == ""


def test_wrong_password_and_unknown_id_look_the_same(client):
    """★ 가르면 어느 아이디가 존재하는지 알려 주는 조회 도구가 된다."""
    login_id = create_login_id(client)
    client.post("/api/register", json={"login_id": login_id, "password": PASSWORD})

    # 없는 아이디도 **매번 새로 만든다.** 고정 문자열을 쓰면 검사를 여러 번 돌리는 동안
    # 그 아이디에 실패가 쌓여 잠기고(시도 제한이 제대로 도는 것이다), 401 대신 429 가 온다.
    missing = f"nobody{create_login_id(client)}"
    wrong = client.post("/api/login", json={"login_id": login_id, "password": OTHER_PASSWORD})
    unknown = client.post("/api/login", json={"login_id": missing, "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]


def test_account_reports_whether_it_is_registered(client):
    anonymous = client.post("/api/account").json()
    headers = build_headers(anonymous["token"])
    assert client.get("/api/account", headers=headers).json()["login_id"] is None
    client.post(
        "/api/register",
        json={"login_id": f"state{anonymous['account_id']}", "password": PASSWORD},
        headers=headers,
    )
    assert client.get("/api/account", headers=headers).json()["login_id"] is not None


def test_password_is_not_stored_in_plaintext(client):
    """★ 유출된 저장소가 곧 평문 비밀번호이면 안 된다."""
    import psycopg

    from game.app.store.connection import get_database_url

    login_id = create_login_id(client)
    client.post("/api/register", json={"login_id": login_id, "password": PASSWORD})
    with psycopg.connect(get_database_url()) as connection:
        row = connection.execute(
            "SELECT password_hash, password_salt FROM account WHERE login_id = %s", (login_id,)
        ).fetchone()
    assert row is not None
    assert PASSWORD not in str(row[0])
    assert row[1] and row[0] != row[1]


# ── 시도 제한 ────────────────────────────────────────────────────────────


def test_repeated_failures_lock_the_account(client):
    """★ scrypt 만으로는 대량 시도를 못 막는다. 세어서 끊는다."""
    from game.app.store.throttle import MAX_FAILURES

    login_id = create_login_id(client)
    client.post("/api/register", json={"login_id": login_id, "password": PASSWORD})

    for _ in range(MAX_FAILURES):
        response = client.post(
            "/api/login", json={"login_id": login_id, "password": OTHER_PASSWORD}
        )
        assert response.status_code == 401
    # 상한을 넘기면 비밀번호가 맞아도 통과시키지 않는다.
    locked = client.post("/api/login", json={"login_id": login_id, "password": PASSWORD})
    assert locked.status_code == 429


def test_success_clears_the_failure_count(client):
    """오타를 한 번 냈다가 맞춘 사람이 다음에 막히면 안 된다."""
    from game.api.deps import get_pool
    from game.app.store.credentials import normalize_login_id
    from game.app.store.throttle import MAX_FAILURES, count_recent_failures

    login_id = create_login_id(client)
    client.post("/api/register", json={"login_id": login_id, "password": PASSWORD})
    for _ in range(MAX_FAILURES - 1):
        client.post("/api/login", json={"login_id": login_id, "password": OTHER_PASSWORD})
    assert (
        client.post("/api/login", json={"login_id": login_id, "password": PASSWORD}).status_code
        == 200
    )
    assert count_recent_failures(get_pool(), normalize_login_id(login_id)) == 0


def test_locking_one_account_does_not_lock_another(client):
    """한 계정을 잠근다고 다른 계정이 막히면 그것은 서비스 거부 수단이 된다."""
    from game.app.store.throttle import MAX_FAILURES

    victim = create_login_id(client)
    bystander = create_login_id(client)
    for name in (victim, bystander):
        client.post("/api/register", json={"login_id": name, "password": PASSWORD})
    for _ in range(MAX_FAILURES):
        client.post("/api/login", json={"login_id": victim, "password": OTHER_PASSWORD})
    assert (
        client.post("/api/login", json={"login_id": victim, "password": PASSWORD}).status_code
        == 429
    )
    assert (
        client.post("/api/login", json={"login_id": bystander, "password": PASSWORD}).status_code
        == 200
    )
