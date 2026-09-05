"""관리자 등급 (설계/9_에이전트_운영 §3.1).

**권한이 이분법이면 에이전트를 못 붙인다.** 불리언 하나가 콘텐츠 발행·아이템 지급·회수·
카탈로그 편집·몬스터 레벨을 전부 열었다 — CS 에이전트가 콘텐츠를 발행할 수 있으면 안
되고, 밸런스 에이전트가 아이템을 지급할 수 있으면 안 된다.

여기서 지키는 것은 셋이다.

1. **등급이 사다리가 아니다.** `author` 와 `operator` 는 서로를 포함하지 않는다.
2. **발행은 `owner` 뿐이다.** 시즌을 가르는 행위라 사람이 누른다.
3. **경로마다 필요한 등급을 못 박는다.** 새 경로가 붙거나 등급이 넓어지는 순간 이
   목록을 함께 고치게 해서, 그것이 무엇을 여는지 한 번 더 보게 한다.
"""

import os

import pytest

from game.app.store.admin import (
    ROLE_AUTHOR,
    ROLE_OBSERVER,
    ROLE_OPERATOR,
    ROLE_OWNER,
    check_role_allows,
)
from game.app.store.connection import DATABASE_URL_ENV

# ── 등급 규칙 — DB 없이 돈다 ──────────────────────────────────────────────


def test_owner_can_do_everything():
    for wanted in (ROLE_OBSERVER, ROLE_AUTHOR, ROLE_OPERATOR, ROLE_OWNER):
        assert check_role_allows(ROLE_OWNER, wanted)


def test_everyone_admin_can_read():
    """읽기는 등급을 안 가린다 — 지켜보는 것을 막을 이유가 없다."""
    for role in (ROLE_OBSERVER, ROLE_AUTHOR, ROLE_OPERATOR, ROLE_OWNER):
        assert check_role_allows(role, ROLE_OBSERVER)


def test_the_grades_are_not_a_ladder():
    """★ `author` 와 `operator` 는 서로를 포함하지 않는다.

    사다리로 만들면 콘텐츠를 쓰는 에이전트가 아이템을 회수할 수 있게 되고, 그러면 등급을
    나눈 뜻이 없다.
    """
    assert not check_role_allows(ROLE_AUTHOR, ROLE_OPERATOR)
    assert not check_role_allows(ROLE_OPERATOR, ROLE_AUTHOR)


def test_no_agent_grade_reaches_owner():
    """★ 발행은 어느 에이전트 등급에도 안 딸린다."""
    for role in (ROLE_OBSERVER, ROLE_AUTHOR, ROLE_OPERATOR):
        assert not check_role_allows(role, ROLE_OWNER)


def test_an_observer_writes_nothing():
    assert not check_role_allows(ROLE_OBSERVER, ROLE_AUTHOR)
    assert not check_role_allows(ROLE_OBSERVER, ROLE_OPERATOR)


def test_an_unknown_grade_opens_nothing():
    """오타가 조용히 권한이 되면 안 된다."""
    for wanted in (ROLE_OBSERVER, ROLE_OWNER):
        assert not check_role_allows("", wanted)
        assert not check_role_allows("admin", wanted)


# ── 경로별 등급 — 못 박는다 ───────────────────────────────────────────────

# 경로가 어느 의존성으로 잠겨 있는가. **넓히려면 여기를 먼저 고쳐야 한다.**
WANTED = {
    # 읽기. 등급을 안 가린다.
    "/api/admin/overview": "resolve_admin",
    "/api/admin/catalog": "resolve_admin",
    "/api/admin/catalog/items": "resolve_admin",
    "/api/admin/drops/{kind_id}": "resolve_admin",
    "/api/admin/catalog/drafts": "resolve_admin",
    "/api/admin/content": "resolve_admin",
    "/api/admin/content/{asset}": "resolve_admin",
    "/api/admin/bots": "resolve_admin",
    "/api/admin/bot/bag": "resolve_admin",
    "/api/admin/bot/detail": "resolve_admin",
    "/api/admin/doppel/detail": "resolve_admin",
    "/api/admin/doppel/gear": "resolve_admin",
    "/api/admin/replay": "resolve_admin",
    "/api/admin/testers": "resolve_admin",
    "/api/admin/watch": "resolve_admin",
    # 콘텐츠 초안. **발행은 여기 없다.**
    "/api/admin/content/draft": "resolve_author",
    "/api/admin/content/discard": "resolve_author",
    # 아이템 편집도 이제 초안이다 (§3.2). 즉시 반영되던 셋이 여기로 내려왔다.
    "/api/admin/catalog/item": "resolve_author",
    "/api/admin/catalog/edit": "resolve_author",
    "/api/admin/catalog/retire": "resolve_author",
    "/api/admin/catalog/draft/discard": "resolve_author",
    # 계정·세계 개입. 콘텐츠는 여기 없다.
    "/api/admin/monster/level": "resolve_operator",
    "/api/admin/auction/cancel": "resolve_operator",
    "/api/admin/item/recall": "resolve_operator",
    "/api/admin/bot": "resolve_operator",
    "/api/admin/bot/gift": "resolve_operator",
    "/api/admin/testers/mark": "resolve_operator",
    # 발행. 시즌을 가르는 행위라 **사람만** 누른다.
    #
    # 드롭 가중치가 아직 owner 인 것은 그것만 초안을 안 거치기 때문이다 — 카탈로그는
    # 2026-09-05 에 초안 경로가 생겼고(§3.2), 드롭 표는 아직이다.
    "/api/admin/content/publish": "resolve_owner",
    "/api/admin/catalog/publish": "resolve_owner",
    "/api/admin/drops": "resolve_owner",
}


