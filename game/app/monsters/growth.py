"""몬스터 성장 — 경험치·레벨과 **폭주 방지** (docs/설계/6_몬스터 §2·§5, 결정 #35).

성장이 스탯만이 아니라 **규칙 슬롯·CPU 예산을 올린다.** 몬스터도 규칙표로 행동하므로
슬롯이 늘면 판단이 정교해지고, 도감이 그 규칙표를 공개하므로 플레이어는 무엇이 달라졌는지
읽을 수 있다. 스탯만 오르면 "숫자가 커졌다" 로 끝난다 (P1).

**폭주 방지를 넷 다 건다** (결정 #35). 하나만으로는 부족하다.

* **구역·층 격리** — 저층 몬스터는 저층 상한을 쓴다. 신규 진입 자리가 구조적으로 보장된다.
* **레벨 상한** — 구역별 상한에서 멈춘다. 가장 단순하고 확실하다.
* **처치 시 감쇠** — 잡히면 레벨이 내려간다. 플레이어의 승리가 세계에 흔적을 남긴다.
* **성장률 체감** — 레벨이 높을수록 다음 레벨이 멀어진다. 상한 없이 부드럽게 눌린다.
"""

from dataclasses import dataclass

# 레벨 1 에서 2 로 가는 데 드는 경험치. 이후는 체감 곡선이 정한다.
BASE_XP_STEP = 100

# 성장률 체감 (정수 퍼센트). 레벨마다 필요 경험치가 이만큼 는다 — 상한이 없어도
# 부드럽게 눌리는 축이다.
XP_GROWTH_PERCENT = 135
PERCENT_BASE = 100

# 구역(층)당 레벨 상한. 저층 몬스터가 무한히 크면 신규 플레이어가 들어갈 자리가 없다.
# 층 하나당 이만큼 열린다.
LEVEL_CAP_PER_FLOOR = 5
MIN_LEVEL = 1

# 처치되면 내려가는 레벨 수. 0 이면 플레이어의 승리가 세계에 아무 흔적을 안 남긴다.
DEFEAT_LEVEL_LOSS = 1

# 레벨이 올리는 것. 스탯이 아니라 **표현력**이다 — 도감이 그 변화를 읽게 해 준다.
LEVELS_PER_RULE_SLOT = 4
LEVELS_PER_CPU = 2

# 레벨당 스탯 증가 (정수 퍼센트). 낮게 두는 이유는 성장의 무게를 표현력 쪽에 두기
# 위해서다 — 스탯만 오르면 "숫자가 커졌다" 로 끝난다.
STAT_PERCENT_PER_LEVEL = 6


@dataclass(frozen=True)
class Growth:
    """레벨 하나가 주는 것."""

    level: int
    bonus_rule_slots: int
    bonus_cpu: int
    stat_percent: int


def get_level_cap(floor: int) -> int:
    """이 층의 레벨 상한 (결정 #35 — 구역 격리 + 상한).

    Args:
        floor: 몬스터가 사는 층.

    Returns:
        올라갈 수 있는 최대 레벨.
    """
    return max(MIN_LEVEL, floor * LEVEL_CAP_PER_FLOOR)


def compute_required_xp(level: int) -> int:
    """다음 레벨까지 필요한 경험치 (결정 #35 — 성장률 체감).

    정수만 쓴다. 부동소수를 쓰면 같은 경험치가 서버 재시작 뒤에 다른 레벨을 낼 수 있다.

    Args:
        level: 지금 레벨.

    Returns:
        다음 레벨까지 필요한 양.
    """
    required = BASE_XP_STEP
    for _ in range(max(0, level - MIN_LEVEL)):
        required = required * XP_GROWTH_PERCENT // PERCENT_BASE
    return required


def compute_level_xp(level: int) -> int:
    """그 레벨에 딱 닿는 누적 경험치.

    관리자가 레벨을 직접 정할 때 경험치를 함께 맞추는 데 쓴다 — 레벨만 바꾸면 다음
    경험치 한 점에 원래 레벨로 되돌아가고, 손댄 것이 조용히 사라진다.

    Args:
        level: 목표 레벨.

    Returns:
        그 레벨에 닿는 누적 경험치.
    """
    return sum(compute_required_xp(step) for step in range(MIN_LEVEL, level))


def compute_cap_xp(floor: int) -> int:
    """그 층의 상한 레벨에 딱 닿는 누적 경험치.

    **상한 위로는 쌓지 않는다.** 쌓게 두면 처치 감쇠가 무의미해진다 — 한 레벨어치를
    덜어 내도 여전히 상한 위라 레벨이 그대로다. 검사가 이것을 잡았다.

    Args:
        floor: 몬스터가 사는 층.

    Returns:
        상한 레벨에 닿는 누적 경험치.
    """
    return sum(compute_required_xp(level) for level in range(MIN_LEVEL, get_level_cap(floor)))


def compute_level(total_xp: int, floor: int) -> tuple[int, int]:
    """누적 경험치에서 레벨과 남은 경험치를 낸다.

    Args:
        total_xp: 누적 경험치.
        floor: 몬스터가 사는 층. 상한을 정한다.

    Returns:
        (레벨, 그 레벨에서의 잔여 경험치).
    """
    cap = get_level_cap(floor)
    level = MIN_LEVEL
    remaining = max(0, total_xp)
    while level < cap:
        needed = compute_required_xp(level)
        if remaining < needed:
            break
        remaining -= needed
        level += 1
    return level, remaining


def build_growth(level: int) -> Growth:
    """레벨이 주는 것을 계산한다.

    Args:
        level: 몬스터 레벨.

    Returns:
        표현력 보너스와 스탯 퍼센트.
    """
    steps = max(0, level - MIN_LEVEL)
    return Growth(
        level=level,
        bonus_rule_slots=steps // LEVELS_PER_RULE_SLOT,
        bonus_cpu=steps // LEVELS_PER_CPU,
        stat_percent=PERCENT_BASE + steps * STAT_PERCENT_PER_LEVEL,
    )


def compute_defeat_xp(total_xp: int, level: int, floor: int) -> int:
    """처치됐을 때 남는 누적 경험치 (결정 #35 — 처치 시 감쇠).

    한 레벨어치를 덜어 낸다. 0 밑으로는 내려가지 않는다 — 음수 경험치는 뜻이 없다.

    Args:
        total_xp: 지금 누적 경험치.
        level: 지금 레벨.
        floor: 사는 층.

    Returns:
        감쇠 뒤의 누적 경험치.
    """
    target = max(MIN_LEVEL, level - DEFEAT_LEVEL_LOSS)
    if target == level:
        # 이미 최저 레벨이면 그 레벨의 잔여 경험치만 버린다.
        _, remaining = compute_level(total_xp, floor)
        return max(0, total_xp - remaining)
    lost = sum(compute_required_xp(item) for item in range(target, level))
    return max(0, total_xp - lost)
