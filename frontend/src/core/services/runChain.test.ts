/**
 * 층 사슬 대조 (게이트 G3).
 *
 * **연쇄는 방 하나짜리 골든이 잡지 못하는 것을 잡는다.** 시드 분기, HP·포션 인계, 층
 * 압력 유지 — 셋 다 방 사이에서만 일어나므로 단일 방 대조로는 검증되지 않는다. 두 코어가
 * 두 번째 방부터 갈라져도 `sim_golden` 은 침묵한다.
 */
import { describe, expect, it } from 'vitest'

import golden from '../golden/chain_golden.json'
import { BALANCE, BLOCK_CATALOG, ENEMY_RULESETS, G0_RULESETS, ROOM_TEMPLATES } from '../resources'
import { parseBalance } from './runBattle'
import { SEED_STRIDE, runRoomChain } from './runChain'

interface RoomRow {
  readonly outcome: string
  readonly ticks: number
  readonly player_hp: number
}

interface ChainRow {
  readonly ruleset_id: string | null
  readonly room_ids: readonly string[]
  readonly seed: number
  readonly cleared_rooms: number
  readonly outcome: string
  readonly total_ticks: number
  readonly player_hp: number
  readonly per_room: readonly RoomRow[]
}

const BALANCE_DATA = parseBalance(BALANCE)
const BY_ID = new Map(ROOM_TEMPLATES.map((template) => [template.templateId, template]))

/**
 * 골든 한 줄을 그대로 재현한다.
 *
 * @param row 기준 줄.
 * @returns 연쇄 결과.
 */
function runGoldenRow(row: ChainRow): ReturnType<typeof runRoomChain> {
  const templates = row.room_ids.map((roomId) => {
    const template = BY_ID.get(roomId)
    if (template === undefined) {
      throw new Error(`없는 방이다: ${roomId}`)
    }
    return template
  })
  const ruleset = row.ruleset_id === null ? undefined : G0_RULESETS.get(row.ruleset_id)
  if (row.ruleset_id !== null && ruleset === undefined) {
    throw new Error(`없는 규칙표다: ${row.ruleset_id}`)
  }
  return runRoomChain({
    templates,
    balance: BALANCE_DATA,
    catalog: BLOCK_CATALOG,
    ...(ruleset === undefined ? {} : { playerRuleset: ruleset }),
    enemyRulesets: ENEMY_RULESETS,
    seed: row.seed,
  })
}

describe('층 사슬 — 파이썬 대조', () => {
  const rows = golden.chains as readonly ChainRow[]

  it('★ 골든에 사례가 실려 있다', () => {
    expect(rows.length).toBeGreaterThan(0)
  })

  it('★ 시드 분기 간격이 파이썬과 같다 — 다르면 두 번째 방부터 갈린다', () => {
    expect(SEED_STRIDE).toBe(golden.seed_stride)
  })

  for (const [index, row] of rows.entries()) {
    it(`★ 사례 ${String(index)} — ${row.ruleset_id ?? '폴백'} · ${row.room_ids.join('→')}`, () => {
      const result = runGoldenRow(row)
      expect(result.outcome).toBe(row.outcome)
      expect(result.clearedRooms).toBe(row.cleared_rooms)
      expect(result.totalTicks).toBe(row.total_ticks)
      expect(result.playerHp).toBe(row.player_hp)
      expect(result.perRoom.map((room) => room.ticks)).toEqual(row.per_room.map((r) => r.ticks))
      expect(result.perRoom.map((room) => room.playerHp)).toEqual(
        row.per_room.map((r) => r.player_hp),
      )
    })
  }

  it('★ HP 가 방을 넘어 이어진다 — 방마다 회복되면 연쇄가 뜻을 잃는다', () => {
    // 같은 방을 세 번 도는 사례에서 체력이 단조 감소해야 한다.
    const carry = rows.find((row) => new Set(row.room_ids).size === 1 && row.cleared_rooms >= 3)
    expect(carry).toBeDefined()
    const hps = runGoldenRow(carry as ChainRow).perRoom.map((room) => room.playerHp)
    expect(hps.length).toBeGreaterThanOrEqual(3)
    for (let index = 1; index < hps.length; index += 1) {
      expect(hps[index]).toBeLessThan(hps[index - 1] as number)
    }
  })
})
