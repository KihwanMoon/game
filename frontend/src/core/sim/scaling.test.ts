/**
 * 층 깊이 스케일 대조 — `tests/test_scaling.py` 의 짝.
 *
 * 골든 리플레이가 층 2~3 케이스로 결과를 이미 고정하지만, 어긋났을 때 그것만으로는
 * "어느 층에서 몇을 곱했는가" 가 로그 3천 줄 속에 묻힌다. 여기서 산술만 따로 못박아
 * 두면 실패 메시지가 곧 원인이 된다.
 */
import { describe, expect, it } from 'vitest'

import { BALANCE, ROOM_TEMPLATES } from '../resources'
import { buildEngine, parseBalance } from '../services/runBattle'
import { FIRST_FLOOR } from '../schemas'
import {
  DEFAULT_FLOOR_SCALE,
  buildFloorScale,
  calculateDepthBonusPct,
  calculateScaledStat,
  getScaledEnemyStats,
} from './scaling'
import { calculateScaledAttack } from './pressure'

const RUSHER_HP = 40
const RUSHER_ATTACK = 8
const DEEP_FLOOR = 3
const STALL_TICKS = 100

const BALANCE_DATA = parseBalance(BALANCE)

/**
 * id 로 룸 템플릿을 찾는다.
 *
 * @param roomId 찾을 방 id.
 * @returns 찾은 템플릿.
 * @throws 그 id 의 템플릿이 없는 경우.
 */
function findRoom(roomId: string) {
  const found = ROOM_TEMPLATES.find((one) => one.templateId === roomId)
  if (found === undefined) {
    throw new Error(`룸 템플릿이 없다: ${roomId}`)
  }
  return found
}

describe('층 깊이 스케일', () => {
  it('balance.json 의 floor_scale 을 읽는다', () => {
    const scale = buildFloorScale(BALANCE_DATA.floorScale)
    expect(scale.hpPctPerFloor).toBeGreaterThan(0)
    expect(scale.attackPctPerFloor).toBeGreaterThan(0)
  })

  it('절이 없으면 기본값으로 떨어진다', () => {
    expect(buildFloorScale(undefined)).toEqual(DEFAULT_FLOOR_SCALE)
  })

  it('음수 퍼센트는 거부한다', () => {
    // 층이 깊어질수록 적이 약해지면 층 진행이 난이도가 아니라 보상이 된다.
    expect(() => buildFloorScale({ enemy_hp_pct_per_floor: -1 })).toThrow(/0 이상/)
  })

  it('층 1 이 기준이라 아무것도 곱하지 않는다', () => {
    expect(calculateDepthBonusPct(25, FIRST_FLOOR)).toBe(0)
    expect(calculateScaledStat(RUSHER_HP, 25, FIRST_FLOOR)).toBe(RUSHER_HP)
  })

  it('정수 내림으로 접는다 (R5)', () => {
    // 부동소수를 쓰면 플랫폼마다 결과가 갈려 리플레이가 깨진다.
    expect(calculateScaledStat(RUSHER_ATTACK, 20, DEEP_FLOOR)).toBe(11)
    expect(Number.isInteger(calculateScaledStat(7, 20, DEEP_FLOOR))).toBe(true)
  })

  it('최대 HP 와 공격력 두 축을 각각 스케일한다', () => {
    const scaled = getScaledEnemyStats(
      { hp_max: RUSHER_HP, attack: RUSHER_ATTACK },
      buildFloorScale(BALANCE_DATA.floorScale),
      DEEP_FLOOR,
    )
    expect(scaled).toEqual({ hpMax: 60, attack: 11 })
  })

  it('방 배치가 층 스케일을 거친다', () => {
    const template = findRoom('open_field')
    const shallow = buildEngine({ template, balance: BALANCE_DATA, seed: 1, floor: FIRST_FLOOR })
    const deep = buildEngine({ template, balance: BALANCE_DATA, seed: 1, floor: DEEP_FLOOR })
    const weak = shallow.state.entities.get('goblin_rusher_0')
    const strong = deep.state.entities.get('goblin_rusher_0')
    expect([weak?.hpMax, weak?.attack]).toEqual([RUSHER_HP, RUSHER_ATTACK])
    expect([strong?.hpMax, strong?.attack]).toEqual([60, 11])
    // 스케일은 최대 HP 를 올리는 것이지 다친 채로 시작시키는 것이 아니다.
    expect(strong?.hp).toBe(strong?.hpMax)
  })

  it('추격자도 같은 기준으로 선다', () => {
    const engine = buildEngine({
      template: findRoom('open_field'),
      balance: BALANCE_DATA,
      seed: 1,
      floor: DEEP_FLOOR,
    })
    const hunter = engine.pressure.createHunter(engine.state)
    expect([hunter?.hpMax, hunter?.attack]).toEqual([60, 11])
  })

  it('층 깊이와 층 체류 스케일은 곱해진다', () => {
    // 체류 압력이 "지금 이 적이 가진 힘의 몇 %" 여야 깊은 층에서 희석되지 않는다.
    const engine = buildEngine({
      template: findRoom('open_field'),
      balance: BALANCE_DATA,
      seed: 1,
      floor: DEEP_FLOOR,
    })
    engine.pressure.floorTicks = STALL_TICKS
    const bonusPct = engine.pressure.applyScale(engine.state)
    const depthScaled = calculateScaledStat(RUSHER_ATTACK, 20, DEEP_FLOOR)
    expect(engine.state.entities.get('goblin_rusher_0')?.attack).toBe(
      calculateScaledAttack(depthScaled, bonusPct),
    )
  })

  it('플레이어는 층 스케일 대상이 아니다', () => {
    // floor_scale 은 enemy_* 다. 양쪽이 함께 오르면 층 진행의 압력이 0 이 된다.
    const template = findRoom('open_field')
    const shallow = buildEngine({ template, balance: BALANCE_DATA, seed: 1, floor: FIRST_FLOOR })
    const deep = buildEngine({ template, balance: BALANCE_DATA, seed: 1, floor: DEEP_FLOOR })
    const before = shallow.state.entities.get('player')
    const after = deep.state.entities.get('player')
    expect([before?.hpMax, before?.attack, before?.defense]).toEqual([
      after?.hpMax,
      after?.attack,
      after?.defense,
    ])
  })
})
