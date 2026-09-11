/**
 * 층 보상 선택 화면 (GDD §2.2, 2026-09-11).
 *
 * 「5층 이후에 보상이 안 들어온거같아」에서 시작했다. 서버는 층과 무관하게 같은 확률로
 * 주고 있었고, 진짜로 없는 것은 **기획의 고리 한 칸**이었다 — 클리어 뒤의 보상 선택.
 *
 * 여기서 지키는 것은 셋이다.
 *
 * 1. **고를 것이 없으면 안 그린다.** 빈 카드는 눌러도 아무 일이 없어 고장으로 읽힌다.
 * 2. **무엇이 얼마나 붙는지 적는다.** 「확장 슬롯」만 적으면 고를 근거가 없다.
 * 3. **고르면 그 id 가 그대로 나간다.** 화면이 번호로 바꾸면 서버가 되굴린 후보와 못 맞춘다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { RewardChoice, formatRewardEffect } from './RewardChoice'

const OFFERS = [
  { rewardId: 'module_slot', labelKo: '확장 슬롯', targetStat: 'rule_slots', amount: 1 },
  { rewardId: 'affix_attack', labelKo: '예리함', targetStat: 'attack', amount: 2 },
  { rewardId: 'potion_pair', labelKo: '포션 꾸러미', targetStat: 'POTION', amount: 2 },
]

describe('층 보상 선택', () => {
  it('★ 고를 것이 없으면 아무것도 안 그린다', () => {
    const html = renderToStaticMarkup(
      <RewardChoice floor={0} offers={OFFERS} onTake={() => undefined} />,
    )
    expect(html).toBe('')
  })

  it('★ 후보가 비면 그리지 않는다 — 빈 카드는 고장으로 읽힌다', () => {
    const html = renderToStaticMarkup(
      <RewardChoice floor={3} offers={[]} onTake={() => undefined} />,
    )
    expect(html).toBe('')
  })

  it('★ 셋을 이름과 효과로 적는다', () => {
    const html = renderToStaticMarkup(
      <RewardChoice floor={3} offers={OFFERS} onTake={() => undefined} />,
    )
    expect(html).toContain('3층 보상')
    expect(html).toContain('확장 슬롯')
    expect(html).toContain('규칙 줄 +1')
    expect(html).toContain('공격 +2')
    expect(html).toContain('물약 충전 +2')
  })

  it('★ 축 이름을 한글로 적는다 — id 를 그대로 적으면 한 칸만 영문이 된다', () => {
    expect(formatRewardEffect(OFFERS[0]!)).toBe('규칙 줄 +1')
    expect(formatRewardEffect({ ...OFFERS[0]!, targetStat: 'cpu_budget', amount: 3 })).toBe('cpu +3')
  })

  it('★ 모르는 축은 id 를 적는다 — 빈칸보다 낫다', () => {
    expect(formatRewardEffect({ ...OFFERS[0]!, targetStat: 'brand_new', amount: 1 })).toBe(
      'brand_new +1',
    )
  })

  it('★ 고르는 중에는 못 누른다 — 두 번 눌러 두 번 고르는 것을 막는다', () => {
    const html = renderToStaticMarkup(
      <RewardChoice floor={3} offers={OFFERS} isBusy onTake={() => undefined} />,
    )
    expect(html).toContain('disabled')
  })
})
