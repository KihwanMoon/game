/**
 * 오늘의 도전이 「내일 또 올 이유」로 읽히는가.
 *
 * **데일리는 이미 돌고 있었는데 결과를 아무도 못 봤다** (2026-09-20). 티켓을 하루 한
 * 번 내주고 시드를 날짜로 고정하는 것까지 서버가 하고 있었지만, 화면에는 「티켓을
 * 받았다」 한 줄이 전부였다 — 같은 판을 다 같이 돈다는 사실이 안 보이면 데일리는 그냥
 * 「어제와 다른 한 판」이다.
 *
 * 그래서 한 줄이 **세 경우를 갈라 말하는지**를 본다. 안 잡았다·받아만 뒀다·돌았다는
 * 할 말이 각각 다르고, 셋을 뭉뚱그리면 그 줄이 거짓말을 한다.
 */
import { describe, expect, it } from 'vitest'

import { formatDailySummary, type DailyBoardView } from './dailyBoard'

function buildBoard(patch: Partial<DailyBoardView> = {}): DailyBoardView {
  return { day: '2026-09-20', players: 0, rows: [], hasEntry: false, myFloor: 0, myRank: 0, ...patch }
}

describe('오늘의 도전 한 줄', () => {
  it('서버에 못 닿으면 아무 말도 안 한다 — 서버가 없어도 게임은 돈다', () => {
    expect(formatDailySummary(undefined)).toBe('')
  })

  it('★ 아직 안 잡았으면 받으라고 말한다', () => {
    const text = formatDailySummary(buildBoard({ players: 12 }))
    expect(text).toContain('12명이 잡았다')
    expect(text).toContain('받으면')
  })

  it('아무도 안 잡았으면 0명이라고 안 적는다', () => {
    expect(formatDailySummary(buildBoard())).toContain('아직 아무도 안 잡았다')
  })

  it('★ 받아만 둔 것과 돈 것을 가른다 — 0층이라고 적으면 못한 것처럼 읽힌다', () => {
    expect(formatDailySummary(buildBoard({ hasEntry: true, players: 3 }))).toContain('받아 뒀다')
    expect(formatDailySummary(buildBoard({ hasEntry: true, myFloor: 7, players: 3 }))).toContain(
      '7장까지',
    )
  })

  it('★ 윗자리 밖이면 순위를 안 적는다 — 0위라고 적으면 거짓말이다', () => {
    const outside = formatDailySummary(buildBoard({ hasEntry: true, myFloor: 4, players: 30 }))
    expect(outside).not.toContain('위')
    const inside = formatDailySummary(
      buildBoard({ hasEntry: true, myFloor: 9, myRank: 2, players: 30 }),
    )
    expect(inside).toContain('2위')
  })
})
