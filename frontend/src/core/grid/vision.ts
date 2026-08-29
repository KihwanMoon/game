/**
 * 시야(LOS) — `game/app/grid/vision.py` 의 이식 (GDD §4.1·§4.4, TDD §5.4).
 *
 * 원거리 적이 직선 시야가 통할 때만 쏘고 벽 뒤로 숨는 것이 유효한 대응이 되어야 그리드가
 * 존재할 이유가 생긴다 (P2).
 *
 * **정수 브레젠험만 쓴다.** 부동소수 기울기로 그으면 같은 시드가 다른 선을 낼 수 있고 그
 * 순간 리플레이가 깨진다 (R5).
 *
 * **대칭은 좌표 정렬로 보장한다.** 브레젠험은 오차가 정확히 반일 때 진행 방향에 따라 다른
 * 칸을 지나므로 A→B 와 B→A 가 갈릴 수 있다. 항상 사전순으로 작은 좌표에서 긋도록 고정하면
 * 두 방향이 같은 선을 쓴다.
 */

import {
  type Position,
  checkSamePosition,
  comparePositions,
  formatPositionKey,
  getManhattanDistance,
  parsePositionKey,
} from './geometry'
import { TILE_BREAKABLE_WALL, TILE_COVER, TILE_WALL, WALKABLE_TILES } from '../schemas'
import { findMinBy, sortByKey } from '../ordering'

/**
 * 시야를 막는 타일 (GDD §4.4). 가시덤불(3)은 이동만 늦출 뿐 시야는 막지 않는다.
 * 파괴 가능 벽(2)은 부서지기 전까지 막으며, 부순 뒤에는 WorldState 의 타일 덮어쓰기가
 * 반영되므로 이 목록은 그대로 두고 시야가 열린다.
 */
export const BLOCKING_TILES: ReadonlySet<number> = new Set([
  TILE_WALL,
  TILE_BREAKABLE_WALL,
  TILE_COVER,
])

/**
 * 엄폐할 곳이 없을 때의 거리. perception 의 "방에 없음" 규약과 같은 값이라 규칙표가 두
 * 변수를 같은 방식으로 비교할 수 있다.
 */
export const NO_COVER_DISTANCE = -1

/**
 * 좌표 하나의 타일을 읽을 수 있는 것.
 *
 * RoomTemplate 과 WorldState 가 둘 다 만족한다. 둘을 가르는 것은 파괴된 벽이며, 전투 중
 * 판정은 그것을 반영하는 WorldState 쪽을 넘겨야 한다.
 */
export interface TileReader {
  /**
   * 좌표의 타일 ID 를 돌려준다.
   *
   * @param x 가로 좌표.
   * @param y 세로 좌표.
   * @returns 타일 ID.
   */
  getTile(x: number, y: number): number
}

/**
 * 타일 읽기와 방 크기를 묶은, 시야 함수들이 받는 격자.
 *
 * WorldState 는 파괴된 벽을 반영한 타일을 주지만 크기는 room 이 안다. 둘을 여기서 묶는다.
 */
export class VisionGrid implements TileReader {
  /**
   * 격자를 만든다.
   *
   * @param tiles 타일을 읽어 줄 것. 전투 중이면 WorldState 를 넘긴다.
   * @param width 방의 가로 칸 수.
   * @param height 방의 세로 칸 수.
   */
  constructor(
    readonly tiles: TileReader,
    readonly width: number,
    readonly height: number,
  ) {}

  /**
   * 좌표의 타일 ID 를 돌려준다.
   *
   * @param x 가로 좌표.
   * @param y 세로 좌표.
   * @returns 타일 ID. 격자 밖은 벽으로 취급한다.
   */
  getTile(x: number, y: number): number {
    if (x < 0 || x >= this.width || y < 0 || y >= this.height) {
      return TILE_WALL
    }
    return this.tiles.getTile(x, y)
  }
}

/** 한 시점(視點)에서 방 전체를 본 결과 (TDD §5.4). 만들어진 뒤 바뀌지 않는다. */
export interface VisibilityMap {
  readonly origin: Position
  /** 보이는 칸들의 좌표 열쇠. 순회해서 상태를 만들지 않는다 — 포함 검사 전용이다. */
  readonly visible: ReadonlySet<string>
}

