/**
 * 스킬이 거는 예고가 두 코어에서 같이 도는가 (게이트 G3).
 *
 * **덫이었다가 대조가 됐다 (2026-09-09).** 파이썬이 `skills.json` 의 `telegraph` 를 읽어
 * 예고를 걸기 시작했을 때 TS 는 스킬 표조차 없었고, 그래서 「예고를 쓰는 스킬이 생기면
 * 운다」는 덫만 놓아 두었다. 이제 TS 도 같은 표를 읽으므로 실제로 대조한다.
 *
 * 골든에 안 기대는 이유는 골든이 이 경로를 하나도 안 덮기 때문이다 — 방어 태세가
 * 정확히 그 틈으로 조용히 갈려 있었다.
 */
import { describe, expect, it } from 'vitest'

import { BALANCE, ROOM_TEMPLATES } from '../resources'
import { PLAYER_ENTITY_ID, buildEngine, parseBalance } from '../services/runBattle'
import { createPlannedAction } from './plan'
import { CANCEL_BY_HIT } from './telegraph'

const METEOR = 'METEOR'

function buildProbe(telegraph: number, switches: Record<string, boolean> = {}) {
  const balance = parseBalance(BALANCE)
  const template = ROOM_TEMPLATES.find((one) => one.templateId === 'open_field')
  if (template === undefined) {
    throw new Error('open_field 템플릿이 없다')
  }
  const engine = buildEngine({ template, balance, seed: 3 })
  const skills = engine.config.skills as Map<string, unknown>
  skills.set(METEOR, {
    skillId: METEOR,
    family: '',
    shape: { kind: 'AREA', radius: 2, length: 0 },
    targetFaction: '',
    coefPct: 200,
    cooldown: 0,
    reach: null,
    telegraph,
    cancelOnAct: switches.act ?? false,
    cancelOnHit: switches.hit ?? false,
    healPct: 0,
    guardPct: 0,
    guardTicks: 0,
    tags: [],
  })
  const player = engine.state.entities.get(PLAYER_ENTITY_ID)
  if (player === undefined) {
    throw new Error('플레이어가 없다')
  }
  return { engine, player }
}

function castPlan() {
  return createPlannedAction({ entityId: PLAYER_ENTITY_ID, actionId: 'USE_SKILL', skillId: METEOR })
}

describe('스킬 예고 이식', () => {
  it('예고를 쓰는 스킬은 즉발 대신 붉은 칸을 띄운다', () => {
    const { engine } = buildProbe(3)
    engine.applyActions([castPlan()])
    const active = engine.telegraphs.listActive()
    expect(active.length).toBe(1)
    expect(active[0]?.skillId).toBe(METEOR)
    expect(active[0]?.remainingTicks).toBe(3)
  })

  it('피해가 시전 시점에 얼어붙는다 — 파이썬과 같은 셈이다', () => {
    const { engine, player } = buildProbe(2)
    const before = player.attack
    engine.applyActions([castPlan()])
    const frozen = engine.telegraphs.listActive()[0]?.damage
    expect(frozen).toBe(before * 2)
  })

  it('예고를 안 쓰는 스킬은 지금대로 즉발이다', () => {
    const { engine } = buildProbe(0)
    engine.applyActions([castPlan()])
    expect(engine.telegraphs.listActive().length).toBe(0)
  })

  it('켜 둔 예고만 다른 행동에 끊긴다', () => {
    const on = buildProbe(3, { act: true })
    on.engine.applyActions([castPlan()])
    on.engine.applyActions([createPlannedAction({ entityId: PLAYER_ENTITY_ID, actionId: 'HOLD' })])
    expect(on.engine.telegraphs.listActive().length).toBe(0)

    const off = buildProbe(3)
    off.engine.applyActions([castPlan()])
    off.engine.applyActions([createPlannedAction({ entityId: PLAYER_ENTITY_ID, actionId: 'HOLD' })])
    expect(off.engine.telegraphs.listActive().length).toBe(1)
  })

  it('막아 낸 피해로는 안 끊긴다 — 그러면 방어가 벌이 된다', () => {
    const { engine, player } = buildProbe(3, { hit: true })
    engine.applyActions([castPlan()])
    engine.telegraphs.applyCancel(engine.state, engine.log, player.entityId, CANCEL_BY_HIT)
    expect(engine.telegraphs.listActive().length).toBe(0)
  })

  it('시전자가 자기 시전을 읽는다 — self_is_casting', () => {
    const { engine, player } = buildProbe(3)
    engine.applyActions([castPlan()])
    engine.state.tick = 1
    engine.runTelegraph()
    expect(engine.telegraphs.isCasting(player.entityId)).toBe(true)
  })
})