def find_guard(route):
    """그 경로를 잠근 의존성의 이름을 준다.

    Args:
        route: FastAPI 라우트.

    Returns:
        의존성 함수 이름. 관리자 의존성이 없으면 빈 문자열.
    """
    names = [
        getattr(item.call, "__name__", "")
        for item in getattr(route, "dependant", None).dependencies
    ]
    return next((name for name in names if name.startswith("resolve_")), "")


def test_every_admin_route_declares_its_grade():
    """★ 경로마다 필요한 등급을 못 박는다.

    새 경로가 붙거나 등급이 넓어지는 순간 이 목록을 함께 고치게 해서, 그것이 무엇을
    여는지 한 번 더 보게 한다. `test_api_admin_guards.py` 가 **어떤 경로가 있는가**를
    지키고, 이쪽이 **그 경로가 무엇을 허락하는가**를 지킨다.
    """
    from game.api.main import create_app

    found = {
        route.path: find_guard(route)
        for route in create_app().routes
        if "/admin/" in getattr(route, "path", "")
    }
    assert found == WANTED


# ── 실제로 막히는가 — DB 가 필요하다 ─────────────────────────────────────

fastapi_testclient = pytest.importorskip("fastapi.testclient")

live = pytest.mark.skipif(
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


def build_graded(client, role):
    """그 등급의 계정 하나를 만든다.

    Args:
        client: 테스트 클라이언트.
        role: 세울 등급.

    Returns:
        기기 토큰.
    """
    from game.api.deps import get_pool

    token = client.post("/api/account").json()["token"]
    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    with get_pool().connection() as connection:
        connection.execute("UPDATE account SET admin_role = %s WHERE id = %s", (role, account_id))
    return token


@live
def test_an_author_cannot_publish(client):
    """★ 초안을 쓰는 에이전트가 발행까지 하면 시즌이 아무도 모르게 갈린다."""
    token = build_graded(client, ROLE_AUTHOR)
    response = client.post(
        "/api/admin/content/publish",
        json={"generation": 99, "note": "이러면 안 된다"},
        headers=build_headers(token),
    )
    # 403 이다 — 404 면 「막혔다」와 「없어졌다」가 구별되지 않아 고장으로 신고된다.
    assert response.status_code == 403


@live
def test_an_author_cannot_recall_an_item(client):
    token = build_graded(client, ROLE_AUTHOR)
    response = client.post(
        "/api/admin/item/recall",
        json={"target_id": 1, "reason": "이러면 안 된다"},
        headers=build_headers(token),
    )
    assert response.status_code == 403


@live
def test_an_operator_cannot_touch_content(client):
    token = build_graded(client, ROLE_OPERATOR)
    response = client.post(
        "/api/admin/content/draft",
        json={"asset": "balance", "payload": {}, "note": "이러면 안 된다"},
        headers=build_headers(token),
    )
    assert response.status_code == 403


@live
def test_an_observer_can_look_but_not_touch(client):
    """읽기는 열려 있고 쓰기는 전부 막힌다 — 지킴이 등급이다."""
    token = build_graded(client, ROLE_OBSERVER)
    assert client.get("/api/admin/overview", headers=build_headers(token)).status_code == 200
    blocked = client.post(
        "/api/admin/testers/mark",
        json={"account_id": 1, "is_tester": True},
        headers=build_headers(token),
    )
    assert blocked.status_code == 403


@live
def test_someone_with_no_grade_sees_nothing(client):
    """★ 관리자가 아니면 404 다 — 403 은 경로의 존재를 알려 준다."""
    token = client.post("/api/account").json()["token"]
    assert client.get("/api/admin/overview", headers=build_headers(token)).status_code == 404
