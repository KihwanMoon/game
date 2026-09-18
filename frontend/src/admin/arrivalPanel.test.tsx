/**
 * 유입 패널 (U1, 2026-09-18).
 *
 * 이 화면이 답하려는 것은 하나다 — **들어온 사람 중 몇이 실제로 놀았나.**
 * 그 답이 없어서 DB 를 직접 열어야 했고, 그러면 아무도 안 본다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { ArrivalPanel, formatArrivalSummary } from './ArrivalPanel'
import type { ArrivalList } from '../storage/arrivalAdmin'

const LIST: ArrivalList = {
  days: 14,
  arrived: 124,
  joined: 1,
  played: 2,
  rows: [
    {
      accountId: 330,
      name: 'user_ddc5',
      isJoined: false,
      isBot: false,
      createdAt: '2026-09-17 14:00',
      runs: 0,
      bestFloor: 0,
    },
    {
      accountId: 12,
      name: '길잡이',
      isJoined: true,
      isBot: false,
      createdAt: '2026-09-02 11:20',
      runs: 40,
      bestFloor: 3,
    },
    {
      accountId: 9,
      name: 'bot_3f9a',
      isJoined: false,
      isBot: true,
      createdAt: '2026-09-03 09:00',
      runs: 900,
      bestFloor: 7,
    },
  ],
}

describe('요약', () => {
  it('★ 깔때기로 적는다 — 수를 따로 늘어놓으면 관계를 사람이 계산해야 한다', () => {
    expect(formatArrivalSummary(LIST)).toBe('14일 · 들어옴 124 → 판 낸 이 2 → 가입 1')
  })

  it('기간을 밝힌다 — 기간 없는 수는 옛날에 붐볐던 곳과 구별되지 않는다', () => {
    expect(formatArrivalSummary({ ...LIST, days: 30 })).toContain('30일')
  })
})

describe('유입 패널', () => {
  it('★ **서버에 판이 안 남은 줄을 세어 경보로 올린다**', () => {
    // 출격을 눌러 계정까지 생겼는데 판이 0 이면 사람이 안 논 것이 아니라 우리가 못
    // 받은 것이다 — `requestTicket` 이 실패하면 화면이 `applyLocalRun()` 으로 떨어지고,
    // 그 판은 G1 계측에서 통째로 빠진다. 이 화면이 그것을 보려고 있다.
    const html = renderToStaticMarkup(<ArrivalPanel list={LIST} />)
    expect(html).toContain('1명은 출격했는데 서버에 판이 안 남았다')
  })

  it('★ 봇은 그 경보에 안 센다 — 우리가 들인 것이라 유입이 아니다', () => {
    const onlyBot: ArrivalList = {
      ...LIST,
      rows: [{ ...LIST.rows[2]!, runs: 0 }],
    }
    const html = renderToStaticMarkup(<ArrivalPanel list={onlyBot} />)
    expect(html).not.toContain('서버에 판이 안 남았다')
  })

  it('경보가 0 이면 안 적는다 — 없는 경보를 늘 띄우면 아무도 안 읽는다', () => {
    const healthy: ArrivalList = { ...LIST, rows: [LIST.rows[1]!] }
    const html = renderToStaticMarkup(<ArrivalPanel list={healthy} />)
    expect(html).not.toContain('서버에 판이 안 남았다')
  })

  it('★ 가입과 익명을 색만으로 가르지 않는다 — 글리프와 말이 함께 선다', () => {
    const html = renderToStaticMarkup(<ArrivalPanel list={LIST} />)
    expect(html).toContain('가입')
    expect(html).toContain('익명')
  })

  it('못 읽으면 그 사실을 적는다 — 빈 화면은 「아무도 없다」로 읽힌다', () => {
    const html = renderToStaticMarkup(<ArrivalPanel list={undefined} />)
    expect(html).toContain('서버에 닿지 못했다')
  })
})
