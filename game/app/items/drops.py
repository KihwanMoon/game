"""두 단계 추첨 — 등급을 먼저, 그 안에서 아이템을 (설계/4_아이템 §15.2).

한 표에 섞지 않는 이유가 이 모듈의 전부다. 아이템마다 절대 확률을 적어 두면 **보통
등급에 아이템 하나를 더하는 순간 유물 등급의 확률까지 내려간다.** 콘텐츠를 늘리는 일이
밸런스를 흔드는 일이 되고, 그러면 아무도 아이템을 못 늘린다.

몬스터 레벨은 **1단계에만** 개입한다. 2단계에 넣으면 "레벨 높은 적이 단검을 더 자주
준다" 같은, 아무도 설명할 수 없는 규칙이 생긴다.

`secrets` 를 쓰는 것은 R5 위반이 아니다 — 게임 난수가 아니라 예측 불가능해야 하는 값이고
코어 밖이다 (`loot.py` 머리말과 같은 이유).

**여기 있는 수식은 자리다.** 밸런스는 나중에 정한다.
"""

import secrets

from game.app.items.loot import convert_affix_roll
from game.schemas.item import GRADE_AFFIX_ROLLS, Affix

# 아무것도 안 나온 몫. 등급과 같은 저울에 올리려면 이름이 하나 필요하다.
GRADE_MISS = "MISS"

PERCENT_BASE = 100

# 천장 한 걸음이 더하는 가중치 (D2). 연속으로 안 나온 만큼 그 등급이 무거워진다.
# 확률만으로는 "나는 안 나온다" 를 못 막는다.
PITY_STEP = 2


def get_below(bound: int) -> int:
    """0 이상 bound 미만의 예측 불가능한 정수.

    Args:
        bound: 상한(미포함). 1 이하면 0 이다.

    Returns:
        뽑힌 정수.
    """
    return secrets.randbelow(bound) if bound > 1 else 0


def compute_grade_weight(weight: int, level_scale_pct: int, level: int, misses: int) -> int:
    """등급 하나의 최종 가중치를 낸다.

    레벨과 천장이 **더해지지 곱해지지 않는다.** 곱하면 레벨 10 짜리 개체 하나가 분포를
    통째로 뒤집고, 그러면 층 설계가 뜻을 잃는다.

    Args:
        weight: 표에 적힌 기본 가중치.
        level_scale_pct: 레벨 1당 기본 가중치의 몇 퍼센트를 더할지.
        level: 잡은 개체의 레벨.
        misses: 이 등급의 연속 미획득 수.

    Returns:
        최종 가중치. 0 아래로는 안 내려간다.
    """
    bonus = weight * level_scale_pct * max(0, level) // PERCENT_BASE
    return max(0, weight + bonus + misses * PITY_STEP)


def get_weighted(entries: tuple[tuple[str, int], ...]) -> str | None:
    """가중치대로 하나를 뽑는다.

    **정렬된 튜플을 받는다.** 딕셔너리를 순회해 뽑으면 같은 난수가 실행마다 다른 것을
    내고, 그러면 굴림 기록으로 확률을 검증할 수 없다.

    Args:
        entries: (이름, 가중치) 들. 가중치가 0 인 것도 담겨 있어도 된다.

    Returns:
        뽑힌 이름. 가중치 합이 0 이면 None.
    """
    total = sum(max(0, weight) for _name, weight in entries)
    if total <= 0:
        return None
    cursor = get_below(total)
    for name, weight in entries:
        cursor -= max(0, weight)
        if cursor < 0:
            return name
    return entries[-1][0]


def build_grade_pool(
    weights: tuple[tuple[str, int, int], ...],
    miss_weight: int,
    level: int,
    pity: dict[str, int],
) -> tuple[tuple[str, int], ...]:
    """1단계 저울을 만든다 — 「안 나옴」도 같은 저울에 올린다.

    따로 두면 "먼저 나올지 정하고 그 다음 등급을 정한다" 가 되어, 레벨이 등급 분포를
    미는 것과 드롭률을 올리는 것이 갈린다. 한 저울에 올리면 레벨이 상위 등급을 밀 때
    「안 나옴」의 몫이 자연히 줄어든다.

    Args:
        weights: (등급, 가중치, 레벨당 배율%) 들.
        miss_weight: 아무것도 안 나오는 몫.
        level: 잡은 개체의 레벨.
        pity: 등급별 연속 미획득 수.

    Returns:
        (등급 또는 MISS, 가중치) 들. 이름 순으로 정렬돼 있다.
    """
    pool = [
        (grade, compute_grade_weight(weight, scale, level, pity.get(grade, 0)))
        for grade, weight, scale in weights
    ]
    pool.append((GRADE_MISS, max(0, miss_weight)))
    return tuple(sorted(pool))


def create_affix_rolls(affixes: tuple[Affix, ...], grade: str) -> tuple[Affix, ...]:
    """등급이 정한 개수만큼 접사를 굴린다 (§15.4).

    **등급이 접사 개수를 정한다.** 이름표로만 두면 「유물 단검」이 「보통 단검」보다
    나은 점이 없어 등급이 뜻을 잃는다.

    Args:
        affixes: 카탈로그의 기준 접사.
        grade: 굴린 등급.

    Returns:
        굴린 접사들.
    """
    low, high = GRADE_AFFIX_ROLLS.get(grade, (1, 1))
    count = low + get_below(high - low + 1)
    return tuple(convert_affix_roll(item) for item in affixes[:count])
