/**
 * 세계 화면 검사 (F단계) — **순위와 경매장뿐이다.**
 *
 * 레벨·깊이·능력치 배분은 `growthRender.test.tsx` 가 본다. 그것은 세계에 대한 사실이
 * 아니라 나에 대한 사실이라 패널이 갈렸다.
 *
 * **API 만 있고 화면이 없으면 아무도 못 쓴다** — 도감에서 한 번 겪은 실수다.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { WorldPanel } from './WorldPanel'
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

const AUCTION: AuctionView = {
  listings: [
    {
      listingId: 1,
      itemId: 11,
      labelKo: '철 투구',
      price: 300,
      isMine: false,
      affixes: [{ stat: 'hp_max', flat: 8, percent: 0, labelKo: '튼튼함', statLabel: '최대체력' }],
      expiresInMinutes: 42,
      fee: 15,
      slot: 'HEAD',
      grade: 'COMMON',
    },
    {
      listingId: 2,
      itemId: 12,
      labelKo: '대검',
      price: 900,
      isMine: true,
      affixes: [],
      expiresInMinutes: 10,
      fee: 45,
      slot: 'WEAPON_MAIN',
      grade: 'FINE',
    },
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
      link="online"
      detail=""
      worn={new Map()}
      onBuy={noop}
      onCancel={noop}
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
        link="offline"
        detail=""
        worn={new Map()}
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

describe('경매 — 사기 전에 알아야 할 것 (모바일 우선)', () => {
  const markup = renderToStaticMarkup(
    <WorldPanel
      progress={PROGRESS}
      leaderboard={undefined}
      auction={AUCTION}
      accountId={1}
      link="online"
      detail=""
      worn={new Map()}
      onBuy={() => undefined}
      onCancel={() => undefined}
      onDaily={() => undefined}
    />,
  )

  it('★ 접사가 보인다 — 이름과 값만 보고 사면 저주를 돈 주고 산다', () => {
    expect(markup).toContain('튼튼함 · 최대체력 +8')
  })

  it('★ 언제 사라지는지 보인다', () => {
    expect(markup).toContain('42분 뒤 사라진다')
  })

  it('★ 내 매물에는 못 돌려받는 수수료를 적는다', () => {
    expect(markup).toContain('수수료 45')
  })

  it('★ 버튼이 자기 줄에 있다 — 한 줄에 몰면 좁은 폭에서 밀려 나간다', () => {
    // 세로 배치에서 버튼은 --tap-min(44px)까지 커진다. 이름·접사와 같은 줄에 두면
    // 그 높이가 줄을 밀어 올려 겹친다.
    expect(markup).toContain('wld__listing')
  })
})



describe('세계 패널이 나에 대한 것을 안 그린다', () => {
  const markup = renderToStaticMarkup(
    <WorldPanel
      progress={PROGRESS}
      leaderboard={LEADERBOARD}
      auction={AUCTION}
      accountId={7}
      link="online"
      detail=""
      worn={new Map()}
      onBuy={noop}
      onCancel={noop}
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

describe('사기 전에 내 것과 견준다', () => {
  const WORN = new Map([
    [
      'HEAD',
      {
        itemId: 99,
        catalogId: 'helm_old',
        labelKo: '낡은 투구',
        kind: 'EQUIPMENT',
        slot: 'HEAD',
        hands: null,
        equippedSlot: 'HEAD',
        isBroken: false,
        isBound: false,
        isRecovered: false,
        sealedSlots: 0,
        unsealCost: 0,
        grade: 'COMMON',
        attackRange: 0,
        affixes: [
          { stat: 'hp_max', flat: 3, percent: 0, labelKo: '', statLabel: '최대체력' },
        ],
        requirements: [],
        canEquip: true,
      },
    ],
  ])

  const markup = renderToStaticMarkup(
    <WorldPanel
      progress={PROGRESS}
      leaderboard={LEADERBOARD}
      auction={AUCTION}
      accountId={7}
      link="online"
      detail=""
      worn={WORN}
      onBuy={noop}
      onCancel={noop}
      onDaily={noop}
    />,
  )

  it('★ 매물이 내 것보다 얼마나 나은지 적는다 — 사면 귀속돼 되돌릴 수 없다', () => {
    // 철 투구는 체력 +8, 낡은 투구는 +3 이므로 차이는 +5 다.
    expect(markup).toContain('invd__compare')
    expect(markup).toContain('+5')
  })

  it('★ 빈 자리는 그렇게 말한다 — 견줄 상대가 없는 것과 같은 것은 다르다', () => {
    // 대검 자리(WEAPON_MAIN)에는 아무것도 안 꼈다.
    expect(markup).toContain('빈 자리')
  })

  it('★ 스탯별로 낸다 — 한 숫자로 접으면 기준을 코드가 정하게 된다', () => {
    // 견줌 줄마다 **어느 스탯인지**가 붙어 있어야 한다. 「+5」만 있으면 무엇이 +5 인지
    // 모르고, 그것은 판단을 대신해 주는 척하면서 아무 말도 안 하는 것이다.
    expect(markup).toContain('invd__compare-name')
    expect(markup).toContain('최대체력')
    // 「이게 낫다」 같은 한 줄 판정을 내리지 않는다.
    expect(markup).not.toContain('추천')
    expect(markup).not.toContain('더 좋다')
  })
})
