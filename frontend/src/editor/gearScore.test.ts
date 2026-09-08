/**
 * 저울이 파이썬과 같은 수를 내는가 (`game/app/bots/upgrade.compute_weighted_score`).
 *
 * **`gear_priority.json` 을 함께 읽는 것만으로는 부족하다.** 무게는 같아도 셈이 다르면
 * 미리보기가 「2개 교체」라 적고 서버는 하나만 바꾼다 — 사본을 안 두려고 파일을 공유한
 * 이유가 무색해진다.
 *
 * 갈리는 자리는 **음수 퍼센트** 하나다. 파이썬 `//` 는 내림이고 `Math.trunc` 는 0 쪽으로
 * 자른다. 저주 접사가 정확히 음수 퍼센트이고(`[과부하] cpu −25%`), `cpu_budget` 에
 * 무게가 붙기 전에는 `weight === 0` 이 그 항을 건너뛰어 안 드러났다.
 */
import { describe, expect, it } from 'vitest'

import { computeGearScore } from './maintenanceUpgrade'

const ATTACK = { cpu_budget: 2, attack: 4 }

describe('저울의 셈', () => {
  it('저주 퍼센트를 내림한다 — 파이썬 `//` 와 같아야 한다', () => {
    // cpu 10 에 −25%: 파이썬 `10 * -25 // 100` = −3. `Math.trunc` 면 −2 가 된다.
    const score = computeGearScore(
      [{ stat: 'cpu_budget', flat: 0, percent: -25, labelKo: '[과부하]', statLabel: 'CPU' }],
      0,
      ATTACK,
      { cpu_budget: 10 },
    )
    expect(score).toBe(-6)
  })

  it('내림이 0 쪽 자르기와 갈리는 값들에서 전부 맞는다', () => {
    // 파이썬 실측: cpu 8 → −2, 10 → −3, 12 → −3, 14 → −4.
    const expected = new Map([
      [8, -4],
      [10, -6],
      [12, -6],
      [14, -8],
    ])
    for (const [cpu, want] of expected) {
      const score = computeGearScore(
        [{ stat: 'cpu_budget', flat: 0, percent: -25, labelKo: '[과부하]', statLabel: 'CPU' }],
        0,
        ATTACK,
        { cpu_budget: cpu },
      )
      expect(score, `cpu ${String(cpu)}`).toBe(want)
    }
  })

  it('양수 퍼센트는 두 셈이 원래 같다 — 회귀 확인용', () => {
    const score = computeGearScore(
      [{ stat: 'cpu_budget', flat: 0, percent: 25, labelKo: '여유', statLabel: 'CPU' }],
      0,
      ATTACK,
      { cpu_budget: 10 },
    )
    expect(score).toBe(4)
  })
})
