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


def test_a_stale_version_is_refused(client, admin):
    """★ 버전을 안 올리고 발행하면 저장된 리플레이가 조용히 거짓이 된다."""
    raw = read_skills()
    response = client.post(
        "/api/admin/content/draft",
        json={"asset": "skills", "payload": raw, "note": "버전 그대로"},
        headers=build_headers(admin),
    )
    assert response.status_code == 400
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


def test_there_is_no_publish_route(client, admin):
    """★ 발행이 라우트면 관리자가 화면에서 시즌을 가를 수 있다 — 사람 손을 타야 한다."""
    from game.api.main import create_app

    paths = [getattr(route, "path", "") for route in create_app().routes]
    assert not [path for path in paths if "publish" in path]
