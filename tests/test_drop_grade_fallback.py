"""후보가 없는 등급 (설계/4_아이템 §15.2).

**천장을 태우는 자리가 여기다.** 예전에는 후보를 찾기 전에 「나왔다」를 눌러서, 표가 빈
등급을 뽑을 때마다 천장이 0 으로 돌아가고 손에는 아무것도 안 남았다 — 프로덕션 원장에
상급 19건·유물 7건이 그렇게 사라져 있었다. 오래 못 받은 사람일수록 그 경로를 자주 밟으므로
천장이 있으나 마나가 된다.

여기서 지키는 것은 둘이다.

1. **후보가 없으면 천장이 그대로 쌓인다.**
2. **강등해서 준 것은 뽑힌 등급을 받은 것이 아니다.** 유물을 뽑아 보통을 받았으면 유물
   천장은 계속 쌓여야 한다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)

# 1단계 저울의 자리. 실제 가중치는 이 검사와 무관하다 — 뽑힌 등급을 직접 넣기 때문이다.
PROBE_ENTRIES = (("COMMON", 1), ("FINE", 1), ("MISS", 1), ("RELIC", 1))


@pytest.fixture
def client():
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as running:
        yield running


def build_account(client):
    """계정 하나와 그 개체를 만든다.

    Args:
        client: 테스트 클라이언트.

    Returns:
        (계정 id, 개체 id).
    """
    from game.api.deps import get_pool
    from game.app.store.accounts import find_player_entity

    account = client.post("/api/account").json()
    account_id = int(account["account_id"])
    return account_id, find_player_entity(get_pool(), account_id)


def create_empty_source(account_id):
    """아이템 가중치가 하나도 없는 드롭 소스를 만든다.

    Args:
        account_id: 계정 id. 소스 식별자를 이 실행 전용으로 만드는 데 쓴다.

    Returns:
        소스 id.
    """
    from game.api.deps import get_pool
    from game.app.store.drops import SOURCE_MONSTER, save_source

    return save_source(get_pool(), SOURCE_MONSTER, f"probe_empty_{account_id}")


def create_common_only_source(account_id):
    """보통 등급에만 후보가 있는 소스를 만든다.

    Args:
        account_id: 계정 id.

    Returns:
        (소스 id, 아이템 id).
    """
    from game.api.deps import apply_catalog_reload, get_pool
    from game.app.store.drops import SOURCE_MONSTER, save_source
    from game.app.store.item_catalog import save_catalog_entry
    from game.schemas.item import EquipSlot, ItemCatalogEntry, ItemKind, WeaponHands

    pool = get_pool()
    catalog_id = f"fallbackprobe_{account_id}"
    save_catalog_entry(
        pool,
        ItemCatalogEntry(
            catalog_id=catalog_id,
            kind=ItemKind.EQUIPMENT,
            label_ko="강등 표본 검",
            slot=EquipSlot.WEAPON_MAIN,
            hands=WeaponHands.ONE,
        ),
    )
    apply_catalog_reload()
    source_id = save_source(pool, SOURCE_MONSTER, f"probe_common_{account_id}")
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO drop_item_weight (source_id, grade, catalog_id, weight)"
            " VALUES (%s, 'COMMON', %s, 1) ON CONFLICT DO NOTHING",
            (source_id, catalog_id),
        )
    return source_id, catalog_id


def apply_roll(account_id, entity_id, source_id, rolled):
    """뽑힌 등급을 직접 넣어 2단계를 돌린다.

    Args:
        account_id: 계정 id.
        entity_id: 개체 id.
        source_id: 드롭 소스.
        rolled: 1단계가 뽑았다고 칠 등급.

    Returns:
        화면에 적을 한 줄.
    """
    from game.api.deps import get_pool
    from game.api.loot_service import apply_grade_roll

    return apply_grade_roll(
        get_pool(),
        entity_id,
        {
            "account_id": account_id,
            "rolled": rolled,
            "entries": PROBE_ENTRIES,
            "source_id": source_id,
            "floor": 1,
            "fields": {
                "submission_id": None,
                "source_kind": "MONSTER_KIND",
                "source_ref": f"probe_{account_id}",
                "monster_level": 1,
                "floor": 1,
                "generation": 1,
            },
        },
    )


def read_misses(account_id, grade):
    """그 등급의 연속 미획득 수를 읽는다.

    Args:
        account_id: 계정 id.
        grade: 등급.

    Returns:
        미획득 수. 기록이 없으면 0.
    """
    from game.api.deps import get_pool
    from game.app.store.drops import read_pity

    return read_pity(get_pool(), account_id).get(grade, 0)


def test_an_empty_grade_does_not_burn_the_pity(client):
    """★ 후보가 없어 못 준 굴림이 천장을 0 으로 되돌리면 천장이 있으나 마나가 된다."""
    account_id, entity_id = build_account(client)
    source_id = create_empty_source(account_id)
    for _step in range(3):
        apply_roll(account_id, entity_id, source_id, "RELIC")
    # 세 번 다 후보가 없었다. 세 번 다 미획득으로 쌓여야 한다.
    assert read_misses(account_id, "RELIC") == 3


def test_an_empty_grade_gives_nothing_and_says_so(client):
    """★ 못 준 굴림은 빈손으로 돌아가고 원장에 사유가 남는다 (D4)."""
    from game.api.deps import get_pool

    account_id, entity_id = build_account(client)
    source_id = create_empty_source(account_id)
    assert apply_roll(account_id, entity_id, source_id, "RELIC") == ""
    with get_pool().connection() as connection:
        rows = connection.execute(
            "SELECT grade, detail FROM item_roll_log WHERE account_id = %s", (account_id,)
        ).fetchall()
    assert [(str(row[0]), str(row[1])) for row in rows] == [("RELIC", "그 등급에 후보가 없다")]


def test_a_demotion_keeps_the_rolled_grade_unpaid(client):
    """★ 유물을 뽑아 보통을 받았으면 유물 천장은 계속 쌓여야 한다.

    강등을 「받았다」로 치면 유물 천장이 영원히 0 근처에 머문다.
    """
    account_id, entity_id = build_account(client)
    source_id, _catalog_id = create_common_only_source(account_id)
    note = apply_roll(account_id, entity_id, source_id, "RELIC")
    assert "획득" in note
    assert read_misses(account_id, "RELIC") == 1
    # 실제로 준 등급의 천장만 0 으로 되돌아간다.
    assert read_misses(account_id, "COMMON") == 0


def test_a_demoted_item_carries_the_grade_it_was_issued_at(client):
    """★ 강등해서 준 것은 보통이다 — 유물로 적으면 봉인 칸이 공짜로 둘 생긴다 (§17)."""
    from game.api.deps import get_pool

    account_id, entity_id = build_account(client)
    source_id, catalog_id = create_common_only_source(account_id)
    apply_roll(account_id, entity_id, source_id, "RELIC")
    with get_pool().connection() as connection:
        row = connection.execute(
            "SELECT grade, sealed_slots FROM item_instance WHERE catalog_id = %s", (catalog_id,)
        ).fetchone()
    assert (str(row[0]), int(row[1])) == ("COMMON", 0)


def test_the_ledger_records_the_demotion(client):
    """★ 강등을 안 남기면 나중에 분포를 재 볼 때 상급이 실제보다 많아 보인다."""
    from game.api.deps import get_pool

    account_id, entity_id = build_account(client)
    source_id, _catalog_id = create_common_only_source(account_id)
    apply_roll(account_id, entity_id, source_id, "RELIC")
    with get_pool().connection() as connection:
        row = connection.execute(
            "SELECT grade, detail FROM item_roll_log WHERE account_id = %s", (account_id,)
        ).fetchone()
    assert str(row[0]) == "COMMON"
    assert "RELIC → COMMON 강등" in str(row[1])
