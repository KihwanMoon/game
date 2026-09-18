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

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { formatPulseWindow, WorldPanel } from './WorldPanel'
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
  respecCost: 0,
  respecIsFree: true,
  bonusRuleSlots: 1,
  bonusCpu: 1,
  reachedFloor: 1,
  floorCap: 10,
  loadout: undefined,
}

const LEADERBOARD: LeaderboardView = {
  coreVersion: 'b5.v2.e1',
  entries: [
    { rank: 1, handle: 'victor', score: 900, level: 6, accountId: 7, met: -1 },
    { rank: 2, handle: 'other', score: 400, level: 3, accountId: 8, met: -1 },
  ],
}

describe('세계 패널', () => {
  const markup = renderToStaticMarkup(
    <WorldPanel
      progress={PROGRESS}
      leaderboard={LEADERBOARD}
      doppelBoard={undefined}
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
      doppelBoard={undefined}
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
        doppelBoard={undefined}
        accountId={undefined}
        link="offline"
        detail=""
        onDaily={noop}
      />,
    )
    expect(markup).toContain('서버에 닿지 못했다')
  })
})

/*
 * 생 hex·자체 `@media` 검사는 여기 없다 — **`editor.css` 전량을 보는 자리가 따로 있다**
 * (`editorRender.test.tsx` 의 hex·px·그림자, `mobileEditor.test.tsx` 의 `@media`).
 *
 * 예전에는 여기서 `css.slice(css.indexOf('/* ── 세계 패널'))` 로 제 구역만 잘라 봤는데, **표지 주석이
 * 바뀌면 `indexOf` 가 -1 이라 마지막 글자 한 개를 검사하고 통과했다.** 못 잡는 검사는
 * 없느니만 못하다 — 초록색으로 「봤다」고 말하기 때문이다. 전량 검사가 이 구역을
 * 포함하므로 지우는 쪽이 맞다.
 */

describe('세계 패널이 나에 대한 것을 안 그린다', () => {
  const markup = renderToStaticMarkup(
    <WorldPanel
      progress={PROGRESS}
      leaderboard={LEADERBOARD}
      doppelBoard={undefined}
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

describe('둔갑 판', () => {
  const DOPPEL_BOARD: LeaderboardView = {
    coreVersion: 'b5.v2.e1',
    entries: [
      { rank: 1, handle: 'victor', score: 12, level: 0, accountId: 7, met: 20 },
      { rank: 2, handle: 'other', score: 9, level: 0, accountId: 8, met: 51 },
    ],
  }

  it('★ 줄이 있으면 둔갑 판을 먼저 편다 — 누적 경험치는 「오래 돌린 사람이 이긴다」다', () => {
    const html = renderToStaticMarkup(
      <WorldPanel
        progress={PROGRESS}
        leaderboard={LEADERBOARD}
        doppelBoard={DOPPEL_BOARD}
        accountId={7}
        link="online"
        detail=""
        onDaily={() => undefined}
      />,
    )
    expect(html).toContain('점수는 내 둔갑이 이긴 판이다')
    expect(html).not.toContain('점수는 누적 경험치다')
  })

  it('★ 승수 옆에 만난 판이 선다 — 열 번을 스무 판에 이룬 쪽과 쉰 판에 이룬 쪽은 다르다', () => {
    const html = renderToStaticMarkup(
      <WorldPanel
        progress={PROGRESS}
        leaderboard={LEADERBOARD}
        doppelBoard={DOPPEL_BOARD}
        accountId={7}
        link="online"
        detail=""
        onDaily={() => undefined}
      />,
    )
    expect(html).toContain('20판')
    expect(html).toContain('51판')
    expect(html).not.toContain('lv 0')
  })

  it('★ 빈 둔갑 판은 안 편다 — 빈 판이 첫 화면이면 순위표가 비었다로 읽힌다', () => {
    const html = renderToStaticMarkup(
      <WorldPanel
        progress={PROGRESS}
        leaderboard={LEADERBOARD}
        doppelBoard={{ coreVersion: 'b5.v2.e1', entries: [] }}
        accountId={7}
        link="online"
        detail=""
        onDaily={() => undefined}
      />,
    )
    expect(html).toContain('점수는 누적 경험치다')
  })
})

describe('세계 접속 현황', () => {
  // **두 수가 다른 것을 센다** (2026-09-18). `visitors` 는 출격을 누른 사람이고
  // (`requireAccount`: "여는 것만으로는 안 만든다"), `windowVisits` 는 열어 본 사람이다
  // — Cloudflare 가 엣지에서 센 것을 서버가 받아 적는다. 예전 주석이 "계정 수가 곧
  // 「앱을 연 사람 수」에 가깝다" 고 적어 뒀는데 그 전제가 코드와 어긋나 있었다.
  const PULSE = {
    visitors: 316,
    joined: 7,
    freshToday: 12,
    freshWeek: 120,
    runs: 5250,
    windowDays: 7,
    windowVisits: 1200,
    windowPlayed: 120,
    conversionPct: 10,
    trafficSource: 'cloudflare',
  }

  /**
   * 명부를 그린다.
   *
   * @param pulse 접속 현황. 없으면 안 넘긴다.
   * @returns 마크업.
   */
  function drawWorld(pulse?: typeof PULSE): string {
    return renderToStaticMarkup(
      <WorldPanel
        progress={PROGRESS}
        leaderboard={LEADERBOARD}
        doppelBoard={undefined}
        accountId={7}
        link="online"
        detail=""
        onDaily={noop}
        {...(pulse === undefined ? {} : { pulse })}
      />,
    )
  }

  it('★ 이름과 오늘을 함께 적는다 — 누계만 적으면 멈춘 세계와 구별이 안 된다', () => {
    const markup = drawWorld(PULSE)
    expect(markup).toContain('316')
    expect(markup).toContain('12')
    expect(markup).toContain('5250')
  })

  it('★ 들름에서 판으로 가는 깔때기를 한 줄로 잇는다', () => {
    // **화살표로 잇는 이유.** 두 수를 따로 적으면 관계를 보는 사람이 스스로 계산해야
    // 하고, 「사람이 오는데 안 한다」와 「아예 안 온다」가 안 갈린다.
    expect(formatPulseWindow(PULSE)).toBe('이번 주 들름 1200 → 판 120 (10%) · cloudflare 기준')
  })

  it('★ 계측을 못 받은 것과 아무도 안 온 것을 가른다', () => {
    // 들름 0 은 「아무도 안 왔다」가 아니라 「아직 못 받았다」일 수 있다. 같은 줄로
    // 적으면 없는 사실을 단언하게 되므로 깔때기를 접고 판 수만 적는다.
    expect(formatPulseWindow({ ...PULSE, windowVisits: 0, conversionPct: 0 })).toBe('이번 주 판 120')
    // 창 자체가 없으면(옛 서버) 줄을 통째로 안 그린다.
    expect(formatPulseWindow({ ...PULSE, windowDays: 0 })).toBe('')
  })

  it('★ 기간과 출처를 밝힌다 — 갈아 끼우는 날 수가 뛰는 이유가 화면에 있어야 한다', () => {
    expect(formatPulseWindow({ ...PULSE, windowDays: 30 })).toContain('30일')
    // 출처를 모르면 그 칸을 비운다. 없는 출처를 지어내지 않는다.
    expect(formatPulseWindow({ ...PULSE, trafficSource: '' })).not.toContain('기준')
  })

  it('★ 못 받으면 그 줄을 안 그린다 — 0 을 적으면 「아무도 없다」가 된다', () => {
    expect(drawWorld()).not.toContain('돈 판')
  })
})
