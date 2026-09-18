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
  it('★ 판이 안 남은 줄을 세되 **원인은 단언하지 않는다**', () => {
    // 티켓을 못 받았을 수도, 그냥 들렀다 갔을 수도 있다 — `1227425`(2026-09-17) 전에는
    // 페이지를 여는 것만으로 계정이 생겼고 그 시절 줄이 여기 섞인다. 원인을 적으면
    // 아직 안 센 것을 센 것처럼 말하게 된다.
    const html = renderToStaticMarkup(<ArrivalPanel list={LIST} />)
    expect(html).toContain('1명은 서버에 판이 안 남았다')
    expect(html).not.toContain('티켓을 못 받은 것이다')
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
