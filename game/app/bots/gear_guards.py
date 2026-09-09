"""자동 정비가 **사람이 안 고른 상실**을 만들지 않게 막는다.

`upgrade.py` 에서 갈라 나왔다. 저쪽은 **무엇이 더 센가**(저울)이고, 여기는 **무엇을
잃으면 안 되는가**(관문)다. 파일이 400줄 상한을 넘은 것이 계기였을 뿐, 가르는 선은
책임이다 (§4).

**저울이 못 보는 축들이다.** 점수는 크기를 재는데, 이 넷은 잃는 순간 규칙표의 뜻이
달라지거나 실행이 막힌다 — 점수로 견줄 값이 아니라 조건이다. 2026-09-08~09 하루에
넷이 차례로 드러났고, 그때마다 저울이 「이득」이라 세는 교체가 캐릭터를 나쁘게 만들고
있었다.
"""

from game.app.bots.gear_item import GearItem

PERCENT_BASE = 100

# 규칙표 예산 축. 다른 스탯과 달리 「잃으면 규칙표가 반려된다」 (`check_keeps_budget`).
CPU_STAT = "cpu_budget"
# 소모품 칸 축. 잃으면 **끼워 둔 것이 잠긴다** (`store/consumables` 의 「칸이 줄면 넘치는
# 줄은 안 읽힌다」). 스킬·CPU 와 같은 자리라 같은 관문을 세운다.
SLOT_STATS: tuple[str, ...] = ("potion_slots", "scroll_slots")
# 사거리 축. **규칙표가 직접 읽는다** — `적거리 <= 사거리` 가 그 값을 본다.
REACH_STAT = "attack_range"


def check_keeps_skill(current: GearItem, candidate: GearItem) -> bool:
    """갈아 껴도 지금 열린 스킬이 그대로 열리는가.

    **점수로 견주지 않는다.** 스킬에 무게를 주면 「공격 +4 와 AREA_ATTACK 중 무엇이
    무거운가」를 저울이 답해야 하는데, 그것은 밸런스가 아니라 그 사람의 규칙표가 정할
    일이다. 여기서 막는 것은 하나다 — **자동 정비가 사람이 안 고른 상실을 만드는 것.**

    실측으로 오늘 카탈로그에 이런 교체가 16건 있었다. 대검(AREA_ATTACK) → 단층 검이
    ATTACK 저울에서 12점 앞서므로, 정비를 켜 둔 사람은 출격 버튼을 누른 그 판에
    `USE_SKILL[AREA_ATTACK]` 이 「불가」로 떨어진 것을 본다 — 규칙표를 안 고쳤는데
    뜻이 바뀌었으므로 P1 위반이다. 로그는 이유를 말하지만(`BlockedRule`), 말해 주는
    자리는 **이미 그 판이 돌기 시작한 뒤**다.

    **손으로 바꾸는 길은 막지 않는다.** 장비 교체가 규칙 재설계를 부르는 것은 이 게임이
    파는 것이고(P3), 파는 것과 몰래 뺏는 것은 다르다.

    Args:
        current: 지금 낀 것.
        candidate: 갈아 낄 후보.

    Returns:
        지금 아무것도 안 열거나 후보가 같은 것을 열면 True.
    """
    return not current.grants_skill or current.grants_skill == candidate.grants_skill


def check_keeps_budget(current: GearItem, candidate: GearItem, base_stats: dict[str, int]) -> bool:
    """갈아 껴도 CPU 예산이 안 줄어드는가.

    **스킬 상실보다 무겁다.** 스킬을 잃으면 그 규칙 하나가 런타임에 「불가」로 떨어질
    뿐인데(`rule_vm.BlockedRule`), CPU 를 잃으면 **규칙표 전체가 제출에서 반려된다**
    (`validator` 의 `total_cpu > cpu_budget`). 그것도 브라우저에서 판을 다 돈 뒤에.

    CPU 는 전투 수치가 아니라 **규칙표 예산 그 자체**다. 저울이 그것을 다른 스탯과 같은
    무게로 재는 것은 옳지만(`cpu_budget: 2`), 「점수가 더 높으니 예산을 깎아도 된다」는
    성립하지 않는다 — 사람이 안 고른 상실이라는 점에서 스킬과 같은 자리다.

    Args:
        current: 지금 낀 것.
        candidate: 갈아 낄 후보.
        base_stats: 퍼센트를 값으로 바꾸는 기준.

    Returns:
        후보의 CPU 기여가 지금 것 이상이면 True.
    """
    return count_budget_gift(candidate, base_stats) >= count_budget_gift(current, base_stats)


def count_budget_gift(item: GearItem, base_stats: dict[str, int]) -> int:
    """이 장비가 CPU 예산에 더하는 몫.

    Args:
        item: 볼 장비.
        base_stats: 퍼센트를 값으로 바꾸는 기준.

    Returns:
        더하는 값. 저주면 음수다.
    """
    total = 0
    for stat, flat, percent in item.affixes:
        if stat != CPU_STAT:
            continue
        total += flat + base_stats.get(CPU_STAT, 0) * percent // PERCENT_BASE
    return total


