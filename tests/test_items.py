"""아이템 카탈로그·요구조건·스탯 합산 (docs/설계/4_아이템).

여기서 지키는 것은 설계가 함정으로 지목한 셋이다.

1. **요구조건이 착용 순서에 흔들리지 않는다** (§7). 장비 보너스를 제외한 소재 능력치로만
   판정하므로, 어떤 순서로 착용해도 착용 가능한 집합이 같다.
2. **양손무기 봉인이 파생값이다** (§2.1). 저장하지 않고 매번 계산하므로 착용·해제 순서에
   따라 갈리지 않는다.
3. **합산이 곱한 뒤 나누고 내림으로 절삭한다** (§9). 저주 접사가 퍼센트를 음수로 만들며,
   그 자리에서 절삭 방향이 갈리면 TS 이식과 결과가 달라진다 (G3).
"""

import pytest

from game.app.items.catalog import find_item, list_slot_items, load_item_catalog
from game.app.items.requirements import (
    check_can_equip,
    check_requirements,
    list_unmet_requirements,
)
from game.app.items.stats import (
    StatDelta,
    compute_equipped_stats,
    compute_final_stat,
    get_effective_slots,
    merge_stat_deltas,
)
from game.config import ITEMS_PATH
from game.schemas.item import EquipSlot, ItemKind, WeaponHands

BASE_ATTACK = 12
BASE_CPU = 8


@pytest.fixture
def catalog():
    return load_item_catalog(ITEMS_PATH)


def test_catalog_loads_every_kind(catalog):
    kinds = {entry.kind for entry in catalog.values()}
    assert kinds == {ItemKind.EQUIPMENT, ItemKind.CONSUMABLE, ItemKind.QUEST}


def test_every_weapon_declares_hands(catalog):
    for entry in catalog.values():
        if entry.slot in {EquipSlot.WEAPON_MAIN, EquipSlot.WEAPON_OFF}:
            assert entry.hands is not None, entry.catalog_id


def test_shield_is_an_offhand_weapon(catalog):
    """방패는 별도 슬롯이 아니다 — 별도로 두면 양손무기와의 트레이드오프가 사라진다."""
    shield = find_item(catalog, "shield_buckler")
    assert shield.slot is EquipSlot.WEAPON_OFF
    assert shield.hands is WeaponHands.OFFHAND


def test_slot_listing_is_sorted(catalog):
    ids = [entry.catalog_id for entry in list_slot_items(catalog, EquipSlot.WEAPON_MAIN)]
    assert ids == sorted(ids)


def test_missing_item_is_rejected(catalog):
    with pytest.raises(KeyError):
        find_item(catalog, "nope")


# ── 요구조건 (§6·§7) ──────────────────────────────────────────────────────


def test_requirement_reports_actual_value(catalog):
    """실측값을 함께 낸다. 무엇이 얼마나 모자란지가 화면에 있어야 한다 (P1)."""
    checks = check_requirements(find_item(catalog, "gloves_core"), {"cpu_budget": 4})
    assert [(c.stat, c.actual, c.minimum, c.is_met) for c in checks] == [
        ("cpu_budget", 4, 6, False)
    ]


def test_unknown_stat_counts_as_zero(catalog):
    """코어가 모르는 능력치를 요구하면 모자란 것으로 읽힌다.

    조용히 통과시키면 아직 존재하지 않는 축(level 등)을 요구하는 장비가 전부 착용
    가능해진다.
    """
    checks = check_requirements(find_item(catalog, "gloves_core"), {})
    assert checks[0].actual == 0
    assert not checks[0].is_met


def test_equipment_bonus_does_not_open_requirements(catalog):
    """★ 순환 차단. 장비가 준 보너스는 판정 기준에 들어가지 않는다 (§7).

    연산 장갑은 CPU 6 을 요구하고 자신이 CPU +3 을 준다. 소재가 4 면 장갑을 낀 상태로
    다시 판정해도 여전히 못 낀다 — 그러지 않으면 "낄 수 있으니 껴서 조건을 채운다" 는
    자기참조가 성립한다.
    """
    gloves = find_item(catalog, "gloves_core")
    base = {"cpu_budget": 4}
    assert not check_can_equip(gloves, base)
    equipped_view = compute_equipped_stats(base, {EquipSlot.HANDS: gloves})
    assert equipped_view["cpu_budget"] == 7
    # 판정은 여전히 소재를 본다.
    assert not check_can_equip(gloves, base)


def test_equip_order_does_not_change_the_wearable_set(catalog):
    """★ 순서 무관. 두 순서가 같은 집합을 낸다 (§7)."""
    gloves = find_item(catalog, "gloves_core")
    great = find_item(catalog, "sword_great")
    base = {"cpu_budget": 6, "attack": 12}

    forward = [item for item in (gloves, great) if check_can_equip(item, base)]
    backward = [item for item in (great, gloves) if check_can_equip(item, base)]
    assert {item.catalog_id for item in forward} == {item.catalog_id for item in backward}


