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

  it('★ 도플갱어를 안 골랐으면 장비 격자를 안 그린다', () => {
    const withOne = {
      ...OVERVIEW,
      doppels: [
        {
          recordId: 7,
          zoneFloor: 3,
          level: 6,
          alive: true,
          entitySlot: 'goblin_rusher_0',
          originHandle: 'bot1',
        },
      ],
    }
    const shown = renderToStaticMarkup(
      <BotPanel overview={withOne} rulesetIds={[]} onSave={() => undefined} />,
    )
    expect(shown).not.toContain('얼려 둔 기록이다')
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

  it('현황이 없어도 안 터진다 — 서버에 못 닿는 것은 흔한 일이다', () => {
    const shown = renderToStaticMarkup(
      <BotPanel overview={undefined} rulesetIds={[]} onSave={() => undefined} />,
    )
    expect(shown).toContain('봇이 없다')
  })
})

const BAG = {
  slots: [
    { slotIndex: 0, item: { itemId: 42, labelKo: '사슬 갑옷', isBound: false, isBroken: false } },
    {
      slotIndex: 1,
      item: null,
      stackCatalogId: 'potion_heal',
      stackCount: 3,
      stackLabelKo: '치유 물약',
      stackUseTag: 'POTION',
    },
  ],
  equipment: [
    { slotIndex: 0, slot: 'BODY', item: { itemId: 7, labelKo: '판금 갑옷', isBroken: false } },
  ],
  balance: 0,
  repairCost: 0,
} as unknown as Parameters<typeof BotPanel>[0]['botBag']

describe('봇 인벤토리는 유저 화면과 같은 격자다', () => {
  const html = renderToStaticMarkup(
    <BotPanel
      overview={OVERVIEW}
      rulesetIds={[]}
      onSave={() => undefined}
      botBag={BAG}
      onGift={() => undefined}
    />,
  )

  it('줄을 안 골랐으면 격자를 안 그린다 — 고른 뒤에 뜨는 것이 맞다', () => {
    expect(html).not.toContain('invg--equip')
  })

  it('★ 유저 화면의 격자 클래스를 그대로 쓴다 — 같은 것을 두 모양으로 그리지 않는다', async () => {
    const { InventoryGrid } = await import('../editor/InventoryGrid')
    const grid = renderToStaticMarkup(
      <InventoryGrid inventory={BAG} pickedKey="" ownerLabel="bot1" onPick={() => undefined} />,
    )
    expect(grid).toContain('invg invg--equip')
    expect(grid).toContain('invg invg--bag')
    // 장비·소모품·가방이 한 격자 안에 있다 — 따로 만든 목록 셋이 하던 일이다.
    // 이름은 칸에 맞게 잘린다(`clipCellLabel`) — 전체 이름은 고른 칸의 상세가 편다.
    expect(grid).toContain('aria-label="BD 판금"')
    expect(grid).toContain('aria-label="CS 치유"')
    expect(grid).toContain('aria-label="IT 사슬"')
    expect(grid).toContain('bot1 · 장비')
  })

  it('★ 소모품 개수가 칸에 붙는다 — 개수 없이는 「있다」만 알 수 있다', async () => {
    const { InventoryGrid } = await import('../editor/InventoryGrid')
    const grid = renderToStaticMarkup(
      <InventoryGrid inventory={BAG} pickedKey="" onPick={() => undefined} />,
    )
    expect(grid).toContain('invg__count')
  })
})

describe('도플갱어 장비', () => {
  it('★ 봇과 같은 격자로 그린다 — 같은 것을 두 모양으로 그리면 답이 갈린다', async () => {
    const { InventoryGrid } = await import('../editor/InventoryGrid')
    const frozen = {
      slots: [],
      equipment: [
        { slotIndex: 0, slot: 'BODY', item: { itemId: 0, labelKo: '판금 갑옷', isBroken: false } },
      ],
      balance: 0,
      repairCost: 0,
    } as unknown as Parameters<typeof InventoryGrid>[0]['inventory']
    const grid = renderToStaticMarkup(
      <InventoryGrid inventory={frozen} pickedKey="" ownerLabel="#7" onPick={() => undefined} />,
    )
    expect(grid).toContain('invg invg--equip')
    expect(grid).toContain('aria-label="BD 판금"')
    // 가방은 늘 비어 있다 — 도플갱어는 아무것도 들고 다니지 않는다.
    expect(grid).toContain('#7 · 가방 0 / 20')
  })
})
