"""타겟 셀렉터 — 행동이 대상을 고르는 방식 (GDD §3.3).

**셀렉터를 조건보다 먼저 푼다** (Phase 0 F-1 결정). 조건의 `대상 HP%` 같은 값은 그렇게
정해진 대상을 가리킨다. 순서를 반대로 두면 조건이 무엇을 재는지 정의되지 않는다.

셀렉터가 아무도 못 고르면 그 규칙은 발동할 수 없다 — 없는 소환사를 공격하라는 규칙이
틱을 버리는 것을 막는다.
"""

from game.app.grid.geometry import get_manhattan_distance
from game.app.simulation.state import Entity, WorldState

SELECTOR_NEAREST = "NEAREST"
SELECTOR_LOWEST_HP = "LOWEST_HP"
SELECTOR_HIGHEST_THREAT = "HIGHEST_THREAT"
SELECTOR_TYPE_RANGED = "TYPE_RANGED"
SELECTOR_TYPE_SUMMONER = "TYPE_SUMMONER"
SELECTOR_CASTING = "CASTING"
SELECTOR_BOSS = "BOSS"

TYPE_BY_SELECTOR = {
    SELECTOR_TYPE_RANGED: "RANGED",
    SELECTOR_TYPE_SUMMONER: "SUMMONER",
}


def resolve_target(
    selector_id: str, actor: Entity, state: WorldState, kind_types: dict[str, str]
) -> Entity | None:
    """셀렉터가 가리키는 대상을 찾는다.

    동점이 나오면 entity_id 사전순으로 가른다. 여기서 PRNG 를 쓰지 않는 이유는 조건
    평가가 순수해야 하기 때문이다(TDD §5.2) — 같은 스냅샷에 대해 두 번 물으면 같은
    답이 나와야 한다.

    Args:
        selector_id: 셀렉터 id.
        actor: 대상을 고르는 주체.
        state: 세계 상태.
        kind_types: 엔티티 종류에서 적 유형으로의 대응표.

    Returns:
        고른 대상. 조건에 맞는 적이 없으면 None.
    """
    hostiles = state.list_hostiles(actor)
    if not hostiles:
        return None

    if selector_id in TYPE_BY_SELECTOR:
        wanted = TYPE_BY_SELECTOR[selector_id]
        hostiles = tuple(e for e in hostiles if kind_types.get(e.kind_id) == wanted)
    elif selector_id == SELECTOR_BOSS:
        hostiles = tuple(e for e in hostiles if kind_types.get(e.kind_id) == "BOSS")
    elif selector_id == SELECTOR_CASTING:
        # 시전 판정은 텔레그래프에 딸려 있다 (Phase 2 W6). 그때까지 아무도 고르지 못한다.
        hostiles = ()

    if not hostiles:
        return None

    if selector_id == SELECTOR_LOWEST_HP:
        return min(hostiles, key=lambda e: (e.hp, e.entity_id))
    if selector_id == SELECTOR_HIGHEST_THREAT:
        # 위협도는 아직 스탯이 아니다. 공격력을 대리 지표로 쓴다 — Phase 4 에서
        # 보스·정예가 들어오면 실제 위협도 계산으로 바꾼다.
        return max(hostiles, key=lambda e: (e.attack, e.entity_id))
    return min(
        hostiles,
        key=lambda e: (get_manhattan_distance(actor.position, e.position), e.entity_id),
    )