def check_keeps_slots(current: GearItem, candidate: GearItem) -> bool:
    """갈아 껴도 소모품 칸이 안 줄어드는가.

    **스킬·CPU 와 같은 자리의 세 번째 상실이다.** 칸이 줄면 넘치는 줄은 안 읽히고
    (`store/consumables.list_consumable_slots`), 그 칸에 있던 물약·주문서가 **잠긴다** —
    지워지지는 않지만 그 판에는 없는 것과 같다.

    저울이 그것을 못 본다. 실측으로 `약사 갑옷 → 보루 갑옷` 은 DEFENSE 저울에서 +41 인데,
    잃은 칸에 영약과 인장 주문서가 들어 있으면 실제 로드아웃은 방어 16→14 · 체력
    141→125 · 충전 POTION 9→2 · SCROLL 7→1 이 된다. **저울이 이득이라 세는 바로 그
    순간 캐릭터가 나빠진다.**

    칸 자체에는 무게를 준다(`gear_priority.json`) — 그것은 「자리 하나가 얼마짜리인가」다.
    여기서 막는 것은 다른 것이다: **사람이 안 고른 상실.** 손으로 바꾸는 길은 안 막는다.

    Args:
        current: 지금 낀 것.
        candidate: 갈아 낄 후보.

    Returns:
        쓰임새마다 후보의 칸 기여가 지금 것 이상이면 True.
    """
    return all(
        count_affix_gift(candidate, stat) >= count_affix_gift(current, stat) for stat in SLOT_STATS
    )


def check_keeps_reach(current: GearItem, candidate: GearItem) -> bool:
    """갈아 껴도 **접사가 준 사거리**가 안 줄어드는가.

    **규칙표가 직접 읽는 축이다.** `적거리 <= 사거리` 가 그 값을 보므로, 잃으면 규칙의
    뜻이 사람이 안 고친 채로 달라진다 — 스킬 상실과 같은 자리다. 실측으로
    `조준 투구(사거리 +1) → 예지 투구` 가 ATTACK 저울에서 정확히 여유폭만큼 앞선다.

    **무기의 사거리는 안 본다.** 그것은 필드이고, 바뀌는 것은 사람이 무기를 고른
    결과다 (결정 #13). 여기서 막는 것은 방어구가 조용히 사거리를 빼앗는 경우다.

    Args:
        current: 지금 낀 것.
        candidate: 갈아 낄 후보.

    Returns:
        후보의 사거리 접사가 지금 것 이상이면 True.
    """
    return count_affix_gift(candidate, REACH_STAT) >= count_affix_gift(current, REACH_STAT)


def count_affix_gift(item: GearItem, stat: str) -> int:
    """이 장비의 **접사**가 그 축에 더하는 몫.

    **필드는 안 센다.** 무기의 `attack_range` 는 접사가 아니라 필드이고, 그것이 바뀌는
    것은 사람이 무기를 고른 결과다 — 활을 들면 사거리가 바뀌고 같은 규칙표가 저절로
    다르게 도는 것이 이 게임이 파는 것이다 (결정 #13).

    Args:
        item: 볼 장비.
        stat: 축 이름.

    Returns:
        더하는 값. 퍼센트는 안 본다 — 칸과 사거리는 정수로만 는다.
    """
    return sum(flat for name, flat, _percent in item.affixes if name == stat)


def check_keeps_everything(
    current: GearItem, candidate: GearItem, base_stats: dict[str, int]
) -> bool:
    """사람이 안 고른 상실이 하나도 없는가 — 관문 넷을 한자리에.

    **저울이 못 보는 축들이다.** 점수는 「무엇이 더 센가」를 재는데, 이 넷은 잃는 순간
    **규칙표의 뜻이 달라지거나 실행이 막힌다** — 점수로 견줄 값이 아니라 조건이다.

    | 축 | 잃으면 |
    |:--|:--|
    | 스킬 | 그 규칙이 런타임에 「불가」로 떨어진다 |
    | CPU 예산 | 규칙표 **전체**가 제출에서 반려된다 |
    | 소모품 칸 | 그 칸의 물약·주문서가 잠긴다 |
    | 사거리 접사 | `적거리 <= 사거리` 의 뜻이 달라진다 |

    넷을 한 함수로 모은 것은 순환 복잡도 때문만이 아니다. **다섯 번째가 생길 때 여기
    하나만 보면 된다** — 실제로 오늘 하루에 넷이 차례로 드러났고, 그때마다 부르는 쪽을
    고쳐야 했다.

    **손으로 바꾸는 길은 안 막는다.** 장비 교체가 규칙 재설계를 부르는 것은 이 게임이
    파는 것이고(P3), 파는 것과 몰래 뺏는 것은 다르다.

    Args:
        current: 지금 낀 것.
        candidate: 갈아 낄 후보.
        base_stats: 퍼센트를 값으로 바꾸는 기준.

    Returns:
        넷을 다 지키면 True.
    """
    return (
        check_keeps_skill(current, candidate)
        and check_keeps_budget(current, candidate, base_stats)
        and check_keeps_slots(current, candidate)
        and check_keeps_reach(current, candidate)
    )
