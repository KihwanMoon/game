"""정비 규칙 — 런이 끝나면 서버가 자동으로 손본다 (설계/4_아이템 §5).

전투 규칙표의 형제이지 그 일부가 아니다. 블록으로 만들면 시즌이 갈리고 재시뮬이
복잡해질 뿐이라, 계정 설정의 닫힌 스위치로 두고 **티켓이 닫힐 때** 서버가 실행한다.

여기서 지키는 것은 다섯이다.

1. **기본은 전부 꺼짐이다.** 돈이 나가고 아이템이 사라지는 일은 사람이 켠 것이어야 한다.
2. **버리기는 가방의 그 등급만 본다.** 낀 것·소모품 스택·되찾은 것은 안 버린다.
3. **잔액이 마르면 멈춘다.** 빚을 내서 정비하지 않는다.
4. **보충은 수동 보충과 같은 값이다.** 정비라고 싸지면 수동을 누를 이유가 없다.
5. **버리기 등급은 닫힌 목록이다.** 오타가 조용히 「안 버림」이 되면 안 된다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)


@pytest.fixture
def client():
    """서버 하나."""
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as running:
        yield running


@pytest.fixture
def token(client):
    """새 계정의 토큰."""
    return client.post("/api/account").json()["token"]


def build_headers(token):
    """토큰을 헤더로 만든다.

    Args:
        token: 계정 토큰.

    Returns:
        요청 헤더.
    """
    return {"X-Game-Token": token}


def find_ids(client, token):
    """계정 id 와 개체 id 를 얻는다.

    Args:
        client: 서버.
        token: 계정 토큰.

    Returns:
        (계정 id, 개체 id).
    """
    from game.api.deps import get_pool
    from game.app.store.accounts import find_player_entity

    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    return account_id, find_player_entity(get_pool(), account_id)


def test_the_default_does_nothing(client, token):
    """★ 저장한 적 없는 계정의 정비는 빈 목록이고, 실행해도 아무 일도 없다."""
    from game.api.maintenance_service import apply_maintenance

    body = client.get("/api/maintenance", headers=build_headers(token)).json()
    assert body == {"rows": []}
    account_id, _entity_id = find_ids(client, token)
    assert apply_maintenance(account_id) == ""


def test_rows_keep_their_order(client, token):
    """★ 행 순서가 실행 순서다 — 저장이 흔들면 「버리고 복구」가 「복구하고 버리기」가 된다."""
    rows = [
        {"action": "REPAIR", "grade": ""},
        {"action": "DISCARD", "grade": "COMMON"},
        {"action": "SELL_STOCK", "grade": ""},
    ]
    saved = client.put("/api/maintenance", json={"rows": rows}, headers=build_headers(token)).json()
    assert saved["rows"] == rows
    again = client.get("/api/maintenance", headers=build_headers(token)).json()
    assert again["rows"] == rows


def test_an_unknown_row_is_refused(client, token):
    """★ 오타가 조용히 「안 함」이 되면, 켰다고 믿은 정비가 안 돈다."""
    headers = build_headers(token)
    for rows in (
        [{"action": "DISCARD", "grade": "COMMOM"}],
        [{"action": "EXPLODE", "grade": ""}],
        [{"action": "REPAIR", "grade": "COMMON"}],
        # 등급으로는 여전히 유물을 못 고른다. 유물까지 버리려면 「전부」를 골라야 하고,
        # 그것은 **등급이 아니라 「등급을 안 본다」**는 선언이라 실수로 눌리지 않는다.
        [{"action": "DISCARD", "grade": "RELIC"}],
    ):
        refused = client.put("/api/maintenance", json={"rows": rows}, headers=headers)
        assert refused.status_code == 422, rows


def test_sell_stock_leaves_loaded_slots_alone(client, token):
    """★ 재고 판매가 끼운 칸까지 팔면, 정비 한 번에 들고 갈 것이 사라진다."""
    from game.api.deps import get_pool
    from game.api.maintenance_service import apply_sell_rule
    from game.app.store.consumables import apply_slot_load, list_consumable_slots
    from game.app.store.equipment import read_balance
    from game.app.store.inventory_slots import apply_stack_grant

    account_id, entity_id = find_ids(client, token)
    pool = get_pool()
    apply_slot_load(pool, entity_id, "POTION", 0, "potion_heal", 2)
    apply_stack_grant(pool, entity_id, "potion_heal", 9)
    apply_stack_grant(pool, entity_id, "potion_heal", 9)
    sold, earned = apply_sell_rule(pool, account_id, entity_id)
    assert (sold, earned) == (2, 40)
    assert read_balance(pool, account_id) >= 40
    loaded = [s for s in list_consumable_slots(pool, entity_id) if s.catalog_id]
    assert loaded and loaded[0].charges == 2, "끼운 칸이 사라졌다"


def test_discard_takes_only_that_grade_from_the_bag(client, token):
    """★ 낀 것을 버리면 스탯이 유령이 되고, 되찾은 것을 버리면 되찾기가 뜻을 잃는다."""
    from game.api.deps import get_item_catalog, get_pool
    from game.api.maintenance_service import apply_discard_rule
    from game.app.store.equipment import apply_equip
    from game.app.store.items import create_item, list_equipment, list_inventory

    account_id, entity_id = find_ids(client, token)
    pool = get_pool()
    catalog = get_item_catalog()
    armor = next(key for key, entry in sorted(catalog.items()) if entry.slot is not None)
    worn = create_item(pool, entity_id, armor, (), grade="COMMON")
    apply_equip(pool, entity_id, worn, catalog[armor].slot)
    create_item(pool, entity_id, armor, (), grade="COMMON")
    fine = create_item(pool, entity_id, armor, (), grade="FINE")
    assert None not in (worn, fine)

    # 되찾은 물건 하나. 몬스터에게서 도로 빼앗아 온 것을 자동으로 버리면 되찾기가
    # 뜻을 잃는다.
    recovered = create_item(pool, entity_id, armor, (), grade="COMMON")
    # 되찾음은 저장된 플래그가 아니라 `taken_from`(빼앗겼던 계정)이 채워진 채 내 가방에
    # 있는 상태다.
    with pool.connection() as connection:
        connection.execute(
            "UPDATE item_instance SET taken_from = %s WHERE id = %s", (account_id, recovered)
        )

    assert apply_discard_rule(pool, entity_id, "COMMON") == 1
    left = [entry.item.item_id for entry in list_inventory(pool, entity_id) if entry.item]
    assert fine in left, "다른 등급까지 버렸다"
    assert recovered in left, "되찾은 것을 버렸다"
    assert worn in [item.item_id for item in list_equipment(pool, entity_id).values()], (
        "낀 것을 버렸다"
    )


def test_refill_stops_when_the_wallet_runs_dry(client, token):
    """★ 빚을 내서 정비하지 않는다 — 반쯤 채우지도 않는다."""
    from game.api.deps import get_pool
    from game.api.maintenance_service import apply_refill_rule
    from game.app.store.consumables import apply_slot_fill, apply_slot_load
    from game.app.store.equipment import read_balance

    account_id, entity_id = find_ids(client, token)
    pool = get_pool()
    # 회복 물약(칸 20×2충전=40)을 두 칸에 끼우고 전부 비운 뒤, 한 칸 값만 준다.
    for index in range(2):
        apply_slot_load(pool, entity_id, "POTION", index, "potion_heal", 2)
        apply_slot_fill(pool, entity_id, "POTION", index, 0)
    from game.app.store.equipment import add_currency

    add_currency(pool, account_id, 40)
    filled, paid = apply_refill_rule(pool, account_id, entity_id)
    assert (filled, paid) == (2, 40), "한 칸 값으로 두 칸을 채웠다"
    assert read_balance(pool, account_id) == 0


def test_maintenance_runs_only_when_the_ticket_closes(client, token):
    """★ 층 청구마다 돌면 런 중에 가방이 바뀐다 — 죽기 전에 주운 것이 사라질 수 있다."""
    from pathlib import Path

    source = Path("game/api/routes/run.py").read_text(encoding="utf-8")
    call = source.index("apply_maintenance(account.account_id)")
    guard = source.rindex("if is_run_closed", 0, call)
    # 호출이 닫힘 가드 안에 있다 — 가드와 호출 사이에 다른 if 블록 경계가 없어야 한다.
    between = source[guard:call]
    assert "is_run_closed" in between
    assert between.count("\n    if ") <= 1, "닫힘 가드 밖에서 정비가 돈다"


def build_bag_item(client, token, grade, is_recovered=False):
    """가방에 장비 하나를 넣는다.

    Args:
        client: 테스트 클라이언트.
        token: 기기 토큰.
        grade: 굴린 등급.
        is_recovered: 되찾은 것으로 표시할지. 저장된 플래그가 아니라 `taken_from`
            (빼앗겼던 계정)이 채워진 채 내 가방에 있는 상태다.

    Returns:
        만든 아이템 id.
    """
    from game.api.deps import get_item_catalog, get_pool
    from game.app.store.items import create_item

    account_id, entity_id = find_ids(client, token)
    catalog = get_item_catalog()
    armor = next(key for key, entry in sorted(catalog.items()) if entry.slot is not None)
    item_id = create_item(get_pool(), entity_id, armor, (), grade=grade)
    if is_recovered:
        with get_pool().connection() as connection:
            connection.execute(
                "UPDATE item_instance SET taken_from = %s WHERE id = %s", (account_id, item_id)
            )
    return item_id


def test_discard_all_empties_the_bag(client, token):
    """★ 되찾음 보호가 실제로는 가방을 영영 안 비웠다.

    죽고 되찾기를 되풀이하면 **가방 전체에** 그 표시가 붙는다 — 봇 하나는 17칸이 17칸 다
    되찾은 것이었고, 그래서 새 전리품이 들어올 자리가 없어 판마다 흘렸다. 「전부」는 그
    보호를 함께 내려놓는다: 등급도 유물도 되찾음도 안 본다.
    """
    from game.api.deps import get_pool
    from game.api.maintenance_service import apply_discard_rule
    from game.app.store.items import list_inventory
    from game.app.store.maintenance import DISCARD_ALL

    _account_id, entity_id = find_ids(client, token)
    build_bag_item(client, token, "COMMON", is_recovered=True)
    build_bag_item(client, token, "FINE")
    build_bag_item(client, token, "RELIC")

    assert apply_discard_rule(get_pool(), entity_id, DISCARD_ALL) == 3
    assert not [entry for entry in list_inventory(get_pool(), entity_id) if entry.item]


def test_discard_all_leaves_worn_gear_alone(client, token):
    """★ 낀 것은 안 버린다 — 「전부」여도 그렇다.

    낀 것을 버리면 스탯이 유령이 된다. 「전부」가 넓히는 것은 **가방 안에서** 무엇을
    남기느냐이지, 가방 밖까지 손대라는 뜻이 아니다.
    """
    from game.api.deps import get_item_catalog, get_pool
    from game.api.maintenance_service import apply_discard_rule
    from game.app.store.equipment import apply_equip
    from game.app.store.items import create_item, list_equipment
    from game.app.store.maintenance import DISCARD_ALL

    _account_id, entity_id = find_ids(client, token)
    pool = get_pool()
    catalog = get_item_catalog()
    armor = next(key for key, entry in sorted(catalog.items()) if entry.slot is not None)
    worn = create_item(pool, entity_id, armor, (), grade="RELIC")
    apply_equip(pool, entity_id, worn, catalog[armor].slot)

    apply_discard_rule(pool, entity_id, DISCARD_ALL)

    assert worn in [item.item_id for item in list_equipment(pool, entity_id).values()]


def test_discard_all_is_in_the_closed_vocabulary(client, token):
    """★ 저장 층이 받아야 화면이 그것을 쓸 수 있다 — 어휘는 한 곳에서 닫힌다."""
    rows = [{"action": "UPGRADE_GEAR", "grade": "ATTACK"}, {"action": "DISCARD", "grade": "ALL"}]
    saved = client.put("/api/maintenance", json={"rows": rows}, headers=build_headers(token))
    assert saved.status_code == 200, saved.text
    read = client.get("/api/maintenance", headers=build_headers(token)).json()
    assert [(row["action"], row["grade"]) for row in read["rows"]] == [
        ("UPGRADE_GEAR", "ATTACK"),
        ("DISCARD", "ALL"),
    ]


def test_the_run_route_applies_the_saved_rows(client, token):
    """★ 손으로 한 번 돌린다.

    정비가 「티켓이 닫힐 때만」 돌던 시절, 7층까지 이기고 그만두는 사람에게는 한 번도
    안 돌았다 — 그 판은 영영 안 닫히기 때문이다. 봇은 매판 죽어 늘 닫히므로 봇에서만
    도는 것처럼 보였다.
    """
    from game.api.deps import get_pool
    from game.app.store.consumables import apply_slot_load, list_consumable_slots
    from game.app.store.equipment import add_currency

    account_id, entity_id = find_ids(client, token)
    pool = get_pool()
    apply_slot_load(pool, entity_id, "POTION", 0, "potion_heal", 0)
    add_currency(pool, account_id, 5000)
    client.put(
        "/api/maintenance",
        json={"rows": [{"action": "REFILL", "grade": ""}]},
        headers=build_headers(token),
    )

    response = client.post("/api/maintenance/run", headers=build_headers(token))

    assert response.status_code == 200, response.text
    assert "보충" in response.json()["detail"]
    loaded = [one for one in list_consumable_slots(pool, entity_id) if one.catalog_id]
    assert loaded and loaded[0].charges > 0, "채워지지 않았다"


def test_running_with_nothing_to_do_is_quiet(client, token):
    """★ 할 일이 없었다는 것도 답이다 — 빈 줄을 그냥 두면 눌린 건지 아닌지 모른다."""
    client.put(
        "/api/maintenance",
        json={"rows": [{"action": "REPAIR", "grade": ""}]},
        headers=build_headers(token),
    )

    response = client.post("/api/maintenance/run", headers=build_headers(token))

    assert response.status_code == 200
    assert response.json()["detail"] == ""


def test_a_ticket_issue_runs_maintenance(client, token):
    """★ 나가기 직전에 정비한다 — 「판과 판 사이」의 확실한 신호는 이 순간뿐이다.

    **로드아웃을 짜기 전이어야 한다.** 뒤에 두면 고친 장비와 채운 물약을 두고 나가게
    되고, 정비가 한 판 늦게 반영된다.
    """
    from game.api.deps import get_pool
    from game.app.store.consumables import apply_slot_load, list_consumable_slots
    from game.app.store.equipment import add_currency

    account_id, entity_id = find_ids(client, token)
    pool = get_pool()
    apply_slot_load(pool, entity_id, "POTION", 0, "potion_heal", 0)
    add_currency(pool, account_id, 5000)
    client.put(
        "/api/maintenance",
        json={"rows": [{"action": "REFILL", "grade": ""}]},
        headers=build_headers(token),
    )

    issued = client.post("/api/ticket", json={"room_id": "corridor"}, headers=build_headers(token))

    assert issued.status_code == 200, issued.text
    loaded = [one for one in list_consumable_slots(pool, entity_id) if one.catalog_id]
    assert loaded and loaded[0].charges > 0, "티켓을 받았는데 안 채워졌다"
    # 그 판에 실제로 들고 나가는 값에도 반영돼야 한다 — 아니면 한 판 늦는다.
    assert issued.json()["loadout"]["consumables"].get("POTION", 0) > 0
