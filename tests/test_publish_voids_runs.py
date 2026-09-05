"""발행과 열린 티켓 (설계/9_에이전트_운영 §3.3).

**결백한 사람이 변조자처럼 기록되고 있었다.** 제출의 코어 버전 검사는 클라이언트를
**티켓과만** 대조하고 서버와는 안 한다. 그래서 발행 뒤에 낸 제출은 검사를 통과하는데,
재시뮬은 `get_context()` 즉 **방금 갈아 끼운** 데이터로 돈다 — 결과가 갈리고 `mismatch`
가 난다. 불일치의 원인은 셋(변조·버전 시차·우리 버그)이고 그중 하나가 변조다(결정 #47).

지금은 발행이 드물어 안 드러난다. 에이전트를 붙이면 발행이 잦아지는 것이 요점이라 이것이
상시가 되고, **두 번째 원인이 대량 생산된다.**

고른 길: 발행이 열린 티켓을 **바로 무효로 만든다.** 판은 똑같이 잃지만 잃은 이유가
남는다 — 그 차이가 「변조로 기록됨」과 「발행 때문에 무효」다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

fastapi_testclient = pytest.importorskip("fastapi.testclient")

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)

REASON = "발행 무효 검사"

# 티켓이 가리키는 방. 어느 방이든 되지만 실제로 있는 것이어야 한다.
ROOM_ID = "corridor"


@pytest.fixture
def client():
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as running:
        yield running


def build_headers(token):
    return {"X-Game-Token": token}


def build_player(client):
    """평범한 계정 하나와 티켓 하나를 만든다.

    Args:
        client: 테스트 클라이언트.

    Returns:
        토큰과 티켓 절.
    """
    token = client.post("/api/account").json()["token"]
    ticket = client.post("/api/ticket", json={"room_id": ROOM_ID}, headers=build_headers(token))
    assert ticket.status_code == 200, ticket.json()
    return token, ticket.json()


def test_a_publish_voids_the_open_run(client):
    """★ **이것이 이 변경의 전부다.** 발행이 놀던 판을 무효로 만든다."""
    from game.api.deps import get_pool
    from game.app.store.tickets import VOID_PUBLISH, apply_ticket_void, read_void_reason

    token, ticket = build_player(client)
    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]

    assert apply_ticket_void(get_pool(), VOID_PUBLISH) >= 1
    assert read_void_reason(get_pool(), ticket["ticket_id"], account_id) == VOID_PUBLISH


def test_the_player_is_told_why_the_run_died(client):
    """★ 「쓸 수 없는 티켓이다」 하나로는 만료·이미 씀·발행 무효가 구별되지 않는다.

    쓰는 사람에게 그 셋은 전부 「판이 사라졌다」로 보이고, 그러면 자기 잘못인지 우리
    잘못인지 물을 데가 없다.
    """
    from game.api.deps import get_core_version, get_pool
    from game.app.store.tickets import VOID_PUBLISH, apply_ticket_void

    token, ticket = build_player(client)
    apply_ticket_void(get_pool(), VOID_PUBLISH)

    response = client.post(
        "/api/run",
        json={
            "ticket_id": ticket["ticket_id"],
            "ruleset": {"ruleset_id": "probe", "version": 1, "rules": []},
            "core_version": get_core_version(),
        },
        headers=build_headers(token),
    )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert VOID_PUBLISH in detail
    assert "무효" in detail


def test_an_ordinary_expiry_says_nothing_extra(client):
    """★ 빈 사유는 「그냥 시간이 지났다」다 — 안 그러면 모든 만료가 발행 탓으로 읽힌다."""
    from game.api.deps import get_pool
    from game.app.store.tickets import read_void_reason

    token, ticket = build_player(client)
    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    assert read_void_reason(get_pool(), ticket["ticket_id"], account_id) == ""


def test_voiding_leaves_used_tickets_alone(client):
    """★ 지나간 제출은 그때의 데이터로 이미 확정됐다 — 되짚어 무효로 만들지 않는다."""
    from game.api.deps import get_pool
    from game.app.store.tickets import VOID_PUBLISH, apply_ticket_void, mark_ticket_consumed

    _token, ticket = build_player(client)
    assert mark_ticket_consumed(get_pool(), ticket["ticket_id"])
    before = apply_ticket_void(get_pool(), VOID_PUBLISH)
    # 이미 쓴 티켓은 세어지지 않는다. 다시 돌려도 같은 수가 나온다.
    assert apply_ticket_void(get_pool(), VOID_PUBLISH) <= before


def test_someone_elses_ticket_stays_private(client):
    """★ 남의 티켓 상태를 알려 주면 티켓 id 를 훑는 도구가 된다."""
    from game.api.deps import get_pool
    from game.app.store.tickets import VOID_PUBLISH, apply_ticket_void, read_void_reason

    _token, ticket = build_player(client)
    other = client.post("/api/account").json()
    apply_ticket_void(get_pool(), VOID_PUBLISH)
    assert read_void_reason(get_pool(), ticket["ticket_id"], int(other["account_id"])) == ""


def test_the_publisher_is_warned_before_pressing(client):
    """★ 누른 뒤에 알면 이미 끊긴 뒤다 — 몇 판이 끊길지가 버튼 위에 있어야 한다."""
    from game.api.deps import get_pool
    from game.app.store.admin import ROLE_OWNER, set_admin_role

    _token, _ticket = build_player(client)
    account = client.post("/api/account").json()
    login_id = f"voidadmin{account['account_id']}"
    client.post(
        "/api/register",
        json={"login_id": login_id, "password": "probe-password-1"},
        headers=build_headers(account["token"]),
    )
    assert set_admin_role(get_pool(), login_id, ROLE_OWNER)

    body = client.get("/api/admin/content", headers=build_headers(account["token"])).json()
    assert body["open_runs"] >= 1


def test_publishing_content_voids_and_says_how_many(client):
    """★ 발행 라우트가 실제로 무효로 만들고, 몇 건인지 돌려준다.

    누른 사람이 남의 판을 몇 개 끊었는지 모르면 발행이 공짜로 보인다.
    """
    from game.api.deps import get_pool
    from game.app.store.admin import ROLE_OWNER, set_admin_role
    from game.app.store.content_pack import read_pack_generation

    token, ticket = build_player(client)
    account = client.post("/api/account").json()
    login_id = f"voidpub{account['account_id']}"
    client.post(
        "/api/register",
        json={"login_id": login_id, "password": "probe-password-1"},
        headers=build_headers(account["token"]),
    )
    assert set_admin_role(get_pool(), login_id, ROLE_OWNER)
    admin = account["token"]

    # 아무 초안이나 하나 올린다 — 발행은 낼 것이 있어야 돈다.
    current = client.get("/api/admin/content/balance", headers=build_headers(admin)).json()[
        "current"
    ]
    drafted = client.post(
        "/api/admin/content/draft",
        json={"asset": "balance", "payload": current, "note": REASON},
        headers=build_headers(admin),
    )
    assert drafted.status_code == 200, drafted.json()

    published = client.post(
        "/api/admin/content/publish",
        json={"generation": read_pack_generation(get_pool()) + 1, "note": REASON},
        headers=build_headers(admin),
    )
    assert published.status_code == 200, published.json()
    assert published.json()["voided"] >= 1, "발행이 열린 판을 안 끊었다"

    # 그리고 그 사람은 이유를 듣는다.
    from game.api.deps import get_core_version

    response = client.post(
        "/api/run",
        json={
            "ticket_id": ticket["ticket_id"],
            "ruleset": {"ruleset_id": "probe", "version": 1, "rules": []},
            "core_version": get_core_version(),
        },
        headers=build_headers(token),
    )
    assert response.status_code == 409
    assert "무효" in response.json()["detail"]
