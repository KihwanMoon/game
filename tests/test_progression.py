"""플레이어 성장 (F단계, 결정 #10·#11).

레벨이 **둘을 함께** 준다 — 표현력(상한 있음)과 능력치 포인트(상한 없음).
그 비대칭이 이 게임의 2단 구조를 만든다 (기획/2_GDD_v2 §0.1).
"""

import pytest

from game.app.progression.levels import (
    MAX_BONUS_CPU,
    MAX_BONUS_RULE_SLOTS,
    MIN_LEVEL,
    STAT_KEYS,
    STAT_POINTS_PER_LEVEL,
    add_run_xp,
    build_growth,
    check_allocation,
    compute_level,
    compute_required_xp,
    count_spent_points,
)


def test_level_has_no_cap():
    """★ 결정: 스탯 성장 상한 없음. 몬스터와 다른 지점이다."""
    level, _ = compute_level(10_000_000)
    assert level > 20


def test_required_xp_grows():
    steps = [compute_required_xp(level) for level in range(1, 6)]
    assert steps == sorted(steps) and steps[-1] > steps[0]


def test_level_is_deterministic():
    """부동소수를 쓰면 같은 경험치가 서버 재시작 뒤에 다른 레벨을 낼 수 있다."""
    assert compute_level(5000) == compute_level(5000)


def test_expressiveness_is_capped():
    """★ CPU 와 슬롯이 무한하면 제약이 사라지고, 제약이 사라지면 설계가 고민이 아니게 된다 (P3)."""
    growth = build_growth(500)
    assert growth.bonus_rule_slots == MAX_BONUS_RULE_SLOTS
    assert growth.bonus_cpu == MAX_BONUS_CPU


def test_stat_points_are_not_capped():
    """★ 능력치는 상한이 없다 — 표현력과 반대다."""
    low = build_growth(10).stat_points
    high = build_growth(200).stat_points
    assert high > low
    assert high == (200 - MIN_LEVEL) * STAT_POINTS_PER_LEVEL


def test_level_one_gives_nothing():
    growth = build_growth(MIN_LEVEL)
    assert (growth.bonus_rule_slots, growth.bonus_cpu, growth.stat_points) == (0, 0, 0)


def test_allocation_cannot_exceed_points():
    """★ 받은 것보다 많이 쓸 수 없다."""
    level = 10
    available = build_growth(level).stat_points
    assert check_allocation({"str": available}, level) == ""
    assert "모자란다" in check_allocation({"str": available + 1}, level)


def test_unknown_stat_is_rejected():
    """모르는 능력치를 받으면 화면이 만든 오타가 그대로 저장된다."""
    assert "모르는" in check_allocation({"luck": 1}, 10)


def test_negative_allocation_is_rejected():
    assert "음수" in check_allocation({"str": -1}, 10)


def test_stat_keys_are_the_decided_three():
    """결정 #11 — 힘·민첩·지능 신설."""
    assert set(STAT_KEYS) == {"str", "dex", "int"}


def test_spent_points_ignore_unknown_keys():
    assert count_spent_points({"str": 2, "luck": 99}) == 2


@pytest.mark.parametrize(("is_cleared", "is_more"), [(True, True), (False, False)])
def test_winning_gives_more_xp(is_cleared, is_more):
    """진 판도 빈손은 아니다 — "실패한 런도 자산을 남긴다"(GDD §2.3)를 경험치에도 건다."""
    assert (add_run_xp(True) > add_run_xp(False)) is True
    assert add_run_xp(is_cleared) > 0