/**
 * 그 타일이 시야를 막는가.
 *
 * @param tileId 타일 ID.
 * @returns 벽·파괴 가능 벽·엄폐물이면 true.
 */
export function isBlockingTile(tileId: number): boolean {
  return BLOCKING_TILES.has(tileId)
}

/**
 * 두 칸을 잇는 브레젠험 직선 위의 칸들을 양 끝 포함해 돌려준다 (R5: 정수 덧셈만).
 *
 * @param origin 시작 좌표.
 * @param target 끝 좌표.
 * @returns origin 에서 target 까지 지나는 칸들.
 */
function iterLineCells(origin: Position, target: Position): readonly Position[] {
  let x = origin.x
  let y = origin.y
  const stepX = target.x > x ? 1 : -1
  const stepY = target.y > y ? 1 : -1
  const spanX = Math.abs(target.x - x)
  const spanY = -Math.abs(target.y - y)
  let error = spanX + spanY

  const cells: Position[] = [{ x, y }]
  while (x !== target.x || y !== target.y) {
    const doubled = 2 * error
    if (doubled >= spanY) {
      error += spanY
      x += stepX
    }
    if (doubled <= spanX) {
      error += spanX
      y += stepY
    }
    cells.push({ x, y })
  }
  return cells
}

/**
 * 두 칸 사이에 직선 시야가 통하는가 (GDD §4.1).
 *
 * 양 끝 칸은 판정에서 뺀다 — 서 있는 칸이 자기 시야를 막지는 않는다. 선을 늘 사전순 작은
 * 좌표에서 긋기 때문에 두 인자를 바꿔 넣어도 답이 같다.
 *
 * @param grid 타일을 읽을 격자.
 * @param origin 보는 쪽 좌표.
 * @param target 보이는 쪽 좌표.
 * @returns 중간에 시야를 막는 타일이 없으면 true.
 */
export function checkLineOfSight(grid: VisionGrid, origin: Position, target: Position): boolean {
  if (checkSamePosition(origin, target)) {
    return true
  }
  const ordered = comparePositions(origin, target) <= 0 ? [origin, target] : [target, origin]
  const cells = iterLineCells(ordered[0] as Position, ordered[1] as Position)
  return !cells.slice(1, -1).some((cell) => isBlockingTile(grid.getTile(cell.x, cell.y)))
}

/**
 * 한 좌표에서 보이는 칸을 방 전체에 대해 미리 계산한다 (TDD §5.4).
 *
 * 방 진입 시 관측자마다 한 번 부르는 것이 용도다. LOS 는 O(적 수 × 사거리) 라 매 틱
 * 전량 재계산하면 틱 예산을 먹는다.
 *
 * @param grid 타일을 읽을 격자.
 * @param origin 시점 좌표.
 * @param maxRange 이 맨해튼 거리까지만 본다. null 이면 방 전체.
 * @returns origin 에서 보이는 칸들을 담은 맵.
 */
export function buildVisibilityMap(
  grid: VisionGrid,
  origin: Position,
  maxRange: number | null = null,
): VisibilityMap {
  const visible = new Set<string>()
  for (let y = 0; y < grid.height; y += 1) {
    for (let x = 0; x < grid.width; x += 1) {
      const cell: Position = { x, y }
      const withinRange = maxRange === null || getManhattanDistance(origin, cell) <= maxRange
      if (withinRange && checkLineOfSight(grid, origin, cell)) {
        visible.add(formatPositionKey(cell))
      }
    }
  }
  return { origin, visible }
}

/**
 * 사전 계산된 맵에서 그 칸이 보이는지 조회한다. O(1) 이다.
 *
 * @param visionMap buildVisibilityMap 이 만든 맵.
 * @param position 조회할 칸.
 * @returns 맵의 시점에서 그 칸이 보이면 true.
 */
export function checkVisibility(visionMap: VisibilityMap, position: Position): boolean {
  return visionMap.visible.has(formatPositionKey(position))
}

