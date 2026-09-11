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
    "DEFERRED_ACTIONS",
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

# 틱을 안 쓰는 스킬들. **규칙표에서는 한 줄을 차지하지만 그 틱의 행동은 아니다** —
# 켜 두면 다음 피격에 저절로 발동하고, 그 사이에도 개체는 제 할 일을 한다.
#
# 데이터가 아니라 여기 상수인 이유: 「자리를 안 먹는다」는 밸런스 값이 아니라 규칙이다.
# 데이터로 두면 다음 사람이 공격 스킬에 켜 볼 수 있고, 그러면 한 틱에 둘을 때린다.
FREE_SKILLS: frozenset[str] = frozenset({GUARD_SKILL_ID})

# 틱을 안 쓰는 소모품들 (2026-09-11 실측). **같은 기제면 같은 규칙이다** — 보호 주문서는
# 방벽과 똑같은 `GUARD` 상태를 똑같은 값으로 거는데, 한쪽만 틱을 내면 세계에 규칙이
# 둘이 된다. 실측도 같은 말을 했다: 층 배치 80런에서 보호 주문서를 쓰는 규칙표가
# 기준(57%)보다 **낮은** 47% 였다 — 켜는 데 낸 한 틱이 2틱 50% 보다 컸다.
#
# **즉발 주문서는 여기 없다.** 순간이동·화염은 그 자체가 행동이라 틱을 낸다. 공짜가
# 되는 것은 「켜 두고 다음 피격을 기다리는」 것뿐이다.
#
# 충전이라는 대가는 그대로다. 스킬은 쿨타임만 내지만 주문서는 **장수가 준다.**
FREE_ITEMS: frozenset[str] = frozenset({"SCROLL"})

# 아직 만들 수 없는 행동과 그 사유. 조용히 무시하지 않고 로그로 알린다.
# **W6 통합으로 비었다.** 목록과 `record_deferred` 를 남겨 두는 것은 규칙표가 부를 수는
# 있으나 실행할 수 없는 행동이 다시 생길 때를 위해서다. 도감도 이 표를 읽어 경고한다.
#
# **실행기가 아니라 여기 있다** (2026-09-11). 이동이 `movement.py` 로 갈라지면서 실행기
# 두 곳이 같은 표를 봐야 했다 — 계획이 가리킬 수 있는 행동의 목록이므로 자리는 이쪽이다.
DEFERRED_ACTIONS: dict[str, str] = {}

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
    # **자리를 안 먹는 행동들** (2026-09-10 결정). 규칙표는 켜고 끄는 것만 정하고 틱을
    # 안 쓴다 — 방벽이 그 첫 자리다.
    #
    # 실측이 이유다. 한 틱을 통째로 내고 2틱 50% 를 사는데, 그 틱에 때렸으면 들어갔을
    # 공격이 더 컸다 — 5칸 예산에서 46% → 35% 였고, 여유칸이 생겨도 본전이었다
    # (설계/5_스킬 §2.1). 값을 올리는 대신 **자리값을 없앤다.**
    free_skills: tuple[str, ...] = ()
    # 자리를 안 먹는 소모품들 (`plan.FREE_ITEMS`). 스킬 쪽과 가른 이유는 실행기가
    # 다르기 때문이다 — 이쪽은 충전을 태우고 저쪽은 쿨타임을 건다.
    free_items: tuple[str, ...] = ()
    # **규칙표가 직접 다루는 소모품 태그들** (2026-09-11). 조건 발동이 이 목록을 비껴
    # 간다 — 내가 적은 줄이 기본보다 세다. 안 그러면 자동이 먼저 태워서 「내 규칙이 영영
    # 안 뜬다」가 되고, 그것은 P1 을 가장 직접적으로 깨는 모양이다.
    managed_items: tuple[str, ...] = ()


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
