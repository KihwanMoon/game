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
  calculateScaledStat,
  getScaledEnemyStats,
  getShiftedInitiative,
} from './scaling'
import { calculateScaledAttack } from './pressure'

const RUSHER_HP = 40
const RUSHER_ATTACK = 8
const RUSHER_INITIATIVE = 60
const DEEP_FLOOR = 3
const STALL_TICKS = 100

const BALANCE_DATA = parseBalance(BALANCE)
/** 밸런스의 층 배율. **숫자를 박지 않는다** — 박으면 배율을 고칠 때마다 무관하게 빨개진다. */
const DEPTH_MULT = buildFloorScale(BALANCE_DATA.floorScale).multPctPerFloor
/** 깊은 층의 몽둥이 도깨비. 파이썬 `build_deep_rusher` 와 같은 계산이다. */
const DEEP_RUSHER = {
  hpMax: calculateScaledStat(RUSHER_HP, DEPTH_MULT, DEEP_FLOOR),
  attack: calculateScaledStat(RUSHER_ATTACK, DEPTH_MULT, DEEP_FLOOR),
}

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
    expect(scale.multPctPerFloor).toBeGreaterThan(100)
  })

  it('절이 없으면 기본값으로 떨어진다', () => {
    expect(buildFloorScale(undefined)).toEqual(DEFAULT_FLOOR_SCALE)
  })

  it('약해지는 배율은 거부한다', () => {
    // 층이 깊어질수록 적이 약해지면 층 진행이 난이도가 아니라 보상이 된다.
    expect(() => buildFloorScale({ enemy_mult_pct_per_floor: 90 })).toThrow(/100 이상/)
  })

  it('층 1 이 기준이라 아무것도 곱하지 않는다', () => {
    expect(calculateScaledStat(100, 110, 2)).toBe(110)
    expect(calculateScaledStat(RUSHER_HP, 110, FIRST_FLOOR)).toBe(RUSHER_HP)
  })

  it('정수로 계산하고 끝에서 한 번만 내린다 (R5, e15)', () => {
    // 부동소수를 쓰면 플랫폼마다 결과가 갈려 리플레이가 깨진다. 9 × 1.21 = 10.89 → 10.
    expect(calculateScaledStat(9, 110, DEEP_FLOOR)).toBe(10)
    expect(Number.isInteger(calculateScaledStat(7, 110, DEEP_FLOOR))).toBe(true)
    // 파이썬 `test_depth_compounds_per_floor` 와 같은 값이다.
    expect(calculateScaledStat(100, 110, 10)).toBe(235)
  })

  it('★ 작은 값도 자란다 (e15) — 층마다 내리면 공격 8 × 105% 가 20장까지 8 이었다', () => {
    expect(calculateScaledStat(8, 105, 11)).toBe(13)
  })

  it('★ 선공은 층이 아니라 플레이어를 따라 옮긴다 (G3)', () => {
    // 파이썬 `test_initiative_follows_the_player_not_the_floor` 와 같은 질문이다.
    // 안 옮기면 민첩을 올린 캐릭터에게 모든 적이 느려지고, `적 선공 > 내 선공` 은
    // 영영 거짓인 항이 된다 — 그것을 읽는 규칙은 cpu 만 먹는다 (2026-09-14 실측).
    const stats = { hp_max: RUSHER_HP, attack: RUSHER_ATTACK, initiative: RUSHER_INITIATIVE }
    const flat = buildFloorScale(BALANCE_DATA.floorScale)
    expect(getScaledEnemyStats(stats, flat, DEEP_FLOOR).initiative).toBe(RUSHER_INITIATIVE)
    const shifted = buildFloorScale(BALANCE_DATA.floorScale, 50)
    expect(getScaledEnemyStats(stats, shifted, FIRST_FLOOR).initiative).toBe(RUSHER_INITIATIVE + 50)
    expect(getShiftedInitiative(5, buildFloorScale(BALANCE_DATA.floorScale, -99))).toBe(0)
  })

  it('최대 HP 와 공격력 두 축을 각각 스케일한다', () => {
    const scaled = getScaledEnemyStats(
      { hp_max: RUSHER_HP, attack: RUSHER_ATTACK, initiative: RUSHER_INITIATIVE },
      buildFloorScale(BALANCE_DATA.floorScale),
      DEEP_FLOOR,
    )
    // **선공은 층으로 안 자란다.** 자라는 것은 HP 와 공격력뿐이고, 선공이 움직이는
    // 축은 층이 아니라 플레이어다 (아래 시험).
    expect(scaled).toEqual({ ...DEEP_RUSHER, initiative: RUSHER_INITIATIVE })
    expect(scaled.hpMax).toBeGreaterThan(RUSHER_HP)
    expect(scaled.attack).toBeGreaterThan(RUSHER_ATTACK)
  })

  it('방 배치가 층 스케일을 거친다', () => {
    const template = findRoom('open_field')
    const shallow = buildEngine({ template, balance: BALANCE_DATA, seed: 1, floor: FIRST_FLOOR })
    const deep = buildEngine({ template, balance: BALANCE_DATA, seed: 1, floor: DEEP_FLOOR })
    const weak = shallow.state.entities.get('goblin_rusher_0')
    const strong = deep.state.entities.get('goblin_rusher_0')
    expect([weak?.hpMax, weak?.attack]).toEqual([RUSHER_HP, RUSHER_ATTACK])
    expect([strong?.hpMax, strong?.attack]).toEqual([DEEP_RUSHER.hpMax, DEEP_RUSHER.attack])
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
    expect([hunter?.hpMax, hunter?.attack]).toEqual([DEEP_RUSHER.hpMax, DEEP_RUSHER.attack])
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
    const depthScaled = calculateScaledStat(RUSHER_ATTACK, DEPTH_MULT, DEEP_FLOOR)
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
