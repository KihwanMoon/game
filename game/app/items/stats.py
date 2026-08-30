"""장비 스탯 합산 (docs/설계/4_아이템 §9, GDD §6.4).

    최종 스탯 = (기본값 + 고정 합계) × (1 + 퍼센트 합계 / 100)

정수로만 계산한다 (R5). 그리고 **연산 순서가 결과를 정한다.**

* **곱한 뒤에 나눈다.** 먼저 나누면 정수 절삭이 두 번 일어나 값이 달라진다.
* **내림으로 절삭한다.** 저주 접사가 있어 퍼센트 합계가 음수가 될 수 있고, 그 자리에서
  파이썬의 `//` 와 TypeScript 의 `Math.trunc` 가 갈린다. TS 이식은 `Math.floor` 를
  써야 하며, 이것이 게이트 G3 가 깨지는 실제 경로다.
* **클램프는 합산이 전부 끝난 뒤 한 번만.** 슬롯마다 걸면 순서가 결과를 바꾼다.

합산 순서는 SLOT_ORDER 고정이다. 정수 덧셈은 교환법칙이 성립하지만, 클램프가 끼는
순간 순서가 뜻을 갖는다.
"""

from dataclasses import dataclass

from game.schemas.item import SLOT_ORDER, EquipSlot, ItemCatalogEntry, WeaponHands

# 퍼센트 기준. 100 이 1.0배다.
PERCENT_BASE = 100


@dataclass(frozen=True)
class StatDelta:
    """한 스탯에 대한 고정 합계와 퍼센트 합계."""

    flat: int = 0
    percent: int = 0


def get_effective_slots(
    equipped: dict[EquipSlot, ItemCatalogEntry],
) -> tuple[tuple[EquipSlot, ItemCatalogEntry | None], ...]:
    """봉인을 반영한 유효 장비 구성을 만든다.

    양손무기는 주무기 자리를 차지하고 보조 자리를 봉인한다. **봉인을 저장된 상태로
    두지 않고 매번 계산하는 이유**는 착용·해제 순서에 따라 상태가 갈리기 때문이다 —
    보조에 무언가를 둔 채 주무기를 양손으로 바꾸면, 저장하는 구현에서는 그 무언가가
    어디로 갔는지가 순서에 따라 달라진다.

    Args:
        equipped: 슬롯에서 착용 중인 항목으로의 대응표.

    Returns:
        SLOT_ORDER 순서의 (슬롯, 항목) 짝. 봉인된 슬롯은 항목이 None 이다.
    """
    main = equipped.get(EquipSlot.WEAPON_MAIN)
    is_two_handed = main is not None and main.hands is WeaponHands.TWO
    result: list[tuple[EquipSlot, ItemCatalogEntry | None]] = []
    for slot in SLOT_ORDER:
        if slot is EquipSlot.WEAPON_OFF and is_two_handed:
            result.append((slot, None))
            continue
        result.append((slot, equipped.get(slot)))
    return tuple(result)


def merge_stat_deltas(
    equipped: dict[EquipSlot, ItemCatalogEntry],
) -> dict[str, StatDelta]:
    """착용 중인 장비의 접사를 스탯별로 합친다.

    Args:
        equipped: 슬롯에서 착용 중인 항목으로의 대응표.

    Returns:
        스탯 이름에서 합계로의 대응표.
    """
    totals: dict[str, StatDelta] = {}
    for _slot, entry in get_effective_slots(equipped):
        if entry is None:
            continue
        for affix in entry.affixes:
            current = totals.get(affix.stat, StatDelta())
            totals[affix.stat] = StatDelta(
                flat=current.flat + affix.flat,
                percent=current.percent + affix.percent,
            )
    return totals


def compute_final_stat(base: int, delta: StatDelta, minimum: int = 0) -> int:
    """스탯 하나의 최종값을 낸다.

    Args:
        base: 기본값.
        delta: 이 스탯에 붙은 고정·퍼센트 합계.
        minimum: 하한. 합산이 전부 끝난 뒤 한 번만 적용한다.

    Returns:
        내림 절삭된 최종값.
    """
    # 곱한 뒤에 나눈다. 먼저 나누면 절삭이 두 번 일어난다.
    scaled = (base + delta.flat) * (PERCENT_BASE + delta.percent) // PERCENT_BASE
    return max(minimum, scaled)


def compute_equipped_stats(
    base_stats: dict[str, int], equipped: dict[EquipSlot, ItemCatalogEntry]
) -> dict[str, int]:
    """장비를 반영한 최종 스탯표를 만든다.

    장비가 건드리지 않은 스탯은 기본값 그대로 나온다. 기본값에 없는 스탯을 장비가
    올리면 0 에서 시작한다 — 카탈로그가 코어보다 앞서 나갈 수 있어야 하기 때문이다.

    Args:
        base_stats: 장비 보너스를 제외한 소재 능력치.
        equipped: 슬롯에서 착용 중인 항목으로의 대응표.

    Returns:
        스탯 이름 순으로 정렬된 최종 스탯표.
    """
    deltas = merge_stat_deltas(equipped)
    names = sorted(set(base_stats) | set(deltas))
    return {
        name: compute_final_stat(base_stats.get(name, 0), deltas.get(name, StatDelta()))
        for name in names
    }
