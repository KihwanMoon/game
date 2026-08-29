/**
 * 타겟 셀렉터 — `game/app/simulation/selectors.py` 의 이식 (GDD §3.3).
 *
 * **셀렉터를 조건보다 먼저 푼다** (Phase 0 F-1 결정). 조건의 `대상 HP%` 같은 값은 그렇게
 * 정해진 대상을 가리킨다. 순서를 반대로 두면 조건이 무엇을 재는지 정의되지 않는다.
 *
 * 셀렉터가 아무도 못 고르면 그 규칙은 발동할 수 없다 — 없는 소환사를 공격하라는 규칙이
 * 틱을 버리는 것을 막는다. 블록 목록 v4 의 아군 셀렉터가 이 성질에 그대로 기댄다: 부상한
 * 아군이 없으면 `HEAL` 규칙은 발동하지 않고 아래 규칙으로 넘어가므로, 치유형이 회복 한
 * 줄에 굳지 않는다.
 */

import { getManhattanDistance } from '../grid/geometry'
import { findMaxBy, findMinBy } from '../ordering'
import type { Entity, WorldState } from './state'

export const SELECTOR_NEAREST = 'NEAREST'
export const SELECTOR_LOWEST_HP = 'LOWEST_HP'
export const SELECTOR_HIGHEST_THREAT = 'HIGHEST_THREAT'
export const SELECTOR_TYPE_RANGED = 'TYPE_RANGED'
export const SELECTOR_TYPE_SUMMONER = 'TYPE_SUMMONER'
export const SELECTOR_TYPE_HEALER = 'TYPE_HEALER'
export const SELECTOR_CASTING = 'CASTING'
export const SELECTOR_BOSS = 'BOSS'
export const SELECTOR_ALLY_WOUNDED = 'ALLY_WOUNDED'

/** 셀렉터 9종. 순서는 blocks.json 과 같고, 인지 스냅샷이 이 순서로 거리를 푼다. */
export const ALL_SELECTORS: readonly string[] = [
  SELECTOR_NEAREST,
  SELECTOR_LOWEST_HP,
  SELECTOR_HIGHEST_THREAT,
  SELECTOR_TYPE_RANGED,
  SELECTOR_TYPE_SUMMONER,
  SELECTOR_TYPE_HEALER,
  SELECTOR_CASTING,
  SELECTOR_BOSS,
  SELECTOR_ALLY_WOUNDED,
]

/** 적 유형을 직접 가리키는 셀렉터들. BOSS 도 유형 하나이므로 같은 표에 둔다. */
const TYPE_BY_SELECTOR: ReadonlyMap<string, string> = new Map([
  [SELECTOR_TYPE_RANGED, 'RANGED'],
  [SELECTOR_TYPE_SUMMONER, 'SUMMONER'],
  [SELECTOR_TYPE_HEALER, 'HEALER'],
  [SELECTOR_BOSS, 'BOSS'],
])

/** HP 가 가장 낮은 쪽을 고르는 셀렉터들. 적대·아군 양쪽에 하나씩이다. */
const LOWEST_HP_SELECTORS: ReadonlySet<string> = new Set([
  SELECTOR_LOWEST_HP,
  SELECTOR_ALLY_WOUNDED,
])

/**
 * 셀렉터가 고를 수 있는 후보를 진영과 조건으로 좁힌다.
 *
 * @param selectorId 셀렉터 id.
 * @param actor 대상을 고르는 주체.
 * @param state 세계 상태.
 * @param kindTypes 엔티티 종류에서 적 유형으로의 대응표.
 * @returns 후보들. 순서는 listActors 와 같다.
 */
export function listCandidates(
  selectorId: string,
  actor: Entity,
  state: WorldState,
  kindTypes: ReadonlyMap<string, string>,
): readonly Entity[] {
  if (selectorId === SELECTOR_ALLY_WOUNDED) {
    // 만피인 아군은 회복 대상이 아니다. 여기서 거르지 않으면 HEAL 규칙이 참인데 회복량
    // 0 으로 끝나 쿨타임도 걸리지 않고, 그 규칙에 치유형이 굳는다.
    return state.listAllies(actor).filter((other) => other.hp < other.hpMax)
  }

  const hostiles = state.listHostiles(actor)
  const wanted = TYPE_BY_SELECTOR.get(selectorId)
  if (wanted !== undefined) {
    return hostiles.filter((other) => kindTypes.get(other.kindId) === wanted)
  }
  if (selectorId === SELECTOR_CASTING) {
    // 시전 판정은 예고판이 답한다. 예고판은 엔진이 들고 있으므로 TELEGRAPH 페이즈가
    // 정렬해 내려 준 WorldState.castingIds 를 읽는다 (W6 통합).
    return hostiles.filter((other) => state.castingIds.includes(other.entityId))
  }
  return hostiles
}

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
 * @returns 고른 대상. 조건에 맞는 후보가 없으면 undefined.
 */
export function resolveTarget(
  selectorId: string,
  actor: Entity,
  state: WorldState,
  kindTypes: ReadonlyMap<string, string>,
): Entity | undefined {
  const candidates = listCandidates(selectorId, actor, state, kindTypes)
  if (candidates.length === 0) {
    return undefined
  }

  if (LOWEST_HP_SELECTORS.has(selectorId)) {
    return findMinBy(candidates, (entity) => [entity.hp, entity.entityId])
  }
  if (selectorId === SELECTOR_HIGHEST_THREAT) {
    // 위협도는 아직 스탯이 아니다. 공격력을 대리 지표로 쓴다 — Phase 4 에서 보스·정예가
    // 들어오면 실제 위협도 계산으로 바꾼다.
    return findMaxBy(candidates, (entity) => [entity.attack, entity.entityId])
  }
  return findMinBy(candidates, (entity) => [
    getManhattanDistance(actor.position, entity.position),
    entity.entityId,
  ])
}
