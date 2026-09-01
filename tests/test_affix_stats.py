"""접사 스탯의 정본 (설계/4_아이템 §9).

**오타 하나가 아무 효과 없는 접사를 만든다.** 합산은 정본 목록에 있는 이름만 보므로,
`atttack` 이라고 적힌 접사는 붙어도 전투에 반영되지 않는다. 그리고 그 사실은 화면
어디에도 안 나온다 — 관리자는 올린 줄 알고, 플레이어는 받은 줄 안다.

여기서 지키는 것은 셋이다.

1. **쓰는 경로마다 문지기가 있다.** 등록과 고치기 둘 다.
2. **화면이 목록을 따로 들고 있지 않는다.** 정본을 응답에 실어 보낸다.
3. **봉인 옵션 풀도 정본 안에 있다.** 돈을 받고 아무 효과 없는 옵션을 주면 안 된다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)

REASON = "검사용 조작"
TYPO_AFFIX = {"stat": "atttack", "flat": 3, "label_ko": "오타 날"}


@pytest.fixture
def client():
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as running:
        yield running


@pytest.fixture
def admin(client):
    """관리자 토큰. 승격은 스크립트와 같은 경로(저장 층)로만 한다."""
    from game.api.deps import get_pool
    from game.app.store.admin import set_admin

    account = client.post("/api/account").json()
    login_id = f"statadmin{account['account_id']}"
    client.post(
        "/api/register",
        json={"login_id": login_id, "password": "probe-password-1"},
        headers={"X-Game-Token": account["token"]},
    )
    assert set_admin(get_pool(), login_id, True)
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
        "id": f"statprobe_{account_id}",
        "kind": "EQUIPMENT",
        "label_ko": "스탯 표본 검",
        "slot": "WEAPON_MAIN",
        "hands": "ONE",
        "grade": "COMMON",
        "min_floor": 1,
        "affixes": [{"stat": "attack", "flat": 3, "label_ko": "표본 날"}],
        "reason": REASON,
        **patch,
    }


def create_item(client, token, payload):
    return client.post("/api/admin/catalog/item", json=payload, headers={"X-Game-Token": token})


def test_an_unknown_stat_is_refused_on_registration(client, admin):
    """★ 모르는 스탯으로 등록하면 거절한다 — 통과시키면 조용히 죽은 접사가 된다."""
    token, account_id = admin
    response = create_item(client, token, build_item(account_id, affixes=[TYPO_AFFIX]))
    assert response.status_code == 400
    assert "atttack" in response.json()["detail"]


def test_an_unknown_stat_is_refused_on_edit(client, admin):
    """★ 고치기에도 같은 문지기를 둔다 — 수치 수정이 등록보다 훨씬 자주 일어난다."""
    token, account_id = admin
    payload = build_item(account_id)
    assert create_item(client, token, payload).status_code in {200, 409}
    response = client.post(
        "/api/admin/catalog/edit",
        json={
            "catalog_id": payload["id"],
            "label_ko": payload["label_ko"],
            "min_floor": 1,
            "affixes": [TYPO_AFFIX],
            "reason": REASON,
        },
        headers={"X-Game-Token": token},
    )
    assert response.status_code == 400
    assert "atttack" in response.json()["detail"]


def test_a_known_stat_still_goes_through(client, admin):
    """★ 문지기가 정상 편집까지 막으면 아이템을 고칠 수 없다."""
    token, account_id = admin
    payload = build_item(account_id)
    assert create_item(client, token, payload).status_code in {200, 409}
    response = client.post(
        "/api/admin/catalog/edit",
        json={
            "catalog_id": payload["id"],
            "label_ko": payload["label_ko"],
            "min_floor": 1,
            "affixes": [{"stat": "cpu_budget", "percent": -25, "label_ko": "굼뜬 제어"}],
            "reason": REASON,
        },
        headers={"X-Game-Token": token},
    )
    assert response.status_code == 200
    row = next(item for item in response.json()["items"] if item["catalog_id"] == payload["id"])
    assert row["affixes"] == ["굼뜬 제어 -25%"]


def test_the_catalog_response_carries_the_canon(client, admin):
    """★ 화면이 목록을 따로 들고 있으면 정본이 둘이 된다."""
    from game.schemas.item import COMBAT_STATS

    token, _account_id = admin
    body = client.get("/api/admin/catalog/items", headers={"X-Game-Token": token}).json()
    assert body["stats"] == list(COMBAT_STATS)


def test_the_sealed_option_pool_stays_inside_the_canon(client):
    """★ 봉인 옵션이 정본 밖 스탯이면 **돈을 받고 아무것도 안 준다** (§17)."""
    from game.api.deps import get_pool
    from game.app.store.items import list_affix_pool
    from game.schemas.item import COMBAT_STATS

    rows = list_affix_pool(get_pool())
    assert rows
    assert [row[0] for row in rows if row[0] not in COMBAT_STATS] == []


def test_the_canon_lists_only_what_the_loadout_sums():
    """★ 정본과 합산 대상이 갈리면 목록이 다시 둘이 된다."""
    from game.app.items import loadout
    from game.schemas import item

    assert loadout.COMBAT_STATS is item.COMBAT_STATS
