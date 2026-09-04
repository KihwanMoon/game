/**
 * 고른 물건을 지금 낀 것과 견준다.
 *
 * **점수 하나로 접지 않는 것**이 이 모듈의 규율이다. 「이게 더 좋다」를 한 숫자로 말하려면
 * 어느 스탯이 얼마나 값한지를 코드가 정해야 하고, 그 기준이 틀리면 화면이 **틀린 답을
 * 자신 있게** 말한다 — 봇의 장비 교체는 그 기준을 감수했지만 저쪽은 봇의 취향이 정해져
 * 있고 이쪽은 사람이 고른다.
 */
import { describe, expect, it } from 'vitest'

import type { AffixView } from '../storage'

import { compareToWorn, formatDelta, mergeAffixes } from './compareItems'

/**
 * 접사 하나를 짠다.
 *
 * @param stat 스탯 열쇠.
 * @param flat 고정값.
 * @param percent 퍼센트.
 * @returns 접사.
 */
function affix(stat: string, flat: number, percent = 0): AffixView {
  return { stat, flat, percent, labelKo: '', statLabel: stat === 'attack' ? '공격력' : stat }
}

describe('접사 합치기', () => {
  it('같은 스탯에 둘이 붙으면 합친다 — 굴림과 봉인 해제가 각각 붙을 수 있다', () => {
    const merged = mergeAffixes([affix('attack', 3), affix('attack', 2, 10)])
    expect(merged.get('attack')).toEqual({ flat: 5, percent: 10, label: '공격력' })
  })
})

describe('지금 낀 것과의 차이', () => {
  it('★ 스탯별로 낸다 — 점수 하나로 접으면 기준을 코드가 정하게 된다', () => {
    const rows = compareToWorn([affix('attack', 5)], [affix('attack', 2)])
    expect(rows).toHaveLength(1)
    expect(rows[0]?.flatDelta).toBe(3)
  })

  it('★ 고른 쪽에만 있는 스탯도 낸다 — 새로 붙는 것이 안 보이면 안 된다', () => {
    const rows = compareToWorn([affix('attack_range', 2)], [])
    expect(rows.map((row) => row.stat)).toEqual(['attack_range'])
    expect(rows[0]?.flatDelta).toBe(2)
  })

  it('★ 지금 쪽에만 있는 스탯도 낸다 — **끼면 사라지는 것**이 안 보이면 함정이다', () => {
    const rows = compareToWorn([], [affix('defense', 9)])
    expect(rows.map((row) => row.stat)).toEqual(['defense'])
    expect(rows[0]?.flatDelta).toBe(-9)
  })

  it('빈 자리와 견주면 전부 이득이다 — 그때는 그것이 맞는 답이다', () => {
    const rows = compareToWorn([affix('attack', 5)], [])
    expect(rows[0]?.flatDelta).toBe(5)
  })

  it('같은 값은 줄에서 뺀다 — 안 달라지는 것을 적으면 달라지는 것이 묻힌다', () => {
    const rows = compareToWorn([affix('attack', 3)], [affix('attack', 3)])
    expect(rows).toEqual([])
  })

  it('★ 정렬이 스탯 이름 순이다 — 접사 순서에 기대면 두 칸을 번갈아 볼 수 없다', () => {
    const rows = compareToWorn([affix('hp_max', 1), affix('attack', 1), affix('defense', 1)], [])
    expect(rows.map((row) => row.stat)).toEqual(['attack', 'defense', 'hp_max'])
  })
})

describe('차이 문구', () => {
  it('★ 고정값과 퍼센트를 안 합친다 — 합치려면 기준값이 필요하고 그것이 또 기준을 정하는 일이다', () => {
    const rows = compareToWorn([affix('attack', 3, 5)], [])
    expect(formatDelta(rows[0]!)).toBe('+3 +5%')
  })

  it('음수는 부호로도 적는다 — 색 하나면 못 가르는 사람에게 사라진다', () => {
    const rows = compareToWorn([], [affix('attack', 4)])
    expect(formatDelta(rows[0]!)).toBe('−4')
  })
})
