"""관리자 경로의 차단 규율.

`test_api_admin.py` 에서 갈라 둔 이유는 책임이 다르기 때문이다 — 저쪽은 관리자가 무엇을
보고 무엇을 고치는가이고, 이쪽은 **관리자가 아닌 사람이 무엇을 못 하는가**다.

여기서 지키는 것은 셋이다.

1. **404 로 답한다.** 403 이면 "거기 뭔가 있다" 를 알려 준다.
2. **승격 엔드포인트가 없다.** 그 하나가 뚫리면 세계 전체가 뚫린다.
3. **관리자 경로 목록을 못 박는다.** 새 경로가 붙는 순간 그것이 얼마나 위험한지 한 번
   더 보게 한다.
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


def build_admin(client):
    """가입한 계정 하나를 만들어 관리자로 올린다. **스크립트와 같은 경로를 쓴다.**"""
    from game.api.deps import get_pool
    from game.app.store.admin import ROLE_OWNER, set_admin_role

    account = client.post("/api/account").json()
    login_id = f"admin{account['account_id']}"
    client.post(
        "/api/register",
        json={"login_id": login_id, "password": PASSWORD},
        headers=build_headers(account["token"]),
    )
    assert set_admin_role(get_pool(), login_id, ROLE_OWNER)
    return account["token"]


# ── 차단 ─────────────────────────────────────────────────────────────────


def test_a_normal_account_sees_nothing(client, token):
    """★ 관리자가 아니면 **404** 다 — 403 은 경로의 존재를 알려 준다."""
    assert client.get("/api/admin/overview", headers=build_headers(token)).status_code == 404


def test_no_token_sees_nothing(client):
    """★ 토큰 없이 열려 있으면 그 자체로 끝이다."""
    assert client.get("/api/admin/overview").status_code in {401, 403, 404, 422}


def test_a_normal_account_cannot_change_a_monster(client, token):
    """★ 읽기만 막고 쓰기를 열어 두면 막은 뜻이 없다."""
    response = client.put(
        "/api/admin/monster/level",
        json={"record_id": 1, "level": 5},
        headers=build_headers(token),
    )
    assert response.status_code == 404


def test_there_is_no_route_that_grants_admin(client):
    """★ **승격 엔드포인트가 있으면 안 된다.**

    그 하나가 뚫리는 순간 세계 전체가 뚫린다. 길은 스크립트뿐이다.
    """
    from game.api.main import create_app

    paths = [route.path for route in create_app().routes]
    assert not [path for path in paths if "grant" in path or "promote" in path]
    # 관리자 경로는 조회와 개입뿐이다.
    # 관리자 경로는 **조회와 개입뿐**이다. 늘어나면 이 목록을 함께 고치게 해서,
    # 새 경로가 붙는 순간 그것이 얼마나 위험한지 한 번 더 보게 한다.
    assert sorted(path for path in paths if "/admin/" in path) == [
        "/api/admin/auction/cancel",
        # 봇 조회·개입 (T11). 여기서 하는 것은 멈춤·재개와 성격 고치기뿐이고, **지우는
        # 조작은 두지 않는다** — 지우면 그 봇이 벌어 둔 장비·도감·순위가 함께 사라진다.
        "/api/admin/bot",
        # 봇의 가방을 본다. **봇만** 본다 — 아무 계정이나 열리면 남의 가방을 들여다보는
        # 길이 된다.
        "/api/admin/bot/bag",
        # 봇 하나를 유저 화면과 같은 모양으로 연다 — 규칙표·캐릭터·가방·소모품·스킬·
        # 리플레이. **읽기만이다.** 여기에 착용·해제가 붙으면 관리자가 봇의 빌드를 손으로
        # 만들게 되고, 그러면 봇의 성적이 더 이상 봇의 규칙표를 뜻하지 않는다.
        "/api/admin/bot/detail",
        # 사람 → 봇 한 방향. 도착 즉시 귀속이라 돌아오는 길이 없다 (결정 #07).
        "/api/admin/bot/gift",
        "/api/admin/bots",
        "/api/admin/catalog",
        # 아이템 편집은 **초안으로 간다** (2026-09-05, 설계/9 §3.2). 예전에는 이 셋이
        # 즉시 카탈로그를 바꿨다 — 다른 다섯 자산은 사람이 발행을 눌러야 반영되는데
        # 아이템만 문이 열려 있었고, 그 문으로 에이전트가 들어오면 검토가 없어진다.
        "/api/admin/catalog/draft/discard",
        "/api/admin/catalog/drafts",
        "/api/admin/catalog/edit",
        "/api/admin/catalog/item",
        "/api/admin/catalog/items",
        # 쌓인 것을 한 번에 반영한다. **사람만** — 세대가 여기서 한 번 오른다.
        "/api/admin/catalog/publish",
        "/api/admin/catalog/retire",
        "/api/admin/content",
        "/api/admin/content/discard",
        "/api/admin/content/draft",
        "/api/admin/content/publish",
        "/api/admin/content/{asset}",
        # 도플갱어 하나를 연다. 봇보다 탭이 적고, 그 차이가 곧 이 개체가 무엇인지를
        # 말한다 — 계정이 아니라 얼려 둔 기록이라 가방도 소모품도 없다.
        "/api/admin/doppel/detail",
        # 도플갱어가 끼고 있던 것. **가진 아이템이 아니라 얼려 둔 기록이다** — 그 개체는
        # 어떤 아이템도 소유하지 않는다.
        "/api/admin/doppel/gear",
        "/api/admin/drops",
        "/api/admin/drops/{kind_id}",
        "/api/admin/item/recall",
        "/api/admin/monster/level",
        "/api/admin/overview",
        # 지나간 판을 다시 돌릴 **입력**을 준다 — 시드·방·층·로드아웃·스냅샷. 전부
        # 티켓에서 나오고 **클라이언트가 보낸 것은 하나도 안 실린다** (설계/7_변조방지 §4).
        # 결과를 여기서 주는 것이 아니라, 받는 쪽이 다시 돌려서 같은 답이 나오는지 본다.
        "/api/admin/replay",
        # G1 의 **분모**를 사람이 정하는 자리다 (2026-09-05). 표시만 하고 권한은 안
        # 준다 — 표시된 계정에 생기는 것은 통계에 세어진다는 것뿐이다. 그래도 관리자
        # 경로인 이유는, 분모를 아무나 바꿀 수 있으면 게이트가 판정이 아니게 되기 때문이다.
        "/api/admin/testers",
        "/api/admin/testers/mark",
    ]


def test_an_anonymous_account_cannot_be_promoted(client, token):
    """★ 익명은 관리자가 될 수 없다 — 토큰 하나가 곧 세계 전체가 된다."""
    from game.api.deps import get_pool
    from game.app.store.admin import ROLE_OWNER, set_admin_role

    handle = client.get("/api/account", headers=build_headers(token)).json()["handle"]
    assert not set_admin_role(get_pool(), handle, ROLE_OWNER)
