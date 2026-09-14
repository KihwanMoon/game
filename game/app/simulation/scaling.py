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

DEFAULT_MULT_PCT_PER_FLOOR = 120

# 층 번호의 시작값(FIRST_FLOOR)은 schemas.room 이 정본이다 — min_floor 의 기본값과
# 같은 값이어야 하므로 여기서 다시 적지 않는다. 층 1 의 보너스는 0 이다.

PERCENT_BASE = 100


@dataclass(frozen=True)
class FloorScale:
    """개체를 만들 때 스탯에 얹는 것들. 대부분은 balance.json 의 floor_scale 절이다."""

    mult_pct_per_floor: int = DEFAULT_MULT_PCT_PER_FLOOR
    # 선공에 더할 값. **층이 아니라 플레이어를 따라간다** — 파일에서 오지 않고 판을
    # 짤 때 계산된다 (`services/run_battle.build_engine`). 여기 얹어 두는 이유는 개체를
    # 만드는 세 자리가 이미 이 값을 들고 다니기 때문이고, 따로 실어 나르면 언젠가 한
    # 자리가 빠진다 — 그러면 같은 방에 기준이 다른 적이 섞인다.
    initiative_shift: int = 0


def build_floor_scale(floor_scale: dict, initiative_shift: int = 0) -> FloorScale:
    """floor_scale 절을 규칙 값으로 옮긴다.

    Args:
        floor_scale: balance.json 의 floor_scale 딕셔너리.
        initiative_shift: 적 선공에 더할 값. 플레이어가 기준값에서 얼마나 자랐는가다.

    Returns:
        읽어들인 규칙. 빠진 항목은 기본값으로 채운다.

    Raises:
        ValueError: 퍼센트가 음수인 경우. 층이 깊어질수록 적이 약해지면 층 진행이
            난이도가 아니라 보상이 된다.
    """
    mult = int(floor_scale.get("enemy_mult_pct_per_floor", DEFAULT_MULT_PCT_PER_FLOOR))
    if mult < PERCENT_BASE:
        raise ValueError(f"층 스케일 배율은 100 이상이어야 한다: {mult}")
    return FloorScale(mult_pct_per_floor=mult, initiative_shift=initiative_shift)


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


def get_scaled_enemy_stats(stats: dict, scale: FloorScale, floor: int) -> tuple[int, int, int]:
    """적 한 종류의 조정된 최대 HP · 공격력 · 선공.

    개체를 만드는 모든 자리(방 배치·소환·추격자)가 이 함수를 거쳐야 한다. 한 자리라도
    빠뜨리면 같은 층에 서로 다른 기준의 적이 섞여, 도감이 적은 수치와 실제가 갈린다.
    **선공을 여기에 함께 둔 것도 그래서다** — 따로 두면 세 자리 중 하나가 빠진다.

    Args:
        stats: balance.json 의 그 종류 항목.
        scale: 층 스케일 규칙.
        floor: 현재 층.

    Returns:
        (최대 HP, 공격력, 선공).
    """
    return (
        calculate_scaled_stat(stats["hp_max"], scale.mult_pct_per_floor, floor),
        calculate_scaled_stat(stats["attack"], scale.mult_pct_per_floor, floor),
        get_shifted_initiative(stats["initiative"], scale),
    )


def get_shifted_initiative(base: int, scale: FloorScale) -> int:
    """플레이어를 따라 옮긴 선공 (2026-09-14).

    **선공은 절대값이 아니라 밴드다.** 적 선공은 20~78 로 고정인데 플레이어 선공은
    `50 + 2×민첩` 으로 한계 없이 자란다. 그래서 민첩을 올린 캐릭터에게는 5층부터 모든
    적이 느려지고, 레벨 20 을 넘기면 전 층에서 그렇게 된다 (실측: 붙은 틱 30번 중
    「나보다 빠른 적」 0번). 그 상태에서 `적 선공 > 내 선공` 은 **영영 거짓인 항**이고,
    그것을 읽는 규칙은 cpu 만 먹는다.

    옮기면 밴드가 보존된다 — 돌미륵은 늘 나보다 30 느리고 주린 이리는 늘 28 빠르다.
    **민첩이 선공 순서를 사지는 못하게 된다**(방어는 그대로 산다). 그 대가로 축이
    레벨·빌드와 무관하게 살아 있다 (실측: 죽은 층 10 → 1).

    Args:
        base: balance.json 에 적힌 그 종류의 선공.
        scale: 옮길 양을 담은 규칙.

    Returns:
        옮긴 선공. **0 아래로는 안 내려간다** — 음수 선공은 정렬에서만 뜻이 있고
        화면에서는 읽을 수 없는 수다.
    """
    return max(0, base + scale.initiative_shift)
