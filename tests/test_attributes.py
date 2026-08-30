"""능력치 배분이 전투 스탯으로 바뀐다 (결정 #51).

**축마다 여는 것이 달라야 한다.** 세 축이 모두 공격력으로 수렴하면 배분이 선택이 아니라
계산이 되고, 그러면 포인트를 주는 의미가 사라진다 (P3).
"""

from game.app.items.catalog import find_item, load_item_catalog
from game.app.items.loadout import build_player_loadout
from game.app.progression.attributes import (
    BASE_SKILL_POWER_PCT,
    MAX_CPU_FROM_INT,
    build_attribute_bonus,
)
from game.config import ITEMS_PATH
from game.schemas.item import EquipSlot

BASE = {
    "hp_max": 100,
    "attack": 12,
    "defense": 5,
    "attack_range": 1,
    "initiative": 50,
    "cpu_budget": 8,
}
BASE_SLOTS = 5


def test_empty_allocation_changes_nothing():
    bonus = build_attribute_bonus({})
    assert bonus.attack == 0
    assert bonus.hp_max == 0
    assert bonus.skill_power_pct == BASE_SKILL_POWER_PCT


def test_each_axis_opens_something_different():
    """★ 이것이 깨지면 배분이 선택이 아니라 계산이 된다."""
    strength = build_attribute_bonus({"str": 10})
    dexterity = build_attribute_bonus({"dex": 10})
    intellect = build_attribute_bonus({"int": 10})
    assert strength.attack > 0 and strength.initiative == 0
    assert dexterity.initiative > 0 and dexterity.attack == 0
    assert intellect.skill_power_pct > BASE_SKILL_POWER_PCT
    assert intellect.attack == 0


def test_intellect_cpu_has_a_ceiling():
    """★ 능력치에는 상한이 없지만 그중 **CPU 로 바뀌는 몫**은 막는다.

    CPU 는 표현력이고, 표현력이 무한하면 정교한 로직의 가치가 사라진다 (P3).
    """
    assert build_attribute_bonus({"int": 1000}).cpu_budget == MAX_CPU_FROM_INT


def test_intellect_skill_power_has_no_ceiling():
    """스킬위력에는 상한을 두지 않았다 — 능력치 성장 상한 없음이 그쪽에 남는다."""
    low = build_attribute_bonus({"int": 100}).skill_power_pct
    high = build_attribute_bonus({"int": 200}).skill_power_pct
    assert high > low


def test_negative_allocation_never_subtracts():
    """★ 손상된 값이 스탯을 깎으면 안 된다.

    깎이면 저장 값을 건드려 남의 캐릭터를 약하게 만드는 길이 열린다.
    """
    bonus = build_attribute_bonus({"str": -50, "dex": -50, "int": -50})
    assert bonus.attack == 0
    assert bonus.defense == 0
    assert bonus.skill_power_pct == BASE_SKILL_POWER_PCT


def test_allocation_reaches_the_loadout():
    """★ 배분이 티켓까지 닿는다 — 여기가 끊기면 포인트가 죽은 값이다."""
    bare = build_player_loadout(BASE, {}, level=1, base_rule_slots=BASE_SLOTS)
    built = build_player_loadout(
        BASE, {}, level=1, base_rule_slots=BASE_SLOTS, stats={"str": 10, "int": 6}
    )
    assert built.attack > bare.attack
    assert built.hp_max > bare.hp_max
    assert built.skill_power_pct > bare.skill_power_pct
    assert built.cpu_budget > bare.cpu_budget


def test_allocation_is_added_after_equipment_percent():
    """★ 배분분은 장비 합산 **뒤에** 붙는다.

    안에 넣으면 장비의 퍼센트 접사가 배분분까지 불려, 같은 배분이 장비마다 다른 몫을
    낸다. 레벨 보너스와 같은 이유다.
    """
    catalog = load_item_catalog(ITEMS_PATH)
    equipped = {EquipSlot.HEAD: find_item(catalog, "helm_iron")}
    without = build_player_loadout(BASE, equipped, level=1, base_rule_slots=BASE_SLOTS)
    with_points = build_player_loadout(
        BASE, equipped, level=1, base_rule_slots=BASE_SLOTS, stats={"str": 10}
    )
    gain = with_points.hp_max - without.hp_max
    bare_gain = build_attribute_bonus({"str": 10}).hp_max
    assert gain == bare_gain
