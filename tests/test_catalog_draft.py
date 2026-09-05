"""아이템 카탈로그 초안·발행 (설계/9_에이전트_운영 §3.2).

**아이템만 문이 열려 있었다.** 스킬·블록·밸런스·룸·적 규칙표는 사람이 발행을 눌러야
반영되는데, 카탈로그는 정본이 DB 라 등록·수정·폐기가 **즉시** 세계를 바꿨다. 그 상태로
아이템 에이전트를 붙이면 검토 없이 세계가 바뀐다.

`test_api_catalog_admin.py` 가 **무엇이 반영되는가**를 재고, 이 파일이 **언제 반영되는가**
를 잰다. 저쪽이 올리고 곧바로 발행하는 것은 그 때문이다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

fastapi_testclient = pytest.importorskip("fastapi.testclient")

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)

REASON = "초안 경로 검사"


@pytest.fixture
def client():
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as running:
        yield running


@pytest.fixture(autouse=True)
def empty_queue(client):
    """검사마다 빈 큐에서 시작한다.

    초안 표는 **공유 큐다** — 누가 올렸든 발행 한 번이 전부를 반영한다. 그것이 설계이고
    (검토는 사람이 한 번에 한다), 그래서 검사끼리도 서로의 초안을 본다.
    """
    from game.api.deps import get_pool
    from game.app.store.catalog_draft import clear_catalog_drafts

    clear_catalog_drafts(get_pool())
    yield
    clear_catalog_drafts(get_pool())


def build_headers(token):
    return {"X-Game-Token": token}


def build_graded(client, role):
    """그 등급의 계정 하나를 만든다.

    Args:
        client: 테스트 클라이언트.
        role: 세울 등급.

    Returns:
        토큰과 계정 id.
    """
    from game.api.deps import get_pool

    account = client.post("/api/account").json()
    with get_pool().connection() as connection:
        connection.execute(
            "UPDATE account SET admin_role = %s WHERE id = %s",
            (role, int(account["account_id"])),
        )
    return account["token"], int(account["account_id"])


def build_item(account_id, **patch):
    """이 실행에서만 쓰는 아이템 절을 만든다.

    Args:
        account_id: 계정 id. id 를 이 실행 전용으로 만드는 데 쓴다.
        patch: 덮어쓸 값들.

    Returns:
        아이템 절.
    """
    return {
        "id": f"draftprobe_{account_id}",
        "kind": "EQUIPMENT",
        "label_ko": "초안 표본 검",
        "slot": "WEAPON_MAIN",
        "hands": "ONE",
        "grade": "COMMON",
        "min_floor": 1,
        "affixes": [{"stat": "attack", "flat": 3, "label_ko": "표본 날"}],
        "reason": REASON,
        **patch,
    }


def read_items(client, token):
    return client.get("/api/admin/catalog/items", headers=build_headers(token)).json()


def find_row(body, catalog_id):
    return next((row for row in body["items"] if row["catalog_id"] == catalog_id), None)


def publish(client, token, generation=None):
    """쌓인 것을 발행한다.

    Args:
        client: 테스트 클라이언트.
        token: 관리자 토큰.
        generation: 적어 보낼 세대. 안 주면 지금 것을 읽어 쓴다.

    Returns:
        발행 응답.
    """
    now = read_items(client, token)["generation"] if generation is None else generation
    return client.post(
        "/api/admin/catalog/publish",
        json={"generation": now, "reason": REASON},
        headers=build_headers(token),
    )


# ── 시점 ─────────────────────────────────────────────────────────────────


def test_a_draft_does_not_reach_the_catalog(client):
    """★ **이것이 이 변경의 전부다.** 올린 것은 아직 아이템이 아니다.

    예전에는 등록이 즉시 카탈로그에 들어갔다. 아이템 에이전트를 붙이면 그 문으로 검토
    없이 세계가 바뀐다 — 다른 다섯 자산은 사람이 발행을 눌러야 반영되는데 아이템만
    열려 있었다.
    """
    token, account_id = build_graded(client, "owner")
    item = build_item(account_id)
    assert (
        client.post("/api/admin/catalog/item", json=item, headers=build_headers(token)).status_code
        == 200
    )
    assert find_row(read_items(client, token), item["id"]) is None, "초안이 카탈로그에 닿았다"


def test_publishing_moves_it_in(client):
    token, account_id = build_graded(client, "owner")
    item = build_item(account_id)
    client.post("/api/admin/catalog/item", json=item, headers=build_headers(token))
    assert publish(client, token).status_code == 200
    assert find_row(read_items(client, token), item["id"]) is not None


def test_a_draft_does_not_move_the_generation(client):
    """★ 세대는 발행이 한 번만 올린다 (§15.8).

    예전에는 조작마다 올라서, 아이템 열 개를 손보면 시즌 경계가 열 번 그였다.
    """
    token, account_id = build_graded(client, "owner")
    before = read_items(client, token)["generation"]
    client.post(
        "/api/admin/catalog/item",
        json=build_item(account_id),
        headers=build_headers(token),
    )
    client.post(
        "/api/admin/catalog/retire",
        json={"catalog_id": "helm_iron", "is_retired": True, "reason": REASON},
        headers=build_headers(token),
    )
    assert read_items(client, token)["generation"] == before, "초안이 세대를 움직였다"
    publish(client, token)
    # 두 조작이었지만 경계는 한 번이다.
    assert read_items(client, token)["generation"] == before + 1
    client.post(
        "/api/admin/catalog/retire",
        json={"catalog_id": "helm_iron", "is_retired": False, "reason": REASON},
        headers=build_headers(token),
    )
    publish(client, token)


def test_the_drafts_are_listed_with_who_put_them_there(client):
    """에이전트가 올린 것과 사람이 올린 것을 화면에서 못 가르면 검토가 흐려진다."""
    token, account_id = build_graded(client, "owner")
    item = build_item(account_id)
    body = client.post("/api/admin/catalog/item", json=item, headers=build_headers(token)).json()
    row = next(one for one in body["drafts"] if one["catalog_id"] == item["id"])
    assert row["action"] == "item"
    assert row["reason"] == REASON
    assert row["handle"] != ""
    assert row["problem"] == ""


def test_a_second_draft_on_the_same_item_replaces_the_first(client):
    """★ 쌓아 두면 발행할 때 어느 순서로 먹일지가 문제가 되고, 그 순서는 아무도 안 정했다."""
    token, account_id = build_graded(client, "owner")
    item = build_item(account_id)
    client.post("/api/admin/catalog/item", json=item, headers=build_headers(token))
    body = client.post(
        "/api/admin/catalog/item",
        json={**item, "label_ko": "나중 뜻"},
        headers=build_headers(token),
    ).json()
    rows = [one for one in body["drafts"] if one["catalog_id"] == item["id"]]
    assert len(rows) == 1


def test_a_draft_can_be_thrown_away(client):
    token, account_id = build_graded(client, "owner")
    item = build_item(account_id)
    client.post("/api/admin/catalog/item", json=item, headers=build_headers(token))
    body = client.post(
        "/api/admin/catalog/draft/discard",
        json={"catalog_id": item["id"]},
        headers=build_headers(token),
    ).json()
    assert not [one for one in body["drafts"] if one["catalog_id"] == item["id"]]


# ── 문 ───────────────────────────────────────────────────────────────────


def test_an_author_can_draft_but_not_publish(client):
    """★ 초안을 쓰는 에이전트가 발행까지 하면 시즌이 아무도 모르게 갈린다."""
    token, account_id = build_graded(client, "author")
    assert (
        client.post(
            "/api/admin/catalog/item",
            json=build_item(account_id),
            headers=build_headers(token),
        ).status_code
        == 200
    )
    assert publish(client, token).status_code == 403


def test_publishing_needs_the_current_generation(client):
    """★ 세대를 손으로 적어야 눌린다 — 그 사이 다른 발행이 있었다면 보고 있는 목록이 옛것이다."""
    token, account_id = build_graded(client, "owner")
    client.post(
        "/api/admin/catalog/item",
        json=build_item(account_id),
        headers=build_headers(token),
    )
    assert publish(client, token, generation=9999).status_code == 409


def test_publishing_nothing_is_refused(client):
    """빈 발행이 세대를 올리면 시즌 경계가 아무 이유 없이 그어진다."""
    token, _account_id = build_graded(client, "owner")
    before = read_items(client, token)["generation"]
    assert publish(client, token).status_code == 400
    assert read_items(client, token)["generation"] == before


def test_publishing_needs_a_reason(client):
    """★ 시즌을 가르는 행위라 왜 했는지가 남아야 한다."""
    token, account_id = build_graded(client, "owner")
    client.post(
        "/api/admin/catalog/item",
        json=build_item(account_id),
        headers=build_headers(token),
    )
    generation = read_items(client, token)["generation"]
    response = client.post(
        "/api/admin/catalog/publish",
        json={"generation": generation, "reason": ""},
        headers=build_headers(token),
    )
    assert response.status_code == 400


def test_a_draft_that_stopped_being_valid_says_so_before_publishing(client):
    """★ 눌러서 알게 하면 절반이 반영된 상태를 상상하게 된다.

    같은 id 를 두 계정이 각각 초안으로 올리고 한쪽이 먼저 발행하면, 남은 초안은 이제
    「이미 있는 id」다. 그 사실이 발행 버튼을 누르기 전에 보여야 한다.
    """
    token, account_id = build_graded(client, "owner")
    item = build_item(account_id)
    client.post("/api/admin/catalog/item", json=item, headers=build_headers(token))
    publish(client, token)
    # 이미 카탈로그에 있는 것을 다시 등록 초안으로 올릴 수는 없다 — 그 자리에서 막힌다.
    blocked = client.post("/api/admin/catalog/item", json=item, headers=build_headers(token))
    assert blocked.status_code == 409
    assert "고치기" in blocked.json()["detail"]
