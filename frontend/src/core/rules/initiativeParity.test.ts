/**
 * 선공을 규칙표가 읽는다 — 블록 v12 의 이식 (2026-09-11).
 *
 * **오래 화면에만 있던 값이었다.** 선공은 틱 안 행동 순서를 정하는데 규칙표가 못 읽어서,
 * 신발을 바꿔도 규칙을 다시 짤 이유가 안 생겼다 — 아이템이 움직일 수 있는 폭(44~66)에서
 * 승률 변화가 **0** 이었다.
 *
 * 파이썬 짝은 `tests/test_initiative_block.py` 다 — 같은 값을 같은 이름으로 본다. 한쪽만
 * 읽으면 같은 규칙표가 브라우저와 서버에서 다르게 판정된다 (G3).
 */
import { describe, expect, it } from 'vitest'

import { BALANCE, BLOCK_CATALOG, ROOM_TEMPLATES } from '../resources'
import { PLAYER_ENTITY_ID, buildEngine, parseBalance } from '../services/runBattle'
import { buildSnapshot } from '../sim/perception'
import { evaluateCondition } from './ruleVm'

/** 플레이어(선공 50)와 선공을 정한 적 하나. */
function buildProbe(targetInitiative: number) {
  const template = ROOM_TEMPLATES.find((one) => one.templateId === 'open_field')
  if (template === undefined) {
    throw new Error('open_field 템플릿이 없다')
  }
  const engine = buildEngine({ template, balance: parseBalance(BALANCE), seed: 3 })
  const player = engine.state.entities.get(PLAYER_ENTITY_ID)
  if (player === undefined) {
    throw new Error('플레이어가 없다')
  }
  player.initiative = 50
  const enemy = engine.state.listHostiles(player)[0]
  if (enemy === undefined) {
    throw new Error('적이 없다')
  }
  enemy.initiative = targetInitiative
  return { engine, player, enemy }
}

/** `대상 선공 > 내 선공` 을 판정한다. */
function checkFaster(targetInitiative: number): { fired: boolean; expr: string } {
  const { engine, player, enemy } = buildProbe(targetInitiative)
  const snapshot = buildSnapshot({
    state: engine.state,
    entity: player,
    kindTypes: engine.config.kindTypes,
  })
  return evaluateCondition(
    {
      op: 'SINGLE',
      terms: [
        { lhs: 'target_initiative', comparison: '>', rhs: { stat: 'initiative' }, lhsParam: null },
      ],
    },
    { snapshot, catalog: BLOCK_CATALOG, target: enemy, cpuHeadroom: 0, actor: player },
  )
}

describe('선공 블록 이식', () => {
  it('★ 나보다 빠른 적이면 참이다', () => {
    expect(checkFaster(60).fired).toBe(true)
  })

  it('★ 느린 적이면 거짓이다 — 방패 골렘(20)이 그 자리다', () => {
    expect(checkFaster(20).fired).toBe(false)
  })

  it('★ 동률은 거짓이다 — 순서가 무작위로 갈리는 자리다', () => {
    expect(checkFaster(50).fired).toBe(false)
  })

  it('★ 항별 실측값을 병기한다 (GDD §8.2)', () => {
    const { expr } = checkFaster(60)
    expect(expr).toContain('60')
    expect(expr).toContain('50')
  })

  it('★ 카탈로그가 둘을 다 갖는다 — 없으면 편집기가 못 내놓는다', () => {
    expect(BLOCK_CATALOG.perceptions.has('target_initiative')).toBe(true)
    expect(BLOCK_CATALOG.rhsStats.has('initiative')).toBe(true)
  })
})
