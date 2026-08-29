/**
 * 격자·길찾기·시야의 골든 테스트 (TDD §10, 게이트 G3).
 *
 * "그럴듯한 경로인가" 가 아니라 "파이썬 코어와 같은 답인가" 를 본다. 기준값은
 * `scripts/export_grid_golden.py` 가 파이썬 코어에서 뽑아 둔 것이며, 여기서 값을 고쳐
 * 통과시키는 것은 검증을 지우는 것과 같다 — 기준을 바꾸려면 파이썬 쪽을 먼저 본다.
 *
 * 좌표 목록은 **순서까지** 대조한다. 같은 집합을 다른 순서로 내는 구현은 같은 구현이
 * 아니다 — 거리장의 내리막과 엄폐의 동점이 정확히 그 순서로 갈리기 때문이다 (R5).
 * 그래서 항목마다 따로 단언하지 않고 목록을 통째로 비교한다.
 */

import { describe, expect, it } from 'vitest'

import goldenRaw from '../golden/grid_golden.json'
import { buildDistanceField, findNextStep } from '../pathfinding/distanceField'
import { ROOM_TEMPLATES } from '../resources'
import { TILE_WALL, getRoomTile } from '../schemas'

import {
  NEIGHBOR_OFFSETS,
  STEP_OFFSETS,
  type Position,
  formatPositionKey,
  getManhattanDistance,
  iterNeighbors,
  iterSteps,
  parsePositionKey,
} from './geometry'
import {
  VisionCache,
  VisionGrid,
  buildVisibilityMap,
  calculateCoverDistance,
  checkCover,
  checkExposure,
  checkLineOfSight,
  checkVisibility,
  findCoverPositions,
  findNearestCover,
  listVisiblePositions,
} from './vision'

interface GoldenVisibility {
  readonly origin: string
  readonly max_range: number | null
  readonly visible: readonly string[]
}

interface GoldenExposure {
  readonly position: string
  readonly is_exposed: boolean
  readonly is_covered: boolean
}

interface GoldenNearest {
  readonly origin: string
  readonly position: string | null
  readonly distance: number
  readonly position_with_occupied: string | null
  readonly distance_with_occupied: number
}

interface GoldenCover {
  readonly threats: readonly string[]
  readonly occupied: readonly string[]
  readonly positions: readonly string[]
  readonly positions_with_occupied: readonly string[]
  readonly nearest: readonly GoldenNearest[]
}

interface GoldenDistanceField {
  readonly goals: readonly string[]
  readonly blocked: readonly string[]
  readonly entries: readonly { readonly cell: string; readonly distance: number }[]
  readonly next_steps: readonly { readonly origin: string; readonly step: string | null }[]
}

interface GoldenGrid {
  readonly name: string
  readonly width: number
  readonly height: number
  readonly tiles: readonly (readonly number[])[]
  readonly visibility: readonly GoldenVisibility[]
  readonly exposure: readonly GoldenExposure[]
  readonly cover: GoldenCover
  readonly distance_fields: readonly GoldenDistanceField[]
}

interface GoldenDocument {
  readonly geometry: {
    readonly step_offsets: readonly (readonly number[])[]
    readonly neighbor_offsets: readonly (readonly number[])[]
    readonly manhattan: readonly { origin: string; target: string; distance: number }[]
    readonly steps: readonly { origin: string; cells: readonly string[] }[]
    readonly neighbors: readonly { origin: string; cells: readonly string[] }[]
  }
  readonly grids: readonly GoldenGrid[]
}

// JSON 리터럴 추론은 `position` 이 어떤 방에서는 늘 문자열이고 다른 방에서는 늘 null 이라는
// 이유로 배열 타입을 합집합으로 쪼갠다. 그러면 같은 모양의 방들을 한 루프로 돌 수 없다.
// 여기서 한 번만 형태를 선언하고, 그 선언이 맞는지는 아래 단언들이 곧바로 검증한다.
const goldenDocument = goldenRaw as unknown as GoldenDocument

/** 골든의 타일 배열을 그대로 읽는 격자. 룸 로더를 거치지 않아 대조가 독립적이다. */
function createGoldenGrid(entry: GoldenGrid): VisionGrid {
  return new VisionGrid(
    { getTile: (x: number, y: number): number => entry.tiles[y]?.[x] ?? TILE_WALL },
    entry.width,
    entry.height,
  )
}

function listKeys(positions: readonly Position[]): string[] {
  return positions.map(formatPositionKey)
}

function parseKeys(keys: readonly string[]): Position[] {
  return keys.map(parsePositionKey)
}

function formatOptionalKey(position: Position | undefined): string | null {
  return position === undefined ? null : formatPositionKey(position)
}

