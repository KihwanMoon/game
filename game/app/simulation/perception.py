"""인지 스냅샷 — PERCEPTION 페이즈가 만들고 DECIDE 가 읽는다 (TDD §4.1, §5.4).

**틱당 한 번만 만들고 그 틱의 모든 규칙이 공유한다.** 규칙마다 다시 재면 같은 틱 안에서
값이 달라져 "동시에 같은 세계를 본다"는 전제가 깨진다.

로드맵 기준으로 아직 만들 수 없는 값이 있다. LOS·엄폐·텔레그래프는 Phase 2 W6 산출물
이고, CPU 여유는 RuleVM(W2)이 규칙표를 컴파일해야 나온다. 그 블록들은 스냅샷에 넣지
않으며, 읽으려 하면 None 이 나와 호출자가 그 사실을 알 수 있다 — 0 이나 False 로
채우면 "값이 없다"와 "값이 0이다"가 구분되지 않는다 (§7.1 이 경고한 오판).
"""

from dataclasses import dataclass

from game.app.grid.geometry import get_manhattan_distance, iter_neighbors
from game.app.simulation.selectors import ALL_SELECTORS, resolve_target
from game.app.simulation.state import Entity, WorldState
from game.schemas.room import TILE_DOOR, TILE_SPRING, TILE_STAIRS, WALKABLE_TILES

# 인지 변수 nearest_tile_distance 의 인자에서 타일 ID 로.
TILE_BY_NAME = {"DOOR": TILE_DOOR, "STAIRS": TILE_STAIRS, "SPRING": TILE_SPRING}

# W1 시점에 아직 값을 만들 수 없는 블록. 비어 있는 이유를 코드가 알고 있어야
# 나중에 "왜 안 되지"를 다시 조사하지 않는다.
DEFERRED_BLOCKS = {
    "self_exposed_to_los": "Phase 2 W6 — LOS 가시성 맵",
    "cover_wall_distance": "Phase 2 W6 — 엄폐 판정",
    "self_on_hazard_telegraph": "Phase 2 W6 — 텔레그래프",
    "target_is_casting": "Phase 2 W6 — 텔레그래프",
    # 아래 둘은 스냅샷이 아니라 RuleVM 이 답한다. 대상 계열은 규칙마다 셀렉터가 다르고,
    # CPU 여유는 규칙표를 알아야 계산된다. 미구현이 아니라 소유자가 다른 것이다.
}


@dataclass(frozen=True)
class PerceptionSnapshot:
    """한 엔티티가 이번 틱에 본 세계. 만들어진 뒤 바뀌지 않는다."""

    entity_id: str
    tick: int
    values: dict[str, int | bool]

    def read(self, block_id: str, param: str | None = None) -> int | bool | None:
        """인지 변수 값을 읽는다.

        Args:
            block_id: 인지 변수 id.
            param: 인자를 받는 블록의 인자. 예: 쿨타임의 스킬 id.

        Returns:
            값. 아직 구현되지 않은 블록이면 None.
        """
        return self.values.get(block_id if param is None else f"{block_id}[{param}]")


def _count_open_neighbors(state: WorldState, entity: Entity) -> int:
    """주변 8칸 중 이동 가능한 칸 수를 센다 (포위도).

    이동은 4방향이지만 포위 판정은 8칸이다 — 근접 적이 인접 8칸을 점유하기 때문이다
    (GDD §4.3). 두 기준이 다른 것은 의도된 것이다.

    Args:
        state: 세계 상태.
        entity: 기준 엔티티.

    Returns:
        0 이상 8 이하의 칸 수.
    """
    occupied = {other.position for other in state.list_actors() if other is not entity}
    return sum(
        1
        for pos in iter_neighbors(entity.position)
        if state.get_tile(*pos) in WALKABLE_TILES and pos not in occupied
    )


def _get_nearest_tile_distance(state: WorldState, entity: Entity, kinds: set[int]) -> int:
    """지정한 타일 종류 중 가장 가까운 것까지의 거리.

    Args:
        state: 세계 상태.
        entity: 기준 엔티티.
        kinds: 찾을 타일 ID 집합.

    Returns:
        맨해튼 거리. 방에 하나도 없으면 -1.
    """
    distances = [
        get_manhattan_distance(entity.position, (x, y))
        for y in range(state.room.height)
        for x in range(state.room.width)
        if state.get_tile(x, y) in kinds
    ]
    return min(distances) if distances else -1


def build_snapshot(
    state: WorldState, entity: Entity, kind_types: dict[str, str]
) -> PerceptionSnapshot:
    """한 엔티티의 인지 변수를 이번 틱 값으로 고정한다.

    Args:
        state: 세계 상태.
        entity: 대상 엔티티.
        kind_types: 엔티티 종류 id 에서 적 유형(MELEE 등)으로의 대응표.

    Returns:
        읽기 전용 스냅샷.
    """
    hostiles = state.list_hostiles(entity)

    values: dict[str, int | bool] = {
        "self_hp_percent": entity.hp_percent,
        "self_potion_count": entity.potions,
        "self_on_heal_tile": state.get_tile(*entity.position) == TILE_SPRING,
        # LOS 를 아직 못 보므로 시야 = 방 전체다. W6 에서 가시성 맵으로 좁힌다.
        "visible_enemy_count": len(hostiles),
        "open_neighbor_count": _count_open_neighbors(state, entity),
        "room_elapsed_ticks": state.tick,
    }

    # 셀렉터별 대상 거리 (블록 목록 v2, F-1 잔여 해결). 규칙이 자기 TARGET 과 무관하게
    # 물을 수 있어야 하므로 스냅샷에서 7개를 모두 미리 푼다 — 틱당 1회 원칙은 지켜진다.
    for selector_id in ALL_SELECTORS:
        picked = resolve_target(selector_id, entity, state, kind_types)
        values[f"target_distance[{selector_id}]"] = (
            get_manhattan_distance(entity.position, picked.position) if picked else -1
        )

    # 타일 종류별 최단 거리 (v2, F-3). 회복타일이 방에 있는지 물을 수 있어야
    # MOVE_TO_HEAL 이 헛돌지 않는다.
    for tile_name, tile_id in TILE_BY_NAME.items():
        values[f"nearest_tile_distance[{tile_name}]"] = _get_nearest_tile_distance(
            state, entity, {tile_id}
        )

    present_types = {kind_types.get(other.kind_id, "") for other in hostiles}
    for enemy_type in ("MELEE", "RANGED", "SUMMONER", "BOMBER"):
        values[f"enemy_type_present[{enemy_type}]"] = enemy_type in present_types
    for skill in ("SKILL_1", "SKILL_2", "AREA_ATTACK"):
        values[f"self_cooldown_ready[{skill}]"] = entity.cooldowns.get(skill, 0) <= 0
    for status in ("POISON", "SLOW", "STUN"):
        values[f"self_has_status[{status}]"] = entity.statuses.get(status, 0) > 0
    for flag in ("A", "B", "C", "D"):
        values[f"flag_state[{flag}]"] = entity.flags.get(flag, False)

    return PerceptionSnapshot(entity_id=entity.entity_id, tick=state.tick, values=values)
