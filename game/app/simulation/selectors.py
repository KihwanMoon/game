"""타겟 셀렉터 — 행동이 대상을 고르는 방식 (GDD §3.3).

**셀렉터를 조건보다 먼저 푼다** (Phase 0 F-1 결정). 조건의 `대상 HP%` 같은 값은 그렇게
정해진 대상을 가리킨다. 순서를 반대로 두면 조건이 무엇을 재는지 정의되지 않는다.

셀렉터가 아무도 못 고르면 그 규칙은 발동할 수 없다 — 없는 소환사를 공격하라는 규칙이
틱을 버리는 것을 막는다. 블록 목록 v4 의 아군 셀렉터가 이 성질에 그대로 기댄다:
부상한 아군이 없으면 `HEAL` 규칙은 발동하지 않고 아래 규칙으로 넘어가므로, 치유형이
회복 한 줄에 굳지 않는다.
"""

from game.app.grid.geometry import get_manhattan_distance
from game.app.simulation.state import Entity, WorldState

SELECTOR_NEAREST = "NEAREST"
SELECTOR_LOWEST_HP = "LOWEST_HP"
SELECTOR_HIGHEST_THREAT = "HIGHEST_THREAT"
SELECTOR_TYPE_RANGED = "TYPE_RANGED"
SELECTOR_TYPE_SUMMONER = "TYPE_SUMMONER"
SELECTOR_TYPE_HEALER = "TYPE_HEALER"
SELECTOR_CASTING = "CASTING"
SELECTOR_BOSS = "BOSS"
SELECTOR_ALLY_WOUNDED = "ALLY_WOUNDED"
SELECTOR_SELF = "SELF"

# 유형을 **우선**하되 없으면 가장 가까운 것으로 떨어지는 셀렉터들 (블록 v15).
#
# **선호 대상이 없는 방에서 아무것도 안 하는 표가 벤치마크에 다섯 벌 있었다** — 전부
# 0% 였다(2026-09-15 실측, 층 생성 120런). 소환사를 우선하는데 소환사가 없으면 그 줄이
# 영영 거짓이고, 규칙이 전부 거짓이면 엔진이 접근으로 채운다 — 걸어가다 죽는다.
#
# 고치는 길은 두 가지였다. **줄을 하나 더 받치거나**(v8_cut_the_healer 가 그렇게 했다),
# 셀렉터가 스스로 떨어지거나. 앞의 것은 슬롯 다섯 중 하나를 먹는다 — 예산이 줄면 못
# 쓴다. 그래서 뒤의 것을 연다.
#
# **기존 셀렉터는 안 바꾼다.** 「그 유형만, 없으면 아무것도 안 함」은 여전히 적을 수
# 있어야 한다 — 그것이 뜻인 표가 있고(굿판이 차기 전에 부르는 쪽만 끊는다), 바꾸면
# 저장된 내력이 조용히 다른 판을 돈다.
SELECTOR_TYPE_RANGED_FIRST = "TYPE_RANGED_FIRST"
SELECTOR_TYPE_SUMMONER_FIRST = "TYPE_SUMMONER_FIRST"
SELECTOR_TYPE_HEALER_FIRST = "TYPE_HEALER_FIRST"

# 순서는 blocks.json 의 selectors 절과 같다. 인지 스냅샷이 이 순서로 거리를 푼다.
ALL_SELECTORS = (
    SELECTOR_NEAREST,
    SELECTOR_LOWEST_HP,
    SELECTOR_HIGHEST_THREAT,
    SELECTOR_TYPE_RANGED,
    SELECTOR_TYPE_SUMMONER,
    SELECTOR_TYPE_HEALER,
    SELECTOR_CASTING,
    SELECTOR_BOSS,
    SELECTOR_ALLY_WOUNDED,
    SELECTOR_SELF,
    SELECTOR_TYPE_RANGED_FIRST,
    SELECTOR_TYPE_SUMMONER_FIRST,
    SELECTOR_TYPE_HEALER_FIRST,
)

