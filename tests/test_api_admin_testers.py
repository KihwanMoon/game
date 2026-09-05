"""테스터 표시 라우트 (로드맵 §게이트 G1).

**여기서 지키는 것은 분모다.** G1 은 「테스터 5명 중 3명」을 묻는데 이 게임은 익명으로
시작하므로, 자동으로 세면 접속했다 떠난 계정까지 전부 테스터가 된다 — 실측으로 36명 중
17명이 한 판짜리였고 그것이 평균 재도전을 1.2회로 눌러 놓고 있었다.

표시가 **권한이 아니라는 것**도 여기서 지킨다. 켜도 그 계정에 생기는 것은 통계에
세어진다는 것뿐이고, 관리자 경로가 열리지 않는다.
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


def build_account(client):
    """계정 하나를 만든다.

    Args:
        client: 테스트 클라이언트.

    Returns:
        토큰과 계정 id.
    """
    token = client.post("/api/account").json()["token"]
    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    return token, account_id


def build_admin(client):
    """관리자 토큰 하나를 만든다.

    Args:
        client: 테스트 클라이언트.

    Returns:
        관리자 토큰.
    """
    from game.api.deps import get_pool

    token, account_id = build_account(client)
    with get_pool().connection() as connection:
        connection.execute("UPDATE account SET admin_role = 'owner' WHERE id = %s", (account_id,))
    return token


def find_row(body, account_id):
    """응답에서 그 계정의 줄을 찾는다.

    Args:
        body: 응답 절.
        account_id: 찾을 계정.

    Returns:
        찾은 줄. 없으면 None.
    """
    return next((row for row in body["rows"] if row["account_id"] == account_id), None)


def test_marking_an_account_makes_it_count(client):
    """★ 표시한 계정만 G1 의 분모에 들어간다."""
    admin = build_admin(client)
    _, target = build_account(client)

    before = client.get("/api/admin/testers", headers=build_headers(admin)).json()
    assert find_row(before, target)["is_tester"] is False

    after = client.post(
        "/api/admin/testers/mark",
        json={"account_id": target, "is_tester": True},
        headers=build_headers(admin),
    )
    assert after.status_code == 200
    assert find_row(after.json(), target)["is_tester"] is True
    assert after.json()["marked"] >= 1


def test_a_mark_can_be_taken_back(client):
    """부른 사람이 안 왔으면 뺄 수 있어야 한다 — 못 빼면 분모가 영영 부풀어 있다."""
    admin = build_admin(client)
    _, target = build_account(client)

    client.post(
        "/api/admin/testers/mark",
        json={"account_id": target, "is_tester": True},
        headers=build_headers(admin),
    )
    body = client.post(
        "/api/admin/testers/mark",
        json={"account_id": target, "is_tester": False},
        headers=build_headers(admin),
    ).json()
    assert find_row(body, target)["is_tester"] is False


def test_marking_is_not_a_promotion(client):
    """★ 표시는 권한이 아니다.

    켜도 그 계정에 생기는 것은 통계에 세어진다는 것뿐이다. 관리자 경로가 함께 열리면
    「통계용 표시」 하나가 세계 전체를 여는 열쇠가 된다.
    """
    admin = build_admin(client)
    token, target = build_account(client)

    client.post(
        "/api/admin/testers/mark",
        json={"account_id": target, "is_tester": True},
        headers=build_headers(admin),
    )
    assert client.get("/api/admin/testers", headers=build_headers(token)).status_code == 404
    assert client.get("/api/admin/overview", headers=build_headers(token)).status_code == 404


def test_a_normal_account_cannot_mark_anyone(client):
    """★ 분모를 아무나 바꿀 수 있으면 게이트가 판정이 아니게 된다."""
    token, target = build_account(client)
    response = client.post(
        "/api/admin/testers/mark",
        json={"account_id": target, "is_tester": True},
        headers=build_headers(token),
    )
    assert response.status_code == 404


def test_a_bot_cannot_be_marked(client):
    """★ 봇에 붙으면 G1 이 재는 것이 다시 러너가 된다.

    실측으로 봇을 안 거를 때와 거를 때의 판정이 뒤집혔다 — 「첫 패배 후 재도전」이
    7명(통과)에서 1명(미달)이 됐고, 여섯이 봇이었다.
    """
    from game.api.deps import get_pool

    admin = build_admin(client)
    _, target = build_account(client)
    with get_pool().connection() as connection:
        connection.execute("UPDATE account SET is_bot = TRUE WHERE id = %s", (target,))

    body = client.post(
        "/api/admin/testers/mark",
        json={"account_id": target, "is_tester": True},
        headers=build_headers(admin),
    ).json()
    # 봇은 목록에도 안 나오고, 표시도 안 붙는다.
    assert find_row(body, target) is None
    with get_pool().connection() as connection:
        row = connection.execute(
            "SELECT is_tester FROM account WHERE id = %s", (target,)
        ).fetchone()
    assert row[0] is False


def test_the_list_carries_what_identifies_a_row(client):
    """익명 계정은 번호뿐이다 — 제출 수와 마지막 접속이 없으면 누구인지 짚을 수 없다."""
    admin = build_admin(client)
    _, target = build_account(client)
    row = find_row(client.get("/api/admin/testers", headers=build_headers(admin)).json(), target)
    assert set(row) == {
        "account_id",
        "handle",
        "login_id",
        "is_tester",
        "attempts",
        "last_seen",
    }


def test_the_bar_comes_from_the_server(client):
    """★ 기준 인원을 화면에 박지 않는다.

    두 곳에 적으면 로드맵을 고쳤을 때 한쪽만 따라가고, 그러면 같은 게이트가 두 기준으로
    판정된다. 봇의 `max_runs_per_hour` 와 같은 규약이다.
    """
    from game.app.store.testers import MIN_TESTERS

    admin = build_admin(client)
    body = client.get("/api/admin/testers", headers=build_headers(admin)).json()
    assert body["min_testers"] == MIN_TESTERS


def test_marking_is_written_to_the_ledger(client):
    """★ 분모를 바꾸는 일이므로 누가 언제 했는지가 남아야 한다."""
    from game.api.deps import get_pool

    admin = build_admin(client)
    _, target = build_account(client)
    client.post(
        "/api/admin/testers/mark",
        json={"account_id": target, "is_tester": True},
        headers=build_headers(admin),
    )
    with get_pool().connection() as connection:
        row = connection.execute(
            "SELECT count(*) FROM admin_action WHERE action = 'tester_mark' AND target = %s",
            (f"account:{target}",),
        ).fetchone()
    assert row[0] == 1
