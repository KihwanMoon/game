"""층 깊이 스케일 — 같은 적이 층마다 다른 세기로 나온다 (balance.json 의 floor_scale).

## 무엇을 값 매기는가

`pressure.py` 의 층 체류 스케일과 **다른 축**이다. 둘을 갈라 두는 이유는 값 매기는
대상이 다르기 때문이다.

| | 이 모듈 (층 깊이) | pressure (층 체류) |
|:--|:--|:--|
| 세는 것 | 몇 층까지 내려왔는가 | 이 층에서 몇 틱을 끌었는가 |
| 적용 시점 | 개체를 만들 때 한 번 | 매 틱 다시 |
| 대상 | 최대 HP · 공격력 | 공격력 |

## 곱인가 합인가 — 곱이다

체류 스케일은 기준 공격력(`PressureTracker.base_attacks`)에 퍼센트를 얹는데, 그 기준이
이미 층 깊이로 스케일된 값이므로 두 축은 **곱해진다**. 그렇게 정한 이유는, 시간을 끄는
대가가 "지금 이 적이 가진 힘의 몇 %" 여야 하기 때문이다. 더하기로 두면 +1%p 가 층 1
에서나 층 5 에서나 같은 절대량이 되어, 정작 시간을 끌고 싶어지는 깊은 층에서 압력이
희석된다 — GDD §7 이 막으려던 바로 그 방향이다.

## 층 1 이 기준이다 — 그리고 복리다 (e3)

한 층 내려갈 때마다 `mult/100` 을 곱하고 **층마다 내림으로 접는다** (R5 — 거듭제곱을
부동소수로 계산하면 두 코어가 마지막 자리에서 갈린다). 예전의 합산(pct*(층-1))은 깊은
층에서 기울기가 일정해 체감이 죽었다 — 110 이면 10층 적이 1층의 약 2.36배다.
"""

from dataclasses import dataclass

from game.schemas.room import FIRST_FLOOR

DEFAULT_MULT_PCT_PER_FLOOR = 110

# 층 번호의 시작값(FIRST_FLOOR)은 schemas.room 이 정본이다 — min_floor 의 기본값과
# 같은 값이어야 하므로 여기서 다시 적지 않는다. 층 1 의 보너스는 0 이다.

PERCENT_BASE = 100


@dataclass(frozen=True)
class FloorScale:
    """balance.json 의 floor_scale 절을 그대로 담는 값."""

    mult_pct_per_floor: int = DEFAULT_MULT_PCT_PER_FLOOR


def build_floor_scale(floor_scale: dict) -> FloorScale:
    """floor_scale 절을 규칙 값으로 옮긴다.

    Args:
        floor_scale: balance.json 의 floor_scale 딕셔너리.

    Returns:
        읽어들인 규칙. 빠진 항목은 기본값으로 채운다.

    Raises:
        ValueError: 퍼센트가 음수인 경우. 층이 깊어질수록 적이 약해지면 층 진행이
            난이도가 아니라 보상이 된다.
    """
    mult = int(floor_scale.get("enemy_mult_pct_per_floor", DEFAULT_MULT_PCT_PER_FLOOR))
    if mult < PERCENT_BASE:
        raise ValueError(f"층 스케일 배율은 100 이상이어야 한다: {mult}")
    return FloorScale(mult_pct_per_floor=mult)


def calculate_scaled_stat(base: int, mult_pct_per_floor: int, floor: int) -> int:
    """층 깊이를 복리로 얹은 능력치 (e3).

    **층마다 내림으로 접는다.** `base * mult^(floor-1) / 100^(floor-1)` 을 한 번에
    계산하면 큰 정수가 되고, 부동소수로 하면 두 코어가 마지막 자리에서 갈린다 — 층을
    한 층씩 내려가며 곱하고 접는 것이 TS 와 비트 단위로 같은 유일한 길이다.

    Args:
        base: balance.json 에 적힌 층 1 기준값.
        mult_pct_per_floor: 한 층 내려갈 때마다 곱할 퍼센트 (110 = ×1.1).
        floor: 현재 층.

    Returns:
        내림 정수로 접은 능력치.
    """
    value = base
    for _step in range(max(0, floor - FIRST_FLOOR)):
        value = value * mult_pct_per_floor // PERCENT_BASE
    return value


def get_scaled_enemy_stats(stats: dict, scale: FloorScale, floor: int) -> tuple[int, int]:
    """적 한 종류의 층 스케일된 최대 HP 와 공격력.

    개체를 만드는 모든 자리(방 배치·소환·추격자)가 이 함수를 거쳐야 한다. 한 자리라도
    빠뜨리면 같은 층에 서로 다른 기준의 적이 섞여, 도감이 적은 수치와 실제가 갈린다.

    Args:
        stats: balance.json 의 그 종류 항목.
        scale: 층 스케일 규칙.
        floor: 현재 층.

    Returns:
        (최대 HP, 공격력).
    """
    return (
        calculate_scaled_stat(stats["hp_max"], scale.mult_pct_per_floor, floor),
        calculate_scaled_stat(stats["attack"], scale.mult_pct_per_floor, floor),
    )
