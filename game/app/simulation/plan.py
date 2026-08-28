"""틱 진행의 공용 타입 — 계획, 설정, 페이즈 이름.

엔진과 행동 실행기가 함께 쓰는 것만 둔다. 한쪽에 두면 다른 쪽이 그것을 import 하면서
순환 참조가 생긴다.
"""

from dataclasses import dataclass
from typing import Protocol

from game.app.combat.damage import DamageRules
from game.app.simulation.perception import PerceptionSnapshot
from game.app.simulation.state import Entity, WorldState

PHASE_UPKEEP = "UPKEEP"
PHASE_TELEGRAPH = "TELEGRAPH"
PHASE_PERCEPTION = "PERCEPTION"
PHASE_DECIDE = "DECIDE"
PHASE_ACT = "ACT"
PHASE_RESOLVE = "RESOLVE"
PHASE_CLEANUP = "CLEANUP"

PHASE_ORDER = (
    PHASE_UPKEEP,
    PHASE_TELEGRAPH,
    PHASE_PERCEPTION,
    PHASE_DECIDE,
    PHASE_ACT,
    PHASE_RESOLVE,
    PHASE_CLEANUP,
)

OUTCOME_ONGOING = "ONGOING"
OUTCOME_PLAYER_WIN = "PLAYER_WIN"
OUTCOME_PLAYER_LOSS = "PLAYER_LOSS"
OUTCOME_TIMEOUT = "TIMEOUT"


@dataclass(frozen=True)
class PlannedAction:
    """DECIDE 가 내놓는 계획. 아직 세계를 바꾸지 않았다."""

    entity_id: str
    action_id: str
    target_id: str | None = None
    rule_index: int | None = None
    expr: str = ""
    # 플래그 기록은 상태 변경이므로 DECIDE 가 아니라 ACT 에서 적용한다 (TDD §5.2).
    set_flag: str | None = None


class DecisionPolicy(Protocol):
    """행동 결정기. RuleVM 과 폴백 정책이 이 모양을 만족한다."""

    def plan_action(
        self, entity: Entity, snapshot: PerceptionSnapshot, state: WorldState
    ) -> PlannedAction:
        """이번 틱의 행동을 정한다. 부작용을 내지 않는다."""
        ...


@dataclass(frozen=True)
class EngineConfig:
    """엔진이 balance.json 에서 받아 쓰는 값들."""

    damage_rules: DamageRules
    kind_types: dict[str, str]
    skill_coef_pct: dict[str, int]
    floor: int = 1
    max_ticks: int = 400
    combat_regen_pct: int = 50
