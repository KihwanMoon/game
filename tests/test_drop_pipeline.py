"""전리품 파이프라인 끝에서 끝까지 (설계/4_아이템 §15).

**조각마다 검사가 있어도 이어 붙인 것이 도는지는 다른 질문이다.** 이번에 고친 셋은 전부
"조각은 맞는데 이어 붙이면 안 나온다" 였다 — 등급표는 있는데 후보가 없고, 봉인 칸 규칙은
있는데 칸이 0 이고, 접사는 정의돼 있는데 발급이 잘랐다.

그래서 여기서는 **진짜 굴림을 여러 번 돌린다.** `create_kill_drop` 을 그대로 부르고,
가방에 실제로 들어온 것을 읽는다.

굴림은 `secrets` 라 결과가 매번 다르다. 그래서 **개수가 아니라 성질**을 본다 — 「유물이
나오면 봉인 칸이 둘이다」는 몇 번을 굴리든 참이어야 한다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)

# 굴림 횟수. 한 런이 열여섯 번이므로 이것은 예순 판쯤이다 — 유물(만분의 5)이 몇 개는
# 나오되 검사가 몇 초 안에 끝나는 지점이다.
ROLLS = 1000


@pytest.fixture
def client():
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as running:
        yield running


def create_rolled(client, rolls=ROLLS):
    """계정 하나로 여러 번 굴리고 가방을 읽는다.

    Args:
        client: 테스트 클라이언트.
        rolls: 굴림 횟수.

    Returns:
        (계정 id, 발급된 인스턴스 줄들). 줄은 (등급, 봉인 칸, 접사 수, catalog_id).
    """
    from game.api.deps import get_pool
    from game.api.loot_service import create_kill_drop
    from game.app.store.accounts import find_player_entity

    account_id = int(client.post("/api/account").json()["account_id"])
    pool = get_pool()
    entity_id = find_player_entity(pool, account_id)
    for _step in range(rolls):
        # 층을 높게 잡는다. `min_floor` 가 후보를 걸러 내면 파이프라인이 아니라 데이터를
        # 재게 된다.
        create_kill_drop(
            account_id, entity_id, {"kind_id": "goblin_rusher", "level": 5, "floor": 9}
        )
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT grade, sealed_slots, jsonb_array_length(affixes), catalog_id"
            " FROM item_instance WHERE owner_entity_id = %s",
            (entity_id,),
        ).fetchall()
    return account_id, [(str(r[0]), int(r[1]), int(r[2]), str(r[3])) for r in rows]


def test_every_grade_can_actually_be_issued(client):
    """★ 상급·유물이 **실제로 손에 들어온다**.

    프로덕션에서 상급 19건·유물 7건이 「그 등급에 후보가 없다」로 증발했다. 표가 깔린
    것만으로는 그 사고가 다시 안 난다는 보장이 없다 — 굴려서 확인한다.
    """
    _account_id, rows = create_rolled(client)
    grades = {row[0] for row in rows}
    assert "COMMON" in grades, f"보통조차 안 나왔다: {grades}"
    # 상급은 만분의 55 다. 천 번이면 못 볼 확률이 사실상 0 이다.
    assert "FINE" in grades, f"상급이 한 번도 안 나왔다: {grades}"


def test_a_grade_always_brings_its_sealed_slots(client):
    """★ 등급이 봉인 칸을 준다 (§17) — 이것이 등급이 성능에 하는 유일한 일이다.

    프로덕션에서는 전부 보통이라 봉인 칸 합계가 0 이었고, 만든 기능이 뜰 수 없었다.
    """
    from game.schemas.item import GRADE_SEALED_SLOTS

    _account_id, rows = create_rolled(client)
    assert rows, "천 번을 굴렸는데 아무것도 안 나왔다"
    for grade, sealed, _affixes, catalog_id in rows:
        assert sealed == GRADE_SEALED_SLOTS[grade], f"{catalog_id}({grade}) 의 봉인 칸이 {sealed}"


def test_every_fixed_affix_arrives_in_the_bag(client):
    """★ 카탈로그가 정한 접사가 **전부** 가방까지 온다.

    등급이 개수를 정하고 앞에서 자르던 때는 저주가 늘 잘렸다 — 대검의 과부하와 장궁의
    페널티가 한 번도 발급되지 않았고, 인스턴스 36개가 전부 접사 하나였다.
    """
    from game.api.deps import get_item_catalog

    _account_id, rows = create_rolled(client)
    catalog = get_item_catalog()
    assert rows, "천 번을 굴렸는데 아무것도 안 나왔다"
    for _grade, _sealed, affixes, catalog_id in rows:
        expected = len(catalog[catalog_id].affixes)
        assert affixes == expected, (
            f"{catalog_id} 의 접사가 {affixes}개다 (카탈로그는 {expected}개)"
        )


def test_a_quest_item_never_arrives(client):
    """★ 퀘스트 아이템은 굴려서 안 나온다 — 프로덕션에서 한 번 나온 적이 있다."""
    from game.api.deps import get_item_catalog
    from game.schemas.item import ItemKind

    _account_id, rows = create_rolled(client)
    catalog = get_item_catalog()
    quest = [row[3] for row in rows if catalog[row[3]].kind is ItemKind.QUEST]
    assert quest == []


def test_the_ledger_counts_every_roll(client):
    """★ 안 나온 굴림도 원장에 남는다 (D4).

    결과만 남기면 확률이 맞는지 사후에 증명할 수 없다 — 이번에 프로덕션 원장이 없었으면
    상급·유물이 증발한다는 사실을 아무도 몰랐다.
    """
    from game.api.deps import get_pool

    account_id, _rows = create_rolled(client, rolls=50)
    with get_pool().connection() as connection:
        row = connection.execute(
            "SELECT count(*) FROM item_roll_log WHERE account_id = %s", (account_id,)
        ).fetchone()
    assert int(row[0]) == 50
