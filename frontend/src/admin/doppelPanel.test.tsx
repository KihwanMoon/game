/**
 * 도플갱어 패널 검사 — **봇 탭에서 갈라 나왔다.**
 *
 * 한 탭에 봇 표와 도플갱어 표가 함께 있어서, 봇 하나를 열면 그 상세가 도플갱어 목록 뒤로
 * 밀렸다 — 두 표가 서로의 자리를 다퉜다. 둘은 다른 것이다: 봇은 **계정**이고 도플갱어는
 * **얼려 둔 개체 기록**이다.
 *
 * 여기서 지키는 것은 셋이다.
 *
 * 1. **봇과 같은 UI 를 쓴다** — 같은 탭 껍데기. 같은 것을 두 모양으로 그리면 답이 갈린다.
 * 2. **탭 수가 다르다** — 정비·스킬·리플레이가 없고, 없는 이유를 화면이 적는다.
 * 3. **조작이 없다** — 아이템이 아니라 기록이라 걸 자리가 없다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { DoppelDetail } from '../storage'

import { DoppelDetailPanel } from './BotDetail'
import { DoppelPanel } from './DoppelPanel'

const OVERVIEW = {
  maxRunsPerHour: 5,
  minCadenceSec: 720,
  bots: [],
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
} as unknown as Parameters<typeof DoppelPanel>[0]['overview']

const DETAIL: DoppelDetail = {
  recordId: 7,
  originHandle: 'bot1',
  zoneFloor: 3,
  level: 6,
  isAlive: true,
  entitySlot: 'doppel_7',
  ruleset: { rules: [{ priority: 1, action: 'ATTACK' }] },
}

describe('도플갱어 목록', () => {
  it('도플갱어가 없으면 왜 없는지 말한다 — 빈 화면은 고장으로 읽힌다', () => {
    const html = renderToStaticMarkup(
      <DoppelPanel
        overview={{ ...OVERVIEW, doppels: [] } as typeof OVERVIEW}
        detail={undefined}
        gear={undefined}
      />,
    )
    expect(html).toContain('아직 도플갱어가 없다')
  })

  it('도플갱어가 있으면 누구의 그림자인지 적는다', () => {
    const html = renderToStaticMarkup(
      <DoppelPanel overview={OVERVIEW} detail={undefined} gear={undefined} />,
    )
    expect(html).toContain('bot1 의 그림자')
    expect(html).toContain('3층')
  })

  it('★ 안 골랐으면 상세가 자기 자리를 지키며 비어 있다 — 빈 패널은 고장으로 읽힌다', () => {
    const html = renderToStaticMarkup(
      <DoppelPanel overview={OVERVIEW} detail={undefined} gear={undefined} />,
    )
    expect(html).toContain('줄을 고르면')
    expect(html).not.toContain('얼려 둔 기록이다')
  })
})

describe('도플갱어 상세 — 봇과 같은 UI, 다른 탭 수', () => {
  const html = renderToStaticMarkup(<DoppelDetailPanel detail={DETAIL} gear={undefined} />)

  it('★ 봇과 같은 탭 껍데기를 쓴다', () => {
    expect(html).toContain('botd__tabs')
  })

  it('★ 있는 탭은 셋이다 — 전투 규칙 · 캐릭터 · 장비', () => {
    for (const label of ['전투 규칙', '캐릭터', '장비']) {
      expect(html).toContain(label)
    }
  })

  it('★ 없는 탭은 세우지 않고 왜 없는지 적는다 — 빈 탭은 고장으로 읽힌다', () => {
    expect(html).not.toContain('>정비 규칙<')
    expect(html).not.toContain('>리플레이<')
    expect(html).toContain('계정이 아니라 얼려 둔 개체 기록이라')
  })

  it('★ 규칙표가 id 가 아니라 절이다 — 죽던 순간의 것을 통째로 얼려 갖고 있다', () => {
    expect(html).toContain('[1]')
    expect(html).toContain('ATTACK')
  })

  it('머리에 원본과 층·레벨을 적는다 — 탭을 안 열어도 무엇인지 알아야 한다', () => {
    expect(html).toContain('bot1')
    expect(html).toContain('3층 · lv6')
  })
})
