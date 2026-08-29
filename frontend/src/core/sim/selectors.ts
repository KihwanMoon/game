/**
 * 타겟 셀렉터 — `game/app/simulation/selectors.py` 의 이식 (GDD §3.3).
 *
 * **셀렉터를 조건보다 먼저 푼다** (Phase 0 F-1 결정). 조건의 `대상 HP%` 같은 값은 그렇게
 * 정해진 대상을 가리킨다. 순서를 반대로 두면 조건이 무엇을 재는지 정의되지 않는다.
 *
 * 셀렉터가 아무도 못 고르면 그 규칙은 발동할 수 없다 — 없는 소환사를 공격하라는 규칙이
 * 틱을 버리는 것을 막는다.
 */

import { getManhattanDistance } from '../grid/geometry'
import { findMaxBy, findMinBy } from '../ordering'
import type { Entity, WorldState } from './state'

export const SELECTOR_NEAREST = 'NEAREST'
export const SELECTOR_LOWEST_HP = 'LOWEST_HP'
export const SELECTOR_HIGHEST_THREAT = 'HIGHEST_THREAT'
export const SELECTOR_TYPE_RANGED = 'TYPE_RANGED'
export const SELECTOR_TYPE_SUMMONER = 'TYPE_SUMMONER'
export const SELECTOR_CASTING = 'CASTING'
export const SELECTOR_BOSS = 'BOSS'

/** 셀렉터 7종. 순서는 블록 목록 v2 와 같고, 인지 스냅샷이 이 순서로 거리를 푼다. */
export const ALL_SELECTORS: readonly string[] = [
  SELECTOR_NEAREST,
  SELECTOR_LOWEST_HP,
  SELECTOR_HIGHEST_THREAT,
  SELECTOR_TYPE_RANGED,
  SELECTOR_TYPE_SUMMONER,
  SELECTOR_CASTING,
  SELECTOR_BOSS,
]

/** 적 유형을 직접 가리키는 셀렉터들. */
const TYPE_BY_SELECTOR: ReadonlyMap<string, string> = new Map([
  [SELECTOR_TYPE_RANGED, 'RANGED'],
  [SELECTOR_TYPE_SUMMONER, 'SUMMONER'],
])

const TYPE_BOSS = 'BOSS'

/**
 * 셀렉터가 가리키는 대상을 찾는다.
 *
 * 동점이 나오면 entityId 사전순으로 가른다. 여기서 PRNG 를 쓰지 않는 이유는 조건 평가가
 * 순수해야 하기 때문이다(TDD §5.2) — 같은 스냅샷에 대해 두 번 물으면 같은 답이 나와야 한다.
 *
 * @param selectorId 셀렉터 id.
 * @param actor 대상을 고르는 주체.
 * @param state 세계 상태.
 * @param kindTypes 엔티티 종류에서 적 유형으로의 대응표.
 * @returns 고른 대상. 조건에 맞는 적이 없으면 undefined.
 */
export function resolveTarget(
  selectorId: string,
  actor: Entity,
  state: WorldState,
  kindTypes: ReadonlyMap<string, string>,
): Entity | undefined {
  let hostiles = state.listHostiles(actor)
  if (hostiles.length === 0) {
    return undefined
  }

  const wanted = TYPE_BY_SELECTOR.get(selectorId)
  if (wanted !== undefined) {
    hostiles = hostiles.filter((entity) => kindTypes.get(entity.kindId) === wanted)
  } else if (selectorId === SELECTOR_BOSS) {
    hostiles = hostiles.filter((entity) => kindTypes.get(entity.kindId) === TYPE_BOSS)
  } else if (selectorId === SELECTOR_CASTING) {
    // 시전 판정은 예고판이 답한다. 예고판은 엔진이 들고 있으므로 TELEGRAPH 페이즈가
    // 정렬해 내려 준 WorldState.castingIds 를 읽는다 (W6 통합).
    hostiles = hostiles.filter((entity) => state.castingIds.includes(entity.entityId))
  }

  if (hostiles.length === 0) {
    return undefined
  }

  if (selectorId === SELECTOR_LOWEST_HP) {
    return findMinBy(hostiles, (entity) => [entity.hp, entity.entityId])
  }
  if (selectorId === SELECTOR_HIGHEST_THREAT) {
    // 위협도는 아직 스탯이 아니다. 공격력을 대리 지표로 쓴다 — Phase 4 에서 보스·정예가
    // 들어오면 실제 위협도 계산으로 바꾼다.
    return findMaxBy(hostiles, (entity) => [entity.attack, entity.entityId])
  }
  return findMinBy(hostiles, (entity) => [
    getManhattanDistance(actor.position, entity.position),
    entity.entityId,
  ])
}
