/**
 * 층을 넘을 때 돌려주는 회복 — `resolve_floor_heal` 의 이식 (결정 #21).
 *
 * **이 규칙이 브라우저에만 없었다** (2026-09-11). 파이썬 연쇄는 층을 넘을 때 최대체력의
 * 30% 를 돌려주는데 TS `ChainCursor` 는 인계 HP 를 그대로 썼다 — 같은 티켓이 브라우저
 * 에서는 더 아픈 판으로 돌았다는 뜻이고, 하강이 깊어질수록 벌어진다 (G3).
 *
 * **골든이 이 자리를 안 덮는다.** 골든 연쇄는 `roomsPerFloor` 가 0 이라 층 경계가 한 번도
 * 안 생긴다 — 층을 넘는 판이 골든에 하나도 없다.
 *
 * 파이썬 짝은 `tests/test_floor_heal_chain.py` 다 — 같은 값을 같은 이름으로 본다.
 */
import { describe, expect, it } from 'vitest'

import { BALANCE, BLOCK_CATALOG, ENEMY_RULESETS, ROOM_TEMPLATES } from '../resources'
import { ChainCursor } from './runChain'
import { PLAYER_ENTITY_ID, parseBalance, runBattle } from './runBattle'
import { readFloorHealPct, resolveFloorHeal } from './floorHeal'

const SEED = 4242
/** 방 하나가 곧 한 층이다. 층 경계를 매 방 만들어야 볼 것이 생긴다. */
const ROOMS_PER_FLOOR = 1

interface Seen {
  /** 그 방에 들어설 때의 HP. */
  readonly opened: number
  /** 그 방을 끝냈을 때의 HP. */
  readonly closed: number
  readonly hpMax: number
}

/** 층 경계가 있는 연쇄를 돌리고 방마다 들어설 때·끝낼 때의 HP 를 적어 둔다. */
function runChain(rooms = 3): readonly Seen[] {
  const template = ROOM_TEMPLATES.find((one) => one.templateId === 'open_field')
  if (template === undefined) {
    throw new Error('open_field 템플릿이 없다')
  }
  const cursor = new ChainCursor({
    templates: Array.from({ length: rooms }, () => template),
    balance: parseBalance(BALANCE),
    catalog: BLOCK_CATALOG,
    enemyRulesets: ENEMY_RULESETS,
    seed: SEED,
    roomsPerFloor: ROOMS_PER_FLOOR,
  })
  const seen: Seen[] = []
  for (let index = 0; index < rooms; index += 1) {
    const engine = cursor.buildNext()
    if (engine === undefined) {
      break
    }
    const player = engine.state.entities.get(PLAYER_ENTITY_ID)
    if (player === undefined) {
      throw new Error('플레이어가 없다')
    }
    const opened = player.hp
    const result = runBattle(engine)
    seen.push({ opened, closed: result.playerHp, hpMax: player.hpMax })
    cursor.recordRoom(result)
  }
  return seen
}

describe('층 회복 이식', () => {
  it('★ 다음 층은 「끝낸 HP + 최대치의 몇 퍼센트」로 연다', () => {
    const healPct = readFloorHealPct(parseBalance(BALANCE).floorScale)
    expect(healPct, '밸런스에 회복 퍼센트가 없다').toBeGreaterThan(0)
    const seen = runChain()
    expect(seen.length).toBeGreaterThanOrEqual(2)
    const first = seen[0]
    const second = seen[1]
    if (first === undefined || second === undefined) {
      throw new Error('두 방을 못 돌았다')
    }
    // **파이썬과 같은 식이다.** 정수 내림이라 마지막 자리까지 같아야 한다 (R5).
    expect(second.opened).toBe(resolveFloorHeal(first.closed, second.hpMax, healPct))
  })

  it('★ 최대치를 안 넘는다', () => {
    expect(resolveFloorHeal(95, 100, 30)).toBe(100)
  })

  it('★ 정수 내림이다 — 부동소수를 쓰면 두 코어가 마지막 자리에서 갈린다', () => {
    expect(resolveFloorHeal(10, 33, 30)).toBe(19)
  })

  it('★ 안 적혀 있으면 0 이다 — 모르면 안 준다', () => {
    expect(readFloorHealPct(undefined)).toBe(0)
    expect(resolveFloorHeal(10, 100, 0)).toBe(10)
  })
})
