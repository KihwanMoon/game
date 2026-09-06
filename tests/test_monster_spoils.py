"""뺏어 든 장비가 몬스터를 세게 만든다 (결정 #34).

**예전에는 표식일 뿐이었다.** 도감이 「내 것을 들고 있다」고 말할 수는 있었지만 그
몬스터가 세지지는 않았고, 그러면 되찾으러 갈 이유가 감정뿐이다.
"""

from game.app.items.stats import merge_stat_deltas
from game.app.store.spoils import (
    build_worn_items,
    compute_spoiled_stat,
    merge_spoil_deltas,
)
from game.schemas.item import (
    EquipSlot,
    ItemCatalogEntry,
    ItemKind,
    WeaponHands,
)


def test_nothing_taken_changes_nothing():
    """★ 뺏은 것이 없으면 값이 그대로다 — 대부분의 개체가 이 경우다."""
    assert compute_spoiled_stat(100, "hp_max", {}) == 100


def test_a_flat_bonus_lands():
    """고정값이 그대로 더해진다."""
    assert compute_spoiled_stat(100, "hp_max", {"hp_max": (12, 0)}) == 112


def test_a_percent_bonus_lands():
    """퍼센트가 곱해진다. 정수 나눗셈이며 내림이다 (R5)."""
    assert compute_spoiled_stat(100, "hp_max", {"hp_max": (0, 15)}) == 115
    assert compute_spoiled_stat(7, "attack", {"attack": (0, 15)}) == 8


def test_flat_comes_before_percent():
    """★ 고정값을 먼저 더하고 퍼센트를 건다.

    사람의 장비 합산과 같은 순서여야 **같은 장비가 두 곳에서 다른 값을 내지 않는다.**
    """
    # (100 + 10) * 1.5 = 165. 반대 순서였다면 100*1.5 + 10 = 160 이다.
    assert compute_spoiled_stat(100, "hp_max", {"hp_max": (10, 50)}) == 165


def test_another_stat_is_untouched():
    """다른 스탯의 접사는 안 건드린다."""
    assert compute_spoiled_stat(100, "attack", {"hp_max": (50, 0)}) == 100


def test_a_curse_cannot_go_below_zero():
    """★ 저주 접사는 음수다 (`설계/4_아이템` §9). 스탯이 음수가 되면 안 된다."""
    assert compute_spoiled_stat(5, "attack", {"attack": (-99, 0)}) == 0


def build_entry(catalog_id: str, slot: EquipSlot, hands: WeaponHands | None = None):
    """카탈로그 한 줄을 만든다. 접사는 개체 쪽에서 오므로 여기서는 비운다.

    Args:
        catalog_id: 아이템 id.
        slot: 어느 칸에 드는가.
        hands: 손 쓰는 방식. 무기가 아니면 None.

    Returns:
        카탈로그 줄.
    """
    return ItemCatalogEntry(
        catalog_id=catalog_id,
        kind=ItemKind.EQUIPMENT,
        label_ko=catalog_id,
        slot=slot,
        hands=hands,
    )


# 접사가 다른 흉갑 셋. 「열일곱 번 죽으면 열일곱 벌」을 재는 데 쓴다.
BODY_CATALOG = {"armor": build_entry("armor", EquipSlot.BODY)}


def build_armor_rows(count: int) -> list[tuple]:
    """같은 칸에 드는 흉갑을 count 벌 만든다. 최근 것이 앞이다.

    Args:
        count: 몇 벌인가.

    Returns:
        (catalog_id, affixes) 줄들.
    """
    return [("armor", [{"stat": "defense", "flat": 10}]) for _ in range(count)]


