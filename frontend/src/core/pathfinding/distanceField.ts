/**
 * 거리장 — `game/app/pathfinding/distance_field.py` 의 이식 (TDD §6).
 *
 * 목표까지의 최소 이동 비용을 방 전체에 미리 깔아 둔다. 문·계단·회복타일처럼 목표가
 * 고정된 이동은 방 진입 시 한 번만 계산하면 되고 이후 탐색 비용이 0 이다.
 *
 * Phase 1 은 균일 비용이라 BFS 면 충분하다. 가시덤불(이동 2틱)이 들어오는 순간 가중
 * 다익스트라로 바꿔야 하며, 그때 이 모듈의 인터페이스는 그대로 둔다.
 *
 * 거리장은 좌표 열쇠로 키를 만든 `Map` 이다. 좌표 객체를 그대로 키로 쓰면 동등성이
 * 참조로 판정되어 같은 칸이 매번 새 항목이 된다.
 */

import { STEP_OFFSETS, type Position, formatPositionKey } from '../grid/geometry'
import type { TileReader } from '../grid/vision'
import { WALKABLE_TILES } from '../schemas'

/** 좌표 열쇠에서 걸음 수로의 대응표. 닿을 수 없는 칸은 아예 없다. */
export type DistanceField = ReadonlyMap<string, number>

/**
 * 목표들로부터의 최소 걸음 수를 방 전체에 채운다.
 *
 * 목표 칸은 통행 가능 여부를 묻지 않고 0 으로 깐다. APPROACH 의 목표가 곧 적이 선 칸
 * 이므로 그래야 길이 이어진다 — 마지막 한 걸음을 막는 것은 호출자의 몫이다.
 *
 * @param tiles 타일 통행 가능 여부를 읽을 것. 전투 중이면 WorldState 를 넘긴다.
 * @param goals 거리 0 이 되는 목표 칸들.
 * @param blocked 통행 불가로 취급할 추가 칸의 좌표 열쇠. 다른 엔티티가 선 자리 등.
 * @returns 좌표 열쇠에서 걸음 수로의 대응표.
 */
export function buildDistanceField(
  tiles: TileReader,
  goals: readonly Position[],
  blocked: ReadonlySet<string> = new Set(),
): DistanceField {
  const field = new Map<string, number>()
  const frontier: Position[] = []
  for (const goal of goals) {
    if (!field.has(formatPositionKey(goal))) {
      field.set(formatPositionKey(goal), 0)
      frontier.push(goal)
    }
  }

  let head = 0
  while (head < frontier.length) {
    const current = frontier[head] as Position
    head += 1
    const here = field.get(formatPositionKey(current)) as number
    for (const [dx, dy] of STEP_OFFSETS) {
      const step: Position = { x: current.x + dx, y: current.y + dy }
      const key = formatPositionKey(step)
      if (field.has(key) || blocked.has(key)) {
        continue
      }
      if (!WALKABLE_TILES.has(tiles.getTile(step.x, step.y))) {
        continue
      }
      field.set(key, here + 1)
      frontier.push(step)
    }
  }
  return field
}

/**
 * 거리장을 따라 한 칸 내려간다.
 *
 * 같은 거리의 이웃이 여럿이면 STEP_OFFSETS 순서에서 먼저 오는 쪽을 고른다. 순서를
 * 고정하지 않으면 같은 시드가 다른 경로를 내 리플레이가 깨진다 (R5).
 *
 * @param field buildDistanceField 가 만든 거리장.
 * @param origin 현재 위치.
 * @returns 한 걸음 나아간 좌표. 이미 목표이거나 길이 없으면 undefined.
 */
export function findNextStep(field: DistanceField, origin: Position): Position | undefined {
  const here = field.get(formatPositionKey(origin))
  if (here === undefined || here === 0) {
    return undefined
  }
  for (const [dx, dy] of STEP_OFFSETS) {
    const step: Position = { x: origin.x + dx, y: origin.y + dy }
    if (field.get(formatPositionKey(step)) === here - 1) {
      return step
    }
  }
  return undefined
}
