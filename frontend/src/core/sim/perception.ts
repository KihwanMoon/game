/**
 * 인지 스냅샷 — `game/app/simulation/perception.py` 의 이식 (TDD §4.1, §5.4).
 *
 * **틱당 한 번만 만들고 그 틱의 모든 규칙이 공유한다.** 규칙마다 다시 재면 같은 틱 안에서
 * 값이 달라져 "동시에 같은 세계를 본다" 는 전제가 깨진다.
 *
 * LOS·엄폐·텔레그래프 계열의 값을 만들려면 지형 격자와 예고판이 필요한데 둘 다 엔진이
 * 들고 있으므로 인자로 받는다. 넘기지 않으면 그 키를 **아예 만들지 않아** read() 가
 * undefined 를 돌려준다 — 0 이나 false 로 채우면 "값이 없다" 와 "값이 0이다" 가
 * 구분되지 않는다.
 */

import {
  type Position,
  formatPositionKey,
  getManhattanDistance,
  iterNeighbors,
} from '../grid/geometry'
import {
  type VisionGrid,
  calculateCoverDistance,
  checkExposure,
  checkLineOfSight,
} from '../grid/vision'
import { TILE_DOOR, TILE_SPRING, TILE_STAIRS, WALKABLE_TILES } from '../schemas'
import { ALL_SELECTORS, resolveTarget } from './selectors'
import { type Entity, type WorldState, getHpPercent } from './state'
import { type TelegraphBoard, getForesightTicks } from './telegraph'

/** 인지 변수 nearest_tile_distance 의 인자에서 타일 ID 로. 파이썬 dict 의 순서를 지킨다. */
const TILE_BY_NAME: readonly (readonly [string, number])[] = [
  ['DOOR', TILE_DOOR],
  ['STAIRS', TILE_STAIRS],
  ['SPRING', TILE_SPRING],
]

/** 인지 변수 enemy_type_present 가 묻는 적 유형들. */
const ENEMY_TYPES: readonly string[] = ['MELEE', 'RANGED', 'SUMMONER', 'BOMBER']

/**
 * 인지 변수 self_cooldown_ready 가 묻는 스킬들. SUMMON 이 끼는 것은 v3 부터다 — 소환
 * 주기를 규칙표가 물을 수 있어야 `쿨타임[SUMMON] 완료 → 소환` 이 성립한다 (GDD §5).
 */
const COOLDOWN_SKILLS: readonly string[] = ['SKILL_1', 'SKILL_2', 'AREA_ATTACK', 'SUMMON']

/** 인지 변수 self_has_status 가 묻는 상태이상들. */
const STATUS_NAMES: readonly string[] = ['POISON', 'SLOW', 'STUN']

/** 규칙표가 쓰는 플래그 4종. */
const FLAG_NAMES: readonly string[] = ['A', 'B', 'C', 'D']

/** 방에 그 타일이 하나도 없을 때의 거리. */
const TILE_NOT_FOUND_DISTANCE = -1

/**
 * 아직 값을 만들 수 없는 블록과 그 사유. 비어 있는 이유를 코드가 알고 있어야 나중에
 * "왜 안 되지" 를 다시 조사하지 않는다.
 *
 * **W6 통합으로 비었다.** 여기 들지 않는 것이 둘 있다 — target_hp_percent·
 * target_is_casting 은 규칙마다 셀렉터가 다르고, self_cpu_headroom 은 규칙표를 알아야
 * 계산된다. 둘 다 RuleVM 이 답한다. 미구현이 아니라 소유자가 다른 것이다.
 */
export const DEFERRED_BLOCKS: ReadonlyMap<string, string> = new Map()

/** 한 엔티티가 이번 틱에 본 세계. 만들어진 뒤 바뀌지 않는다. */
export interface PerceptionSnapshot {
  readonly entityId: string
  readonly tick: number
  readonly values: ReadonlyMap<string, number | boolean>
}

/**
 * 인지 변수 값을 읽는다.
 *
 * @param snapshot 읽을 스냅샷.
 * @param blockId 인지 변수 id.
 * @param param 인자를 받는 블록의 인자. 예: 쿨타임의 스킬 id.
 * @returns 값. 이번 틱에 만들어지지 않은 블록이면 undefined.
 */
export function readSnapshot(
  snapshot: PerceptionSnapshot,
  blockId: string,
  param: string | null = null,
): number | boolean | undefined {
  return snapshot.values.get(param === null ? blockId : `${blockId}[${param}]`)
}

/**
 * 주변 8칸 중 이동 가능한 칸 수를 센다 (포위도).
 *
 * 이동은 4방향이지만 포위 판정은 8칸이다 — 근접 적이 인접 8칸을 점유하기 때문이다
 * (GDD §4.3). 두 기준이 다른 것은 의도된 것이다.
 *
 * @param state 세계 상태.
 * @param entity 기준 엔티티.
 * @returns 0 이상 8 이하의 칸 수.
 */
function countOpenNeighbors(state: WorldState, entity: Entity): number {
  const occupied = new Set(
    state
      .listActors()
      .filter((other) => other !== entity)
      .map((other) => formatPositionKey(other.position)),
  )
  return iterNeighbors(entity.position).filter(
    (pos) =>
      WALKABLE_TILES.has(state.getTile(pos.x, pos.y)) && !occupied.has(formatPositionKey(pos)),
  ).length
}

/**
 * 지정한 타일 종류 중 가장 가까운 것까지의 거리.
 *
 * @param state 세계 상태.
 * @param entity 기준 엔티티.
 * @param kinds 찾을 타일 ID 집합.
 * @returns 맨해튼 거리. 방에 하나도 없으면 -1.
 */