describe('geometry', () => {
  it('이동 4방향의 순서가 파이썬과 같다', () => {
    expect(STEP_OFFSETS.map((offset) => [...offset])).toEqual(
      goldenDocument.geometry.step_offsets.map((offset) => [...offset]),
    )
  })

  it('포위 8방향의 순서가 파이썬과 같다', () => {
    expect(NEIGHBOR_OFFSETS.map((offset) => [...offset])).toEqual(
      goldenDocument.geometry.neighbor_offsets.map((offset) => [...offset]),
    )
  })

  it('이동 방향과 포위 방향은 서로 다른 목록이다', () => {
    expect(STEP_OFFSETS.length).not.toBe(NEIGHBOR_OFFSETS.length)
  })

  it('맨해튼 거리가 파이썬과 같다', () => {
    const actual = goldenDocument.geometry.manhattan.map((probe) => ({
      origin: probe.origin,
      target: probe.target,
      distance: getManhattanDistance(parsePositionKey(probe.origin), parsePositionKey(probe.target)),
    }))
    expect(actual).toEqual(goldenDocument.geometry.manhattan)
  })

  it('이웃 4칸이 순서까지 같다', () => {
    const actual = goldenDocument.geometry.steps.map((probe) => ({
      origin: probe.origin,
      cells: listKeys(iterSteps(parsePositionKey(probe.origin))),
    }))
    expect(actual).toEqual(goldenDocument.geometry.steps.map((probe) => ({ ...probe })))
  })

  it('이웃 8칸이 순서까지 같다', () => {
    const actual = goldenDocument.geometry.neighbors.map((probe) => ({
      origin: probe.origin,
      cells: listKeys(iterNeighbors(parsePositionKey(probe.origin))),
    }))
    expect(actual).toEqual(goldenDocument.geometry.neighbors.map((probe) => ({ ...probe })))
  })

  it('좌표 열쇠는 왕복해도 같다', () => {
    const position = { x: -3, y: 11 }
    expect(parsePositionKey(formatPositionKey(position))).toEqual(position)
  })

  it('좌표 열쇠가 아닌 문자열은 거부한다', () => {
    expect(() => parsePositionKey('1')).toThrow(/좌표 열쇠/)
    expect(() => parsePositionKey('a,b')).toThrow(/좌표 열쇠/)
  })
})

describe('룸 템플릿', () => {
  const roomGrids = goldenDocument.grids.filter((entry) =>
    ROOM_TEMPLATES.some((template) => template.templateId === entry.name),
  )

  it('파이썬 로더와 같은 방을 읽었다', () => {
    expect(roomGrids.length).toBe(ROOM_TEMPLATES.length)
    for (const entry of roomGrids) {
      const template = ROOM_TEMPLATES.find((item) => item.templateId === entry.name)
      expect(template?.width).toBe(entry.width)
      expect(template?.height).toBe(entry.height)
      expect(template?.tiles.map((row) => [...row])).toEqual(entry.tiles.map((row) => [...row]))
    }
  })

  it('템플릿을 감싼 격자가 골든 격자와 같은 답을 낸다', () => {
    for (const entry of roomGrids) {
      const template = ROOM_TEMPLATES.find((item) => item.templateId === entry.name)
      if (template === undefined) {
        throw new Error(`템플릿이 없다: ${entry.name}`)
      }
      const fromTemplate = new VisionGrid(
        { getTile: (x: number, y: number): number => getRoomTile(template, x, y) },
        template.width,
        template.height,
      )
      const probe = parsePositionKey(entry.visibility[0]?.origin ?? '1,1')
      expect(listKeys(listVisiblePositions(buildVisibilityMap(fromTemplate, probe)))).toEqual(
        listKeys(listVisiblePositions(buildVisibilityMap(createGoldenGrid(entry), probe))),
      )
    }
  })
})

