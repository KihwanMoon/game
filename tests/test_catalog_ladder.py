"""등급 사다리 (설계/4_아이템 §15.4).

**위 등급이 아래 등급의 상위 호환이면 고를 것이 없어진다.** 그러면 등급이 선택이 아니라
계산이 되고, 장비를 고르는 일이 사라진다 (GDD §0).

그래서 카탈로그가 지켜야 할 것이 넷이다.

1. **자리마다 등급이 다 있다.** 한 자리에 유물이 없으면 그 자리는 영원히 보통이다.
2. **유물에는 대가가 있다.** 음수 접사든 요구조건이든 하나는 있어야 한다.
3. **위 등급이 더 깊은 층에서 나온다.** 1층에서 유물이 나오면 깊이 들어갈 이유가 없다.
4. **요구조건이 닿는다.** 레벨당 3점으로 못 채우는 조건은 그 장비를 영영 못 끼게 한다.
"""

from pathlib import Path

from game.app.items.catalog import load_item_catalog
from game.app.progression.attributes import (
    ATTACK_PER_STR,
    DEFENSE_PER_DEX,
    HP_MAX_PER_STR,
    INITIATIVE_PER_DEX,
    INT_PER_CPU,
)
from game.app.progression.levels import STAT_POINTS_PER_LEVEL
from game.schemas.item import EquipSlot, ItemCatalogEntry, ItemKind

CATALOG = load_item_catalog(Path("game/resources/balance/items.json"))
BASE = {"hp_max": 100, "attack": 12, "defense": 5, "cpu_budget": 8, "initiative": 50}

# 한 축에 몰아 줄 수 있는 점수의 눈금. 이 층에 닿는 사람이 쓸 만한 값이어야 한다.
REACHABLE_LEVEL = 10
# 한 점이 그 능력치를 얼마나 올리는지. 못 올리는 축이면 요구조건을 걸 수 없다.
PER_POINT = {
    "attack": ATTACK_PER_STR,
    "hp_max": HP_MAX_PER_STR,
    "defense": DEFENSE_PER_DEX,
    "initiative": INITIATIVE_PER_DEX,
    "cpu_budget": 1 / INT_PER_CPU,
}


def list_equipment(grade: str) -> tuple[ItemCatalogEntry, ...]:
    """그 최저 등급의 장비만 모은다.

    Args:
        grade: 등급 코드.

    Returns:
        카탈로그 항목들.
    """
    return tuple(
        entry
        for entry in sorted(CATALOG.values(), key=lambda item: item.catalog_id)
        if entry.kind is ItemKind.EQUIPMENT and entry.grade == grade
    )


def test_every_slot_has_every_grade():
    """★ 한 자리에 유물이 없으면 그 자리는 영원히 보통이다."""
    for grade in ("COMMON", "FINE", "RELIC"):
        filled = {entry.slot for entry in list_equipment(grade)}
        missing = [slot for slot in EquipSlot if slot not in filled]
        assert missing == [], f"{grade} 에 없는 자리: {[str(s.value) for s in missing]}"


def test_a_relic_always_costs_something():
    """★ 대가 없는 유물은 아래 등급의 상위 호환이고, 그러면 고를 것이 없다."""
    for entry in list_equipment("RELIC"):
        has_penalty = any(item.flat < 0 or item.percent < 0 for item in entry.affixes)
        assert has_penalty or entry.requirements, f"{entry.catalog_id} 에 대가가 없다"


def test_a_higher_grade_starts_deeper():
    """★ 1층에서 유물이 나오면 깊이 들어갈 이유가 없다 (D1)."""
    floors = {
        grade: {entry.min_floor for entry in list_equipment(grade)}
        for grade in ("COMMON", "FINE", "RELIC")
    }
    assert max(floors["COMMON"]) < min(floors["FINE"])
    assert max(floors["FINE"]) < min(floors["RELIC"])


def test_every_requirement_is_reachable():
    """★ 못 채우는 조건은 그 장비를 영영 못 끼게 한다.

    레벨당 3점이고 한 축에 몰아 줄 수 있다. 10 레벨이면 30 점이다 — 그 안에서 닿아야
    한다. 닿기만 하면 되는 것이 아니라 **몰아야** 닿게 두는 것이 노린 바다.
    """
    budget = REACHABLE_LEVEL * STAT_POINTS_PER_LEVEL
    for entry in CATALOG.values():
        for need in entry.requirements:
            gap = need.minimum - BASE.get(need.stat, 0)
            if gap <= 0:
                continue
            per_point = PER_POINT.get(need.stat)
            assert per_point, f"{entry.catalog_id} 가 못 올리는 축을 요구한다: {need.stat}"
            points = gap / per_point
            assert points <= budget, f"{entry.catalog_id} 의 {need.stat} 조건이 안 닿는다"


def test_every_weapon_declares_its_range():
    """★ 무기가 사거리를 안 정하면 활을 껴도 사거리가 안 바뀐다 (§2.2)."""
    weapons = [
        entry
        for entry in CATALOG.values()
        if entry.slot is EquipSlot.WEAPON_MAIN and entry.kind is ItemKind.EQUIPMENT
    ]
    assert weapons
    assert [entry.catalog_id for entry in weapons if entry.attack_range is None] == []


def test_no_two_items_share_a_label():
    """★ 이름이 겹치면 가방에서 어느 것이 어느 것인지 알 수 없다."""
    labels = [entry.label_ko for entry in CATALOG.values()]
    assert len(labels) == len(set(labels))