/**
 * 보이는 칸들을 행 우선 순서로 돌려준다.
 *
 * 가시성 맵의 내부는 열쇠 집합이다. 집합을 그대로 순회해 게임 상태를 만들면 순서가
 * 보장되지 않으므로, 밖으로 내보내는 자리는 (y, x) 오름차순으로 고정한다 (R5).
 *
 * @param visionMap buildVisibilityMap 이 만든 맵.
 * @returns (y, x) 오름차순 좌표들.
 */
export function listVisiblePositions(visionMap: VisibilityMap): readonly Position[] {
  return sortByKey([...visionMap.visible].map(parsePositionKey), (position) => [
    position.y,
    position.x,
  ])
}

/** 방 하나의 관측자별 가시성 맵 (TDD §5.4). */
export class VisionCache {
  readonly maps = new Map<string, VisibilityMap>()

  /**
   * 캐시를 만든다.
   *
   * @param grid 타일을 읽을 격자.
   * @param maxRange 관측 거리 제한. null 이면 방 전체.
   */
  constructor(
    readonly grid: VisionGrid,
    readonly maxRange: number | null = null,
  ) {}

  /**
   * 관측자의 맵을 새로 계산해 넣는다.
   *
   * 벽이 부서져 지형이 바뀌었을 때도 이것을 부른다 — refresh 는 위치만 본다.
   *
   * @param viewerId 관측자 엔티티 id.
   * @param origin 관측자의 현재 좌표.
   * @returns 새로 계산한 맵.
   */
  register(viewerId: string, origin: Position): VisibilityMap {
    const visionMap = buildVisibilityMap(this.grid, origin, this.maxRange)
    this.maps.set(viewerId, visionMap)
    return visionMap
  }

  /**
   * 움직인 관측자만 다시 계산한다.
   *
   * @param viewerId 관측자 엔티티 id.
   * @param origin 관측자의 현재 좌표.
   * @returns 위치가 그대로면 이전 맵 그대로, 움직였으면 새 맵.
   */
  refresh(viewerId: string, origin: Position): VisibilityMap {
    const cached = this.maps.get(viewerId)
    if (cached !== undefined && checkSamePosition(cached.origin, origin)) {
      return cached
    }
    return this.register(viewerId, origin)
  }

  /**
   * 등록된 맵을 꺼낸다.
   *
   * @param viewerId 관측자 엔티티 id.
   * @returns 맵. 등록된 적이 없으면 undefined — "없다" 와 "안 보인다" 는 다른 답이다.
   */
  read(viewerId: string): VisibilityMap | undefined {
    return this.maps.get(viewerId)
  }

  /**
   * 관측자가 그 칸을 보는가.
   *
   * 등록되지 않은 관측자를 false 로 답하지 않는다 — 맵을 만들지 않은 버그가 "안 보인다"
   * 는 정상 판정과 구분되지 않는다.
   *
   * @param viewerId 관측자 엔티티 id.
   * @param position 조회할 칸.
   * @returns 보이면 true.
   * @throws 아직 맵을 만들지 않은 관측자인 경우.
   */
  check(viewerId: string, position: Position): boolean {
    const visionMap = this.maps.get(viewerId)
    if (visionMap === undefined) {
      throw new Error(`가시성 맵이 없는 관측자다: ${viewerId}`)
    }
    return checkVisibility(visionMap, position)
  }

  /**
   * 죽었거나 방을 떠난 관측자의 맵을 버린다.
   *
   * @param viewerId 관측자 엔티티 id. 없으면 아무 일도 하지 않는다.
   */
  drop(viewerId: string): void {
    this.maps.delete(viewerId)
  }
}

/**
 * 그 칸이 위협 중 하나에게라도 보이는가 (인지 변수 self_exposed_to_los).
 *
 * @param grid 타일을 읽을 격자.
 * @param position 판정할 칸.
 * @param threats 위협 좌표들. 정렬된 배열을 넘긴다 (R5).
 * @returns 하나라도 시야가 통하면 true. 위협이 없으면 false 다.
 */
