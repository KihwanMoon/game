/**
 * 더해서 세우는 자리 (설계/6_몬스터, G3).
 *
 * **파이썬과 글자 그대로 같은 규칙이어야 한다.** 두 코어가 같은 시드에서 같은 판을
 * 내야 하고, 자리를 다르게 고르면 그 순간 갈린다.
 */
import { describe, expect, it } from 'vitest'

import { computeFarRank, findFarSpot, listExtraSlots } from './roomExtras'
import type { RoomTemplate } from '../schemas/room'

/** 5×3 빈 방. 가운데 한 칸만 벽이다. */
const ROOM = {
  templateId: 'probe',
  purpose: 'fight',
  tiles: [
    [0, 0, 0, 0, 0],
    [0, 0, 1, 0, 0],
    [0, 0, 0, 0, 0],
  ],
  playerSpawn: { x: 0, y: 0 },
  enemySpawns: [],
  minFloor: 1,
  width: 5,
  height: 3,
} as unknown as RoomTemplate

describe('computeFarRank', () => {
  it('멀수록 앞이다 — 첫 항이 거리의 음수다', () => {
    expect(computeFarRank({ x: 4, y: 2 }, { x: 0, y: 0 })[0]).toBeLessThan(
      computeFarRank({ x: 1, y: 1 }, { x: 0, y: 0 })[0],
    )
  })

  it('★ 체비셰프다 — 대각이 열려도 「몇 걸음인가」가 그 값이다', () => {
    expect(computeFarRank({ x: 3, y: 3 }, { x: 0, y: 0 })[0]).toBe(-3)
  })

  it('같으면 위·왼쪽이 이긴다 — 순서를 못 박아야 두 코어가 같은 칸을 고른다', () => {
    const [, y, x] = computeFarRank({ x: 2, y: 1 }, { x: 0, y: 0 })
    expect([y, x]).toEqual([1, 2])
  })
})

describe('findFarSpot', () => {
  it('★ 플레이어에게서 가장 먼 빈 칸을 고른다', () => {
    // 코앞에 세우면 규칙표가 손쓸 새 없이 첫 틱에 맞는다 — 더하는 것이 곧 처형이 된다.
    // (4,0) 과 (4,2) 는 체비셰프 거리가 같고, 동점이면 위쪽이 이긴다.
    expect(findFarSpot(ROOM, new Set(['0,0']), { x: 0, y: 0 })).toEqual({ x: 4, y: 0 })
  })

  it('찬 칸은 안 고른다', () => {
    const taken = new Set(['0,0', '4,0'])
    // 다음으로 먼 칸은 같은 거리(4)의 그다음 줄이다.
    expect(findFarSpot(ROOM, taken, { x: 0, y: 0 })).toEqual({ x: 4, y: 1 })
  })

  it('★ 벽에는 안 선다', () => {
    const spot = findFarSpot(ROOM, new Set(['0,0']), { x: 2, y: 1 })
    expect(spot).not.toEqual({ x: 2, y: 1 })
  })

  it('빈 칸이 없으면 안 세운다', () => {
    const all = new Set<string>()
    for (let y = 0; y < 3; y += 1) {
      for (let x = 0; x < 5; x += 1) {
        all.add(`${String(x)},${String(y)}`)
      }
    }
    expect(findFarSpot(ROOM, all, { x: 0, y: 0 })).toBeUndefined()
  })
})

describe('listExtraSlots', () => {
  it('방 배치가 안 쓴 것만 낸다', () => {
    const overrides = new Map([
      ['goblin_rusher_0', {}],
      ['doppel_7', {}],
    ])
    expect(listExtraSlots(overrides, new Set(['goblin_rusher_0']))).toEqual(['doppel_7'])
  })

  it('★ 정렬해서 낸다 — 순회 순서가 판을 흔들면 안 된다 (R5)', () => {
    const overrides = new Map([
      ['doppel_9', {}],
      ['doppel_1', {}],
      ['doppel_5', {}],
    ])
    expect(listExtraSlots(overrides, new Set())).toEqual(['doppel_1', 'doppel_5', 'doppel_9'])
  })
})
