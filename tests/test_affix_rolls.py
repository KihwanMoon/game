"""굴림은 값을 흔들지, **지우지 않는다** (2026-09-11, 실제 신고).

「소모품 칸을 늘려 주는 장비가 이름만 있고 옵션이 적용되지 않는다」가 신고였다.

`convert_affix_roll` 이 카탈로그 값에 80~120% 를 곱하고 정수 내림을 한다. 값이 1 인
접사는 **80~99 가 나오면 0 이 된다** — 굴림 폭의 절반이다. 그러면 접사 줄은 그대로
남아 「물약 주머니」라 적히는데 칸은 안 는다.

칸·회로처럼 값이 ±1 인 접사에서 0 은 「나쁘게 굴린 것」이 아니라 **거짓말**이다.
이름이 무언가를 약속하는데 아무 일도 일어나지 않는다.

**나쁘게 굴린 것은 그대로 둔다.** 막는 것은 사라지는 것뿐이다.
"""

from game.app.items.loot import (
    AFFIX_MAX_PERCENT,
    AFFIX_MIN_PERCENT,
    convert_affix_roll,
    resolve_rolled_value,
)
from game.schemas.item import Affix

# 굴림 폭 전체. 어느 값이 나와도 지켜져야 하는 것을 이 범위로 확인한다.
ALL_PERCENTS = range(AFFIX_MIN_PERCENT, AFFIX_MAX_PERCENT + 1)


def test_a_roll_never_erases_an_affix():
    """★ **±1 짜리는 어느 굴림에서도 안 사라진다.**

    이것이 실제로 깨져 있던 자리다 — 굴림 폭의 절반이 「물약 주머니 0칸」을 만들었다.
    """
    for percent in ALL_PERCENTS:
        assert resolve_rolled_value(1, percent) >= 1, percent
        assert resolve_rolled_value(-1, percent) <= -1, percent


def test_a_bad_roll_is_still_a_bad_roll():
    """★ **나쁘게 굴린 아이템은 그대로 있어야 한다.**

    0 을 막는 것이 「전부 최대값」이 되면 굴림 자체가 뜻을 잃는다.
    """
    assert resolve_rolled_value(4, AFFIX_MIN_PERCENT) == 3
    assert resolve_rolled_value(10, AFFIX_MIN_PERCENT) == 8


def test_nothing_appears_out_of_nothing():
    """★ 기준값이 0 이면 결과도 0 이다 — 없는 접사가 굴림으로 생기면 안 된다."""
    for percent in ALL_PERCENTS:
        assert resolve_rolled_value(0, percent) == 0


def test_a_slot_affix_always_opens_a_slot():
    """★ 신고 그대로의 자리 — 「물약 주머니」는 언제나 칸을 하나 연다."""
    for _ in range(50):
        rolled = convert_affix_roll(
            Affix(stat="potion_slots", flat=1, percent=0, label_ko="물약 주머니")
        )
        assert rolled.flat >= 1, "이름만 남고 칸이 안 늘었다"


def test_a_percent_only_affix_survives_too():
    """★ 백분율로 적힌 접사도 같다 — 1% 짜리가 0% 로 굴려지면 같은 거짓말이 된다."""
    for _ in range(50):
        rolled = convert_affix_roll(Affix(stat="hp_max", flat=0, percent=1, label_ko="두툼함"))
        assert rolled.percent >= 1
        assert rolled.flat == 0
