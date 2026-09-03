/**
 * 봇 관리 패널 검사.
 *
 * **결과가 먼저 보여야 한다.** 규칙표와 실력은 우리가 정해 준 값이라 새 사실이 없고,
 * 알아야 할 것은 몇 판을 돌았고 몇 번 이겼는가다 — 승리가 0이면 그 봇은 세계에 아무것도
 * 안 남긴다. 그 사실이 한눈에 안 보이면 봇을 늘릴지 줄일지 정할 수 없다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { BotPanel, formatCadence, formatDue, formatWinRate } from './BotPanel'
import type { BotOverview } from '../storage/botAdmin'

const OVERVIEW: BotOverview = {
  maxRunsPerHour: 5,
  minCadenceSec: 720,
  bots: [
    {
      accountId: 1,
      handle: 'bot1',
      label: '겨눔',
      rulesetId: 'sniper',
      cadenceSec: 720,
      skillPct: 100,
      isActive: true,
      dueInSec: 300,
      runs: 40,
      wins: 3,
      bestFloor: 2,
      balance: 240,
      items: 5,
    },
    {
      accountId: 2,
      handle: 'bot2',
      label: '겁쟁이',
      rulesetId: 'g0_kite',
      cadenceSec: 3600,
      skillPct: 30,
      isActive: false,
      dueInSec: -10,
      runs: 12,
      wins: 0,
      bestFloor: 0,
      balance: 0,
      items: 0,
    },
  ],
  doppels: [],
}

describe('표기', () => {
  it('★ 승률에 분모를 함께 적는다 — 「100%」가 1판인지 100판인지 알아야 한다', () => {
    expect(formatWinRate(3, 40)).toBe('3 / 40 (8%)')
    expect(formatWinRate(0, 0)).toBe('0 / 0')
  })

  it('리듬을 시간당 판으로 되돌린다 — 초로 적으면 읽을 때마다 나눠야 한다', () => {
    expect(formatCadence(720)).toBe('5판/시간')
    expect(formatCadence(3600)).toBe('1판/시간')
    expect(formatCadence(0)).toBe('—')
  })

  it('차례가 지났으면 「차례」라고 적는다 — 음수 초는 아무것도 안 말한다', () => {
    expect(formatDue(-10)).toBe('차례')
    expect(formatDue(300)).toBe('5분 뒤')
  })
})

describe('봇 패널', () => {
  const html = renderToStaticMarkup(
    <BotPanel overview={OVERVIEW} rulesetIds={['sniper', 'g0_kite']} onSave={() => undefined} />,
  )

  it('★ 판·승·최고층이 줄에 있다 — 성격보다 결과가 먼저다', () => {
    expect(html).toContain('3 / 40 (8%)')
    expect(html).toContain('2층')
    expect(html).toContain('bot1')
  })

  it('★ 돌림/멈춤을 글자로도 적는다 — 색은 정보의 유일한 채널이 될 수 없다', () => {
    expect(html).toContain('돌림')
    expect(html).toContain('멈춤')
  })

  it('머리글이 돌고 있는 수와 이긴 봇 수를 적는다', () => {
    expect(html).toContain('1 / 2 돌림')
    expect(html).toContain('이긴 봇 1')
  })

  it('★ 아무도 못 이기면 그 사실을 먼저 말한다', () => {
    const none = {
      ...OVERVIEW,
      bots: OVERVIEW.bots.map((bot) => ({ ...bot, wins: 0 })),
    }
    const shown = renderToStaticMarkup(
      <BotPanel overview={none} rulesetIds={[]} onSave={() => undefined} />,
    )
    expect(shown).toContain('아직 아무 봇도 못 이겼다')
  })

  it('이긴 봇이 있으면 그 경고를 안 띄운다', () => {
    expect(html).not.toContain('아직 아무 봇도 못 이겼다')
  })

  it('도플갱어가 없으면 왜 없는지 말한다 — 빈 화면은 고장으로 읽힌다', () => {
    expect(html).toContain('아직 도플갱어가 없다')
  })

  it('도플갱어가 있으면 누구의 그림자인지 적는다', () => {
    const withOne = {
      ...OVERVIEW,
      doppels: [
        {
          recordId: 7,
          zoneFloor: 3,
          level: 6,
          alive: true,
          entitySlot: 'doppel_7',
          originHandle: 'bot1',
        },
      ],
    }
    const shown = renderToStaticMarkup(
      <BotPanel overview={withOne} rulesetIds={[]} onSave={() => undefined} />,
    )
    expect(shown).toContain('bot1 의 그림자')
    expect(shown).toContain('3층')
  })

  it('★ 넘기기는 되돌릴 수 없다고 먼저 말한다 — 귀속은 눌러 본 뒤에 알면 늦다', () => {
    const shown = renderToStaticMarkup(
      <BotPanel
        overview={OVERVIEW}
        rulesetIds={[]}
        onSave={() => undefined}
        onGift={() => undefined}
      />,
    )
    // 줄을 안 골랐으면 조작이 없다. 고른 뒤에 뜨는 것이 맞다.
    expect(shown).not.toContain('넘기면 귀속된다')
  })

  it('★ 넘기는 길만 있고 되받는 길이 없다 — 한 방향이어야 성립한다', async () => {
    const source = await import('../storage/botAdmin')
    expect(Object.keys(source)).toContain('applyBotGift')
    expect(Object.keys(source).join(' ')).not.toMatch(/takeFromBot|reclaim/)
  })

  it('현황이 없어도 안 터진다 — 서버에 못 닿는 것은 흔한 일이다', () => {
    const shown = renderToStaticMarkup(
      <BotPanel overview={undefined} rulesetIds={[]} onSave={() => undefined} />,
    )
    expect(shown).toContain('봇이 없다')
  })
})
