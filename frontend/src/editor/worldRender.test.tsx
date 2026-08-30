/**
 * 세계 화면 검사 (F단계).
 *
 * **API 만 있고 화면이 없으면 아무도 못 쓴다** — 도감에서 한 번 겪은 실수다.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { WorldPanel, formatAttributeEffect } from './WorldPanel'
import type { AuctionView, LeaderboardView, ProgressView } from '../storage'

const noop = () => undefined

const PROGRESS: ProgressView = {
  level: 6,
  totalXp: 900,
  remainingXp: 120,
  nextXp: 300,
  stats: { str: 4, dex: 0, int: 2 },
  statKeys: ['str', 'dex', 'int'],
  statPoints: 15,
  spentPoints: 6,
  bonusRuleSlots: 1,
  bonusCpu: 1,
  loadout: undefined,
}

const LEADERBOARD: LeaderboardView = {
  coreVersion: 'b5.v2.e1',
  entries: [
    { rank: 1, handle: 'victor', score: 900, level: 6, accountId: 7 },
    { rank: 2, handle: 'other', score: 400, level: 3, accountId: 8 },
  ],
}

const AUCTION: AuctionView = {
  listings: [
    { listingId: 1, itemId: 11, labelKo: '철 투구', price: 300, isMine: false },
    { listingId: 2, itemId: 12, labelKo: '대검', price: 900, isMine: true },
  ],
  balance: 500,
  feePercent: 5,
}

describe('세계 패널', () => {
  const markup = renderToStaticMarkup(
    <WorldPanel
      progress={PROGRESS}
      leaderboard={LEADERBOARD}
      auction={AUCTION}
      accountId={7}
      isOnline
      detail=""
      onAllocate={noop}
      onBuy={noop}
      onCancel={noop}
      onDaily={noop}
    />,
  )

  it('레벨과 다음 레벨까지의 경험치를 적는다', () => {
    expect(markup).toContain('6 · 120 / 300')
  })

  it('★ 점수가 누적 경험치임을 말한다 — 한 판 성적이 아니다', () => {
    expect(markup).toContain('점수는 누적 경험치다')
  })

  it('★ 시즌 이름이 코어 버전이다 (결정 #06)', () => {
    expect(markup).toContain('시즌 b5.v2.e1')
  })

  it('남은 능력치 포인트를 적는다', () => {
    // 15 받고 6 썼으니 9 남았다.
    expect(markup).toContain('남은 포인트 9')
  })

  it('★ 수수료율을 먼저 보여준다 — 걸기 전에 얼마가 나가는지 알아야 한다', () => {
    expect(markup).toContain('수수료 5%')
  })

  it('내 매물은 사는 대신 내리는 버튼이 뜬다', () => {
    expect(markup).toContain('내린다')
    expect(markup).toContain('수수료는 안 돌려준다')
  })

  it('★ 잔액이 모자라면 구매를 잠근다', () => {
    // 잔액 500 인데 대검이 900 이다 — 다만 그것은 내 매물이라, 철 투구(300)는 살 수 있다.
    expect(markup).toContain('구매')
  })

  it('내 순위를 표시한다', () => {
    expect(markup).toContain('victor')
  })
})

describe('세계 패널 — 서버 없음', () => {
  it('순위와 경매가 서버의 것임을 말한다', () => {
    const markup = renderToStaticMarkup(
      <WorldPanel
        progress={undefined}
        leaderboard={undefined}
        auction={undefined}
        accountId={undefined}
        isOnline={false}
        detail=""
        onAllocate={noop}
        onBuy={noop}
        onCancel={noop}
        onDaily={noop}
      />,
    )
    expect(markup).toContain('서버에 닿지 못했다')
  })
})

describe('세계 패널 스타일', () => {
  const css = readFileSync(fileURLToPath(new URL('./editor.css', import.meta.url)), 'utf8')
  const block = css.slice(css.indexOf('/* ── 세계 패널'))

  it('생 hex 색이 없다', () => {
    expect(block).not.toMatch(/#[0-9a-fA-F]{3,8}\b/)
  })

  it('자체 미디어쿼리를 두지 않는다', () => {
    expect(block).not.toContain('@media')
  })
})

describe('능력치 미리보기 (결정 #51)', () => {
  it('★ 찍기 전에 무엇이 오르는지 실측값으로 보인다', () => {
    // "힘 +1" 만 적으면 그것이 공격력을 얼마나 올리는지 알 수 없다. 배분은 되돌릴 수
    // 없으므로 찍기 전에 값이 보여야 한다 (디자인 §8.2 와 같은 이유).
    expect(formatAttributeEffect('str', 10)).toBe('공격 +10 · 체력 +40')
    expect(formatAttributeEffect('dex', 7)).toBe('선공 +14 · 방어 +7')
  })

  it('★ 지능의 CPU 상한이 화면에도 보인다', () => {
    // 상한을 화면이 숨기면 유저는 안 오르는 축에 계속 찍는다.
    expect(formatAttributeEffect('int', 40)).toBe('CPU +8 · 스킬위력 180%')
  })

  it('0점이면 아무것도 적지 않는다 — 빈 줄이 세 개 늘면 목록이 읽히지 않는다', () => {
    expect(formatAttributeEffect('str', 0)).toBe('')
  })
})
