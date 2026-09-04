/**
 * 성장 화면 검사 (결정 #51).
 *
 * **세계 화면에서 갈라 나왔다.** 레벨과 능력치는 세계에 대한 사실이 아니라 나에 대한
 * 사실인데, 순위·경매와 한 패널에 묶여 있었다 — 「내 캐릭터가 뭘 찍을 수 있나」를 보려고
 * 세계를 여는 것이 이상했다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { ProgressView } from '../storage'

import { GrowthPanel, formatAttributeEffect } from './GrowthPanel'
import type { LinkState } from './linkState'

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

/**
 * 성장 패널을 그린다.
 *
 * **기본 매개변수를 두지 않는다.** `undefined` 에 기본값이 발동하므로, 「서버가 아직
 * 안 줬다」를 재려던 검사가 조용히 정상 상태를 재게 된다.
 *
 * @param progress 성장 상태. 없으면 서버가 아직 안 준 것이다.
 * @returns 마크업.
 */
function draw(progress: ProgressView | undefined, link: LinkState = 'online'): string {
  return renderToStaticMarkup(
    <GrowthPanel progress={progress} link={link} onAllocate={noop} />,
  )
}

describe('성장 패널', () => {
  const markup = draw(PROGRESS)

  it('레벨과 다음 레벨까지의 경험치를 적는다', () => {
    expect(markup).toContain('6 · 120 / 300')
  })

  it('남은 능력치 포인트를 적는다', () => {
    // 15 받고 6 썼으니 9 남았다.
    expect(markup).toContain('남은 포인트 9')
  })

  it('★ 남은 포인트가 패널 머리에도 선다 — 펼쳐 봐야 알면 안 쓴 채로 계속 논다', () => {
    // 봇 열이 `stat_json` 을 비운 채 9점씩 놀리고 있던 것과 같은 일이다.
    expect(markup).toContain('ds-panel__meta')
    const head = markup.slice(0, markup.indexOf('ds-panel__body'))
    expect(head).toContain('남은 포인트 9')
  })

  it('★ 세계의 것은 안 그린다 — 순위와 경매는 나에 대한 사실이 아니다', () => {
    expect(markup).not.toContain('순위')
    expect(markup).not.toContain('경매')
  })

  it('★ 못 닿은 것과 아직 안 온 것을 갈라 적는다', () => {
    // 붙었는데 데이터가 안 온 사이 아무 말도 안 하면 「능력치가 없다」로 읽힌다.
    expect(draw(undefined, 'online')).toContain('불러오는 중이다')
    expect(draw(undefined, 'offline')).toContain('레벨과 능력치는 서버가 안다')
    expect(draw(undefined, 'probing')).toContain('서버에 연결하는 중이다')
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

describe('층 깊이 (설계/6_몬스터 §3)', () => {
  /**
   * 도달 층만 바꿔 성장 화면을 그린다.
   *
   * @param reachedFloor 도달 층.
   * @param floorCap 마지막 층.
   * @returns 마크업.
   */
  function drawDepth(reachedFloor: number, floorCap: number): string {
    return draw({ ...PROGRESS, reachedFloor, floorCap })
  }

  it('★ 어디까지 왔는지 말한다 — 없으면 자기가 몇 층인지 모른 채 같은 판을 돈다', () => {
    expect(drawDepth(4, 10)).toContain('4 / 10층')
  })

  it('★ 층이 무엇을 바꾸는지 말한다 — 깊이 가는 이유와 대가가 같은 줄에 있어야 한다', () => {
    expect(drawDepth(4, 10)).toContain('HP +25%')
  })

  it('★ 끝까지 왔으면 그렇게 말한다 — 더 갈 곳이 있는 것처럼 보이면 안 된다', () => {
    expect(drawDepth(10, 10)).toContain('끝까지 왔다')
  })
})
