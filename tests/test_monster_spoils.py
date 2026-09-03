"""뺏어 든 장비가 몬스터를 세게 만든다 (결정 #34).

**예전에는 표식일 뿐이었다.** 도감이 「내 것을 들고 있다」고 말할 수는 있었지만 그
몬스터가 세지지는 않았고, 그러면 되찾으러 갈 이유가 감정뿐이다.
"""

from game.app.store.spoils import compute_spoiled_stat


def test_nothing_taken_changes_nothing():
    """★ 뺏은 것이 없으면 값이 그대로다 — 대부분의 개체가 이 경우다."""
    assert compute_spoiled_stat(100, "hp_max", {}) == 100


def test_a_flat_bonus_lands():
    """고정값이 그대로 더해진다."""
    assert compute_spoiled_stat(100, "hp_max", {"hp_max": (12, 0)}) == 112


def test_a_percent_bonus_lands():
    """퍼센트가 곱해진다. 정수 나눗셈이며 내림이다 (R5)."""
    assert compute_spoiled_stat(100, "hp_max", {"hp_max": (0, 15)}) == 115
    assert compute_spoiled_stat(7, "attack", {"attack": (0, 15)}) == 8


def test_flat_comes_before_percent():
    """★ 고정값을 먼저 더하고 퍼센트를 건다.

    사람의 장비 합산과 같은 순서여야 **같은 장비가 두 곳에서 다른 값을 내지 않는다.**
    """
    # (100 + 10) * 1.5 = 165. 반대 순서였다면 100*1.5 + 10 = 160 이다.
    assert compute_spoiled_stat(100, "hp_max", {"hp_max": (10, 50)}) == 165


def test_another_stat_is_untouched():
    """다른 스탯의 접사는 안 건드린다."""
    assert compute_spoiled_stat(100, "attack", {"hp_max": (50, 0)}) == 100


def test_a_curse_cannot_go_below_zero():
    """★ 저주 접사는 음수다 (`설계/4_아이템` §9). 스탯이 음수가 되면 안 된다."""
    assert compute_spoiled_stat(5, "attack", {"attack": (-99, 0)}) == 0
