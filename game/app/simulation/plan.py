"""틱 진행의 공용 타입 — 계획, 설정, 페이즈 이름.

엔진과 행동 실행기가 함께 쓰는 것만 둔다. 한쪽에 두면 다른 쪽이 그것을 import 하면서
순환 참조가 생긴다.
"""

from dataclasses import dataclass, field, replace
from typing import Protocol

from game.app.combat.damage import DamageRules
from game.app.simulation.perception import PerceptionSnapshot
from game.app.simulation.phases import (
    OUTCOME_ONGOING,
    OUTCOME_PLAYER_LOSS,
    OUTCOME_PLAYER_WIN,
    OUTCOME_TIMEOUT,
    PHASE_ACT,
    PHASE_CLEANUP,
    PHASE_DECIDE,
    PHASE_ORDER,
    PHASE_PERCEPTION,
    PHASE_RESOLVE,
    PHASE_TELEGRAPH,
    PHASE_UPKEEP,
)
from game.app.simulation.scaling import FloorScale
from game.app.simulation.state import Entity, WorldState

# 페이즈·판정 이름은 phases.py 가 정본이다. 여기서 다시 내보내는 것은 엔진 쪽
# 호출자가 계획 타입과 페이즈 이름을 한 곳에서 받게 하기 위한 것이다.
__all__ = [
    "OUTCOME_ONGOING",
    "OUTCOME_PLAYER_LOSS",
    "OUTCOME_PLAYER_WIN",
    "OUTCOME_TIMEOUT",
    "PHASE_ACT",
    "PHASE_CLEANUP",
    "PHASE_DECIDE",
    "PHASE_ORDER",
    "PHASE_PERCEPTION",
    "PHASE_RESOLVE",
    "PHASE_TELEGRAPH",
    "PHASE_UPKEEP",
    "DecisionPolicy",
    "EngineConfig",
    "PlannedAction",
    "PolicyFactory",
]


# 규칙 상태 네 번째 (블록 v5, 결정 #04). 참·발동 / 참·미발동 / 거짓 / **불가**.
# 거짓과 다르다 — 조건은 참인데 실행할 수단이 없다.
OUTCOME_BLOCKED = "불가"

# 방어 태세 상태 이름 (블록 v5). statuses 에 남은 틱 수로 들어가며, UPKEEP 이 줄인다.
STATUS_GUARD = "GUARD"

# 스킬을 정체로 가리키는 행동 (블록 v5, 결정 #04).
USE_SKILL_ACTION = "USE_SKILL"


@dataclass(frozen=True)
class BlockedRule:
    """조건은 참이었으나 실행할 수단이 없어 건너뛴 규칙 하나."""

    rule_index: int
    expr: str
    reason: str


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
    # 실행할 스킬 (블록 v5). USE_SKILL 이 아니면 None 이다.
    skill_id: str | None = None
    # 조건은 참인데 수단이 없어 건너뛴 규칙들 (블록 v5, 결정 #04).
    #
    # **거짓과 다르다.** 거짓은 "조건이 안 맞았다", 불가는 "조건은 맞는데 스킬이 없다" 이고
    # 플레이어가 고쳐야 할 곳이 완전히 다르다 — 앞은 조건을, 뒤는 장비를 본다. 구분하지
    # 않으면 P1(실패는 정보다)이 깨진다.
    blocked: tuple[BlockedRule, ...] = ()


class DecisionPolicy(Protocol):
    """행동 결정기. RuleVM 과 폴백 정책이 이 모양을 만족한다."""

    def plan_action(
        self, entity: Entity, snapshot: PerceptionSnapshot, state: WorldState
    ) -> PlannedAction:
        """이번 틱의 행동을 정한다. 부작용을 내지 않는다."""
        ...


