"""아이템 카탈로그 DB 이관 (설계/4_아이템 §15.7·§15.8).

여기서 지키는 것은 다섯이다.

1. **파일에서 DB 로 한 번만 옮긴다.** 서버가 뜰 때마다 덮으면 관리자가 고친 것이 배포
   한 번에 사라지고, 그러면 정본이 DB 라는 말이 거짓이 된다.
2. **삭제가 없다.** 인스턴스·원장·경매가 catalog_id 를 가리킨다 — 지우면 과거 기록을
   못 읽는다. 폐기는 "새로 안 나온다" 만 뜻한다.
3. **폐기된 것도 읽힌다.** 이미 가방에 있는 것을 읽으려면 그 정의가 필요하다.
4. **세대가 코어 버전을 민다.** 아이템을 고치는 것은 시즌을 가르는 일이다.
5. **스냅샷이 왕복한다.** 골든과 헤드리스는 DB 없이 그 파일을 읽는다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)

PROBE_ITEM = "helm_iron"


@pytest.fixture
def pool():
    from game.app.store.connection import apply_schema, create_pool

    running = create_pool()
    apply_schema(running)
    from game.app.store.catalog_seed import apply_catalog_seed

    apply_catalog_seed(running)
    yield running
    running.close()


def test_the_seed_fills_an_empty_table(pool):
    """★ 파일의 카탈로그가 DB 로 옮겨 온다."""
    from game.app.store.item_catalog import list_catalog

    catalog = list_catalog(pool)
    assert PROBE_ITEM in catalog
    assert catalog[PROBE_ITEM].label_ko != ""


def test_the_seed_does_not_overwrite_what_is_there(pool):
    """★ 뜰 때마다 파일로 덮으면 관리자가 고친 것이 배포 한 번에 사라진다."""
    from dataclasses import replace

    from game.app.store.catalog_seed import apply_catalog_seed
    from game.app.store.item_catalog import list_catalog, save_catalog_entry

    before = list_catalog(pool)[PROBE_ITEM]
    save_catalog_entry(pool, replace(before, label_ko="관리자가 고친 이름"))
    assert apply_catalog_seed(pool) == 0
    assert list_catalog(pool)[PROBE_ITEM].label_ko == "관리자가 고친 이름"
    save_catalog_entry(pool, before)


def test_there_is_no_delete(pool):
    """★ 삭제 함수를 두지 않는다 — 지우면 과거 기록을 못 읽는다."""
    from game.app.store import item_catalog

    names = [name for name in dir(item_catalog) if not name.startswith("_")]
    assert not [name for name in names if "delete" in name or "remove" in name]


def test_a_retired_item_is_still_readable(pool):
    """★ 폐기는 「없다」가 아니라 「새로 안 나온다」다."""
    from game.app.store.item_catalog import apply_retire, list_catalog

    apply_retire(pool, PROBE_ITEM)
    try:
        entry = list_catalog(pool)[PROBE_ITEM]
        assert entry.is_retired
        assert entry.label_ko != ""
    finally:
        apply_retire(pool, PROBE_ITEM, is_retired=False)


def test_the_generation_moves_the_core_version(pool):
    """★ 아이템을 고치는 것은 시즌을 가르는 일이다 (§15.8)."""
    from dataclasses import replace

    from game.app.content_versions import read_content_versions
    from game.app.store.item_catalog import apply_generation_bump, read_generation
    from game.schemas.run_ticket import build_core_version

    base = read_content_versions()
    before = build_core_version(replace(base, items=read_generation(pool)))
    after = build_core_version(replace(base, items=apply_generation_bump(pool)))
    assert before != after


def test_the_snapshot_round_trips(pool):
    """★ 스냅샷이 파서를 통과해야 골든과 헤드리스가 DB 없이 돈다.

    **기본값이 아닌 등급으로 검사한다.** 지금 카탈로그가 전부 보통 등급이라, 내보내기가
    등급을 통째로 빠뜨려도 파서의 기본값(보통)이 그것을 메워 검사가 통과한다 — 실제로
    한 번 그렇게 통과했다.
    """
    from dataclasses import replace

    from game.app.store.item_catalog import list_catalog
    from game.schemas.item import GRADE_RELIC, build_item_payload, parse_item

    for entry in list_catalog(pool).values():
        assert parse_item(build_item_payload(entry)) == entry
        graded = replace(entry, grade=GRADE_RELIC, min_floor=4)
        restored = parse_item(build_item_payload(graded))
        assert restored.grade == GRADE_RELIC
        assert restored.min_floor == 4
        assert restored == graded


def test_the_grade_defaults_to_common(pool):
    """★ 등급이 없는 절이 터지면 배포 순서 하나로 서버가 안 뜬다."""
    from game.schemas.item import GRADE_COMMON, parse_item

    entry = parse_item({"id": "probe_x", "kind": "CONSUMABLE", "label_ko": "표본"})
    assert entry.grade == GRADE_COMMON


def test_the_export_refuses_to_write_an_empty_catalog(pool):
    """★ 빈 파일을 쓰면 씨앗이 사라지고 되살릴 곳이 없어진다.

    이 파일은 파생물이면서 **동시에 빈 DB 를 채우는 씨앗**이다. 시딩 전 DB 에 대고
    내보내기를 돌려 실제로 0개짜리 파일로 덮은 적이 있다.
    """
    import pytest as pytest_module

    from game.config import ITEMS_PATH
    from scripts import export_items as module

    # **파일도 함께 지킨다.** 가드가 없는 상태로 이 검사를 돌리면 내보내기가 저장소의
    # 씨앗 파일을 0개로 덮는다 — 반증하다가 실제로 그렇게 지웠다. 검사가 저장소를
    # 망가뜨릴 수 있으면 그 검사는 돌릴 수 없다.
    original = ITEMS_PATH.read_text(encoding="utf-8")
    saved = module.list_catalog
    module.list_catalog = lambda _pool: {}
    try:
        with pytest_module.raises(RuntimeError):
            module.export_items()
    finally:
        module.list_catalog = saved
        ITEMS_PATH.write_text(original, encoding="utf-8")


def test_the_export_carries_every_item(pool):
    """★ 내보내기가 한 줄이라도 빠뜨리면 헤드리스가 다른 카탈로그로 돈다."""
    import json

    from game.app.store.item_catalog import list_catalog
    from game.config import ITEMS_PATH
    from scripts.export_items import export_items

    original = ITEMS_PATH.read_text(encoding="utf-8")
    try:
        count = export_items()
        written = json.loads(ITEMS_PATH.read_text(encoding="utf-8"))
        assert count == len(list_catalog(pool))
        assert {item["id"] for item in written["items"]} == set(list_catalog(pool))
    finally:
        ITEMS_PATH.write_text(original, encoding="utf-8")
