"""장비·레벨이 전투 입력을 만든다 (결정 #13, #10).

**장비는 전투 전에 캐릭터로 녹는다.** 규칙표는 캐릭터만 읽으므로 장비 전용 DSL 블록이
없고, 사거리가 바뀌면 같은 규칙표가 저절로 다르게 돈다 — 그것이 블록을 안 늘리고 P2 를
만족하는 지점이다.
"""

import pytest

from game.app.items.catalog import find_item, load_item_catalog
from game.app.items.loadout import build_player_loadout
from game.config import ITEMS_PATH
from game.schemas.item import EquipSlot
from game.schemas.loadout import BASE_SKILLS

BASE = {
    "hp_max": 100,
    "attack": 12,
    "defense": 5,
    "attack_range": 1,
    "initiative": 50,
    "cpu_budget": 8,
    "potions": 2,
}
BASE_SLOTS = 5


@pytest.fixture
def catalog():
    return load_item_catalog(ITEMS_PATH)


def test_bare_player_keeps_base_stats(catalog):
    loadout = build_player_loadout(BASE, {}, level=1, base_rule_slots=BASE_SLOTS)
    assert loadout.hp_max == BASE["hp_max"]
    assert loadout.attack == BASE["attack"]
    assert loadout.rule_slots == BASE_SLOTS


def test_bare_player_has_base_skills(catalog):
    """★ 맨몸이어도 기본 행동은 된다 — 여기서 빼면 아무것도 못 한다."""
    loadout = build_player_loadout(BASE, {}, level=1, base_rule_slots=BASE_SLOTS)
    assert set(loadout.skills) == set(BASE_SKILLS)


def test_equipment_changes_combat_stats(catalog):
    """★ 이것이 없으면 장비가 화면에만 존재한다."""
    equipped = {EquipSlot.HEAD: find_item(catalog, "helm_iron")}
    loadout = build_player_loadout(BASE, equipped, level=1, base_rule_slots=BASE_SLOTS)
    assert loadout.hp_max > BASE["hp_max"]


def test_bow_changes_range_so_the_same_ruleset_behaves_differently(catalog):
    """★ 장비 전용 블록 없이 P2 를 만족하는 지점이다.

    활을 들면 사거리가 바뀌고, 규칙표는 `적거리 <= 사거리` 를 스탯 참조로 읽으므로
    같은 규칙표가 저절로 다르게 돈다.
    """
    equipped = {EquipSlot.WEAPON_MAIN: find_item(catalog, "bow_long")}
    loadout = build_player_loadout(BASE, equipped, level=1, base_rule_slots=BASE_SLOTS)
    assert loadout.attack_range > BASE["attack_range"]


def test_equipment_opens_skills(catalog):
    """★ 장비 교체가 규칙 재설계로 이어지는 지점이다."""
    equipped = {EquipSlot.WEAPON_OFF: find_item(catalog, "shield_buckler")}
    loadout = build_player_loadout(BASE, equipped, level=1, base_rule_slots=BASE_SLOTS)
    assert "GUARD_BRACE" in loadout.skills


def test_sealed_slot_grants_nothing(catalog):
    """★ 양손무기가 막은 자리의 장비는 스탯도 스킬도 주지 않는다 (§2.1)."""
    equipped = {
        EquipSlot.WEAPON_MAIN: find_item(catalog, "sword_great"),
        EquipSlot.WEAPON_OFF: find_item(catalog, "shield_buckler"),
    }
    loadout = build_player_loadout(BASE, equipped, level=1, base_rule_slots=BASE_SLOTS)
    assert "GUARD_BRACE" not in loadout.skills
    assert loadout.defense == BASE["defense"]


def test_level_adds_expressiveness_after_equipment(catalog):
    """★ 레벨 보너스는 장비 합산 **뒤에** 붙는다.

    안에 넣으면 장비의 퍼센트 접사가 레벨 보너스까지 불려, 같은 장비가 레벨마다 다른
    값을 낸다.
    """
    equipped = {EquipSlot.WEAPON_MAIN: find_item(catalog, "sword_great")}
    low = build_player_loadout(BASE, equipped, level=1, base_rule_slots=BASE_SLOTS)
    high = build_player_loadout(BASE, equipped, level=20, base_rule_slots=BASE_SLOTS)
    assert high.cpu_budget > low.cpu_budget
    assert high.rule_slots > low.rule_slots
    # 장비가 깎는 퍼센트는 레벨과 무관하게 같은 몫이어야 한다.
    assert high.attack == low.attack


def test_skills_are_sorted(catalog):
    """집합 순회 순서가 티켓에 새어 나가면 안 된다 (R5)."""
    equipped = {EquipSlot.WEAPON_OFF: find_item(catalog, "shield_buckler")}
    loadout = build_player_loadout(BASE, equipped, level=1, base_rule_slots=BASE_SLOTS)
    assert list(loadout.skills) == sorted(loadout.skills)


def test_the_base_potions_survive_a_loadout(catalog):
    """★ **로드아웃이 생겼다고 기본 지급이 사라지면 안 된다.**

    balance.json 의 `potions` 는 누구나 런을 시작할 때 받는 몫이고, 가방은 그 위에
    더해지는 것이다. 가방만 쓰면 로드아웃이 붙는 순간 모두가 빈손이 된다 — 실제로 그렇게
    회귀했고, 이기던 규칙표가 지기 시작해서 드러났다.
    """
    loadout = build_player_loadout(BASE, {}, level=1, base_rule_slots=BASE_SLOTS)
    assert dict(loadout.consumables)["POTION"] == BASE["potions"]


def test_the_bag_adds_on_top(catalog):
    """★ 가방이 기본 지급을 덮으면 물약을 주울 이유가 없다."""
    loadout = build_player_loadout(
        BASE, {}, level=1, base_rule_slots=BASE_SLOTS, consumables={"POTION": 3, "SCROLL": 2}
    )
    counts = dict(loadout.consumables)
    assert counts["POTION"] == BASE["potions"] + 3
    assert counts["SCROLL"] == 2


def test_empty_kinds_are_not_carried(catalog):
    """0개인 종류를 담으면 티켓이 쓸데없이 길어진다."""
    loadout = build_player_loadout(
        BASE, {}, level=1, base_rule_slots=BASE_SLOTS, consumables={"SCROLL": 0}
    )
    assert "SCROLL" not in dict(loadout.consumables)


def test_consumables_are_sorted(catalog):
    """딕셔너리 순회 순서가 티켓에 새어 나가면 안 된다 (R5)."""
    loadout = build_player_loadout(
        BASE, {}, level=1, base_rule_slots=BASE_SLOTS, consumables={"SCROLL": 1, "AAA": 1}
    )
    kinds = [kind for kind, _ in loadout.consumables]
    assert kinds == sorted(kinds)
