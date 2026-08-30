"""장비·레벨에서 전투 입력을 만든다 (결정 #13, #10).

**장비는 전투 전에 캐릭터로 녹는다.** 규칙표는 캐릭터만 읽으므로, 여기서 합산이 끝나면
전투는 장비를 몰라도 된다 — 그것이 장비 전용 DSL 블록을 만들지 않은 이유다.

합산은 `items/stats.py` 가 한다. 이 모듈은 **무엇을 합산에 넣을지**를 정한다 —
양손 봉인(§2.1), 파손 장비 제외, 레벨 보너스, 장비가 여는 스킬.
"""

from game.app.items.stats import StatDelta, compute_final_stat, get_effective_slots
from game.app.progression.attributes import build_attribute_bonus
from game.app.progression.levels import build_growth
from game.schemas.item import EquipSlot, ItemCatalogEntry
from game.schemas.loadout import BASE_SKILLS, PlayerLoadout

# 합산 대상 스탯. 여기 없는 스탯은 접사가 붙어도 전투에 반영되지 않는다.
COMBAT_STATS: tuple[str, ...] = (
    "hp_max",
    "attack",
    "defense",
    "attack_range",
    "initiative",
    "cpu_budget",
)

PERCENT_BASE = 100


def build_player_loadout(
    base_stats: dict[str, int],
    equipped: dict[EquipSlot, ItemCatalogEntry],
    level: int,
    base_rule_slots: int,
    stats: dict[str, int] | None = None,
) -> PlayerLoadout:
    """장비와 레벨을 합쳐 이번 런의 전투 입력을 만든다.

    **파손된 장비는 합산에 들어가지 않는다** — 부르는 쪽이 빼서 넘긴다. 여기서 거르면
    "무엇이 빠졌는지" 를 화면이 알 수 없다.

    Args:
        base_stats: balance.json 의 플레이어 기본 스탯.
        equipped: 슬롯에서 착용 중인 카탈로그 항목으로의 대응표. 봉인은 여기서 계산한다.
        level: 플레이어 레벨.
        base_rule_slots: 기본 규칙 슬롯 수.
        stats: 유저가 배분한 힘·민첩·지능. None 이면 배분이 없는 것으로 본다.

    Returns:
        확정된 전투 입력.
    """
    growth = build_growth(level)
    bonus = build_attribute_bonus(stats or {})
    totals: dict[str, StatDelta] = {}
    skills = set(BASE_SKILLS)
    for _slot, entry in get_effective_slots(equipped):
        if entry is None:
            continue
        if entry.grants_skill:
            skills.add(entry.grants_skill)
        for affix in entry.affixes:
            current = totals.get(affix.stat, StatDelta())
            totals[affix.stat] = StatDelta(
                flat=current.flat + affix.flat, percent=current.percent + affix.percent
            )

    final = {
        stat: compute_final_stat(base_stats.get(stat, 0), totals.get(stat, StatDelta()))
        for stat in COMBAT_STATS
    }
    # 배분한 능력치는 레벨 보너스와 같은 자리에서, **장비 합산 뒤에** 붙는다.
    # 안에 넣으면 장비의 퍼센트 접사가 배분분까지 불려 같은 장비가 배분마다 다른
    # 값을 낸다 (결정 #51).
    return PlayerLoadout(
        hp_max=final["hp_max"] + bonus.hp_max,
        attack=final["attack"] + bonus.attack,
        defense=final["defense"] + bonus.defense,
        attack_range=final["attack_range"],
        initiative=final["initiative"] + bonus.initiative,
        # CPU 는 레벨 보너스가 장비 합산 **뒤에** 붙는다. 안에 넣으면 장비의 퍼센트
        # 접사가 레벨 보너스까지 불려 같은 장비가 레벨마다 다른 값을 낸다.
        cpu_budget=final["cpu_budget"] + growth.bonus_cpu + bonus.cpu_budget,
        rule_slots=base_rule_slots + growth.bonus_rule_slots,
        skill_power_pct=bonus.skill_power_pct,
        # 정렬해서 담는다. 집합 순회 순서가 티켓에 새어 나가면 안 된다 (R5).
        skills=tuple(sorted(skills)),
    )
