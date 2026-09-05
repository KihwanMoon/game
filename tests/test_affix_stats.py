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
    from game.app.store.admin import ROLE_OWNER, set_admin_role

    account = client.post("/api/account").json()
    login_id = f"statadmin{account['account_id']}"
    client.post(
        "/api/register",
        json={"login_id": login_id, "password": "probe-password-1"},
        headers={"X-Game-Token": account["token"]},
    )
    assert set_admin_role(get_pool(), login_id, ROLE_OWNER)
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


def publish(client, token):
    """쌓인 초안을 반영한다.

    아이템 편집이 초안을 거치게 됐다 (2026-09-05, 설계/9_에이전트_운영 §3.2). **이 파일이
    재는 것은 접사 스탯 문지기**이지 발행 시점이 아니므로, 올린 뒤 곧바로 발행한다.

    Args:
        client: 테스트 클라이언트.
        token: 관리자 토큰.

    Returns:
        발행 응답.
    """
    generation = client.get("/api/admin/catalog/items", headers={"X-Game-Token": token}).json()[
        "generation"
    ]
    return client.post(
        "/api/admin/catalog/publish",
        json={"generation": generation, "reason": REASON},
        headers={"X-Game-Token": token},
    )


def write_catalog(client, token, path, body):
    """초안을 올리고, 통과했으면 곧바로 발행한다.

    Args:
        client: 테스트 클라이언트.
        token: 관리자 토큰.
        path: 라우트 경로.
        body: 보낼 절.

    Returns:
        발행했으면 발행 응답, 거절됐으면 올린 응답.
    """
    response = client.post(path, json=body, headers={"X-Game-Token": token})
    return response if response.status_code != 200 else publish(client, token)


def create_item(client, token, payload):
    return write_catalog(client, token, "/api/admin/catalog/item", payload)


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
    response = write_catalog(
        client,
        token,
        "/api/admin/catalog/edit",
        {
            "catalog_id": payload["id"],
            "label_ko": payload["label_ko"],
            "min_floor": 1,
            "affixes": [TYPO_AFFIX],
            "reason": REASON,
        },
    )
    assert response.status_code == 400
    assert "atttack" in response.json()["detail"]


def test_a_known_stat_still_goes_through(client, admin):
    """★ 문지기가 정상 편집까지 막으면 아이템을 고칠 수 없다."""
    token, account_id = admin
    payload = build_item(account_id)
    assert create_item(client, token, payload).status_code in {200, 409}
    response = write_catalog(
        client,
        token,
        "/api/admin/catalog/edit",
        {
            "catalog_id": payload["id"],
            "label_ko": payload["label_ko"],
            "min_floor": 1,
            "affixes": [{"stat": "cpu_budget", "percent": -25, "label_ko": "굼뜬 제어"}],
            "reason": REASON,
        },
    )
    assert response.status_code == 200
    row = next(item for item in response.json()["items"] if item["catalog_id"] == payload["id"])
    # **무엇을 올리는지 병기한다.** 「굼뜬 제어 -25%」 만 적으면 25% 가 무엇의 25% 인지
    # 화면 어디에도 없다.
    assert row["affixes"] == ["굼뜬 제어 · CPU -25%"]


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


def test_the_label_says_which_stat_it_lifts():
    """★ 「튼튼함 +8」 만 적으면 8 이 체력인지 방어력인지 화면 어디에도 없다.

    조건문에 각 항의 실측값을 병기하는 것과 같은 규칙이다 (GDD §8.2).
    """
    from game.api.catalog_view import format_affix
    from game.schemas.item import Affix

    assert format_affix(Affix(stat="hp_max", flat=8, label_ko="튼튼함")) == "튼튼함 · 최대체력 +8"
    assert (
        format_affix(Affix(stat="cpu_budget", percent=-25, label_ko="굼뜬 제어"))
        == "굼뜬 제어 · CPU -25%"
    )


def test_a_nameless_affix_falls_back_to_korean():
    """★ 이름이 없으면 **영어 키가 그대로 새던** 자리다.

    관리자 화면이 이름 칸을 비웠을 때 능력치 키를 이름으로 박아 넣어, 프로덕션의
    `sword_great_fine` 이 「attack +3」 으로 떠 있었다.
    """
    from game.api.catalog_view import format_affix
    from game.schemas.item import Affix

    assert format_affix(Affix(stat="attack", flat=3)) == "공격력 +3"
    # 이름이 능력치 키 그대로여도 같다 — 이미 그렇게 저장된 줄이 프로덕션에 있다.
    assert format_affix(Affix(stat="attack", flat=3, label_ko="attack")) == "공격력 +3"


def test_an_unknown_stat_keeps_its_raw_name():
    """★ 모르는 이름을 빈칸으로 두면 값만 뜬 줄이 되어 무엇의 값인지 알 길이 없다."""
    from game.api.catalog_view import format_affix
    from game.schemas.item import Affix

    assert format_affix(Affix(stat="mystery", flat=1)) == "mystery +1"


def test_the_stat_labels_cover_the_canon():
    """★ 정본에 있는데 이름이 없는 능력치가 있으면 그 접사만 영어로 뜬다."""
    from game.schemas.item import COMBAT_STATS, STAT_LABELS

    assert [stat for stat in COMBAT_STATS if stat not in STAT_LABELS] == []
