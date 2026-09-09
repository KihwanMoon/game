"""저울과 관문이 함께 읽는 장비 절.

**두 모듈이 이것을 쓰므로 따로 둔다.** `upgrade.py`(무엇이 더 센가)와
`gear_guards.py`(무엇을 잃으면 안 되는가)가 서로를 안 부르게 하는 자리다.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GearItem:
    """값을 매길 장비 하나."""

    item_id: int
    slot: str
    can_equip: bool
    is_broken: bool
    hands: str
    affixes: tuple[tuple[str, int, int], ...]
    attack_range: int
    # 이 장비가 여는 스킬. **점수에 안 들어간다** — 스킬은 무게로 견줄 값이 아니라
    # 「잃으면 규칙표가 죽는다」는 조건이다 (`check_keeps_skill`).
    grants_skill: str = ""