function getNearestTileDistance(
  state: WorldState,
  entity: Entity,
  kinds: ReadonlySet<number>,
): number {
  let nearest = TILE_NOT_FOUND_DISTANCE
  for (let y = 0; y < state.room.height; y += 1) {
    for (let x = 0; x < state.room.width; x += 1) {
      if (!kinds.has(state.getTile(x, y))) {
        continue
      }
      const distance = getManhattanDistance(entity.position, { x, y })
      if (nearest === TILE_NOT_FOUND_DISTANCE || distance < nearest) {
        nearest = distance
      }
    }
  }
  return nearest
}

/**
 * LOS 계열 세 값을 채운다 (GDD §4.1·§4.4).
 *
 * @param values 채울 대상.
 * @param state 세계 상태.
 * @param entity 대상 엔티티.
 * @param hostiles 적대 진영 엔티티들. listActors 순서라 결정론적이다 (R5).
 * @param grid 지형을 읽을 격자.
 */
function addVisionValues(
  values: Map<string, number | boolean>,
  state: WorldState,
  entity: Entity,
  hostiles: readonly Entity[],
  grid: VisionGrid,
): void {
  const threats: readonly Position[] = hostiles.map((other) => other.position)
  const occupied = new Set(
    state
      .listActors()
      .filter((other) => other !== entity)
      .map((other) => formatPositionKey(other.position)),
  )
  values.set('self_exposed_to_los', checkExposure(grid, entity.position, threats))
  values.set(
    'cover_wall_distance',
    calculateCoverDistance(grid, entity.position, threats, occupied),
  )
  // 시야를 방 전체로 세던 근사를 여기서 끝낸다. 원거리 공격이 LOS 를 요구하게 된 이상
  // "보이는 적 수" 도 같은 기준이어야 규칙표가 세운 판단과 실제가 어긋나지 않는다.
  values.set(
    'visible_enemy_count',
    hostiles.filter((other) => checkLineOfSight(grid, entity.position, other.position)).length,
  )
}

/** `buildSnapshot` 이 받는 값들. */
export interface SnapshotInput {
  readonly state: WorldState
  readonly entity: Entity
  /** 엔티티 종류 id 에서 적 유형(MELEE 등)으로의 대응표. */
  readonly kindTypes: ReadonlyMap<string, string>
  /**
   * 지형을 읽을 격자. 엔진이 틱당 하나를 만들어 전 엔티티가 공유한다. 넘기지 않으면
   * LOS 계열 값을 만들지 않는다.
   */
  readonly grid?: VisionGrid | undefined
  /** 진행 중인 예고판. 넘기지 않으면 예고 계열 값을 만들지 않는다. */
  readonly board?: TelegraphBoard | undefined
}

/**
 * 한 엔티티의 인지 변수를 이번 틱 값으로 고정한다.
 *
 * @param input 세계 상태·대상 엔티티와, 있으면 격자·예고판.
 * @returns 읽기 전용 스냅샷.
 */
export function buildSnapshot(input: SnapshotInput): PerceptionSnapshot {
  const { state, entity, kindTypes, grid, board } = input
  const hostiles = state.listHostiles(entity)

  const values = new Map<string, number | boolean>()
  values.set('self_hp_percent', getHpPercent(entity))
  values.set('self_potion_count', entity.potions)
  values.set('self_on_heal_tile', state.getTile(entity.position.x, entity.position.y) === TILE_SPRING)
  values.set('visible_enemy_count', hostiles.length)
  values.set('open_neighbor_count', countOpenNeighbors(state, entity))
  values.set('room_elapsed_ticks', state.tick)

  if (grid !== undefined) {
    addVisionValues(values, state, entity, hostiles, grid)
  }
  if (board !== undefined) {
    // 예측 회로가 있으면 같은 예고를 한 틱 더 일찍 본다 (GDD §6.2).
    values.set(
      'self_on_hazard_telegraph',
      board.isMarked(entity.position, getForesightTicks(entity)),
    )
  }

  // 셀렉터별 대상 거리 (블록 목록 v2, F-1 잔여 해결). 규칙이 자기 TARGET 과 무관하게
  // 물을 수 있어야 하므로 스냅샷에서 7개를 모두 미리 푼다 — 틱당 1회 원칙은 지켜진다.
  for (const selectorId of ALL_SELECTORS) {
    const picked = resolveTarget(selectorId, entity, state, kindTypes)
    values.set(
      `target_distance[${selectorId}]`,
      picked === undefined ? -1 : getManhattanDistance(entity.position, picked.position),
    )
  }

  // 타일 종류별 최단 거리 (v2, F-3). 회복타일이 방에 있는지 물을 수 있어야 MOVE_TO_HEAL
  // 이 헛돌지 않는다.
  for (const [tileName, tileId] of TILE_BY_NAME) {
    values.set(
      `nearest_tile_distance[${tileName}]`,
      getNearestTileDistance(state, entity, new Set([tileId])),
    )
  }

  const presentTypes = new Set(hostiles.map((other) => kindTypes.get(other.kindId) ?? ''))
  for (const enemyType of ENEMY_TYPES) {
    values.set(`enemy_type_present[${enemyType}]`, presentTypes.has(enemyType))
  }
  for (const skill of COOLDOWN_SKILLS) {
    values.set(`self_cooldown_ready[${skill}]`, (entity.cooldowns.get(skill) ?? 0) <= 0)
  }
  for (const status of STATUS_NAMES) {
    values.set(`self_has_status[${status}]`, (entity.statuses.get(status) ?? 0) > 0)
  }
  for (const flag of FLAG_NAMES) {
    values.set(`flag_state[${flag}]`, entity.flags.get(flag) ?? false)
  }

  return { entityId: entity.entityId, tick: state.tick, values }
}
