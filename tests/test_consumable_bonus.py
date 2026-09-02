"""소모품 칸이 늘어나고, 끼운 것이 능력치를 준다 (설계/4_아이템 §5).

칸을 만들 때 **칸 수를 고정으로 두고** 먼저 돌아가게 했다. 여기서 그 둘을 연다.

1. **접사가 칸을 늘린다.** `potion_slots`·`scroll_slots` 가 그 통로다.
2. **끼운 소모품이 부가 옵션을 준다.** 물약은 버티는 쪽, 주문서는 막는 쪽이다.

두 가지 함정이 있고 둘 다 조용하다.

* `COMBAT_STATS` 에 없는 stat 은 **파싱은 되고 합산은 안 된다.** 접사를 붙여도 아무
  일이 안 일어나고 오류도 안 난다.
* 읽는 쪽과 깎는 쪽이 다른 칸 수를 보면 **늘어난 칸만 영원히 공짜**가 된다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV
from game.schemas.consumable import MAX_SLOTS_PER_TAG, SLOT_STATS, resolve_slot_count
from game.schemas.item import (
    COMBAT_STATS,
    STAT_LABELS,
    Affix,
    EquipSlot,
    ItemCatalogEntry,
    ItemKind,
)


def build_wearable(affixes, slot=EquipSlot.BODY):
    """접사를 단 장비 하나를 만든다.

    Args:
        affixes: 붙일 접사들.
        slot: 착용 슬롯.

    Returns:
        카탈로그 항목.
    """
    return ItemCatalogEntry(
        catalog_id="probe_armor",
        kind=ItemKind.EQUIPMENT,
        label_ko="표본 갑옷",
        slot=slot,
        affixes=tuple(affixes),
    )


def test_the_slot_stats_are_in_the_canon():
    """★ **정본에 없으면 조용히 무효다.** 접사는 붙는데 칸은 안 늘고 오류도 안 난다."""
    for stat in sorted(SLOT_STATS.values()):
        assert stat in COMBAT_STATS, f"{stat} 이 COMBAT_STATS 에 없다"
        assert stat in STAT_LABELS, f"{stat} 의 한글 이름이 없다"


def test_an_affix_adds_a_slot():
    """★ 안 늘면 「칸을 늘려 주는 옵션」이 이름뿐이다."""
    assert resolve_slot_count("POTION") == 2
    assert resolve_slot_count("POTION", 1) == 3


def test_slots_never_pass_the_cap():
    """★ 상한이 없으면 봉인을 여러 번 연 캐릭터가 물약을 열 개 들고 다닌다."""
    assert resolve_slot_count("POTION", 99) == MAX_SLOTS_PER_TAG


def test_a_negative_bonus_never_removes_a_slot():
    """★ 음수 접사 하나가 들어오면 끼워 둔 것이 통째로 잠긴다 — 기본 칸은 안 뺏는다."""
    assert resolve_slot_count("POTION", -5) == 2


def test_an_unknown_kind_gains_nothing():
    """★ 어디에도 안 적힌 칸이 생기면 그 칸에 든 물약을 아무도 못 본다."""
    assert resolve_slot_count("TRINKET", 3) == 0


def test_the_bonus_comes_from_worn_gear():
    """★ 장비에서 안 읽으면 접사를 굴려도 칸이 그대로다."""
    from game.api.loadout_service import count_slot_bonus

    equipped = {EquipSlot.BODY: build_wearable([Affix(stat="potion_slots", flat=1)])}
    assert count_slot_bonus(equipped)["POTION"] == 1
    assert count_slot_bonus(equipped)["SCROLL"] == 0


def test_a_sealed_slot_grants_nothing():
    """★ 양손무기가 봉인한 보조 슬롯의 「물약 주머니」가 살아 있으면 봉인이 뜻을 잃는다."""
    from game.api.loadout_service import count_slot_bonus
    from game.schemas.item import WeaponHands

    equipped = {
        EquipSlot.WEAPON_MAIN: ItemCatalogEntry(
            catalog_id="probe_greatsword",
            kind=ItemKind.EQUIPMENT,
            label_ko="표본 대검",
            slot=EquipSlot.WEAPON_MAIN,
            hands=WeaponHands.TWO,
        ),
        EquipSlot.WEAPON_OFF: build_wearable(
            [Affix(stat="potion_slots", flat=1)], slot=EquipSlot.WEAPON_OFF
        ),
    }
    assert count_slot_bonus(equipped)["POTION"] == 0


def build_potion(stat="hp_max", flat=12):
    """부가 옵션을 단 소모품 하나.

    Args:
        stat: 올릴 능력치.
        flat: 올리는 양.

    Returns:
        카탈로그 항목.
    """
    return ItemCatalogEntry(
        catalog_id="probe_potion",
        kind=ItemKind.CONSUMABLE,
        label_ko="표본 물약",
        use_tag="POTION",
        charges=3,
        affixes=(Affix(stat=stat, flat=flat),),
    )


BASE = {"hp_max": 100, "attack": 10, "defense": 5, "attack_range": 1, "initiative": 50}


def test_a_loaded_consumable_raises_a_stat():
    """★ 안 올라가면 「소모품도 장착 시 부가 옵션」이 이름뿐이다."""
    from game.app.items.loadout import build_player_loadout

    plain = build_player_loadout(BASE, {}, level=1, base_rule_slots=3)
    loaded = build_player_loadout(BASE, {}, level=1, base_rule_slots=3, carried=(build_potion(),))
    assert loaded.hp_max == plain.hp_max + 12


def test_two_slots_stack():
    """★ 안 쌓이면 칸을 둘 채울 이유가 없다."""
    from game.app.items.loadout import build_player_loadout

    loaded = build_player_loadout(
        BASE, {}, level=1, base_rule_slots=3, carried=(build_potion(), build_potion())
    )
    assert loaded.hp_max == BASE["hp_max"] + 24


def test_an_unknown_stat_is_still_refused():
    """★ 칸 능력치를 열었다고 아무 이름이나 열리면 안 된다 — 오타가 조용히 무효가 된다."""
    from game.schemas.item import list_unknown_stats

    assert list_unknown_stats((Affix(stat="potion_slot", flat=1),)) == ("potion_slot",)
    assert list_unknown_stats((Affix(stat="potion_slots", flat=1),)) == ()


pytestmark_db = pytest.mark.skipif(
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


@pytestmark_db
def test_the_pool_offers_the_slot_options(client):
    """★ 풀에 없으면 봉인을 열어도 칸 옵션이 안 나온다.

    **이미 채워진 표에도 들어가야 한다.** 「비어 있을 때만 채운다」로 두면 이미 도는
    서버에는 영영 안 들어간다 — 카탈로그와 드롭 표에서 이미 두 번 겪었다.
    """
    from game.api.deps import get_pool
    from game.app.store.items import apply_affix_pool_seed, list_affix_pool

    assert client is not None
    apply_affix_pool_seed(get_pool())
    stats = {row[0] for row in list_affix_pool(get_pool())}
    assert "potion_slots" in stats
    assert "scroll_slots" in stats


@pytestmark_db
def test_a_pouch_opens_a_third_potion_slot(client):
    """★ 끝에서 끝까지 — 장비의 「물약 주머니」가 칸을 하나 열고 티켓이 그것을 싣는다.

    **여기가 층이 갈리는 자리다.** 칸 수를 읽는 쪽(라우트)과 깎는 쪽(정산)과 싣는
    쪽(로드아웃)이 각자 세면, 늘어난 칸만 영원히 공짜가 된다.
    """
    from game.api.deps import get_item_catalog, get_pool
    from game.app.store.accounts import find_player_entity
    from game.app.store.equipment import apply_equip
    from game.app.store.items import create_item
    from game.schemas.loadout import parse_loadout

    headers = {"X-Game-Token": client.post("/api/account").json()["token"]}
    account_id = client.get("/api/account", headers=headers).json()["account_id"]
    pool = get_pool()
    entity_id = find_player_entity(pool, account_id)

    before = client.get("/api/consumables", headers=headers).json()["slots"]
    assert len([s for s in before if s["use_tag"] == "POTION"]) == 2

    # 「물약 주머니」를 굴린 갑옷 하나를 만들어 입힌다. 어느 장비든 상관없다 —
    # 칸을 여는 것은 슬롯이 아니라 접사다.
    catalog_id = next(
        key
        for key, entry in sorted(get_item_catalog().items())
        if entry.slot is not None and entry.kind is ItemKind.EQUIPMENT
    )
    item_id = create_item(
        pool,
        entity_id,
        catalog_id,
        (Affix(stat="potion_slots", flat=1, label_ko="물약 주머니"),),
        grade="FINE",
    )
    assert item_id is not None
    apply_equip(pool, entity_id, item_id, get_item_catalog()[catalog_id].slot)

    after = client.get("/api/consumables", headers=headers).json()["slots"]
    assert len([s for s in after if s["use_tag"] == "POTION"]) == 3, "칸이 안 열렸다"

    # 티켓도 같은 수를 봐야 한다 — 빈 칸 셋이면 공짜 충전도 셋이다.
    issued = client.post("/api/ticket", json={"room_id": "open_field"}, headers=headers).json()
    assert dict(parse_loadout(issued["loadout"]).consumables)["POTION"] == 3


@pytestmark_db
def test_an_extra_slot_is_spent_too(client):
    """★ **늘어난 칸만 영원히 공짜가 되던 자리다.**

    깎는 쪽이 기본 칸 수만 보면, 접사로 연 세 번째 칸의 충전은 아무리 마셔도 안 줄어든다.
    읽는 쪽·싣는 쪽·깎는 쪽이 **같은 칸 수**를 봐야 한다.
    """
    from game.api.deps import get_item_catalog, get_pool
    from game.api.loadout_service import count_slot_bonus
    from game.app.store.accounts import find_player_entity
    from game.app.store.consumables import apply_slot_load, apply_slot_spend, list_consumable_slots
    from game.app.store.equipment import apply_equip
    from game.app.store.items import create_item

    headers = {"X-Game-Token": client.post("/api/account").json()["token"]}
    account_id = client.get("/api/account", headers=headers).json()["account_id"]
    pool = get_pool()
    entity_id = find_player_entity(pool, account_id)
    catalog = get_item_catalog()

    catalog_id = next(
        key
        for key, entry in sorted(catalog.items())
        if entry.slot is not None and entry.kind is ItemKind.EQUIPMENT
    )
    item_id = create_item(
        pool,
        entity_id,
        catalog_id,
        (Affix(stat="potion_slots", flat=1, label_ko="물약 주머니"),),
        grade="FINE",
    )
    assert item_id is not None
    apply_equip(pool, entity_id, item_id, catalog[catalog_id].slot)

    from game.api.loadout_service import build_equipped_entries

    bonus = count_slot_bonus(build_equipped_entries(pool, entity_id, catalog))
    assert bonus["POTION"] == 1

    # 세 칸을 모두 채운다. 한 칸에 두 충전씩 여섯이다.
    for index in range(3):
        apply_slot_load(pool, entity_id, "POTION", index, "potion_heal", 2)

    # 다섯을 썼다. 빈 칸이 없으므로 공짜분은 0 이고, 낮은 칸부터 2·2·1 로 빠진다.
    assert apply_slot_spend(pool, entity_id, "POTION", 5, bonus) == 5
    left = [
        s.charges for s in list_consumable_slots(pool, entity_id, bonus) if s.use_tag == "POTION"
    ]
    assert left == [0, 0, 1], left


@pytestmark_db
def test_the_settlement_sees_the_extra_slot(client):
    """★ 정산이 기본 칸 수로 깎으면, 접사로 연 칸의 물약은 **마셔도 안 줄어든다.**

    앞 검사는 저장 층이 같은 칸 수를 보는지 봤다. 여기는 **제출 경로가 그 값을 넘기는지**
    본다 — 넘기는 것을 빼먹으면 저장 층이 아무리 옳아도 그 칸은 공짜가 된다.
    """
    from game.api.deps import get_item_catalog, get_pool
    from game.api.floor_service import apply_charge_spend
    from game.api.loadout_service import build_equipped_entries, count_slot_bonus
    from game.app.services.verify_run import VERDICT_VERIFIED, VerifiedRun
    from game.app.store.accounts import find_player_entity
    from game.app.store.consumables import apply_slot_load, list_consumable_slots
    from game.app.store.equipment import apply_equip
    from game.app.store.items import create_item
    from game.app.store.tickets import find_open_ticket

    headers = {"X-Game-Token": client.post("/api/account").json()["token"]}
    account_id = client.get("/api/account", headers=headers).json()["account_id"]
    pool = get_pool()
    entity_id = find_player_entity(pool, account_id)
    catalog = get_item_catalog()

    catalog_id = next(
        key
        for key, entry in sorted(catalog.items())
        if entry.slot is not None and entry.kind is ItemKind.EQUIPMENT
    )
    item_id = create_item(
        pool,
        entity_id,
        catalog_id,
        (Affix(stat="potion_slots", flat=1, label_ko="물약 주머니"),),
        grade="FINE",
    )
    assert item_id is not None
    apply_equip(pool, entity_id, item_id, catalog[catalog_id].slot)
    bonus = count_slot_bonus(build_equipped_entries(pool, entity_id, catalog))
    for index in range(3):
        apply_slot_load(pool, entity_id, "POTION", index, "potion_heal", 2)

    issued = client.post("/api/ticket", json={"room_id": "open_field"}, headers=headers).json()
    ticket = find_open_ticket(pool, issued["ticket_id"], account_id)
    assert ticket is not None
    apply_charge_spend(
        account_id,
        ticket,
        VerifiedRun(
            outcome="PLAYER_WIN",
            ticks=1,
            player_hp=1,
            verdict=VERDICT_VERIFIED,
            remaining_consumables=(("POTION", 1),),
        ),
    )
    left = [
        slot.charges
        for slot in list_consumable_slots(pool, entity_id, bonus)
        if slot.use_tag == "POTION"
    ]
    # 여섯을 싣고 하나를 남겼으니 다섯을 썼다. 낮은 칸부터 2·2·1 로 빠진다 —
    # 세 번째 칸이 2 로 남아 있으면 정산이 그 칸을 안 본 것이다.
    assert left == [0, 0, 1], left
