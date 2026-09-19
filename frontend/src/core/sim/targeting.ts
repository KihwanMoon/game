/**
 * 누가 맞는가 — 한 벌. 파이썬 `simulation/targeting` 과 같다 (2026-09-19).
 *
 * **같은 규칙이 두 곳에 다르게 박혀 있었다.** 즉발 범위는 시전자 중심 반경 안의 적만
 * 쳤고 예고형은 칸에 선 것을 진영 없이 쳤다 — 둘 다 `AREA` 인데 판정이 정반대였고,
 * 데이터만 봐서는 구별이 안 됐다. 어느 판정을 쓸지는 이제 재주가 `hits` 로 적는다.
 */
import { formatPositionKey, getManhattanDistance } from '../grid/geometry'
import type { Entity, WorldState } from './state'

/** 대상 하나. 셀렉터가 고른 그 개체가 맞는다 — 비켜설 수 없다. */
export const HITS_TARGET = 'TARGET'
/** 시전자 중심 반경 안의 **적만**. 즉발 범위 공격이 이것이다. */
export const HITS_HOSTILE_AREA = 'HOSTILE_AREA'
/** 칸에 선 것 **전부**. 예고가 좌표에 떨어지므로 아군도 시전자도 맞는다 (GDD §4.3). */
export const HITS_TILES = 'TILES'

/** 아는 값 전부. */
export const HITS_MODES: ReadonlySet<string> = new Set([
  HITS_TARGET,
  HITS_HOSTILE_AREA,
  HITS_TILES,
])

/**
 * 시전자 중심 반경 안의 적을 모은다.
 *
 * @param state 세계 상태.
 * @param caster 시전자.
 * @param radius 맨해튼 반경.
 * @returns 맞을 개체들. 순서는 `listHostiles` 가 정한다 (R5).
 */
export function listAreaVictims(
  state: WorldState,
  caster: Entity,
  radius: number,
): readonly Entity[] {
  return state
    .listHostiles(caster)
    .filter((other) => getManhattanDistance(caster.position, other.position) <= radius)
}

/**
 * 그 칸들에 선 것을 전부 모은다. **진영을 안 가린다.**
 *
 * @param state 세계 상태.
 * @param tiles 맞는 칸들. 포함 검사에만 쓴다 — 순회하면 순서가 흔들린다 (R5).
 * @returns 맞을 개체들. 순서는 `listActors` 가 정한다.
 */
export function listTileVictims(
  state: WorldState,
  tiles: ReadonlySet<string>,
): readonly Entity[] {
  return state.listActors().filter((entity) => tiles.has(formatPositionKey(entity.position)))
}
