"""힘·민첩·지능을 전투 스탯으로 옮긴다 (결정 #51).

**축마다 여는 것이 다르다.** 세 축이 모두 공격력으로 수렴하면 배분이 선택이 아니라
계산이 되고, 그러면 포인트를 주는 의미가 사라진다 (P3).

| 축 | 여는 것 | 왜 |
|:--|:--|:--|
| 힘 | 공격 · 최대체력 | 정면으로 버티고 때리는 축 |
| 민첩 | 선공권 · 방어 | 먼저 움직이고, 맞아도 덜 아픈 축 |
| 지능 | CPU · 스킬위력 | 더 정교한 규칙을 돌리고 스킬로 푸는 축 |

**미리보기에 적었던 「회피」는 넣지 않았다.** 이 게임의 회피는 스탯이 아니라 예고
타일에서 비켜서는 것이고(`simulation/telegraph.py`), 확률 굴림을 더하면 "위치와 규칙으로
푼다" 는 P1 이 무너진다. 민첩은 대신 방어를 연다.

**지능이 여는 CPU 에는 상한이 있다.** 능력치 포인트 자체에는 상한이 없지만, CPU 는
표현력이고 표현력이 무한하면 정교한 로직의 가치가 사라진다 (`levels` 모듈 머리말).
그래서 축은 무한히 올려도 그중 CPU 로 바뀌는 몫만 여기서 막는다.
"""

from dataclasses import dataclass

# 힘 1점이 여는 것.
ATTACK_PER_STR = 1
HP_MAX_PER_STR = 4

# 민첩 1점이 여는 것.
INITIATIVE_PER_DEX = 2
DEFENSE_PER_DEX = 1

# 지능. CPU 는 3점당 1이며 표현력이므로 상한이 있다.
INT_PER_CPU = 3
MAX_CPU_FROM_INT = 8

# 지능 1점당 스킬위력 퍼센트. 정수 퍼센트로만 다룬다 — 부동소수는 플랫폼마다 갈려
# 골든 리플레이를 무너뜨린다 (R5).
SKILL_POWER_PCT_PER_INT = 2

# 스킬위력의 기준값. 100 이 "계수 그대로" 다.
BASE_SKILL_POWER_PCT = 100


@dataclass(frozen=True)
class AttributeBonus:
    """배분한 능력치가 만들어 내는 전투 스탯 가산분."""

    attack: int
    hp_max: int
    initiative: int
    defense: int
    cpu_budget: int
    skill_power_pct: int


def build_attribute_bonus(stats: dict[str, int]) -> AttributeBonus:
    """배분표를 전투 스탯 가산분으로 바꾼다.

    음수 배분은 0 으로 본다. 저장된 값이 손상돼도 스탯이 깎이지는 않아야 한다 —
    변조로 남의 캐릭터를 약하게 만들 길을 열지 않는다.

    Args:
        stats: 축에서 배분 점수로의 대응표. `str`·`dex`·`int` 를 읽는다.

    Returns:
        가산분. 배분이 비어 있으면 스킬위력만 기준값이고 나머지는 0 이다.
    """
    strength = max(0, int(stats.get("str", 0)))
    dexterity = max(0, int(stats.get("dex", 0)))
    intellect = max(0, int(stats.get("int", 0)))
    return AttributeBonus(
        attack=strength * ATTACK_PER_STR,
        hp_max=strength * HP_MAX_PER_STR,
        initiative=dexterity * INITIATIVE_PER_DEX,
        defense=dexterity * DEFENSE_PER_DEX,
        cpu_budget=min(MAX_CPU_FROM_INT, intellect // INT_PER_CPU),
        skill_power_pct=BASE_SKILL_POWER_PCT + intellect * SKILL_POWER_PCT_PER_INT,
    )