class PolicyFactory(Protocol):
    """전투 도중 등장한 엔티티에 규칙표를 붙이는 것.

    소환물과 추격자는 방을 세운 뒤에 생기므로 조립 시점의 일괄 배정이 닿지 않는다.
    붙이지 않으면 그들만 폴백 정책(접근만 하고 공격하지 않음)으로 싸워, 도감이
    보여주는 규칙표와 실제 행동이 갈린다 (GDD §5).
    """

    def build_policy(self, entity: Entity) -> DecisionPolicy | None:
        """그 엔티티에 맞는 결정기를 만든다. 규칙표가 없으면 None."""
        ...


@dataclass(frozen=True)
class EngineConfig:
    """엔진이 balance.json 에서 받아 쓰는 값들."""

    damage_rules: DamageRules
    kind_types: dict[str, str]
    skill_coef_pct: dict[str, int]
    # 스킬이 자체 사거리를 가지면 그것을 쓴다. None 이면 엔티티의 attack_range 다.
    # 이것이 없으면 balance.json 이 선언한 사거리가 조용히 무시되어, 원거리 스킬을
    # 전제한 규칙표(GDD §3.5 카이팅)가 매 틱 '사거리 밖'으로 헛돈다.
    skill_range: dict[str, int | None]
    # 스킬 id -> 사용 후 걸리는 쿨타임(틱). ACT 가 성공한 행동에만 걸고 UPKEEP 이
    # 매 틱 1씩 깎는다. 이것이 비어 있으면 `내 쿨타임[스킬] 완료` 가 영구히 참이 되어
    # 그 항을 쓴 규칙이 사실상 한 항 짧아진다 — 조용히 틀리는 조건이 된다.
    skill_cooldowns: dict[str, int] = field(default_factory=dict)
    # 행동 id -> 회복량. 대상 최대 HP 의 정수 퍼센트다 (블록 목록 v4 의 HEAL).
    # 고정값이 아니라 비율인 이유는 회복이 대상의 덩치에 비례해야 하기 때문이고,
    # 퍼센트 정수인 이유는 R5 다 — 부동소수를 쓰면 플랫폼마다 결과가 갈린다.
    skill_heal_pct: dict[str, int] = field(default_factory=dict)
    # GUARD 계열 (블록 v5, 결정 #16). 받는 피해를 몇 % 줄이고 몇 틱 유지하는가.
    skill_guard_pct: dict[str, int] = field(default_factory=dict)
    skill_guard_ticks: dict[str, int] = field(default_factory=dict)
    # kind_id -> 소환 규칙(주기·상한·소환물). 블록 목록 v3 이 SUMMON 을 행동으로
    # 올린 뒤로 '언제 소환하는가' 는 규칙표가 정한다 — 여기 남는 것은 '무엇을 몇 마리
    # 까지' 와, 쿨타임[SUMMON] 의 초기값이 되는 주기(every_ticks)다.
    summon_rules: dict[str, dict] = field(default_factory=dict)
    enemy_stats: dict[str, dict] = field(default_factory=dict)
    # 층 깊이 스케일. 개체를 만드는 자리(방 배치·소환·추격자)가 전부 이것을 거쳐야
    # 같은 층에 다른 기준의 적이 섞이지 않는다 (scaling.get_scaled_enemy_stats).
    floor_scale: FloorScale = field(default_factory=FloorScale)
    floor: int = 1
    max_ticks: int = 400
    combat_regen_pct: int = 50


def resolve_skill_plan(plan: PlannedAction) -> PlannedAction:
    """`USE_SKILL` 계획을 그 스킬의 계획으로 바꾼다.

    v5 의 `USE_SKILL[id]` 는 한 겹의 지시다. 실행 직전에 풀어 주면 실행기는 예전 행동
    이름만 알면 되고, 스킬이 늘어도 실행기가 늘지 않는다.

    Args:
        plan: 실행할 계획.

    Returns:
        `USE_SKILL` 이면 skill_id 로 바꾼 계획, 아니면 그대로.
    """
    if plan.action_id != USE_SKILL_ACTION or plan.skill_id is None:
        return plan
    return replace(plan, action_id=plan.skill_id)
