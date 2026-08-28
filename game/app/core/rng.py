"""시드 기반 결정론 난수원 (TDD §1.1).

파이썬 표준 `random` 을 쓰지 않는다. 그것은 메르센 트위스터라 Phase 3 의 TypeScript
코어에서 같은 수열을 재현하려면 구현 전체를 옮겨야 하고, 게이트 G3 가 요구하는
"두 코어가 동일 시드에서 완전 동일한 결과"를 사실상 검증 불가능하게 만든다.

대신 SplitMix64 를 쓴다. 상태가 64비트 정수 하나뿐이고 연산이 덧셈·XOR·시프트·곱셈
넷뿐이라, TypeScript 에서 BigInt 로 스무 줄이면 같은 수열이 나온다.

R5(결정론 깨짐) 대응으로 부동소수를 노출하지 않는다. 확률이 필요하면 정수 비교로
표현한다 — 예: 30% 는 `rng.get_below(100) < 30`.
"""

from collections.abc import Sequence
from typing import TypeVar

MASK_64 = (1 << 64) - 1

# SplitMix64 상수. 원 논문(Steele et al., 2014)의 값이며 바꾸면 수열이 달라진다.
GOLDEN_GAMMA = 0x9E3779B97F4A7C15
MIX_MULTIPLIER_A = 0xBF58476D1CE4E5B9
MIX_MULTIPLIER_B = 0x94D049BB133111EB

# FNV-1a 64비트 상수. 파이썬 내장 hash() 는 프로세스마다 시드가 달라져 쓸 수 없다.
FNV_OFFSET_BASIS = 0xCBF29CE484222325
FNV_PRIME = 0x100000001B3

ItemT = TypeVar("ItemT")


def get_label_hash(label: str) -> int:
    """문자열 라벨을 64비트 정수로 접는다.

    파이썬 내장 `hash()` 는 실행마다 시드가 바뀌므로 결정론을 깬다(R5). FNV-1a 는
    명세가 고정되어 있어 TypeScript 에서도 같은 값이 나온다.

    Args:
        label: 서브 시드를 파생시킬 라벨. 예: "floor:2", "node:5".

    Returns:
        64비트 부호 없는 정수.
    """
    digest = FNV_OFFSET_BASIS
    for byte in label.encode("utf-8"):
        digest = ((digest ^ byte) * FNV_PRIME) & MASK_64
    return digest


class DeterministicRng:
    """SplitMix64 난수원. 같은 시드는 반드시 같은 수열을 낸다."""

    def __init__(self, seed: int) -> None:
        """난수원을 시드로 초기화한다.

        Args:
            seed: 시작 시드. 64비트로 잘라서 보관하므로 어떤 정수든 받는다.
        """
        self._seed = seed & MASK_64
        self._state = self._seed

    @property
    def seed(self) -> int:
        """이 난수원을 만든 시드. 리플레이 저장에 쓴다."""
        return self._seed

    def reset(self) -> None:
        """상태를 시드 직후로 되돌린다. 같은 수열이 처음부터 다시 나온다."""
        self._state = self._seed

    def get_uint64(self) -> int:
        """다음 64비트 난수를 뽑는다.

        Returns:
            0 이상 2**64 미만의 정수.
        """
        self._state = (self._state + GOLDEN_GAMMA) & MASK_64
        mixed = self._state
        mixed = ((mixed ^ (mixed >> 30)) * MIX_MULTIPLIER_A) & MASK_64
        mixed = ((mixed ^ (mixed >> 27)) * MIX_MULTIPLIER_B) & MASK_64
        return mixed ^ (mixed >> 31)

    def get_below(self, bound: int) -> int:
        """0 이상 bound 미만의 정수를 균등하게 뽑는다.

        나머지 연산(`% bound`)을 쓰지 않는다. 그것은 bound 가 2의 거듭제곱이 아닐 때
        작은 값 쪽으로 치우치며, 밸런싱을 데이터로 하는 이 프로젝트에서 그 편향은
        그대로 수치 왜곡이 된다. 대신 비트마스크 후 범위 밖을 버리는 방식을 쓴다.

        Args:
            bound: 상한(미포함). 1 이상이어야 한다.

        Returns:
            0 이상 bound 미만의 정수.

        Raises:
            ValueError: bound 가 1 미만인 경우.
        """
        if bound < 1:
            raise ValueError(f"bound 는 1 이상이어야 한다: {bound}")
        mask = (1 << bound.bit_length()) - 1
        while True:
            candidate = self.get_uint64() & mask
            if candidate < bound:
                return candidate

    def get_range(self, low: int, high: int) -> int:
        """low 이상 high 이하의 정수를 균등하게 뽑는다.

        Args:
            low: 하한(포함).
            high: 상한(포함).

        Returns:
            low 이상 high 이하의 정수.

        Raises:
            ValueError: high 가 low 보다 작은 경우.
        """
        if high < low:
            raise ValueError(f"high 가 low 보다 작다: low={low}, high={high}")
        return low + self.get_below(high - low + 1)

    def get_choice(self, items: Sequence[ItemT]) -> ItemT:
        """시퀀스에서 원소 하나를 균등하게 고른다.

        집합(set)이나 딕셔너리 키를 그대로 넘기지 않는다 — 순회 순서가 보장되지 않아
        결정론이 깨진다(R5). 정렬된 시퀀스로 바꿔서 넘긴다.

        Args:
            items: 고를 대상. 비어 있으면 안 된다.

        Returns:
            고른 원소.

        Raises:
            ValueError: items 가 비어 있는 경우.
        """
        if not items:
            raise ValueError("빈 시퀀스에서는 고를 수 없다")
        return items[self.get_below(len(items))]

    def create_stream(self, label: str) -> "DeterministicRng":
        """라벨로 갈라진 독립 난수원을 만든다.

        층·방·전리품처럼 서로 다른 축의 무작위성이 한 수열을 공유하면, 한쪽 호출 횟수가
        바뀔 때 다른 쪽 결과까지 흔들려 회귀 검증이 불가능해진다. TDD §7.3 이 요구하는
        `seed + floor_index + node_id` 결합이 이것이다.

        Args:
            label: 축을 구분하는 라벨. 예: "floor:2/node:5/loot".

        Returns:
            독립적으로 진행하는 새 난수원. 이 난수원의 상태는 바뀌지 않는다.
        """
        return DeterministicRng(self._seed ^ get_label_hash(label))
