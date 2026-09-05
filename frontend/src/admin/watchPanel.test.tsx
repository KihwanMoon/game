/**
 * 지킴이 화면 검사.
 *
 * **여기서 지키는 것은 「먼저 보이는 것」이다.** 지킴이는 5분마다 정확히 판단해 놓고
 * 컨테이너 로그에서 죽고 있었다 (Z1). 화면에 올려도 여덟 줄이 등급 없이 늘어서면
 * 무엇을 먼저 볼지가 안 정해지고, 그러면 결국 안 읽힌다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { WatchPanel, resolveLevelState } from './WatchPanel'
import type { WatchView } from '../storage/watchAdmin'

const QUIET: WatchView = {
  rows: [
    {
      key: '경매',
      level: 'OK',
      text: '매물이 팔린다',
      detail: '창 지난 0 / 열린 3건',
      changedAt: '2026-09-01 09:00',
      seenAt: '2026-09-05 15:00',
    },
  ],
  events: [],
  deploy: {
    changes: [],
    authors: [],
    breakage: [],
    undo: ['git revert <커밋> && docker compose up -d --build frontend backend'],
    gateCommands: ['./tools/check_all.sh', 'pytest -q'],
    openRuns: 0,
  },
}

const BURNING: WatchView = {
  ...QUIET,
  rows: [
    {
      key: '봇 러너',
      level: '틀림',
      text: '봇이 아무도 안 돈다 — 러너를 본다',
      detail: '10 / 10마리 차례 지남',
      changedAt: '2026-09-04 13:20',
      seenAt: '2026-09-05 15:00',
    },
    QUIET.rows[0]!,
  ],
  events: [
    {
      key: '봇 러너',
      level: '틀림',
      text: '봇이 아무도 안 돈다 — 러너를 본다',
      detail: '10 / 10마리 차례 지남',
      happenedAt: '2026-09-04 13:20',
    },
  ],
}

function render(view: WatchView | undefined) {
  return renderToStaticMarkup(<WatchPanel view={view} onRefresh={() => undefined} />)
}

describe('resolveLevelState', () => {
  it('세 등급이 서로 다른 도형을 받는다', () => {
    const found = ['OK', '살핌', '틀림'].map(resolveLevelState)
    expect(new Set(found).size).toBe(3)
  })

  it('모르는 등급을 「괜찮다」로 읽지 않는다', () => {
    // 모르는 것을 통과로 처리하면 새 등급이 생겼을 때 조용히 안 보인다.
    expect(resolveLevelState('처음 보는 것')).not.toBe('true')
  })
})

describe('WatchPanel', () => {
  it('★ 가장 나쁜 것을 먼저 말한다', () => {
    // 여덟 줄을 다 읽게 하면 결국 안 읽힌다.
    expect(render(BURNING)).toContain('1개 지표가 틀렸다 — 고치기 전에 배포하지 않는다')
  })

  it('조용하면 조용하다고 말한다 — 빈 화면은 고장으로 읽힌다', () => {
    expect(render(QUIET)).toContain('지표가 모두 괜찮다')
  })

  it('★ 「언제부터」를 적는다 — 지킴이의 값은 시간축에 있다', () => {
    expect(render(BURNING)).toContain('2026-09-04 13:20 부터')
  })

  it('괜찮은 줄에는 「언제부터」를 안 적는다 — 잡음이 되면 나쁜 줄이 묻힌다', () => {
    const html = render(QUIET)
    expect(html).toContain('2026-09-05 15:00')
    // 「언제부터」는 머리글에 있으므로, 괜찮은 줄의 **값**에 안 붙는지를 본다.
    expect(html).not.toContain('15:00 부터')
  })

  it('등급을 글자로도 적는다 — 색으로만 적지 않는다', () => {
    const html = render(BURNING)
    expect(html).toContain('틀림')
    expect(html).toContain('OK')
  })

  it('★ 되돌리는 법은 나갈 것이 없어도 늘 있다', () => {
    // 없으면 컨펌이 아니라 도박이다.
    expect(render(QUIET)).toContain('되돌리는 법')
    expect(render(QUIET)).toContain('git revert')
  })

  it('★ 게이트는 돌리는 버튼이 아니라 옮겨 칠 명령이다', () => {
    // 화면이 pytest·npm 을 띄울 길을 만들면 그것이 임의 실행 통로가 된다.
    const html = render(QUIET)
    expect(html).toContain('여기서 안 돌린다')
    expect(html).toContain('./tools/check_all.sh')
  })

  it('아직 아무것도 안 남겼으면 왜 비었는지 적는다', () => {
    const html = render({ ...QUIET, rows: [] })
    expect(html).toContain('아직 아무것도 안 남겼다')
  })

  it('아직 안 읽었을 때도 그린다', () => {
    expect(render(undefined)).toContain('지표 0')
  })

  it('바뀐 적이 없으면 그렇게 적는다', () => {
    expect(render(QUIET)).toContain('아직 바뀐 적이 없다')
  })
})
