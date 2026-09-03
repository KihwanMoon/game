"""뺏어 든 장비가 몬스터를 세게 만든다 (결정 #34).

**예전에는 표식일 뿐이었다.** 도감이 「내 것을 들고 있다」고 말할 수는 있었지만 그
몬스터가 세지지는 않았고, 그러면 되찾으러 갈 이유가 감정뿐이다.
"""

from game.app.items.stats import merge_stat_deltas
from game.app.store.spoils import build_worn_items, compute_spoiled_stat
from game.schemas.item import (
    SLOT_ORDER,
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


def test_seventeen_stolen_armours_still_fill_one_slot():
    """★ **칸 상한이 진짜로 있다.**

    예전에는 뺏은 것을 전부 더했다 — 같은 개체에게 열일곱 번 죽으면 열일곱 벌이 한꺼번에
    붙어 1층 몬스터의 방어가 2 에서 52 가 되어 있었다. 사람은 여섯 칸뿐인데 몬스터만
    무제한이면 그것은 성장이 아니라 구멍이다.
    """
    worn = build_worn_items(build_armor_rows(17), BODY_CATALOG)
    assert len(worn) == 1
    deltas = merge_stat_deltas(worn)
    assert deltas["defense"].flat == 10


def test_the_newest_take_wears_the_slot():
    """★ 칸을 차지하는 것은 **가장 최근에 뺏은 것**이다.

    몬스터는 값을 매기지 않고 방금 뜯어낸 것을 걸친다. 줄이 최근 순으로 오므로 첫 줄이
    이긴다 — 낡은 것을 계속 입고 있으면 「방금 내 갑옷을 뜯어 갔다」가 화면에서 거짓이 된다.
    """
    rows = [
        ("armor", [{"stat": "defense", "flat": 3}]),
        ("armor", [{"stat": "defense", "flat": 99}]),
    ]
    assert merge_stat_deltas(build_worn_items(rows, BODY_CATALOG))["defense"].flat == 3


def test_six_slots_all_count():
    """★ 칸이 다르면 여섯 벌이 전부 붙는다 — 상한은 칸마다 하나이지 전체 하나가 아니다."""
    catalog = {
        "w": build_entry("w", EquipSlot.WEAPON_MAIN, WeaponHands.ONE),
        "o": build_entry("o", EquipSlot.WEAPON_OFF, WeaponHands.OFFHAND),
        "h": build_entry("h", EquipSlot.HEAD),
        "b": build_entry("b", EquipSlot.BODY),
        "f": build_entry("f", EquipSlot.FEET),
        "n": build_entry("n", EquipSlot.HANDS),
    }
    rows = [(key, [{"stat": "defense", "flat": 1}]) for key in sorted(catalog)]
    worn = build_worn_items(rows, catalog)
    assert len(worn) == len(SLOT_ORDER)
    assert merge_stat_deltas(worn)["defense"].flat == len(SLOT_ORDER)


def test_a_two_handed_take_seals_the_off_hand():
    """★ 양손무기는 몬스터에게도 보조 칸을 봉인한다.

    사람 쪽 합산을 그대로 부르므로 이 규칙이 따라온다. 갈라 두면 같은 장비가 사람에게
    붙을 때와 몬스터에게 붙을 때 다른 값을 낸다.
    """
    catalog = {
        "great": build_entry("great", EquipSlot.WEAPON_MAIN, WeaponHands.TWO),
        "shield": build_entry("shield", EquipSlot.WEAPON_OFF, WeaponHands.OFFHAND),
    }
    rows = [
        ("great", [{"stat": "attack", "flat": 5}]),
        ("shield", [{"stat": "defense", "flat": 40}]),
    ]
    deltas = merge_stat_deltas(build_worn_items(rows, catalog))
    assert deltas["attack"].flat == 5
    assert "defense" not in deltas


def test_a_consumable_is_not_worn():
    """★ 칸이 없는 것은 안 붙는다 — 몬스터가 물약을 마시지는 않는다."""
    catalog = {
        "potion": ItemCatalogEntry(catalog_id="potion", kind=ItemKind.CONSUMABLE, label_ko="물약")
    }
    rows = [("potion", [{"stat": "hp_max", "flat": 500}])]
    assert build_worn_items(rows, catalog) == {}


def test_an_unknown_catalog_id_is_not_worn():
    """★ 카탈로그에 없는 id 는 조용히 붙지 않는다.

    폐기된 아이템이 개체에 남아 있을 수 있다. 그때 KeyError 로 티켓 발급이 통째로
    죽으면, 아이템 하나 때문에 그 층 전체가 못 도는 일이 된다.
    """
    assert build_worn_items([("gone", [{"stat": "attack", "flat": 9}])], BODY_CATALOG) == {}
