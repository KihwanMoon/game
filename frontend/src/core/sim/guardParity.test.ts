/**
 * 방어 태세가 두 코어에서 같이 도는가 (게이트 G3).
 *
 * **이 갈래가 브라우저에 통째로 없었다 (2026-09-09).** `USE_SKILL[GUARD_BRACE]` 는
 * 파이썬 `_apply_settled` 의 `GUARD_SKILL_ID` 갈래가 `apply_guard` 를 부르는데,
 * TS `applySettled` 에는 그 갈래가 없어 **그냥 끝났다** — 방패를 든 규칙표가 두 코어에서
 * 다르게 돌았다. 주문서 경로(`resolveScroll`)만 같은 상태를 세우고 있어서, 코드를
 * 훑으면 있는 것처럼 보였다.
 *
 * **골든이 이 스킬을 하나도 안 덮어 게이트가 침묵했다.** 그래서 골든에 기대지 않고
 * 여기서 직접 못 박는다.
 *
 * 파이썬 기대값(`skills.json`): `guard_pct 50 · guard_ticks 2 · cooldown 8`.
 */
import { describe, expect, it } from 'vitest'

import { BALANCE, ROOM_TEMPLATES } from '../resources'
import { PLAYER_ENTITY_ID, buildEngine, parseBalance } from '../services/runBattle'
import { GUARD_STATUS } from './abilities'
import { createPlannedAction } from './plan'

function buildProbe() {
  const balance = parseBalance(BALANCE)
  const template = ROOM_TEMPLATES.find((one) => one.templateId === 'open_field')
  if (template === undefined) {
    throw new Error('open_field 템플릿이 없다')
  }
  const engine = buildEngine({ template, balance, seed: 3 })
  const player = engine.state.entities.get(PLAYER_ENTITY_ID)
  if (player === undefined) {
    throw new Error('플레이어가 없다')
  }
  return { engine, player }
}

describe('방어 태세 이식', () => {
  it('상태·쿨타임·로그가 파이썬과 같이 선다', () => {
    const { engine, player } = buildProbe()
    engine.applyActions([
      createPlannedAction({
        entityId: player.entityId,
        actionId: 'USE_SKILL',
        skillId: 'GUARD_BRACE',
      }),
    ])
    expect(player.statuses.get(GUARD_STATUS)).toBe(2)
    expect(player.cooldowns.get('GUARD_BRACE')).toBe(8)
    const line = engine.log.entries.find((entry) => entry.outcome.includes('방어'))
    expect(line?.outcome).toBe('GUARD_BRACE 방어 50% / 2틱')
  })

  it('부를 줄 모르는 스킬은 로그에 남는다 — 조용히 사라지지 않는다', () => {
    const { engine, player } = buildProbe()
    engine.applyActions([
      createPlannedAction({
        entityId: player.entityId,
        actionId: 'USE_SKILL',
        skillId: 'METEOR',
      }),
    ])
    const line = engine.log.entries.find((entry) => entry.outcome.includes('쓸 줄 모른다'))
    expect(line?.expr.startsWith('METEOR')).toBe(true)
  })

  it('이동에는 안 붙는다 — 붙으면 로그가 두 배가 된다', () => {
    const { engine, player } = buildProbe()
    engine.applyActions([
      createPlannedAction({ entityId: player.entityId, actionId: 'APPROACH', targetId: 'e1' }),
    ])
    expect(engine.log.entries.some((entry) => entry.outcome.includes('쓸 줄 모른다'))).toBe(false)
  })
})
