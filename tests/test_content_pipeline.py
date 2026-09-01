"""콘텐츠 발행 파이프라인 — 편집·검증·발행이 갈린다 (설계/4_아이템 §15.7 의 반대편).

여기서 지키는 것은 여섯이다.

1. **초안은 게임을 안 바꾼다.** 스킬·블록·룸·적 규칙표는 두 코어가 함께 읽는 실행
   자산이고 브라우저는 빌드 시점에 인라인한다 — 런타임에 바뀌면 서버 없이 게임이 안 돈다.
2. **코어가 쓰는 그 로더로 검증한다.** 검증기가 둘이면 검증은 통과하는데 배포하면 서버가
   안 뜨는 날이 온다.
3. **버전을 안 올리면 막는다.** 안 올리고 발행하면 저장된 리플레이가 조용히 거짓이 된다.
4. **못 읽는 절은 저장조차 안 된다.** DB 에 남으면 언젠가 발행된다.
5. **발행은 사람 손을 탄다.** 자동이면 순위표 시즌이 아무도 모르게 갈린다.
6. **버려도 파일은 그대로다.** 발행 전이라 게임에 없던 것이다.
"""

import json
import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)


@pytest.fixture
def client():
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as running:
        yield running


@pytest.fixture
def admin(client):
    from game.api.deps import get_pool
    from game.app.store.admin import set_admin

    account = client.post("/api/account").json()
    login_id = f"content{account['account_id']}"
    client.post(
        "/api/register",
        json={"login_id": login_id, "password": "probe-password-1"},
        headers={"X-Game-Token": account["token"]},
    )
    assert set_admin(get_pool(), login_id, True)
    return account["token"]


def build_headers(token):
    return {"X-Game-Token": token}


def read_skills():
    from game.config import SKILLS_PATH

    return json.loads(SKILLS_PATH.read_text(encoding="utf-8"))


def test_a_draft_does_not_touch_the_file(client, admin):
    """★ 초안이 파일을 건드리면 그 순간 브라우저와 서버가 다른 게임을 돈다."""
    from game.config import SKILLS_PATH

    before = SKILLS_PATH.read_text(encoding="utf-8")
    raw = read_skills()
    raw["skill_list_version"] = raw["skill_list_version"] + 1
    response = client.post(
        "/api/admin/content/draft",
        json={"asset": "skills", "payload": raw, "note": "검사용 초안"},
        headers=build_headers(admin),
    )
    assert response.status_code == 200
    assert SKILLS_PATH.read_text(encoding="utf-8") == before, "초안이 파일을 고쳤다"


def test_a_draft_does_not_need_a_version_bump(client, admin):
    """★ 초안 단계에서 버전을 요구하는 것은 이르다 (개정: 설계 §18).

    자산 셋을 고치는 동안 버전을 세 번 올리게 된다. 세대는 **발행 시점에 한 번** 받고,
    그것이 "몰아서 발행" 의 뜻이다.
    """
    raw = read_skills()
    response = client.post(
        "/api/admin/content/draft",
        json={"asset": "skills", "payload": raw, "note": "버전 그대로"},
        headers=build_headers(admin),
    )
    assert response.status_code == 200


def test_publishing_needs_a_higher_generation(client, admin):
    """★ 세대를 안 올리고 발행하면 저장된 리플레이가 조용히 거짓이 된다."""
    discard_all(client, admin)
    raw = read_skills()
    client.post(
        "/api/admin/content/draft",
        json={"asset": "skills", "payload": raw, "note": "검사용 초안"},
        headers=build_headers(admin),
    )
    # **지금 세대와 같은 값으로 낸다.** 0 으로 내면 스키마의 ge=1 이 먼저 막아서
    # 라우트의 세대 검사를 아무도 안 보게 된다 — 실제로 그렇게 통과했다.
    from game.api.deps import get_pool
    from game.app.store.content_pack import read_pack_generation

    current = max(1, read_pack_generation(get_pool()))
    response = client.post(
        "/api/admin/content/publish",
        json={"generation": current, "note": "세대 안 올림"},
        headers=build_headers(admin),
    )
    assert response.status_code == 409
    assert "올려야" in response.json()["detail"]


def test_an_unreadable_draft_is_refused(client, admin):
    """★ 못 읽는 절이 DB 에 남으면 언젠가 발행되고, 그때 배포가 서버를 죽인다."""
    raw = read_skills()
    raw["skill_list_version"] = raw["skill_list_version"] + 1
    raw["skills"] = [{"id": "NO_COEF"}]
    response = client.post(
        "/api/admin/content/draft",
        json={"asset": "skills", "payload": raw, "note": "깨진 절"},
        headers=build_headers(admin),
    )
    assert response.status_code == 400
    assert "읽을 수 없다" in response.json()["detail"]


