"""등급 — 일반·엘리트·보스 (docs/설계/6_몬스터 §1).

등급과 지속성은 **직교한다.** 한 축으로 묶으면 "지속되는 일반 몬스터" 를 표현할 수 없고,
나중에 갈라야 한다. 다만 일반은 항상 EPHEMERAL 이다 — 지속시키면 개체가 무한히 쌓여
스냅샷이 런 티켓 용량을 넘는다.
"""

from enum import StrEnum


class MonsterTier(StrEnum):
    """몬스터 등급 셋."""

    NORMAL = "NORMAL"
    ELITE = "ELITE"
    BOSS = "BOSS"


class Persistence(StrEnum):
    """런이 끝나도 남는가."""

    EPHEMERAL = "EPHEMERAL"
    PERSISTENT = "PERSISTENT"


# 등급이 스탯에 거는 배수 (정수 퍼센트). 엘리트는 눈에 띄게 세지만 보스만큼은 아니다.
TIER_STAT_PERCENT: dict[MonsterTier, int] = {
    MonsterTier.NORMAL: 100,
    MonsterTier.ELITE: 150,
    MonsterTier.BOSS: 260,
}

PERCENT_BASE = 100


def get_tier_percent(tier: MonsterTier) -> int:
    """등급이 거는 스탯 배수.

    Args:
        tier: 등급.

    Returns:
        정수 퍼센트. 100 이 1.0배다.
    """
    return TIER_STAT_PERCENT.get(tier, PERCENT_BASE)


def compute_tier_stat(base: int, tier: MonsterTier) -> int:
    """등급을 반영한 스탯 하나.

    정수 나눗셈이며 내림이다 (R5). 부동소수를 쓰면 두 코어가 같은 적에서 갈린다.

    Args:
        base: 기본값.
        tier: 등급.

    Returns:
        내림 절삭된 값.
    """
    return base * get_tier_percent(tier) // PERCENT_BASE


def check_can_persist(tier: MonsterTier) -> bool:
    """이 등급이 지속될 수 있는가.

    일반은 안 된다 — 지속시키면 세계에 개체가 무한히 쌓이고, 그것을 전부 스냅샷에
    실어야 해서 런 티켓이 감당할 수 없어진다 (docs/설계/6_몬스터 §1).

    Args:
        tier: 등급.

    Returns:
        지속 가능하면 True.
    """
    return tier is not MonsterTier.NORMAL
