"""카탈로그 시딩 (설계/4_아이템 §15.7).

**정본은 DB 이고 파일은 씨앗이다.** 두 방향으로 틀릴 수 있다.

1. 파일로 덮으면 관리자가 고친 것이 배포 한 번에 사라진다 — 폐기한 아이템이 되살아나는
   것도 같은 사고다.
2. 빈 표일 때만 심으면 콘텐츠를 더해도 **이미 돌고 있는 서버에는 영영 안 들어간다.**
   드롭 표에서 겪은 것과 같은 구멍이다.

그래서 규칙은 하나다 — **없는 것만 심고, 있는 것은 안 건드린다.**
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)


@pytest.fixture
def pool():
    """연결 풀. 수명주기가 열어 주므로 클라이언트를 컨텍스트로 쓴다."""
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from game.api.deps import get_pool
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()):
        yield get_pool()


def test_the_file_never_overwrites_what_the_db_holds(pool):
    """★ 관리자가 고친 것이 배포 한 번에 되돌아가면 정본이 DB 라는 말이 거짓이 된다."""
    from dataclasses import replace

    from game.app.store.catalog_seed import apply_catalog_seed
    from game.app.store.item_catalog import list_catalog, save_catalog_entry

    before = list_catalog(pool)["helm_iron"]
    save_catalog_entry(pool, replace(before, label_ko="관리자가 고친 이름"))
    apply_catalog_seed(pool)
    assert list_catalog(pool)["helm_iron"].label_ko == "관리자가 고친 이름"
    save_catalog_entry(pool, before)


def test_a_retired_item_stays_retired(pool):
    """★ 폐기한 것이 되살아나면 폐기가 아무것도 막지 못한다."""
    from game.app.store.catalog_seed import apply_catalog_seed
    from game.app.store.item_catalog import apply_retire, list_catalog

    apply_retire(pool, "sword_short", True)
    apply_catalog_seed(pool)
    assert list_catalog(pool)["sword_short"].is_retired
    apply_retire(pool, "sword_short", False)


def test_a_new_file_entry_reaches_a_running_server(pool, tmp_path, monkeypatch):
    """★ 콘텐츠를 더해도 이미 돌고 있는 서버에 안 들어가면 배포가 아무 일도 안 한다.

    **표가 이미 차 있는 상태에서 본다.** 그냥 시드를 돌리고 "다 있다" 를 확인하면, 빈
    표일 때만 심는 옛 코드도 그대로 통과한다 — 실제로 그렇게 통과했다.
    """
    import json

    from game.app.store import catalog_seed
    from game.app.store.item_catalog import list_catalog

    catalog_seed.apply_catalog_seed(pool)
    fresh_id = f"seedprobe_{len(list_catalog(pool))}_{tmp_path.name}"
    source = tmp_path / "items.json"
    source.write_text(
        json.dumps(
            {
                "item_list_version": 1,
                "items": [
                    {
                        "id": fresh_id,
                        "kind": "EQUIPMENT",
                        "label_ko": "나중에 더한 검",
                        "slot": "WEAPON_MAIN",
                        "hands": "ONE",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(catalog_seed, "ITEMS_PATH", source)
    assert catalog_seed.apply_catalog_seed(pool) == 1
    assert fresh_id in list_catalog(pool)


def test_seeding_twice_adds_nothing(pool):
    """★ 두 번째 시딩이 줄을 더하면 서버가 뜰 때마다 카탈로그가 자란다."""
    from game.app.store.catalog_seed import apply_catalog_seed

    apply_catalog_seed(pool)
    assert apply_catalog_seed(pool) == 0
