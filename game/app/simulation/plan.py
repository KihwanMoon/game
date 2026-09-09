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
from game.app.skills.catalog import SkillDef

# 페이즈·판정 이름은 phases.py 가 정본이다. 여기서 다시 내보내는 것은 엔진 쪽
# 호출자가 계획 타입과 페이즈 이름을 한 곳에서 받게 하기 위한 것이다.
__all__ = [
    "OUTCOME_ONGOING",
    "OUTCOME_PLAYER_LOSS",
    "ATTACK_ACTIONS",
    "MELEE_REACH",
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

# 둔화. **이동이 두 틱에 한 칸이 된다** (GDD §211 의 「이동 2틱 소모」).
STATUS_SLOW = "SLOW"

# 둔화 중 몇 틱마다 한 칸 움직이는가. 2 면 절반 속도다.
SLOW_EVERY = 2

# 방어 감소율과 유지 틱을 읽을 스킬 id. 지금 GUARD 계열이 하나뿐이라 상수로 둔다 —
# 늘어나면 스킬 정의에서 읽어야 한다. 보호 주문서(v6)도 같은 값을 쓴다: 방패와 같은
# 상태라 규칙표를 짜는 사람이 새 개념을 배우지 않아도 된다.
GUARD_SKILL_ID = "GUARD_BRACE"

# 스킬을 정체로 가리키는 행동 (블록 v5, 결정 #04).
USE_SKILL_ACTION = "USE_SKILL"

# 소모품 사용 (v6, #54). 파라미터는 카탈로그 id 가 아니라 태그다 — 물약을 여러 등급으로
# 늘려도 규칙표가 가리키는 것이 그대로여야 한다.
USE_ITEM_ACTION = "USE_ITEM"

# 공격으로 치는 행동들. **규칙 평가와 실행이 같은 목록을 봐야 한다** — 갈리면 규칙은
# 「불가」로 막았는데 실행은 때리거나, 그 반대가 된다.
ATTACK_ACTIONS = frozenset({"ATTACK", "SKILL_1", "SKILL_2"})

# 근접 사거리. 이보다 멀리 닿는 공격만 직선 시야를 묻는다 — 인접한 칸에 시야를 묻는 것은
# 뜻이 없고, 물으면 벽 모서리에서 근접 공격이 안 나간다.
MELEE_REACH = 1


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
    # `USE_ITEM[kind]` 가 가리키는 소모품 태그 (v6, #54). 스킬과 같은 한 겹의 지시다.
    item_kind: str | None = None
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
    # 스킬 id -> 정의. **예전에는 속성마다 표가 따로였다** — 계수·사거리·쿨타임·
    # 회복률·감쇠율·감쇠틱 여섯이다. 속성을 하나 더할 때마다 표가 늘었고, 무엇보다
    # 표끼리 어긋날 수 있었다: 계수 표에만 있고 쿨타임 표에 없는 스킬은 「쿨타임 0」
    # 으로 조용히 돌았다. 레코드 하나면 그 어긋남이 성립하지 않는다 (설계/5_스킬 §9).
    skills: dict[str, SkillDef] = field(default_factory=dict)
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
