"""규칙표가 없을 때 쓰는 기본 행동 결정기.

W2 에서 RuleVM 이 DecisionPolicy 자리에 들어오면 이 모듈은 그 폴백이 된다.

TDD §5.2 가 정의한 DEFAULT 는 "가장 가까운 적에게 접근" 하나뿐이다. 그것만으로는
인접한 뒤 더 다가갈 곳이 없어 아무도 죽지 않으므로, 여기서는 사거리 안이면 공격하는
한 줄을 더 둔다. RuleVM 의 DEFAULT 는 TDD 대로 접근만 한다 — 둘은 다른 것이다.
"""

from dataclasses import dataclass

from game.app.grid.geometry import get_manhattan_distance
from game.app.simulation.engine import PlannedAction
from game.app.simulation.perception import PerceptionSnapshot
from game.app.simulation.state import Entity, WorldState

LOW_HP_PERCENT = 30


@dataclass(frozen=True)
class FallbackPolicy:
    """붙어서 때리고, HP 가 낮으면 포션을 쓴다."""

    def plan_action(
        self, entity: Entity, snapshot: PerceptionSnapshot, state: WorldState
    ) -> PlannedAction:
        """이번 틱의 행동을 정한다. 부작용을 내지 않는다.

        Args:
            entity: 결정 대상.
            snapshot: PERCEPTION 이 고정한 값들.
            state: 세계 상태. 읽기만 한다.

        Returns:
            실행할 계획.
        """
        hp_percent = snapshot.read("self_hp_percent")
        if entity.potions > 0 and isinstance(hp_percent, int) and hp_percent < LOW_HP_PERCENT:
            return PlannedAction(
                entity_id=entity.entity_id,
                action_id="USE_POTION",
                expr=f"HP%({hp_percent}) < {LOW_HP_PERCENT}",
            )

        hostiles = state.list_hostiles(entity)
        if not hostiles:
            return PlannedAction(entity_id=entity.entity_id, action_id="HOLD", expr="적 없음")

        nearest = min(
            hostiles,
            key=lambda other: (
                get_manhattan_distance(entity.position, other.position),
                other.entity_id,
            ),
        )
        distance = get_manhattan_distance(entity.position, nearest.position)
        in_range = distance <= entity.attack_range
        comparison = "<=" if in_range else ">"
        return PlannedAction(
            entity_id=entity.entity_id,
            action_id="ATTACK" if in_range else "APPROACH",
            target_id=nearest.entity_id,
            expr=f"적거리({distance}) {comparison} 사거리({entity.attack_range})",
        )
