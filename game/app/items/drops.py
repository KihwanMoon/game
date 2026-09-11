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
from game.schemas.item import Affix

# 아무것도 안 나온 몫. 등급과 같은 저울에 올리려면 이름이 하나 필요하다.
GRADE_MISS = "MISS"

PERCENT_BASE = 100

# 천장 한 걸음이 더하는 가중치 (D2). 연속으로 안 나온 만큼 그 등급이 무거워진다.
# 확률만으로는 "나는 안 나온다" 를 못 막는다.
PITY_STEP = 1

# **천장의 상한.** 기본 가중치의 이 퍼센트까지만 민다. 상한이 없으면 유물이 문제가 된다 —
# 한 런에 열여섯 번 굴리므로 미획득이 런당 16씩 쌓이고, 가중치 5 짜리 등급은 한 판 만에
# 몇 배가 되어 천장이 아니라 자동 지급이 된다.
PITY_CAP_PCT = 300

# **층이 얹을 수 있는 상한.** 기본 가중치의 이 퍼센트까지만 민다.
#
# 마지막 층이 10 이고 상급이 층당 12% 이므로 지금은 108% 까지만 올라 여기 안 닿는다 —
# 층이 늘어날 때 상위 등급이 조용히 기본이 되는 것을 막는 **난간**이다. 사용자가 정한
# 규율이 「너무 높아지지 않게, 기본적으로 낮은 등급이 높게」다 (2026-09-11).
FLOOR_CAP_PCT = 150

# 층 스케일의 기준 층. 1층에서는 표에 적힌 값 그대로다.
FIRST_FLOOR = 1


def get_below(bound: int) -> int:
    """0 이상 bound 미만의 예측 불가능한 정수.

    Args:
        bound: 상한(미포함). 1 이하면 0 이다.

    Returns:
        뽑힌 정수.
    """
    return secrets.randbelow(bound) if bound > 1 else 0


def compute_grade_weight(weight: int, floor_scale_pct: int, floor: int, misses: int) -> int:
    """등급 하나의 최종 가중치를 낸다.

    **층이 기울인다** (2026-09-11 결정). 예전에는 **잡은 개체의 레벨**로 기울였는데, 그
    값은 지속 몬스터에서 내려가기도 해서(로그에 `goblin_rusher 레벨 3→1` 이 남는다) 깊은
    층이 무작위로 더 나빠졌다. 사람이 느끼는 축은 층이므로 축을 층으로 옮겼다.

    층과 천장이 **더해지지 곱해지지 않는다.** 곱하면 한 층이 분포를 통째로 뒤집고,
    그러면 층 설계가 뜻을 잃는다.

    **얹는 값에 상한이 있다** (`FLOOR_CAP_PCT`). 마지막 층이 10 이라 지금 값으로는 안
    닿지만, 층이 늘어날 때 상위 등급이 조용히 기본이 되는 것을 막는 난간이다.

    천장은 **기본 가중치의 `PITY_CAP_PCT` 퍼센트까지만** 민다. 상한이 없으면 한 런에
    열여섯 번 굴리는 동안 미획득이 쌓여 천장이 자동 지급이 된다.

    Args:
        weight: 표에 적힌 기본 가중치.
        floor_scale_pct: 1층에서 한 층 내려갈 때마다 기본 가중치의 몇 퍼센트를 더할지.
        floor: 이 굴림이 일어난 층. 1층이 기준이라 아무것도 안 얹힌다.
        misses: 이 등급의 연속 미획득 수.

    Returns:
        최종 가중치. 0 아래로는 안 내려간다.
    """
    steps = max(0, floor - FIRST_FLOOR)
    bonus = min(
        weight * floor_scale_pct * steps // PERCENT_BASE,
        weight * FLOOR_CAP_PCT // PERCENT_BASE,
    )
    lifted = min(max(0, misses) * PITY_STEP, weight * PITY_CAP_PCT // PERCENT_BASE)
    return max(0, weight + bonus + lifted)


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
    floor: int,
    pity: dict[str, int],
) -> tuple[tuple[str, int], ...]:
    """1단계 저울을 만든다 — 「안 나옴」도 같은 저울에 올린다.

    따로 두면 "먼저 나올지 정하고 그 다음 등급을 정한다" 가 되어, 층이 등급 분포를 미는
    것과 드롭률을 올리는 것이 갈린다. 한 저울에 올리면 층이 상위 등급을 밀 때 「안 나옴」의
    몫이 자연히 줄어든다 — **깊이 내려가면 좋은 것이 잘 나오는 동시에 조금 더 자주 나온다.**

    Args:
        weights: (등급, 가중치, 층당 배율%) 들.
        miss_weight: 아무것도 안 나오는 몫.
        floor: 이 굴림이 일어난 층.
        pity: 등급별 연속 미획득 수.

    Returns:
        (등급 또는 MISS, 가중치) 들. 이름 순으로 정렬돼 있다.
    """
    pool = [
        (grade, compute_grade_weight(weight, scale, floor, pity.get(grade, 0)))
        for grade, weight, scale in weights
    ]
    pool.append((GRADE_MISS, max(0, miss_weight)))
    return tuple(sorted(pool))


def create_affix_rolls(affixes: tuple[Affix, ...]) -> tuple[Affix, ...]:
    """카탈로그의 고정 접사를 **전부** 값만 흔들어 발급한다 (§15.4).

    **등급을 안 받는다.** 예전에는 등급이 개수를 정해 앞에서 잘랐는데, 카탈로그가 좋은
    접사를 먼저 적어 두므로 **잘리는 쪽이 늘 저주였다** — 대검의 과부하와 장궁의 페널티가
    한 번도 발급되지 않았다. 고정 옵션은 고정이어야 트레이드오프가 성립한다.

    등급이 성능에 하는 일은 봉인 칸 수 하나뿐이다 (§17).

    Args:
        affixes: 카탈로그의 기준 접사.

    Returns:
        값이 흔들린 접사들. 개수는 카탈로그와 같다.
    """
    return tuple(convert_affix_roll(item) for item in affixes)