# 적 유형을 직접 가리키는 셀렉터들. BOSS 도 유형 하나이므로 같은 표에 둔다.
TYPE_BY_SELECTOR = {
    SELECTOR_TYPE_RANGED: "RANGED",
    SELECTOR_TYPE_SUMMONER: "SUMMONER",
    SELECTOR_TYPE_HEALER: "HEALER",
    SELECTOR_BOSS: "BOSS",
    SELECTOR_TYPE_RANGED_FIRST: "RANGED",
    SELECTOR_TYPE_SUMMONER_FIRST: "SUMMONER",
    SELECTOR_TYPE_HEALER_FIRST: "HEALER",
}

# 후보가 없을 때 가장 가까운 적으로 떨어지는 셀렉터들 (블록 v15).
FALLBACK_SELECTORS = frozenset(
    {SELECTOR_TYPE_RANGED_FIRST, SELECTOR_TYPE_SUMMONER_FIRST, SELECTOR_TYPE_HEALER_FIRST}
)

# HP 가 가장 낮은 쪽을 고르는 셀렉터들. 적대·아군 양쪽에 하나씩이다.
LOWEST_HP_SELECTORS = frozenset({SELECTOR_LOWEST_HP, SELECTOR_ALLY_WOUNDED})


def list_candidates(
    selector_id: str, actor: Entity, state: WorldState, kind_types: dict[str, str]
) -> tuple[Entity, ...]:
    """셀렉터가 고를 수 있는 후보를 진영과 조건으로 좁힌다.

    Args:
        selector_id: 셀렉터 id.
        actor: 대상을 고르는 주체.
        state: 세계 상태.
        kind_types: 엔티티 종류에서 적 유형으로의 대응표.

    Returns:
        후보들. 순서는 list_actors 와 같다.
    """
    if selector_id == SELECTOR_SELF:
        # 자기 자신은 늘 후보다 (v8). ALLY_WOUNDED 가 자신을 빼는 것과 짝이다 — 자기
        # 회복·자기 강화를 규칙으로 지을 자리가 없었다. 만피여도 고른다: 거르면
        # 「참인데 대상 없음」과 「거짓」이 섞여 로그가 거짓말한다.
        return (actor,)
    if selector_id == SELECTOR_ALLY_WOUNDED:
        # 만피인 아군은 회복 대상이 아니다. 여기서 거르지 않으면 HEAL 규칙이 참인데
        # 회복량 0 으로 끝나 쿨타임도 걸리지 않고, 그 규칙에 치유형이 굳는다.
        return tuple(other for other in state.list_allies(actor) if other.hp < other.hp_max)

    hostiles = state.list_hostiles(actor)
    wanted = TYPE_BY_SELECTOR.get(selector_id)
    if wanted is not None:
        return tuple(other for other in hostiles if kind_types.get(other.kind_id) == wanted)
    if selector_id == SELECTOR_CASTING:
        # 시전 판정은 예고판이 답한다. 예고판은 엔진이 들고 있으므로 TELEGRAPH
        # 페이즈가 정렬해 내려 준 WorldState.casting_ids 를 읽는다 (W6 통합).
        return tuple(other for other in hostiles if other.entity_id in state.casting_ids)
    return hostiles


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
        고른 대상. 조건에 맞는 후보가 없으면 None.
    """
    candidates = list_candidates(selector_id, actor, state, kind_types)
    if not candidates and selector_id in FALLBACK_SELECTORS:
        # **떨어지는 자리는 여기 하나다.** 후보를 고르는 쪽에서 섞으면 「소환사 우선」이
        # 소환사가 있을 때도 가까운 것을 후보에 넣게 되어 우선이 아니게 된다.
        candidates = list_candidates(SELECTOR_NEAREST, actor, state, kind_types)
    if not candidates:
        return None

    if selector_id in LOWEST_HP_SELECTORS:
        return min(candidates, key=lambda e: (e.hp, e.entity_id))
    if selector_id == SELECTOR_HIGHEST_THREAT:
        # 위협도는 아직 스탯이 아니다. 공격력을 대리 지표로 쓴다 — Phase 4 에서
        # 보스·정예가 들어오면 실제 위협도 계산으로 바꾼다.
        return max(candidates, key=lambda e: (e.attack, e.entity_id))
    return min(
        candidates,
        key=lambda e: (get_manhattan_distance(actor.position, e.position), e.entity_id),
    )
