"""엘리트 접사 굴림 (docs/설계/6_몬스터 §1).

등급 배수만으로는 엘리트가 "같은 적인데 숫자가 큰 것" 이다. 개체마다 다른 접사가 붙어야
도감에서 하나를 지목할 이유가 생긴다.

**`spawn_seed` 에서 파생한다.** 조회할 때마다 굴리면 같은 개체가 볼 때마다 달라진다 —
스냅샷을 얼려 두는 뜻이 사라지고, 도감과 전투가 다른 적을 보게 된다. 굴림 자체는
`DeterministicRng` 를 쓴다: 코어 밖이지만 **같은 시드가 같은 접사를 내야 하므로**
여기서는 예측 불가능성이 아니라 재현성이 필요하다.
"""

from dataclasses import dataclass

from game.app.core.rng import DeterministicRng
from game.app.monsters.tiers import MonsterTier

# 등급별 접사 개수. 보스가 더 많다.
AFFIX_COUNT: dict[MonsterTier, int] = {
    MonsterTier.NORMAL: 0,
    MonsterTier.ELITE: 1,
    MonsterTier.BOSS: 2,
}

# 붙을 수 있는 접사들. 값은 정수 퍼센트이며, 이름이 화면에 그대로 나간다.
AFFIX_POOL: tuple[tuple[str, str, int], ...] = (
    ("hp_max", "억센", 30),
    ("attack", "사나운", 25),
    ("defense", "단단한", 40),
    ("initiative", "재빠른", 20),
)

PERCENT_BASE = 100


@dataclass(frozen=True)
class MonsterAffix:
    """몬스터에 붙은 접사 하나."""

    stat: str
    label_ko: str
    percent: int


def list_monster_affixes(spawn_seed: int, tier: MonsterTier) -> tuple[MonsterAffix, ...]:
    """그 개체의 접사를 굴린다. 같은 시드는 언제나 같은 결과를 낸다.

    같은 접사가 두 번 붙지 않는다 — `억센 억센 고블린` 은 이름이 뜻을 잃는다.

    Args:
        spawn_seed: 개체의 스폰 시드.
        tier: 등급.

    Returns:
        붙은 접사들. 일반 등급이면 빈 튜플.
    """
    count = AFFIX_COUNT.get(tier, 0)
    if count <= 0:
        return ()
    rng = DeterministicRng(spawn_seed)
    remaining = list(AFFIX_POOL)
    picked: list[MonsterAffix] = []
    for _ in range(min(count, len(remaining))):
        index = rng.get_below(len(remaining))
        stat, label, percent = remaining.pop(index)
        picked.append(MonsterAffix(stat=stat, label_ko=label, percent=percent))
    return tuple(picked)


def compute_affixed_stat(base: int, stat: str, affixes: tuple[MonsterAffix, ...]) -> int:
    """접사를 반영한 스탯 하나.

    정수 나눗셈이며 내림이다 (R5). 곱한 뒤에 나눈다 — 먼저 나누면 절삭이 두 번 일어난다.

    Args:
        base: 접사 이전 값.
        stat: 볼 스탯 이름.
        affixes: 붙은 접사들.

    Returns:
        내림 절삭된 값.
    """
    total = sum(item.percent for item in affixes if item.stat == stat)
    return base * (PERCENT_BASE + total) // PERCENT_BASE


def build_affix_label(affixes: tuple[MonsterAffix, ...], label_ko: str) -> str:
    """접사를 앞에 붙인 이름. 도감이 개체를 지목할 수 있게 한다.

    Args:
        affixes: 붙은 접사들.
        label_ko: 종의 이름.

    Returns:
        `사나운 고블린 돌격병` 형태의 이름.
    """
    if not affixes:
        return label_ko
    return " ".join([*(item.label_ko for item in affixes), label_ko])
