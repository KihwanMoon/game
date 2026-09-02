/**
 * 층별 정산 검사.
 *
 * 정산이 상단 알림에서 탭으로 옮겨 온 이유가 여기 걸려 있다 — 알림은 뜰 때마다 아래
 * 전부를 밀었고, 정산은 사라질 것이 아니라 쌓일 것이다.
 */
import { describe, expect, it } from 'vitest'

import { appendSettlement, formatSettlementTabCount, splitRewardNotes } from './settlement'

describe('보상 문구 끊기', () => {
  it('★ 한 줄에 정보 하나로 끊는다 — 가로로 길면 훑을 수 없다', () => {
    expect(splitRewardNotes('화폐 +80 · 경험치 +160 · 사슬 갑옷(FINE) 획득')).toEqual([
      '화폐 +80',
      '경험치 +160',
      '사슬 갑옷(FINE) 획득',
    ])
  })

  it('빈 항목은 버린다', () => {
    expect(splitRewardNotes(' · 화폐 +40 ·  · ')).toEqual(['화폐 +40'])
  })

  it('벌어들인 것이 없으면 빈 목록이다', () => {
    expect(splitRewardNotes('   ')).toEqual([])
  })
})

describe('정산 쌓기', () => {
  it('★ 층 오름차순으로 쌓인다 — 하강한 순서 그대로 읽힌다', () => {
    let list = appendSettlement([], 2, '화폐 +80')
    list = appendSettlement(list, 1, '화폐 +40')
    list = appendSettlement(list, 3, '화폐 +120')
    expect(list.map((item) => item.floor)).toEqual([1, 2, 3])
  })

  it('★ 같은 층은 덮어쓴다 — 두 번 쌓이면 두 번 번 것처럼 읽힌다', () => {
    const first = appendSettlement([], 2, '화폐 +80')
    const again = appendSettlement(first, 2, '화폐 +80 · 경험치 +160')
    expect(again).toHaveLength(1)
    expect(again[0]?.lines).toEqual(['화폐 +80', '경험치 +160'])
  })

  it('적을 것이 없으면 목록이 그대로다 — 빈 층 머리글만 쌓이면 잡음이다', () => {
    const list = appendSettlement([], 2, '화폐 +80')
    expect(appendSettlement(list, 3, '')).toBe(list)
    expect(appendSettlement(list, 0, '화폐 +40')).toBe(list)
  })
})

describe('정산 탭 카운트', () => {
  it('정산한 층 수를 적는다', () => {
    expect(formatSettlementTabCount([{ floor: 1, lines: ['화폐 +40'] }])).toBe('1층')
  })

  it('정산한 것이 없으면 비운다 — `0층` 은 아무것도 안 말한다', () => {
    expect(formatSettlementTabCount([])).toBe('')
  })
})
