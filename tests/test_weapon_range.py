"""무기 사거리 (설계/4_아이템 §2.2).

**사거리는 접사가 아니라 무기의 것이다.** 예전에는 장궁이 `attack_range +3` 접사 하나로
사거리를 흉내냈고, 그 접사가 굴림에서 잘리면 활이 근접무기가 됐다 — `hands` 는 1급
필드인데 사거리는 아니었던 탓이다.

여기서 지키는 것은 셋이다.

1. **더하지 않고 대체한다.** 더하면 같은 활이 캐릭터 기본값에 따라 다른 사거리를 낸다.
2. **접사는 그 위에 더한다.** 「먼 사거리」 접사의 자리가 그것이다.
3. **보조 무기는 사거리를 안 정한다.** 정하면 한 캐릭터에 사거리가 둘이 된다.
"""

from game.app.items.loadout import build_player_loadout
from game.schemas.item import Affix, EquipSlot, ItemCatalogEntry, ItemKind, WeaponHands

BASE_STATS = {
    "hp_max": 100,
    "attack": 12,
    "defense": 5,
    "attack_range": 1,
    "initiative": 50,
    "cpu_budget": 8,
    "rule_slots": 5,
}


def build_weapon(catalog_id, attack_range=None, affixes=(), hands=WeaponHands.ONE):
    """검사용 무기 하나를 만든다.

    Args:
        catalog_id: 아이템 id.
        attack_range: 무기가 정하는 사거리. None 이면 안 정한다.
        affixes: 붙은 접사들.
        hands: 손 규격.

    Returns:
        카탈로그 항목.
    """
    return ItemCatalogEntry(
        catalog_id=catalog_id,
        kind=ItemKind.EQUIPMENT,
        label_ko=catalog_id,
        slot=EquipSlot.WEAPON_MAIN,
        hands=hands,
        attack_range=attack_range,
        affixes=tuple(affixes),
    )


def find_range(equipped):
    """그 장비 구성의 최종 사거리를 낸다.

    Args:
        equipped: 슬롯에서 항목으로의 대응표.

    Returns:
        사거리.
    """
    return build_player_loadout(BASE_STATS, equipped, 1, 5).attack_range


def test_the_main_weapon_replaces_the_base_range():
    """★ 무기가 사거리를 정한다는 말은 기본값을 **대신한다**는 뜻이다.

    더하면 활을 들었을 때 맨손 사거리가 얹혀서, 같은 활이 캐릭터마다 다른 사거리를 낸다.
    """
    assert find_range({EquipSlot.WEAPON_MAIN: build_weapon("bow", attack_range=4)}) == 4


def test_a_weapon_without_a_range_leaves_the_base_alone():
    """★ 사거리를 안 정하는 무기가 사거리를 0 으로 만들면 아무것도 못 때린다.

    None 과 0 을 구분하는 이유가 여기다.
    """
    assert find_range({EquipSlot.WEAPON_MAIN: build_weapon("club")}) == BASE_STATS["attack_range"]


def test_bare_hands_keep_the_base_range():
    """★ 무기가 없으면 기본값이다."""
    assert find_range({}) == BASE_STATS["attack_range"]


def test_an_affix_adds_on_top_of_the_weapon_range():
    """★ 「먼 사거리」 접사는 무기 사거리 **위에** 더한다 — 그것이 접사의 남은 자리다."""
    weapon = build_weapon(
        "bow", attack_range=4, affixes=(Affix(stat="attack_range", flat=2, label_ko="먼 사거리"),)
    )
    assert find_range({EquipSlot.WEAPON_MAIN: weapon}) == 6


def test_the_offhand_does_not_decide_the_range():
    """★ 방패가 사거리를 정하면 한 캐릭터에 사거리가 둘이 된다."""
    shield = ItemCatalogEntry(
        catalog_id="buckler",
        kind=ItemKind.EQUIPMENT,
        label_ko="버클러",
        slot=EquipSlot.WEAPON_OFF,
        hands=WeaponHands.OFFHAND,
        attack_range=9,
    )
    equipped = {
        EquipSlot.WEAPON_MAIN: build_weapon("bow", attack_range=4),
        EquipSlot.WEAPON_OFF: shield,
    }
    assert find_range(equipped) == 4


def test_the_range_survives_the_json_round_trip():
    """★ 스냅샷을 거쳐도 사거리가 남는다 — 빠지면 내보내기 한 번에 활이 근접무기가 된다."""
    from game.schemas.item import build_item_payload, parse_item

    entry = build_weapon("bow", attack_range=4)
    assert parse_item(build_item_payload(entry)).attack_range == 4


def test_a_weapon_without_a_range_stays_absent_in_the_payload():
    """★ 안 정한 것을 0 으로 적어 내보내면 다음 세대가 그것을 「못 때리는 무기」로 읽는다."""
    from game.schemas.item import build_item_payload

    assert "attack_range" not in build_item_payload(build_weapon("club"))


def test_the_seeded_bow_reaches_farther_than_the_sword():
    """★ 씨앗 데이터에서도 활이 검보다 멀리 닿는다.

    구조만 만들고 데이터를 안 옮기면 사거리 필드는 비어 있고 활은 그대로 접사에 목숨을
    건다 — 실제로 그 상태로 넘어갈 뻔했다.
    """
    from pathlib import Path

    from game.app.items.catalog import load_item_catalog

    catalog = load_item_catalog(Path("game/resources/balance/items.json"))
    assert catalog["bow_long"].attack_range == 4
    assert catalog["sword_short"].attack_range == 1
    # 사거리를 필드로 올렸으면 접사에는 남아 있으면 안 된다. 둘 다 두면 값이 두 번 붙는다.
    assert [a for a in catalog["bow_long"].affixes if a.stat == "attack_range"] == []