describe.each(goldenDocument.grids.map((entry) => [entry.name, entry] as const))(
  '격자 %s',
  (_name, entry) => {
    const grid = createGoldenGrid(entry)
    const threats = parseKeys(entry.cover.threats)
    const occupied = new Set(entry.cover.occupied)

    it('가시성 맵이 사거리별로 파이썬과 같다', () => {
      const actual = entry.visibility.map((probe) => ({
        origin: probe.origin,
        max_range: probe.max_range,
        visible: listKeys(
          listVisiblePositions(
            buildVisibilityMap(grid, parsePositionKey(probe.origin), probe.max_range),
          ),
        ),
      }))
      expect(actual).toEqual(entry.visibility.map((probe) => ({ ...probe, visible: [...probe.visible] })))
    })

    it('checkVisibility 가 맵 목록과 같은 답을 낸다', () => {
      for (const probe of entry.visibility) {
        const visionMap = buildVisibilityMap(
          grid,
          parsePositionKey(probe.origin),
          probe.max_range,
        )
        const expected = new Set(probe.visible)
        for (let y = 0; y < entry.height; y += 1) {
          for (let x = 0; x < entry.width; x += 1) {
            expect(checkVisibility(visionMap, { x, y })).toBe(expected.has(`${x},${y}`))
          }
        }
      }
    })

    it('LOS 는 방 전체에서 대칭이다', () => {
      for (const probe of entry.visibility) {
        const origin = parsePositionKey(probe.origin)
        for (let y = 0; y < entry.height; y += 1) {
          for (let x = 0; x < entry.width; x += 1) {
            const target = { x, y }
            expect(checkLineOfSight(grid, origin, target)).toBe(
              checkLineOfSight(grid, target, origin),
            )
          }
        }
      }
    })

    it('노출·엄폐 판정이 파이썬과 같다', () => {
      const actual = entry.exposure.map((probe) => {
        const position = parsePositionKey(probe.position)
        return {
          position: probe.position,
          is_exposed: checkExposure(grid, position, threats),
          is_covered: checkCover(grid, position, threats),
        }
      })
      expect(actual).toEqual(entry.exposure.map((probe) => ({ ...probe })))
    })

    it('엄폐 후보가 행 우선 순서까지 같다', () => {
      expect(listKeys(findCoverPositions(grid, threats))).toEqual([...entry.cover.positions])
      expect(listKeys(findCoverPositions(grid, threats, occupied))).toEqual([
        ...entry.cover.positions_with_occupied,
      ])
    })

    it('가장 가까운 엄폐 칸의 동점 처리가 같다', () => {
      const actual = entry.cover.nearest.map((probe) => {
        const origin = parsePositionKey(probe.origin)
        return {
          origin: probe.origin,
          position: formatOptionalKey(findNearestCover(grid, origin, threats)),
          distance: calculateCoverDistance(grid, origin, threats),
          position_with_occupied: formatOptionalKey(
            findNearestCover(grid, origin, threats, occupied),
          ),
          distance_with_occupied: calculateCoverDistance(grid, origin, threats, occupied),
        }
      })
      expect(actual).toEqual(entry.cover.nearest.map((probe) => ({ ...probe })))
    })

    it('거리장의 BFS 방문 순서와 값이 같다', () => {
      for (const probe of entry.distance_fields) {
        const field = buildDistanceField(
          grid,
          parseKeys(probe.goals),
          new Set(probe.blocked),
        )
        const actual = [...field].map(([cell, distance]) => ({ cell, distance }))
        expect(actual).toEqual(probe.entries.map((item) => ({ ...item })))
      }
    })

    it('거리장 내리막 한 걸음이 같다', () => {
      for (const probe of entry.distance_fields) {
        const field = buildDistanceField(
          grid,
          parseKeys(probe.goals),
          new Set(probe.blocked),
        )
        const actual = probe.next_steps.map((step) => ({
          origin: step.origin,
          step: formatOptionalKey(findNextStep(field, parsePositionKey(step.origin))),
        }))
        expect(actual).toEqual(probe.next_steps.map((step) => ({ ...step })))
      }
    })
  },
)

describe('VisionCache', () => {
  const entry = goldenDocument.grids.find((item) => item.name === 'pillars')
  if (entry === undefined) {
    throw new Error('골든에 pillars 격자가 없다')
  }
  const grid = createGoldenGrid(entry)

  it('위치가 그대로면 같은 맵을 돌려준다', () => {
    const cache = new VisionCache(grid)
    const first = cache.register('archer', { x: 10, y: 2 })
    expect(cache.refresh('archer', { x: 10, y: 2 })).toBe(first)
    expect(cache.refresh('archer', { x: 10, y: 3 })).not.toBe(first)
  })

  it('등록되지 않은 관측자는 오류다 — "안 보인다" 와 구분한다', () => {
    const cache = new VisionCache(grid)
    expect(cache.read('ghost')).toBeUndefined()
    expect(() => cache.check('ghost', { x: 1, y: 1 })).toThrow(/가시성 맵이 없는/)
  })

  it('drop 한 관측자는 다시 없는 상태가 된다', () => {
    const cache = new VisionCache(grid)
    cache.register('archer', { x: 10, y: 2 })
    cache.drop('archer')
    expect(cache.read('archer')).toBeUndefined()
    cache.drop('archer')
  })

  it('사거리 상한이 맵에 반영된다', () => {
    const limited = new VisionCache(grid, 4).register('archer', { x: 1, y: 1 })
    const expected = entry.visibility.find(
      (probe) => probe.origin === '1,1' && probe.max_range === 4,
    )
    expect(expected).toBeDefined()
    expect(listKeys(listVisiblePositions(limited))).toEqual([...(expected?.visible ?? [])])
  })

  it('캐시의 판정이 직접 계산과 일치한다', () => {
    const cache = new VisionCache(grid)
    const origin = { x: 10, y: 2 }
    cache.register('archer', origin)
    for (let y = 0; y < entry.height; y += 1) {
      for (let x = 0; x < entry.width; x += 1) {
        expect(cache.check('archer', { x, y })).toBe(checkLineOfSight(grid, origin, { x, y }))
      }
    }
  })
})
