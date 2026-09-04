"""봇이 더 좋은 것으로 갈아 끼운다.

**빈 자리만 채우고 있었다.** 봇의 장비는 첫 몇 판에 굳고, 그 뒤로 사 온 유물이 가방에서
사망 페널티에 녹았다. 안 하고 있던 이유는 **값을 매기는 기준이 틀리면 봇이 좋은 것을
벗고 나쁜 것을 낀다**는 것이었으므로, 여기서 재는 것은 그 기준이 틀리지 않는가다.
"""

from game.app.bots.upgrade import (
    UPGRADE_MARGIN,
    GearItem,
    compute_item_score,
    find_upgrades,
)

# 실제 밸런스의 플레이어 기본값. 퍼센트를 값으로 바꾸는 기준이다.
BASE = {"hp_max": 100, "attack": 12, "defense": 5, "attack_range": 1, "initiative": 50}


def build_gear(item_id, slot="BODY", affixes=(), attack_range=0, hands="", is_broken=False):
    """장비 하나를 짠다.

    Args:
        item_id: 아이템 id.
        slot: 장비 자리.
        affixes: (스탯, 고정, 퍼센트) 들.
        attack_range: 무기가 정하는 사거리.
        hands: 손 쓰는 방식.
        is_broken: 부서졌는가.

    Returns:
        장비 하나.
    """
    return GearItem(
        item_id=item_id,
        slot=slot,
        can_equip=True,
        is_broken=is_broken,
        hands=hands,
        affixes=tuple(affixes),
        attack_range=attack_range,
    )


def test_a_percent_affix_is_worth_what_the_formula_says():
    """★ 퍼센트를 실제 합산식과 같은 방식으로 값으로 바꾼다.

    환산 상수를 지어내면 그 상수가 곧 아무도 안 정한 밸런스 결정 하나가 된다. 체력 10%
    는 기본 100 에서 10 이고, 근접 가중치 2 를 곱해 20 이다.
    """
    item = build_gear(1, affixes=[("hp_max", 0, 10)])
    assert compute_item_score(item, "melee", BASE) == 20


def test_a_curse_affix_lowers_the_score():
    """저주 접사는 음수 퍼센트다 — 값이 내려가야 봇이 그것을 안 낀다."""
    assert compute_item_score(build_gear(1, affixes=[("attack", 0, -50)]), "melee", BASE) < 0


def test_a_stat_outside_the_table_counts_for_nothing():
    """★ 표에 없는 스탯은 0 이다 — 「물약 칸 +1」 하나로 무기를 바꾸면 안 된다."""
    assert compute_item_score(build_gear(1, affixes=[("potion_slots", 5, 0)]), "melee", BASE) == 0


def test_personas_value_different_things():
    """★ 열이 같은 몸을 가지면 규칙표를 갈라 둔 뜻이 절반 사라진다."""
    reach = build_gear(1, slot="HANDS", affixes=[("attack_range", 1, 0)])
    muscle = build_gear(2, slot="HANDS", affixes=[("attack", 3, 0)])
    assert compute_item_score(reach, "ranged", BASE) > compute_item_score(muscle, "ranged", BASE)
    assert compute_item_score(muscle, "melee", BASE) > compute_item_score(reach, "melee", BASE)


def test_weapon_range_counts_even_though_it_is_not_an_affix():
    """★ 사거리는 접사가 아니라 필드다 (§2.2) — 안 세면 활과 단검이 같아진다."""
    bow = build_gear(1, slot="HANDS", attack_range=3)
    assert compute_item_score(bow, "ranged", BASE) > 0


def test_a_clear_upgrade_is_taken():
    """★ 더 좋은 것이 가방에 있으면 갈아 낀다 — 안 갈아 끼우면 사 온 유물이 가방에서 녹는다."""
    worn = (build_gear(1, affixes=[("defense", 1, 0)]),)
    bag = (build_gear(2, affixes=[("defense", 9, 0)]),)
    assert find_upgrades(bag, worn, "brawler_v2", BASE) == ((worn[0], bag[0]),)


def test_a_narrow_gain_is_left_alone():
    """★ **근소한 차이로는 안 바꾼다.**

    벗은 것은 가방으로 가고, 가방에 있는 것은 죽을 때 삭제된다 (결정 #34). 1점 이득을
    보려고 바꾸면 그 1점보다 큰 것을 잃을 수 있다.
    """
    worn = (build_gear(1, affixes=[("defense", 1, 0)]),)
    # 방어 가중치 2 이므로 차이 하나가 2점이다 — 문턱 아래다.
    bag = (build_gear(2, affixes=[("defense", 2, 0)]),)
    assert find_upgrades(bag, worn, "brawler_v2", BASE) == ()
    assert UPGRADE_MARGIN > 2


def test_a_worse_item_never_replaces_a_better_one():
    """★ **좋은 것을 벗고 나쁜 것을 끼면 안 된다** — 이것이 안 하고 있던 이유였다."""
    worn = (build_gear(1, affixes=[("defense", 20, 0)]),)
    bag = (build_gear(2, affixes=[("defense", 1, 0)]),)
    assert find_upgrades(bag, worn, "brawler_v2", BASE) == ()


def test_an_empty_slot_is_left_to_the_other_rule():
    """빈 자리는 `list_equippable` 이 채운다 — 둘이 같은 자리를 노리면 하나가 거절당한다."""
    bag = (build_gear(2, affixes=[("defense", 9, 0)]),)
    assert find_upgrades(bag, (), "brawler_v2", BASE) == ()


def test_a_broken_item_is_not_worn_and_not_taken_off():
    """부서진 것은 끼울 수도 없고, 그것을 기준으로 벗길 수도 없다 — 먼저 고쳐야 한다."""
    worn = (build_gear(1, affixes=[("defense", 1, 0)], is_broken=True),)
    bag = (build_gear(2, affixes=[("defense", 9, 0)]),)
    assert find_upgrades(bag, worn, "brawler_v2", BASE) == ()
    assert find_upgrades((build_gear(3, is_broken=True),), worn, "brawler_v2", BASE) == ()


def test_weapon_slots_are_left_alone():
    """★ 양손무기가 보조 칸을 봉인하므로 한 칸씩 보는 이 규칙으로는 틀린다."""
    worn = (build_gear(1, slot="WEAPON_MAIN", affixes=[("attack", 1, 0)]),)
    bag = (build_gear(2, slot="WEAPON_MAIN", affixes=[("attack", 40, 0)]),)
    assert find_upgrades(bag, worn, "brawler_v2", BASE) == ()


def test_only_the_best_candidate_per_slot():
    """한 자리에 후보가 여럿이면 제일 나은 것 하나 — 두 번 끼우려다 하나가 거절당한다."""
    worn = (build_gear(1, affixes=[("defense", 1, 0)]),)
    bag = (
        build_gear(2, affixes=[("defense", 9, 0)]),
        build_gear(3, affixes=[("defense", 20, 0)]),
    )
    found = find_upgrades(bag, worn, "brawler_v2", BASE)
    assert len(found) == 1
    assert found[0][1].item_id == 3