export function checkExposure(
  grid: VisionGrid,
  position: Position,
  threats: readonly Position[],
): boolean {
  return threats.some((threat) => checkLineOfSight(grid, threat, position))
}

/**
 * 그 칸이 모든 위협으로부터 가려지는가.
 *
 * @param grid 타일을 읽을 격자.
 * @param position 판정할 칸.
 * @param threats 위협 좌표들.
 * @returns 어느 위협에도 보이지 않으면 true. 위협이 없으면 true 다.
 */
export function checkCover(
  grid: VisionGrid,
  position: Position,
  threats: readonly Position[],
): boolean {
  return !checkExposure(grid, position, threats)
}

/**
 * 모든 위협의 시야에서 벗어난 이동 가능 칸들을 모은다 (행동 MOVE_TO_COVER).
 *
 * 거리장의 목표로 그대로 넘기라고 행 우선 순서로 준다. 닿을 수 있는지는 길찾기 몫이다.
 *
 * @param grid 타일을 읽을 격자.
 * @param threats 피해야 할 위협 좌표들.
 * @param occupied 다른 엔티티가 서 있어 갈 수 없는 칸의 좌표 열쇠.
 * @returns 엄폐가 성립하는 칸들. 위협이 없으면 숨을 이유도 없으므로 빈 배열.
 */
export function findCoverPositions(
  grid: VisionGrid,
  threats: readonly Position[],
  occupied: ReadonlySet<string> = new Set(),
): readonly Position[] {
  if (threats.length === 0) {
    return []
  }
  const found: Position[] = []
  for (let y = 0; y < grid.height; y += 1) {
    for (let x = 0; x < grid.width; x += 1) {
      const cell: Position = { x, y }
      if (
        WALKABLE_TILES.has(grid.getTile(x, y)) &&
        !occupied.has(formatPositionKey(cell)) &&
        checkCover(grid, cell, threats)
      ) {
        found.push(cell)
      }
    }
  }
  return found
}

/**
 * 가장 가까운 엄폐 칸을 찾는다.
 *
 * 거리가 같으면 행 우선 순서에서 먼저 오는 칸을 고른다 — 고정하지 않으면 같은 시드가
 * 다른 칸을 골라 리플레이가 깨진다 (R5).
 *
 * @param grid 타일을 읽을 격자.
 * @param origin 기준 좌표.
 * @param threats 피해야 할 위협 좌표들.
 * @param occupied 다른 엔티티가 서 있어 갈 수 없는 칸의 좌표 열쇠.
 * @returns 가장 가까운 엄폐 칸. 하나도 없으면 undefined.
 */
export function findNearestCover(
  grid: VisionGrid,
  origin: Position,
  threats: readonly Position[],
  occupied: ReadonlySet<string> = new Set(),
): Position | undefined {
  const candidates = findCoverPositions(grid, threats, occupied)
  return findMinBy(candidates, (pos) => [getManhattanDistance(origin, pos), pos.y, pos.x])
}

/**
 * 엄폐 가능한 가장 가까운 칸까지의 거리 (인지 변수 cover_wall_distance).
 *
 * "엄폐 가능 벽" 은 벽 자체가 아니라 **그 뒤에 서면 시야가 끊기는 칸**이다. 벽까지의
 * 거리를 재면 등 뒤의 벽도 가깝다고 답해 움직여도 노출이 그대로다.
 *
 * @param grid 타일을 읽을 격자.
 * @param origin 기준 좌표.
 * @param threats 피해야 할 위협 좌표들.
 * @param occupied 다른 엔티티가 서 있어 갈 수 없는 칸의 좌표 열쇠.
 * @returns 맨해튼 거리. 이미 가려져 있으면 0, 엄폐할 곳이 없으면 NO_COVER_DISTANCE.
 */
export function calculateCoverDistance(
  grid: VisionGrid,
  origin: Position,
  threats: readonly Position[],
  occupied: ReadonlySet<string> = new Set(),
): number {
  const nearest = findNearestCover(grid, origin, threats, occupied)
  if (nearest === undefined) {
    return NO_COVER_DISTANCE
  }
  return getManhattanDistance(origin, nearest)
}
