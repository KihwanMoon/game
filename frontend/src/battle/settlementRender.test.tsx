/**
 * 정산 탭 렌더 검사.
 *
 * jsdom 없이 `renderToStaticMarkup` 으로 읽는다 — 이 저장소의 렌더 검사가 전부 그렇고,
 * 그래서 `SettlementPanel` 은 훅을 안 쓴다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { BattlePortrait, type BattlePortraitProps } from './BattlePortrait'
import { SettlementPanel } from './SettlementPanel'

const SETTLED = [
  { floor: 1, lines: ['화폐 +40', '경험치 +80'] },
  { floor: 2, lines: ['화폐 +80', '사슬 갑옷(FINE) 획득'] },
]

describe('SettlementPanel', () => {
  it('★ 항목마다 제 줄을 갖는다 — 한 줄에 정보 하나가 이 탭의 이유다', () => {
    const html = renderToStaticMarkup(<SettlementPanel settlements={SETTLED} />)
    expect(html.split('settle__row').length - 1).toBe(4)
    expect(html).toContain('1층 정산')
    expect(html).toContain('사슬 갑옷(FINE) 획득')
  })

  it('빈 목록에도 말을 한다 — 빈 화면은 고장으로 읽힌다', () => {
    expect(renderToStaticMarkup(<SettlementPanel settlements={[]} />)).toContain('아직 정산한 층')
  })
})

/**
 * 전투 화면 props 를 최소로 짠다.
 *
 * @param patch 덮어쓸 값.
 * @returns props.
 */
function buildProps(patch: Partial<BattlePortraitProps> = {}): BattlePortraitProps {
  return {
    location: '2층 · corridor',
    tick: 12,
    speed: 1,
    onSpeedChange: () => undefined,
    onInstant: () => undefined,
    onStep: () => undefined,
    onRestart: () => undefined,
    tab: 'reward',
    onTabChange: () => undefined,
    rows: [],
    onToggleRule: () => undefined,
    entries: [],
    cpuUsed: 4,
    cpuBudget: 8,
    hp: 80,
    hpMax: 100,
    potions: 1,
    potionsMax: 2,
    scrolls: 0,
    scrollsMax: 1,
    outcome: 'OUTCOME_ONGOING',
    ...patch,
  }
}

describe('전투 화면의 정산 탭', () => {
  it('★ 로그와 같은 급의 탭으로 선다 — 상단 알림이 아니다', () => {
    const html = renderToStaticMarkup(<BattlePortrait {...buildProps({ settlements: SETTLED })} />)
    expect(html).toContain('정산')
    expect(html).toContain('2층 정산')
    // 탭 카운트가 정산한 층 수를 적는다.
    expect(html).toContain('2층<')
  })

  it('정산 탭을 안 보고 있으면 본문에 안 나온다', () => {
    const html = renderToStaticMarkup(
      <BattlePortrait {...buildProps({ tab: 'log', settlements: SETTLED })} />,
    )
    expect(html).not.toContain('settle__row')
  })
})