def test_a_broken_room_file_is_refused(client, admin):
    """★ 검증기를 따로 만들지 않는다 — 코어가 쓰는 그 로더가 막아야 한다."""
    from game.config import ROOM_TEMPLATES_PATH

    raw = json.loads(ROOM_TEMPLATES_PATH.read_text(encoding="utf-8"))
    raw["room_list_version"] = raw["room_list_version"] + 1
    raw["templates"] = [{"id": "broken"}]
    response = client.post(
        "/api/admin/content/draft",
        json={"asset": "rooms", "payload": raw, "note": "깨진 룸"},
        headers=build_headers(admin),
    )
    assert response.status_code == 400


def test_an_unknown_asset_is_refused(client, admin):
    """★ 모르는 자산을 받으면 발행 스크립트가 쓸 파일을 못 찾는다."""
    response = client.post(
        "/api/admin/content/draft",
        json={"asset": "items", "payload": {}, "note": "아이템은 여기가 아니다"},
        headers=build_headers(admin),
    )
    assert response.status_code == 400


def test_the_screen_says_publishing_is_manual(client, admin):
    """★ 자동으로 반영되는 줄 알면 관리자가 시즌을 모르게 가른다."""
    body = client.get("/api/admin/content", headers=build_headers(admin)).json()
    assert "커밋" in body["publish_hint"]
    assert "반영되지 않는다" in body["publish_hint"]


def test_discarding_leaves_the_file_alone(client, admin):
    """★ 발행 전이라 게임에 없던 것이다 — 버린다고 파일이 바뀌면 안 된다."""
    from game.config import SKILLS_PATH

    raw = read_skills()
    raw["skill_list_version"] = raw["skill_list_version"] + 1
    client.post(
        "/api/admin/content/draft",
        json={"asset": "skills", "payload": raw, "note": "검사용 초안"},
        headers=build_headers(admin),
    )
    before = SKILLS_PATH.read_text(encoding="utf-8")
    response = client.post(
        "/api/admin/content/discard",
        json={"asset": "skills", "payload": {}, "note": "검사 정리"},
        headers=build_headers(admin),
    )
    assert response.status_code == 200
    assert SKILLS_PATH.read_text(encoding="utf-8") == before
    assert not [row for row in response.json()["drafts"] if row["asset"] == "skills"]


def test_publishing_swaps_the_server_context(client, admin):
    """★ 서버가 안 갈아 끼우면 브라우저는 새 팩으로 돌고 서버는 옛 데이터로 채점한다.

    발행을 라우트로 연 것은 콘텐츠 팩을 런타임에 내려받기로 했기 때문이다(설계 §18).
    예전에는 "발행 라우트가 없다" 가 불변 조건이었다 — 재빌드 없이는 브라우저에 닿을
    길이 없었으므로 자동 반영이 곧 두 코어의 분기였다. 팩이 그 분기를 없앴고, 대신
    **세대를 명시적으로 받고 원장에 남기는 것**이 안전장치가 됐다.
    """
    import inspect

    from game.api.routes import content_admin as module

    source = inspect.getsource(module.create_content_publish)
    assert "apply_content_reload" in source, "발행이 서버 컨텍스트를 안 갈아 끼운다"
    assert "record_admin_action" in source, "발행이 원장에 안 남는다"


def discard_all(client, admin):
    """남아 있는 초안을 전부 버린다.

    **발행은 초안 전부를 검증한다.** 다른 검사가 남긴 깨진 초안이 하나 있으면 발행이
    통째로 막히고, 그것은 옳은 동작이지만 이 검사가 보려는 것은 아니다.
    """
    body = client.get("/api/admin/content", headers=build_headers(admin)).json()
    for row in body["drafts"]:
        client.post(
            "/api/admin/content/discard",
            json={"asset": row["asset"], "payload": {}, "note": "검사 정리"},
            headers=build_headers(admin),
        )


def test_publishing_moves_the_core_version(client, admin):
    """★ 발행으로 데이터가 바뀌면 시즌이 갈려야 한다."""
    from game.api.deps import get_core_version, get_pool
    from game.app.store.content_pack import read_pack_generation

    discard_all(client, admin)
    raw = read_skills()
    client.post(
        "/api/admin/content/draft",
        json={"asset": "skills", "payload": raw, "note": "검사용 초안"},
        headers=build_headers(admin),
    )
    before = get_core_version()
    generation = read_pack_generation(get_pool()) + 1
    response = client.post(
        "/api/admin/content/publish",
        json={"generation": generation, "note": "검사용 발행"},
        headers=build_headers(admin),
    )
    assert response.status_code == 200
    assert response.json()["core_version"] != before
    assert get_core_version() != before


def test_the_pack_is_open_to_everyone(client, admin):
    """★ 관리자 전용이면 접속자마다 다른 데이터로 돈다 — 이것이 곧 게임 데이터다."""
    token = client.post("/api/account").json()["token"]
    body = client.get("/api/content/pack", headers=build_headers(token)).json()
    assert set(body["assets"]) == {"balance", "blocks", "enemies", "rooms", "skills"}
    assert body["core_version"] != ""
