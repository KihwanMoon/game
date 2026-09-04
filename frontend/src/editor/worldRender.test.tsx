/**
 * 세계 화면 검사 (F단계) — **순위와 오늘의 도전뿐이다.**
 *
 * 레벨·깊이·능력치 배분은 `growthRender.test.tsx` 가 본다. 그것은 세계에 대한 사실이
 * 아니라 나에 대한 사실이라 패널이 갈렸다.
 *
 * **경매도 여기 없다.** `auctionRender.test.tsx` 가 본다 — 세계는 「나 밖의 일」이고,
 * 경매는 내 가방을 바꾸는 일이다. 여기서 지키는 것은 **그 둘이 다시 안 합쳐지는 것**이다.
 *
 * **API 만 있고 화면이 없으면 아무도 못 쓴다** — 도감에서 한 번 겪은 실수다.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { WorldPanel } from './WorldPanel'
import type { LeaderboardView, ProgressView } from '../storage'

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
  reachedFloor: 1,
  floorCap: 10,
  loadout: undefined,
}

const LEADERBOARD: LeaderboardView = {
  coreVersion: 'b5.v2.e1',
  entries: [
    { rank: 1, handle: 'victor', score: 900, level: 6, accountId: 7 },
    { rank: 2, handle: 'other', score: 400, level: 3, accountId: 8 },
  ],
}

describe('세계 패널', () => {
  const markup = renderToStaticMarkup(
    <WorldPanel
      progress={PROGRESS}
      leaderboard={LEADERBOARD}
      accountId={7}
      link="online"
      detail=""
      onDaily={noop}
    />,
  )

  it('★ 「이것이 너다」는 황동이다 — 의미색을 빌려 쓰지 않는다', () => {
    // 예전에는 `GlyphState state="true"` 라 참/거짓의 녹청 ✓ 로 내 줄을 표시했다.
    // 의미색을 빌려 쓰면 그 색이 무엇을 뜻하는지가 화면마다 갈린다.
    expect(markup).toContain('wld__rank--me')
    expect(markup).toContain('wld__me')
    expect(markup).toContain('◉')
    // 색만으로 알리지 않는다 — 보조 기술이 읽을 한 문장이 함께 있다.
    expect(markup).toContain('이 줄이 나다')
  })

  it('내 줄이 아니면 표시하지 않는다 — 모두가 「나」면 아무 말도 아니다', () => {
    expect(markup.match(/wld__rank--me/g)).toHaveLength(1)
  })

  it('★ 순위가 컬럼으로 선다 — 자리가 맞아야 눈이 세로로 훑는다', () => {
    // 예전에는 `lv6 · 900` 이 한 덩어리라 줄마다 시작 자리가 달라, 누가 얼마나 앞선지
    // 세로로 비교할 수 없었다.
    expect(markup).toContain('wld__rank-lv')
    expect(markup).toContain('wld__rank-score')
    expect(markup).not.toContain('lv6 · 900')
  })

  it('★ 격차가 칸으로도 보인다 — 칸 수가 보조이고 옆의 숫자가 정본이다', () => {
    expect(markup).toContain('wld__bar')
    // 1등은 여덟 칸이 다 켜진다.
    const first = markup.slice(markup.indexOf('wld__bar'))
    expect(first.slice(0, first.indexOf('</span>')).match(/class="on"/g)).toHaveLength(8)
  })

  it('★ 점수가 누적 경험치임을 말한다 — 한 판 성적이 아니다', () => {
    expect(markup).toContain('점수는 누적 경험치다')
  })

  it('★ 시즌 이름이 코어 버전이다 (결정 #06)', () => {
    expect(markup).toContain('시즌 b5.v2.e1')
  })

  it('내 순위를 표시한다', () => {
    expect(markup).toContain('victor')
  })

  it('오늘의 도전이 여기 있다 — 나 밖의 일이다', () => {
    expect(markup).toContain('오늘의 도전')
  })
})

describe('★ 경매가 세계에서 나갔다', () => {
  // 세계 탭은 「나 밖의 일」(순위·도감·오늘의 도전)이고, 경매는 내 가방을 바꾸는 일이다 —
  // 사면 돈이 나가고 아이템이 들어오며 되돌릴 수 없다(귀속된다, 결정 #07). 순위표 아래에
  // 있으면 그만한 무게로 안 보였고, 매물 열둘이면 순위표가 화면 밖으로 밀려났다.
  const markup = renderToStaticMarkup(
    <WorldPanel
      progress={PROGRESS}
      leaderboard={LEADERBOARD}
      accountId={7}
      link="online"
      detail=""
      onDaily={noop}
    />,
  )

  it('매물도 수수료도 여기서 안 그린다', () => {
    expect(markup).not.toContain('경매장')
    expect(markup).not.toContain('수수료')
    expect(markup).not.toContain('wld__listing')
  })

  it('견줌 표도 여기 없다 — 경매 탭의 것이다', () => {
    expect(markup).not.toContain('invd__compare')
  })
})

describe('세계 패널 — 서버 없음', () => {
  it('순위가 서버의 것임을 말한다', () => {
    const markup = renderToStaticMarkup(
      <WorldPanel
        progress={undefined}
        leaderboard={undefined}
        accountId={undefined}
        link="offline"
        detail=""
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

describe('세계 패널이 나에 대한 것을 안 그린다', () => {
  const markup = renderToStaticMarkup(
    <WorldPanel
      progress={PROGRESS}
      leaderboard={LEADERBOARD}
      accountId={7}
      link="online"
      detail=""
      onDaily={noop}
    />,
  )

  it('★ 능력치 배분이 여기 없다 — 「내가 뭘 찍을 수 있나」를 보려고 세계를 열지 않는다', () => {
    expect(markup).not.toContain('남은 포인트')
    expect(markup).not.toContain('배분 확정')
  })

  it('★ 레벨과 깊이도 없다 — 나에 대한 사실은 성장 패널이 든다', () => {
    expect(markup).not.toContain('10층')
    expect(markup).not.toContain('표현력')
  })
})
