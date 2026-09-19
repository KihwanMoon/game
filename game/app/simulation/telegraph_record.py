"""예고 한 건이 들고 있는 값.

**판과 효과가 함께 읽으므로 따로 둔다.** `telegraph.py`(언제 터지는가)와
`telegraph_effects.py`(터졌을 때 무엇이 남는가)가 서로를 안 부르게 하는 자리다 —
`GearItem` 을 저울과 관문 사이에서 뺀 것과 같은 이유다.
"""

from dataclasses import dataclass

from game.app.skills.catalog import CAST_FREE, SkillEffect

# 기본 인지 폭. 남은 틱이 이 값 이하일 때만 인지 변수가 참이 된다.
VISIBLE_TICKS = 1


@dataclass
class Telegraph:
    """예고 한 건. 남은 틱이 0 이 되는 틱에 발동한다."""

    telegraph_id: str
    caster_id: str
    skill_id: str
    # 정렬된 좌표다. 집합으로 들고 있으면 발동 로그의 순서가 흔들린다 (R5).
    tiles: tuple[tuple[int, int], ...]
    remaining_ticks: int
    damage: int
    # 남은 틱이 이 값 이하일 때부터 인지 변수에 잡힌다. lead_ticks 와 같게 두면
    # 등록 순간부터 전 구간이 보인다 (GDD §4.2 의 "N틱 전에 표시").
    visible_ticks: int = VISIBLE_TICKS
    # 시전자를 먼저 죽이는 것이 예고에 대한 또 하나의 답이다. 보스의 확정
    # 광역기처럼 그 답을 막아야 하는 예고만 False 로 등록한다.
    cancel_on_death: bool = True
    # 시전 중 다른 행동을 어떻게 할 것인가 (설계/5_스킬 §10.3).
    #
    # **여기 기본이 `FREE` 인 것이 중요하다.** 스킬 데이터의 기본은 잠금이지만, 이 레코드는
    # 스킬을 안 거치는 예고도 받는다 — 자폭형 몬스터의 절에는 이 키가 아예 없다. 거기에
    # 잠금을 걸면 폭탄이 다음 틱에 못 움직여 콘텐츠의 뜻이 통째로 바뀐다. **모르면 지금
    # 하던 대로 둔다.**
    cast_act: str = CAST_FREE
    # 시전자가 **맞으면** 취소되는가. 위와 같은 이유로 기본이 False 다.
    cancel_on_hit: bool = False
    # 맞은 대상에게 얹을 것들 (설계/5_스킬 §1). **피해와 별개다** — 피해 0 인 장판이
    # 상태만 거는 것이 이 자리다. 정렬된 튜플이라 순회 순서가 안 흔들린다 (R5).
    effects: tuple[SkillEffect, ...] = ()

    def has_tile(self, position: tuple[int, int]) -> bool:
        """그 좌표가 피격 예정 타일인가.

        Args:
            position: 확인할 좌표.

        Returns:
            피격 예정이면 True.
        """
        return position in self.tiles

    def is_visible_within(self, foresight_ticks: int) -> bool:
        """지금 인지 가능한가.

        Args:
            foresight_ticks: 예측 회로가 넓혀 주는 인지 폭.

        Returns:
            남은 틱이 인지 폭 안이면 True.
        """
        return self.remaining_ticks <= self.visible_ticks + foresight_ticks
