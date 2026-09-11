"""층이 등급을 기울인다 (2026-09-11 결정).

「아이템 확률표를 두고 층이 올라갈수록 등급이 높은 아이템 획득률이 높았으면 좋겠다.
단 너무 높아지지 않게. 기본적으로 낮은 등급이 높게」가 요청이었다.

**기울이는 축을 레벨에서 층으로 옮겼다.** 예전에는 잡은 개체의 레벨이 상위 등급을
밀었는데, 그 값은 지속 몬스터에서 내려가기도 해서(`goblin_rusher 레벨 3→1`) 깊은 층이
무작위로 더 나빠졌다. 사람이 느끼는 축은 층이다.

여기서 지키는 것은 넷이다.

1. **1층은 표 그대로다.** 기준이 없으면 「기울었다」를 말할 수 없다.
2. **깊을수록 상위 등급이 잘 나온다.** 단조 증가여야 한다.
3. **그래도 낮은 등급이 지배적이다.** 마지막 층에서도 전리품의 대부분은 보통이다.
4. **상한이 있다.** 층이 늘어나도 상위 등급이 기본이 되지 않는다.
"""

from game.app.items.drops import FLOOR_CAP_PCT, GRADE_MISS, build_grade_pool, compute_grade_weight
from game.app.store.drops import DEFAULT_GRADE_WEIGHTS
from game.schemas.item import GRADE_COMMON, GRADE_FINE, GRADE_RELIC

# 마지막 층 (`balance.json` 의 floor_scale.max_floor).
LAST_FLOOR = 10
# 깊은 층에서도 전리품 중 보통이 차지해야 하는 최소 몫. 「기본적으로 낮은 등급이 높게」.
COMMON_FLOOR_PCT = 60


def build_pool(floor):
    """그 층의 저울을 만든다.

    Args:
        floor: 볼 층.

    Returns:
        등급에서 가중치로.
    """
    graded = tuple(one for one in DEFAULT_GRADE_WEIGHTS if one[0] != GRADE_MISS)
    miss = next(weight for grade, weight, _s in DEFAULT_GRADE_WEIGHTS if grade == GRADE_MISS)
    return dict(build_grade_pool(graded, miss, floor, {}))


def count_share_pct(pool, grade):
    """전리품 중 그 등급의 몫.

    Args:
        pool: 등급에서 가중치로.
        grade: 볼 등급.

    Returns:
        정수 퍼센트. 안 나옴을 뺀 몫에서 센다.
    """
    hit = sum(weight for name, weight in pool.items() if name != GRADE_MISS)
    return pool[grade] * 100 // max(1, hit)


def test_the_first_floor_is_the_table_as_written():
    """★ 1층이 기준이다 — 여기서 기울면 표의 숫자가 뜻을 잃는다."""
    pool = build_pool(1)
    for grade, weight, _scale in DEFAULT_GRADE_WEIGHTS:
        assert pool[grade] == weight, grade


def test_deeper_floors_lift_the_higher_grades():
    """★ 깊을수록 상위 등급이 무거워진다. **단조 증가여야 한다.**"""
    fine = [build_pool(floor)[GRADE_FINE] for floor in range(1, LAST_FLOOR + 1)]
    relic = [build_pool(floor)[GRADE_RELIC] for floor in range(1, LAST_FLOOR + 1)]
    assert fine == sorted(fine) and fine[-1] > fine[0]
    assert relic == sorted(relic) and relic[-1] > relic[0]


def test_the_common_grade_stays_the_bulk_even_at_the_bottom():
    """★ **기본적으로 낮은 등급이 높게** (실제 요청).

    마지막 층에서도 전리품의 대부분은 보통이다 — 상위 등급이 기본이 되면 등급이 뜻을
    잃는다.
    """
    share = count_share_pct(build_pool(LAST_FLOOR), GRADE_COMMON)
    assert share >= COMMON_FLOOR_PCT, f"마지막 층의 보통 몫이 {share}% 다"


def test_the_lift_is_gentle():
    """★ **너무 높아지지 않게** (같은 요청).

    유물은 마지막 층에서도 전리품의 몇 퍼센트다. 여기가 두 자리로 가면 「깊은 층에서는
    유물이 흔하다」가 되고, 그러면 얕은 층을 돌 이유가 사라진다.
    """
    assert count_share_pct(build_pool(LAST_FLOOR), GRADE_RELIC) <= 5


def test_the_floor_bonus_has_a_ceiling():
    """★ 층이 늘어나도 상위 등급이 조용히 기본이 되지 않는다."""
    far = compute_grade_weight(100, 12, 999, 0)
    assert far == 100 + 100 * FLOOR_CAP_PCT // 100


def test_a_miss_is_never_lifted_by_the_floor():
    """★ 「안 나옴」은 안 기울인다 — 깊은 층은 조금 더 자주 준다."""
    assert build_pool(1)[GRADE_MISS] == build_pool(LAST_FLOOR)[GRADE_MISS]


def test_the_hit_rate_rises_but_only_a_little():
    """★ 상위 등급이 무거워진 만큼 안 나옴의 몫이 준다. **그 폭이 작아야 한다.**"""
    rates = []
    for floor in (1, LAST_FLOOR):
        pool = build_pool(floor)
        total = sum(pool.values())
        hit = total - pool[GRADE_MISS]
        rates.append(hit * 10000 // total)
    assert rates[1] > rates[0], "깊은 층이 더 안 준다"
    assert rates[1] - rates[0] <= 100, "드롭률이 1%p 넘게 올랐다"
