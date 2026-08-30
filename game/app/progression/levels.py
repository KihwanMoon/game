"""플레이어 레벨과 경험치.

레벨이 **둘을 함께** 준다 (기획/2_GDD_v2 §0.1).

* **표현력** — 규칙 슬롯·CPU 예산·플래그. 상한이 있다.
* **능력치 포인트** — 힘·민첩·지능에 유저가 직접 배분한다. **상한이 없다.**

상한이 없는 쪽이 GDD §0 을 2단 구조로 바꾼 결정이며, P1(실패는 정보다)의 유효 구간이
초·중반으로 한정되는 대가를 문서가 적어 두었다. 그래서 표현력에는 상한을 남긴다 —
CPU 예산과 슬롯이 무한하면 "정교한 로직" 의 가치까지 사라진다.

**힘·민첩·지능이 전투 스탯으로 어떻게 변환되는지는 아직 정해지지 않았다** (미결 #51).
여기서는 배분만 받아 두고, 변환표가 정해지면 그것을 읽는 쪽이 생긴다.
"""

from dataclasses import dataclass

# 레벨 1→2 에 드는 경험치와 체감률. 몬스터와 값이 다르다 — 플레이어는 상한이 없으므로
# 체감이 더 세야 후반이 무한히 빨라지지 않는다.
BASE_XP_STEP = 120
XP_GROWTH_PERCENT = 118
PERCENT_BASE = 100

MIN_LEVEL = 1

# 표현력 보너스. **여기에는 상한이 있다** — CPU 와 슬롯이 무한하면 제약이 사라지고,
# 제약이 사라지면 규칙 설계가 고민이 아니게 된다 (P3).
LEVELS_PER_RULE_SLOT = 5
MAX_BONUS_RULE_SLOTS = 4
LEVELS_PER_CPU = 3
MAX_BONUS_CPU = 12
LEVELS_PER_FLAG = 8
MAX_BONUS_FLAGS = 2

# 레벨당 받는 능력치 포인트. **상한이 없다** (결정: 스탯 성장 상한 없음).
STAT_POINTS_PER_LEVEL = 3

# 배분할 수 있는 능력치. 무엇을 여는지는 미결 #51 이 정한다.
STAT_KEYS: tuple[str, ...] = ("str", "dex", "int")

# 검증된 런이 주는 경험치. 이기는 것이 확실히 낫지만 진 판도 빈손은 아니다 —
# "실패한 런조차 자산을 남긴다"(GDD §2.3)를 경험치에도 얇게 건다.
XP_WIN = 80
XP_LOSS = 20


@dataclass(frozen=True)
class PlayerGrowth:
    """레벨 하나가 주는 것."""

    level: int
    bonus_rule_slots: int
    bonus_cpu: int
    bonus_flags: int
    stat_points: int


def compute_required_xp(level: int) -> int:
    """다음 레벨까지 필요한 경험치.

    정수만 쓴다 — 부동소수를 쓰면 같은 경험치가 서버 재시작 뒤에 다른 레벨을 낼 수 있다.

    Args:
        level: 지금 레벨.

    Returns:
        다음 레벨까지 필요한 양.
    """
    required = BASE_XP_STEP
    for _ in range(max(0, level - MIN_LEVEL)):
        required = required * XP_GROWTH_PERCENT // PERCENT_BASE
    return required


def compute_level(total_xp: int) -> tuple[int, int]:
    """누적 경험치에서 레벨과 잔여를 낸다. 상한이 없다.

    Args:
        total_xp: 누적 경험치.

    Returns:
        (레벨, 그 레벨에서의 잔여 경험치).
    """
    level = MIN_LEVEL
    remaining = max(0, total_xp)
    while True:
        needed = compute_required_xp(level)
        if remaining < needed:
            return level, remaining
        remaining -= needed
        level += 1


def build_growth(level: int) -> PlayerGrowth:
    """레벨이 주는 것을 계산한다.

    Args:
        level: 플레이어 레벨.

    Returns:
        표현력 보너스와 능력치 포인트.
    """
    steps = max(0, level - MIN_LEVEL)
    return PlayerGrowth(
        level=level,
        bonus_rule_slots=min(MAX_BONUS_RULE_SLOTS, steps // LEVELS_PER_RULE_SLOT),
        bonus_cpu=min(MAX_BONUS_CPU, steps // LEVELS_PER_CPU),
        bonus_flags=min(MAX_BONUS_FLAGS, steps // LEVELS_PER_FLAG),
        stat_points=steps * STAT_POINTS_PER_LEVEL,
    )


def count_spent_points(stats: dict[str, int]) -> int:
    """이미 배분한 포인트 수.

    Args:
        stats: 능력치 배분표.

    Returns:
        배분된 총량. 모르는 열쇠는 세지 않는다.
    """
    return sum(max(0, int(stats.get(key, 0))) for key in STAT_KEYS)


def check_allocation(stats: dict[str, int], level: int) -> str:
    """배분이 받을 수 있는 것인지 본다.

    Args:
        stats: 새 배분표.
        level: 지금 레벨.

    Returns:
        문제가 없으면 빈 문자열, 있으면 사유.
    """
    for key, value in stats.items():
        if key not in STAT_KEYS:
            return f"모르는 능력치다: {key}"
        if int(value) < 0:
            return f"능력치는 음수가 될 수 없다: {key}"
    spent = count_spent_points(stats)
    available = build_growth(level).stat_points
    if spent > available:
        return f"포인트가 모자란다: {spent} > {available}"
    return ""


def add_run_xp(is_cleared: bool) -> int:
    """검증된 런 하나가 주는 경험치.

    Args:
        is_cleared: 이겼는가.

    Returns:
        줄 경험치.
    """
    return XP_WIN if is_cleared else XP_LOSS