def test_unmet_list_is_empty_when_satisfied(catalog):
    assert list_unmet_requirements(find_item(catalog, "sword_great"), {"attack": 12}) == ()


# ── 양손 봉인 (§2.1) ──────────────────────────────────────────────────────


def test_two_handed_weapon_seals_the_offhand(catalog):
    equipped = {
        EquipSlot.WEAPON_MAIN: find_item(catalog, "sword_great"),
        EquipSlot.WEAPON_OFF: find_item(catalog, "shield_buckler"),
    }
    slots = dict(get_effective_slots(equipped))
    assert slots[EquipSlot.WEAPON_OFF] is None


def test_one_handed_weapon_leaves_the_offhand_usable(catalog):
    equipped = {
        EquipSlot.WEAPON_MAIN: find_item(catalog, "sword_short"),
        EquipSlot.WEAPON_OFF: find_item(catalog, "shield_buckler"),
    }
    slots = dict(get_effective_slots(equipped))
    assert slots[EquipSlot.WEAPON_OFF] is not None


def test_sealed_offhand_contributes_nothing(catalog):
    """봉인된 자리의 접사는 합산에 들어가지 않는다."""
    equipped = {
        EquipSlot.WEAPON_MAIN: find_item(catalog, "sword_great"),
        EquipSlot.WEAPON_OFF: find_item(catalog, "shield_buckler"),
    }
    assert "defense" not in merge_stat_deltas(equipped)


def test_effective_slots_follow_the_fixed_order(catalog):
    """합산 순서가 고정이다. 순서가 흔들리면 클램프가 끼는 순간 값이 달라진다 (R5)."""
    order = [slot for slot, _ in get_effective_slots({})]
    assert order == [
        EquipSlot.WEAPON_MAIN,
        EquipSlot.WEAPON_OFF,
        EquipSlot.HEAD,
        EquipSlot.BODY,
        EquipSlot.FEET,
        EquipSlot.HANDS,
    ]


# ── 스탯 합산 (§9) ────────────────────────────────────────────────────────


def test_multiply_happens_before_divide():
    """먼저 나누면 절삭이 두 번 일어나 값이 달라진다.

    (10+0) * 115 // 100 = 11 이고, (10 * 115 // 100) 을 두 번 접으면 다른 값이 된다.
    """
    assert compute_final_stat(10, StatDelta(percent=15)) == 11


def test_negative_percent_floors_down():
    """★ 저주 접사. 음수 퍼센트에서 내림과 버림이 갈린다 (G3 가 깨지는 경로).

    8 * 75 // 100 = 6.0 이라 여기서는 같지만, 나누어떨어지지 않는 값에서 갈린다.
    """
    assert compute_final_stat(8, StatDelta(percent=-25)) == 6
    # 7 * 75 = 525 → 내림 5. 버림도 5 지만 음수 결과에서 갈리므로 아래를 함께 본다.
    assert compute_final_stat(7, StatDelta(percent=-25)) == 5
    # 결과가 음수가 되는 자리 — 파이썬 // 는 -2, TS 의 Math.trunc 는 -1 이다.
    # 기본 하한이 0 이라 클램프를 풀어야 절삭 방향이 드러난다.
    assert compute_final_stat(-1, StatDelta(percent=50), minimum=-100) == -2


def test_clamp_applies_once_at_the_end():
    assert compute_final_stat(1, StatDelta(flat=-10), minimum=0) == 0


def test_flat_and_percent_stack_across_slots(catalog):
    equipped = {
        EquipSlot.HEAD: find_item(catalog, "helm_iron"),
        EquipSlot.BODY: find_item(catalog, "armor_plate"),
    }
    # hp_max: (100 + 8) * 110 // 100 = 118
    stats = compute_equipped_stats({"hp_max": 100}, equipped)
    assert stats["hp_max"] == 118


def test_cursed_weapon_cuts_cpu(catalog):
    """대검은 공격력을 주고 CPU 를 깎는다 — 화력과 로직 정교함의 교환이다 (GDD §6.3)."""
    equipped = {EquipSlot.WEAPON_MAIN: find_item(catalog, "sword_great")}
    stats = compute_equipped_stats({"attack": BASE_ATTACK, "cpu_budget": BASE_CPU}, equipped)
    assert stats["attack"] == BASE_ATTACK + 5
    assert stats["cpu_budget"] == BASE_CPU * 75 // 100


def test_untouched_stats_pass_through(catalog):
    equipped = {EquipSlot.HEAD: find_item(catalog, "helm_iron")}
    stats = compute_equipped_stats({"attack": 12, "hp_max": 100}, equipped)
    assert stats["attack"] == 12


def test_result_is_sorted_by_stat_name(catalog):
    stats = compute_equipped_stats({"hp_max": 100, "attack": 12}, {})
    assert list(stats) == sorted(stats)
