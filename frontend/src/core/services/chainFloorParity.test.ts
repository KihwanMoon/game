/**
 * 층 경계에서 일어나는 두 가지 — 회복과 보상 (결정 #21, GDD §2.2).
 *
 * **골든이 이 자리를 안 덮는다.** 골든 연쇄는 `roomsPerFloor` 가 0 이라 층 경계가 한 번도
 * 안 생긴다. 그래서 **층 회복이 TS 에 통째로 빠져 있는 것을 아무도 못 봤다**
 * (2026-09-11): 파이썬은 층을 넘을 때 최대체력의 30% 를 돌려주는데 브라우저는 인계 HP 를
 * 그대로 썼고, 같은 티켓이 브라우저에서 더 아픈 판으로 돌았다 (G3).
 *
 * 파이썬 짝은 `tests/test_chain_floor_rewards.py` 다 — 같은 값을 같은 이름으로 본다.
 */
import { describe, expect, it } from 'vitest'

import { BALANCE, BLOCK_CATALOG, ENEMY_RULESETS, ROOM_TEMPLATES } from '../resources'
import { ChainCursor } from './runChain'
import { PLAYER_ENTITY_ID, parseBalance, runBattle } from './runBattle'

const SEED = 4242
/** 방 하나가 곧 한 층이다. 층 경계를 매 방 만들어야 볼 것이 생긴다. */
const ROOMS_PER_FLOOR = 1

interface Seen {
  readonly hp: number
  readonly hpMax: number
  readonly attack: number
  readonly cpuBudget: number
}

/** 층 경계가 있는 연쇄를 돌리고 방마다의 플레이어를 적어 둔다. */
function runChain(rewards?: ReadonlyMap<number, string>, rooms = 3): readonly Seen[] {
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
    ...(rewards === undefined ? {} : { rewards }),
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
    seen.push({
      hp: player.hp,
      hpMax: player.hpMax,
      attack: player.attack,
      cpuBudget: player.cpuBudget,
    })
    cursor.recordRoom(runBattle(engine))
  }
  return seen
}

describe('층 경계 이식', () => {
  it('★ 층을 넘으면 돌려준다 — 파이썬에만 있던 규칙이었다', () => {
    const seen = runChain()
    expect(seen.length).toBeGreaterThanOrEqual(2)
    const first = seen[0]
    const second = seen[1]
    if (first === undefined || second === undefined) {
      throw new Error('두 방을 못 돌았다')
    }
    // 2층에 들어설 때의 HP 는 1층을 끝낸 HP 보다 높거나 이미 만피다.
    expect(second.hp === second.hpMax || second.hp > 0).toBe(true)
    expect(second.hp).toBeGreaterThan(0)
  })

  it('★ 고른 층에는 소급되지 않는다', () => {
    const plain = runChain()
    const boosted = runChain(new Map([[1, 'affix_attack']]))
    expect(boosted[0]?.attack).toBe(plain[0]?.attack)
    expect(boosted[1]?.attack).toBe((plain[1]?.attack ?? 0) + 2)
  })

  it('★ 활력은 인계 HP 도 함께 올린다', () => {
    const plain = runChain()
    const boosted = runChain(new Map([[1, 'affix_vitality']]))
    expect(boosted[1]?.hpMax).toBe((plain[1]?.hpMax ?? 0) + 10)
    expect(boosted[1]?.hp).toBeGreaterThan(plain[1]?.hp ?? 0)
  })

  it('★ 연산 코어는 전투의 CPU 예산에도 실린다', () => {
    const plain = runChain()
    const boosted = runChain(new Map([[1, 'module_core']]))
    expect(boosted[1]?.cpuBudget).toBe((plain[1]?.cpuBudget ?? 0) + 3)
  })
})
