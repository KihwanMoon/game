"""이동 계열 행동 — 어디로 갈 것인가 (TDD §4.1).

`actions.py` 에서 갈라 나왔다. 저쪽은 **때리는 것**이고 여기는 **가는 것**이다. 파일이
§4 의 400줄 상한을 넘은 것이 계기였을 뿐, 가르는 선은 책임이다.

`SupportActionMixin` 과 같은 모양의 믹스인이다 — 엔진이 실행기 하나만 들기 때문에 클래스를
쪼개지 않는다. 둘로 나누면 엔진이 어느 쪽에 넘길지를 알아야 하고, 그 판단이 늘어날 때마다
엔진이 두꺼워진다.
"""

from game.app.core.event_log import EventLog
from game.app.grid.geometry import get_manhattan_distance, iter_neighbors
from game.app.grid.vision import VisionGrid, find_cover_positions
from game.app.pathfinding.distance_field import build_distance_field, find_next_step
from game.app.simulation.plan import (
    DEFERRED_ACTIONS,
    EngineConfig,
    PlannedAction,
)
from game.app.simulation.state import Entity, WorldState
from game.schemas.room import TILE_DOOR, TILE_SPRING, TILE_STAIRS, WALKABLE_TILES

# 타일을 목표로 하는 이동. 행동 id 에서 찾을 타일 갈래로.
TILE_MOVE_TARGETS: dict[str, set[int]] = {
    "MOVE_TO_EXIT": {TILE_DOOR, TILE_STAIRS},
    "MOVE_TO_HEAL": {TILE_SPRING},
}


