/**
 * 지나간 판 목록 — **다시 볼 수 있는가** (결정 #09).
 *
 * 리플레이는 오래 관리자 전용이었다. 그런데 결정 #09 가 재려는 것이 「관전이 재미있는가」
 * 라서, 사람이 못 열면 그 질문 자체를 못 던진다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { RunHistoryRow } from '../storage'

import { RunHistoryPanel, formatRunOutcome } from './RunHistoryPanel'

const RUNS: readonly RunHistoryRow[] = [
  {
    submissionId: 7,
    roomId: 'corridor',
    floor: 3,
    seed: 4242,
    outcome: 'PLAYER_WIN',
    ticks: 57,
    playerHp: 89,
    verdict: 'verified',
    submittedAt: '2026-09-05T00:00:00Z',
  },
  {
    submissionId: 8,
    roomId: 'chapel',
    floor: 4,
    seed: 99,
    outcome: 'PLAYER_LOSS',
    ticks: 31,
    playerHp: 0,
    verdict: 'verified',
    submittedAt: '2026-09-05T00:01:00Z',
  },
]

describe('결과 문구', () => {
  it('★ 판정 전과 패배를 가른다 — 서버가 밀렸을 뿐인데 진 것으로 읽히면 안 된다', () => {
    expect(formatRunOutcome('')).toBe('판정 전')
    expect(formatRunOutcome('PLAYER_LOSS')).toBe('패배')
    expect(formatRunOutcome('PLAYER_WIN')).toBe('승리')
    // 시간 초과는 진 것과 다르다 — 규칙표가 아무것도 안 한 것이지 진 것이 아니다.
    expect(formatRunOutcome('TIMEOUT')).toBe('시간 초과')
  })
})

describe('지나간 판 목록', () => {
  const render = (runs: readonly RunHistoryRow[] = RUNS, link: 'online' | 'offline' = 'online') =>
    renderToStaticMarkup(
      <RunHistoryPanel runs={runs} link={link} onReplay={() => undefined} />,
    )

  it('판마다 다시 보기가 선다', () => {
    const html = render()
    expect(html.match(/다시 보기/g)).toHaveLength(2)
  })

  it('★ 시드를 적는다 — 재생이 같은 판을 도는 근거가 그것이다', () => {
    expect(render()).toContain('시드 4242')
  })

  it('그때의 결과를 함께 적는다 — 재생이 같은 답을 내는지 눈으로 대조해야 한다', () => {
    const html = render()
    expect(html).toContain('승리')
    expect(html).toContain('패배')
    expect(html).toContain('57틱')
  })

  it('한 판도 없으면 그렇게 말한다 — 빈 화면은 고장으로 읽힌다', () => {
    const html = render([])
    expect(html).toContain('아직 돈 판이 없다')
    expect(html).not.toContain('다시 보기')
  })

  it('못 닿았으면 「없다」가 아니라 「못 읽었다」로 적는다', () => {
    const html = render([], 'offline')
    expect(html).not.toContain('아직 돈 판이 없다')
    expect(html).toContain('지나간 판은 서버가 안다')
  })
})
