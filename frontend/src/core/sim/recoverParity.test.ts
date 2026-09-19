/**
 * 후경직 이식 (2026-09-19). 파이썬 `tests/test_cast_recover.py` 와 같은 것을 본다.
 *
 * **축이 0 이면 골든이 안 움직인다** — 그래서 골든만으로는 이식됐는지 알 수 없다.
 * 배포된 재주 열여섯이 전부 `recover: 0` 이라, 여기서 값을 넣어 보지 않으면 TS 쪽이
 * 통째로 빠져 있어도 전부 초록이다.
 */
import { describe, expect, it } from 'vitest'

import { RECOVER_EXPR } from './engine'
import { createPlannedAction } from './plan'
import { BALANCE, ROOM_TEMPLATES } from '../resources'
import { PLAYER_ENTITY_ID, buildEngine, parseBalance } from '../services/runBattle'
import { CAST_FREE } from '../skills/catalog'

const PROBE = 'SKILL_1'

function buildProbe(recover: number, telegraph = 0) {
  const template = ROOM_TEMPLATES.find((one) => one.templateId === 'open_field')
  if (template === undefined) {
    throw new Error('방이 없다')
  }
  const engine = buildEngine({ template, balance: parseBalance(BALANCE), seed: 3 })
  const skills = engine.config.skills as Map<string, unknown>
  skills.set(PROBE, {
    skillId: PROBE,
    family: '',
    shape: { kind: telegraph > 0 ? 'AREA' : 'SINGLE', radius: 2, length: 0, hops: 0 },
    targetFaction: '',
    coefPct: 100,
    cooldown: 0,
    reach: null,
    telegraph,
    castAct: CAST_FREE,
    cancelOnHit: false,
    recover,
    healPct: 0,
    guardPct: 0,
    guardTicks: 0,
    tags: [],
    effects: [],
  })
  const player = engine.state.entities.get(PLAYER_ENTITY_ID)
  if (player === undefined) {
    throw new Error('플레이어가 없다')
  }
  const foe = engine.state.listHostiles(player)[0]
  if (foe === undefined) {
    throw new Error('적이 없다')
  }
  return { engine, player, foe }
}

function use(foe: { entityId: string }) {
  return createPlannedAction({
    entityId: PLAYER_ENTITY_ID,
    actionId: 'USE_SKILL',
    skillId: PROBE,
    targetId: foe.entityId,
  })
}

describe('후경직', () => {
  it('★ 즉발은 쓴 그 틱에 굳는다 — 예고가 없어도 뒤가 있다', () => {
    const { engine, player, foe } = buildProbe(2)
    engine.applyActions([use(foe)])
    expect(player.recoverTicks).toBe(2)
  })

  it('★ 기본은 0 이다 — 축을 연 것만으로 지금 게임이 바뀌면 안 된다', () => {
    const { engine, player, foe } = buildProbe(0)
    engine.applyActions([use(foe)])
    expect(player.recoverTicks).toBe(0)
  })

  it('★ 굳은 틱에는 규칙표가 안 돈다 — 안 그러면 경직이 이름뿐이다', () => {
    const { engine, player, foe } = buildProbe(2)
    engine.applyActions([use(foe)])
    const before = { ...player.position }
    engine.runTick()
    expect(player.position).toEqual(before)
    expect(engine.log.entries.some((one) => one.expr === RECOVER_EXPR)).toBe(true)
  })

  it('★ 굳은 것은 풀린다 — 유지 단계가 매 틱 줄인다', () => {
    const { engine, player, foe } = buildProbe(1)
    engine.applyActions([use(foe)])
    expect(player.recoverTicks).toBe(1)
    engine.runTick()
    expect(player.recoverTicks).toBe(0)
  })

  it('★ 예고형은 터진 틱에 굳는다 — 도는 동안은 잠금이 이미 묶고 있다', () => {
    const { engine, player, foe } = buildProbe(2, 2)
    engine.applyActions([use(foe)])
    expect(player.recoverTicks).toBe(0)
    engine.runTick()
    engine.runTick()
    expect(player.recoverTicks).toBeGreaterThan(0)
  })
})