class MoveActionMixin:
    """이동 계열 행동들. `ActionExecutor` 가 이것을 상속한다.

    아래 넷은 **구체 클래스가 채우는 것**이고, 여기 적어 두는 이유는 그것이 계약이기
    때문이다 — 적지 않으면 이 믹스인이 무엇에 기대는지 알 방법이 없다.
    """

    state: WorldState
    log: EventLog
    config: EngineConfig

    def _record(
        self,
        actor_id: str,
        plan: PlannedAction,
        outcome: str,
        delta: int | None,
        expr: str = "",
    ) -> None:
        """로그 한 줄을 남긴다. 구체 클래스가 구현한다.

        Args:
            actor_id: 행위자 id.
            plan: 실행한 계획.
            outcome: 결과 문구.
            delta: 수치 변화. 없으면 None.
            expr: 왼쪽에 적을 식. 비우면 `행동 @대상` 이다.
        """
        raise NotImplementedError

    def _list_occupied(self, entity: Entity) -> frozenset[tuple[int, int]]:
        """자기 자신을 뺀 다른 엔티티들이 서 있는 칸. 구체 클래스가 구현한다.

        Args:
            entity: 기준 엔티티.

        Returns:
            점유된 좌표들.
        """
        raise NotImplementedError

    def _build_grid(self) -> VisionGrid:
        """시야·경로가 볼 격자. 구체 클래스가 구현한다.

        Returns:
            지금 상태의 격자.
        """
        raise NotImplementedError

    def _find_tiles(self, kinds: set[int]) -> tuple[tuple[int, int], ...]:
        """방에서 해당 종류의 타일 좌표를 모은다.

        Args:
            kinds: 찾을 타일 ID 집합.

        Returns:
            좌표들. 없으면 빈 튜플.
        """
        return tuple(
            (x, y)
            for y in range(self.state.room.height)
            for x in range(self.state.room.width)
            if self.state.get_tile(x, y) in kinds
        )

    def _apply_step(
        self, entity: Entity, goals: tuple[tuple[int, int], ...], plan: PlannedAction
    ) -> None:
        """목표들 쪽으로 한 칸 간다. 막히면 제자리이며 그 틱은 낭비된다 (TDD §4.2).

        Args:
            entity: 이동할 엔티티.
            goals: 목표 좌표들.
            plan: 실행 중인 계획.
        """
        if not goals:
            self._record(entity.entity_id, plan, "목표 없음 — 틱 낭비", None)
            return
        occupied = self._list_occupied(entity)
        field_map = build_distance_field(self.state, goals, blocked=occupied)
        step = find_next_step(field_map, entity.position)
        if step is None:
            self._record(entity.entity_id, plan, "길 막힘 — 틱 낭비", None)
            return
        if step in occupied:
            # 거리장은 목표 칸을 점유 여부와 무관하게 0 으로 깐다(APPROACH 의 목표가
            # 곧 적이 선 칸이므로 그래야 길이 이어진다). 그 마지막 한 걸음까지 허용하면
            # 두 개체가 한 칸에 겹쳐 적거리 0 이 나오고 RETREAT 이 영영 막힌다.
            self._record(entity.entity_id, plan, f"다음 칸 점유 {step} — 제자리", None)
            return
        entity.position = step
        self._record(entity.entity_id, plan, f"이동 {step}", None)

    def record_deferred(self, entity: Entity, plan: PlannedAction) -> None:
        """아직 실행할 수 없는 행동이라는 사실을 로그에 남긴다.

        Args:
            entity: 행위자.
            plan: 실행하려던 계획.
        """
        reason = DEFERRED_ACTIONS.get(plan.action_id, "사유 미상")
        self._record(entity.entity_id, plan, f"미구현 — {reason}", None)

    def apply_move(self, entity: Entity, plan: PlannedAction) -> None:
        """이동 계열 행동을 실행한다.

        Args:
            entity: 이동할 엔티티.
            plan: 실행할 계획.
        """
        if plan.action_id in DEFERRED_ACTIONS:
            self.record_deferred(entity, plan)
            return
        # 타일을 목표로 하는 이동들. 표로 두는 이유는 가지가 늘 때마다 return 이 하나씩
        # 늘어 함수가 상한에 닿기 때문이고, 무엇보다 **셋이 같은 모양**이라 그렇다.
        wanted = TILE_MOVE_TARGETS.get(plan.action_id)
        if wanted is not None:
            self._apply_step(entity, self._find_tiles(wanted), plan)
            return
        if plan.action_id == "MOVE_TO_COVER":
            self._apply_cover_move(entity, plan)
            return

        target = self.state.entities.get(plan.target_id or "")
        if target is None or not target.is_alive:
            self._record(entity.entity_id, plan, "대상 없음 — 틱 낭비", None)
            return
        if plan.action_id == "APPROACH":
            self._apply_step(entity, (target.position,), plan)
            return
        occupied = self._list_occupied(entity)
        here = get_manhattan_distance(entity.position, target.position)
        away = tuple(
            pos
            for pos in iter_neighbors(entity.position)
            if self.state.get_tile(*pos) in WALKABLE_TILES
            and pos not in occupied
            and get_manhattan_distance(pos, target.position) > here
        )
        self._apply_step(entity, away, plan)

    def _apply_cover_move(self, entity: Entity, plan: PlannedAction) -> None:
        """모든 적의 시야에서 벗어나는 칸으로 한 칸 간다 (GDD §4.4).

        목표는 벽 자체가 아니라 **그 뒤에 서면 시야가 끊기는 칸**이다. 벽으로 가면
        등을 붙인 채 그대로 노출된다.

        Args:
            entity: 이동할 엔티티.
            plan: 실행 중인 계획.
        """
        # list_hostiles 는 list_actors 순서라 이미 결정론적이다. 집합으로 만들지 않는다 (R5).
        threats = tuple(other.position for other in self.state.list_hostiles(entity))
        goals = find_cover_positions(self._build_grid(), threats, self._list_occupied(entity))
        if entity.position in goals:
            # 목표 거리가 0 이면 find_next_step 이 None 을 돌려줘 "길 막힘" 으로 찍힌다.
            # 이미 숨어 있는 것과 갈 수 없는 것은 다른 사실이다 (P1).
            self._record(entity.entity_id, plan, "이미 엄폐 중", None)
            return
        self._apply_step(entity, goals, plan)