def test_everything_held_counts():
    """★ 든 것이 **다 붙는다** (개정 2026-09-06).

    예전에는 칸마다 하나만 골랐다. 상한이 없던 때는 그 골라내기가 폭주를 막는 유일한
    자리였는데(실측으로 한 마리가 696개를 들고 있었다), 이제 `create_trophy` 가 다섯으로
    막는다 — 막는 자리가 둘이면 어느 쪽이 실제 한도인지가 코드에서 안 읽힌다.
    """
    worn = build_worn_items(build_armor_rows(5), BODY_CATALOG)
    assert len(worn) == 5
    assert merge_spoil_deltas(worn)["defense"].flat == 50


def test_six_slots_all_count():
    """칸이 달라도 같아도 전부 붙는다 — 세는 것은 칸이 아니라 개수다."""
    catalog = {
        "w": build_entry("w", EquipSlot.WEAPON_MAIN, WeaponHands.ONE),
        "o": build_entry("o", EquipSlot.WEAPON_OFF, WeaponHands.OFFHAND),
        "h": build_entry("h", EquipSlot.HEAD),
        "b": build_entry("b", EquipSlot.BODY),
        "f": build_entry("f", EquipSlot.FEET),
        "n": build_entry("n", EquipSlot.HANDS),
    }
    rows = [(key, [{"stat": "defense", "flat": 1}]) for key in sorted(catalog)]
    assert merge_spoil_deltas(build_worn_items(rows, catalog))["defense"].flat == len(catalog)


def test_a_two_handed_take_does_not_seal_anything():
    """★ 몬스터는 **입은 것이 아니라 가진 것**이다 (개정 2026-09-06).

    사람 쪽 합산은 칸 규율을 담는다 — 양손무기가 보조 칸을 봉인하고 한 칸에 하나만 든다.
    같은 함수를 쓰려고 그 규율을 느슨하게 하면 **사람 쪽이 함께 느슨해지므로** 합산을
    갈랐다. 몬스터는 다섯을 가지면 다섯이 다 붙는다.
    """
    catalog = {
        "great": build_entry("great", EquipSlot.WEAPON_MAIN, WeaponHands.TWO),
        "shield": build_entry("shield", EquipSlot.WEAPON_OFF, WeaponHands.OFFHAND),
    }
    rows = [
        ("great", [{"stat": "attack", "flat": 5}]),
        ("shield", [{"stat": "defense", "flat": 40}]),
    ]
    deltas = merge_spoil_deltas(build_worn_items(rows, catalog))
    assert deltas["attack"].flat == 5
    assert deltas["defense"].flat == 40


def test_the_player_side_still_seals():
    """★ 사람 쪽 규율은 그대로다 — 갈라 둔 값이 여기서 나온다."""
    catalog = {
        "great": build_entry("great", EquipSlot.WEAPON_MAIN, WeaponHands.TWO),
        "shield": build_entry("shield", EquipSlot.WEAPON_OFF, WeaponHands.OFFHAND),
    }
    worn = {
        EquipSlot.WEAPON_MAIN: catalog["great"],
        EquipSlot.WEAPON_OFF: catalog["shield"],
    }
    assert "defense" not in merge_stat_deltas(worn)


def test_a_consumable_is_not_worn():
    """★ 칸이 없는 것은 안 붙는다 — 몬스터가 물약을 마시지는 않는다."""
    catalog = {
        "potion": ItemCatalogEntry(catalog_id="potion", kind=ItemKind.CONSUMABLE, label_ko="물약")
    }
    rows = [("potion", [{"stat": "hp_max", "flat": 500}])]
    assert build_worn_items(rows, catalog) == ()


def test_an_unknown_catalog_id_is_not_worn():
    """★ 카탈로그에 없는 id 는 조용히 붙지 않는다.

    폐기된 아이템이 개체에 남아 있을 수 있다. 그때 KeyError 로 티켓 발급이 통째로
    죽으면, 아이템 하나 때문에 그 층 전체가 못 도는 일이 된다.
    """
    assert build_worn_items([("gone", [{"stat": "attack", "flat": 9}])], BODY_CATALOG) == ()
