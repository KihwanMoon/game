/**
 * 능력치 변환 — 파이썬 사본과 대조한다 (결정 #51, 게이트 G3).
 *
 * 화면이 보여 주는 미리보기와 서버가 실제로 계산하는 값이 갈라지면, 유저는 찍기 전에
 * 본 숫자를 믿고 찍었다가 다른 결과를 받는다.
 */
import { describe, expect, it } from 'vitest'

import golden from '../golden/sim_golden.json'
import { buildAttributeBonus } from './attributes'

interface AttributeRow {
  readonly stats: Record<string, number>
  readonly attack: number
  readonly hp_max: number
  readonly initiative: number
  readonly defense: number
  readonly cpu_budget: number
  readonly skill_power_pct: number
}

describe('능력치 변환 (결정 #51)', () => {
  const rows = golden.attributes as readonly AttributeRow[]

  it('★ 골든에 사례가 실려 있다 — 비어 있으면 아래 대조가 통과해도 뜻이 없다', () => {
    expect(rows.length).toBeGreaterThan(0)
  })

  for (const [index, row] of rows.entries()) {
    it(`★ 사례 ${String(index)} 이 파이썬과 같다 — ${JSON.stringify(row.stats)}`, () => {
      const bonus = buildAttributeBonus(row.stats)
      expect(bonus.attack).toBe(row.attack)
      expect(bonus.hpMax).toBe(row.hp_max)
      expect(bonus.initiative).toBe(row.initiative)
      expect(bonus.defense).toBe(row.defense)
      expect(bonus.cpuBudget).toBe(row.cpu_budget)
      expect(bonus.skillPowerPct).toBe(row.skill_power_pct)
    })
  }
})
