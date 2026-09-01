"""드롭 표 시딩 (설계/4_아이템 §15.2, §15.4).

여기서 지키는 것은 셋이다.

1. **아이템은 제 등급과 그 위 등급에 다 깔린다.** 제 등급 한 칸에만 넣으면 상위 등급을
   뽑아 놓고 후보가 없어 굴림이 통째로 증발한다 — 프로덕션에서 26건이 그렇게 사라졌다.
2. **나중에 등록한 것도 들어간다.** 예전에는 등급 가중치가 있으면 곧장 돌아가서, 관리자가
   새로 등록한 아이템이 등록은 되는데 나오지는 않았다.
3. **조정한 가중치를 안 덮는다.** 배포 한 번에 밸런스가 되돌아가면 표를 고칠 수 없다.
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
    """연결 풀. 앱을 세워 마이그레이션까지 끝난 상태를 받는다.

    풀은 수명주기가 열어 주므로 `TestClient` 를 컨텍스트로 써야 한다 — `create_app()`
    만 부르면 풀이 없다.
    """
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from game.api.deps import get_pool
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()):
        yield get_pool()


def build_entry(catalog_id, grade):
    """검사용 카탈로그 항목 하나를 만든다.

    Args:
        catalog_id: 아이템 id.
        grade: 최저 등급.

    Returns:
        카탈로그 항목.
    """
    from game.schemas.item import EquipSlot, ItemCatalogEntry, ItemKind, WeaponHands

    return ItemCatalogEntry(
        catalog_id=catalog_id,
        kind=ItemKind.EQUIPMENT,
        label_ko="표본 검",
        slot=EquipSlot.WEAPON_MAIN,
        hands=WeaponHands.ONE,
        grade=grade,
    )


def create_seeded(pool, entries):
    """항목들을 저장하고 시드를 돌린다.

    Args:
        pool: 연결 풀.
        entries: 카탈로그 항목들.

    Returns:
        새로 채운 줄 수.
    """
    from game.app.store.drops import apply_drop_seed
    from game.app.store.item_catalog import save_catalog_entry

    for entry in entries:
        save_catalog_entry(pool, entry)
    return apply_drop_seed(pool, {entry.catalog_id: entry for entry in entries})


def read_grades(pool, catalog_id):
    """그 아이템이 깔린 등급들을 읽는다.

    Args:
        pool: 연결 풀.
        catalog_id: 아이템 id.

    Returns:
        등급 코드들. 정렬돼 있다.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT grade FROM drop_item_weight WHERE catalog_id = %s ORDER BY grade",
            (catalog_id,),
        ).fetchall()
    return sorted(str(row[0]) for row in rows)


def build_probe_id(pool, suffix):
    """이 실행에서만 쓰는 id 를 만든다.

    **매번 새 id 를 쓴다.** 같은 id 를 쓰면 앞선 실행이 남긴 드롭 표 줄 때문에 "깔렸는가"
    가 코드와 무관하게 통과한다 — 실제로 그렇게 통과했다.

    Args:
        pool: 연결 풀.
        suffix: 구분용 꼬리표.

    Returns:
        아이템 id.
    """
    with pool.connection() as connection:
        row = connection.execute("SELECT nextval('item_instance_id_seq')").fetchone()
    return f"seedprobe_{int(row[0])}_{suffix}"


def test_an_item_lands_in_its_grade_and_every_grade_above(pool):
    """★ 보통 아이템이 유물로도 나온다 — 다른 점은 봉인 칸 수다 (§17).

    제 등급 한 칸에만 넣으면 상급·유물을 뽑아 놓고 후보가 없어 굴림이 증발한다.
    """
    common_id = build_probe_id(pool, "common")
    fine_id = build_probe_id(pool, "fine")
    relic_id = build_probe_id(pool, "relic")
    create_seeded(
        pool,
        (
            build_entry(common_id, "COMMON"),
            build_entry(fine_id, "FINE"),
            build_entry(relic_id, "RELIC"),
        ),
    )
    assert read_grades(pool, common_id) == ["COMMON", "FINE", "RELIC"]
    # 최저 등급이 상급이면 보통 칸에는 안 나온다. 그것이 `grade` 가 뜻하는 바다.
    assert read_grades(pool, fine_id) == ["FINE", "RELIC"]
    assert read_grades(pool, relic_id) == ["RELIC"]


def test_an_item_registered_later_still_enters_the_table(pool):
    """★ 등록은 됐는데 나오지는 않는 아이템이 없어야 한다.

    시드가 등급 가중치만 보고 돌아가면 관리자가 새로 등록한 것이 표에 영영 안 들어간다.
    """
    first_id = build_probe_id(pool, "first")
    later_id = build_probe_id(pool, "later")
    create_seeded(pool, (build_entry(first_id, "COMMON"),))
    filled = create_seeded(pool, (build_entry(first_id, "COMMON"), build_entry(later_id, "COMMON")))
    assert read_grades(pool, later_id) == ["COMMON", "FINE", "RELIC"]
    # 이미 있던 줄은 다시 안 센다 — 나중 것 세 줄뿐이다.
    assert filled == 3


def test_a_tuned_weight_survives_the_next_seed(pool):
    """★ 조정한 가중치가 배포 한 번에 되돌아가면 표를 고칠 수 없다."""
    from game.app.store.drops import SOURCE_ANY, find_source

    catalog_id = build_probe_id(pool, "tuned")
    entry = build_entry(catalog_id, "COMMON")
    create_seeded(pool, (entry,))
    source_id = find_source(pool, SOURCE_ANY)
    with pool.connection() as connection:
        connection.execute(
            "UPDATE drop_item_weight SET weight = 0 WHERE source_id = %s AND catalog_id = %s",
            (source_id, catalog_id),
        )
    assert create_seeded(pool, (entry,)) == 0
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT DISTINCT weight FROM drop_item_weight WHERE catalog_id = %s", (catalog_id,)
        ).fetchall()
    assert [int(row[0]) for row in rows] == [0]


def test_a_quest_item_lands_in_no_grade(pool):
    """★ 퀘스트 아이템은 굴려서 나오지 않는다 (§4).

    프로덕션에서 「봉인된 각인」이 전리품으로 나온 적이 있다. 등급을 셋으로 늘리면 그
    사고가 세 배로 늘어난다.
    """
    from dataclasses import replace

    from game.schemas.item import ItemKind

    catalog_id = build_probe_id(pool, "quest")
    entry = replace(build_entry(catalog_id, "COMMON"), kind=ItemKind.QUEST, slot=None, hands=None)
    create_seeded(pool, (entry,))
    assert read_grades(pool, catalog_id) == []
