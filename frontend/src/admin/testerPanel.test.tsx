/**
 * 테스터 표시 패널 검사.
 *
 * **여기서 지키는 것은 분모다.** 익명으로 시작하는 게임이라 자동으로 세면 접속했다 떠난
 * 계정까지 테스터가 되고, 그 숫자는 「재미있었는가」가 아니라 「몇 명이 지나갔는가」다 —
 * 실측으로 36명 중 17명이 한 판짜리였고 그것이 평균 재도전을 1.2회로 눌러 놓고 있었다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { TesterPanel, formatTesterMeta, formatWho } from './TesterPanel'
import type { TesterList, TesterView } from '../storage/testerAdmin'

const JOINED: TesterView = {
  accountId: 27,
  handle: 'user_a1b2',
  loginId: 'sinindra',
  isTester: true,
  attempts: 791,
  lastSeen: '2026-09-05 10:00',
  isBot: false,
}

const ANONYMOUS: TesterView = {
  accountId: 94,
  handle: 'user_c3d4',
  loginId: '',
  isTester: false,
  attempts: 1,
  lastSeen: '2026-09-04 21:13',
  isBot: false,
}

/** 봇도 표시할 수 있다 (2026-09-10) — 다만 사람 수와 갈라 센다. */
const BOT: TesterView = {
  accountId: 114,
  handle: 'bot3',
  loginId: '',
  isTester: true,
  attempts: 412,
  lastSeen: '2026-09-10 09:20',
  isBot: true,
}

const LIST: TesterList = {
  rows: [JOINED, ANONYMOUS],
  marked: 1,
  markedBots: 0,
  minTesters: 5,
}

describe('formatWho', () => {
  it('가입한 계정은 아이디를 앞에 둔다', () => {
    // 익명은 번호뿐이라, 아이디가 있으면 그것이 화면에서 사람을 짚는 유일한 단서다.
    expect(formatWho(JOINED)).toBe('sinindra (user_a1b2)')
  })

  it('익명은 핸들만 적는다', () => {
    expect(formatWho(ANONYMOUS)).toBe('user_c3d4')
  })
})

describe('TesterPanel', () => {
  it('표시된 수를 기준과 나란히 적는다 — 그것이 G1 의 분모다', () => {
    const html = renderToStaticMarkup(
      <TesterPanel list={LIST} onMark={() => undefined} />,
    )
    expect(html).toContain('사람 1명')
    expect(html).toContain('기준 5명')
  })

  it('★ 분모가 모자라면 먼저 말한다', () => {
    // 안 말하면 「미달」이라는 판정 뒤에 「분모를 안 정했다」가 숨는다.
    const html = renderToStaticMarkup(
      <TesterPanel list={LIST} onMark={() => undefined} />,
    )
    expect(html).toContain('로드맵은 5명을 전제한다')
  })

  it('★ 참/거짓을 글자로도 적는다 — 색만으로 적지 않는다', () => {
    const html = renderToStaticMarkup(
      <TesterPanel list={LIST} onMark={() => undefined} />,
    )
    expect(html).toContain('테스터')
    expect(html).toContain('안 셈')
  })

  it('제출 수를 함께 보여 준다 — 익명 계정을 짚을 단서가 그것뿐이다', () => {
    const html = renderToStaticMarkup(
      <TesterPanel list={LIST} onMark={() => undefined} />,
    )
    expect(html).toContain('제출 791건')
    expect(html).toContain('제출 1건')
  })

  it('★ 제출 수로 거르는 조작을 두지 않는다 — 순환이기 때문이다', () => {
    // 「많이 논 계정」만 분모에 넣고 「평균 재도전 3회」를 재면 기준이 저절로 통과된다.
    const html = renderToStaticMarkup(
      <TesterPanel list={LIST} onMark={() => undefined} />,
    )
    expect(html).not.toContain('건 이상만')
    expect(html).not.toContain('자동')
  })

  it('아무것도 없으면 왜 없는지 적는다 — 빈 화면은 고장으로 읽힌다', () => {
    const html = renderToStaticMarkup(
      <TesterPanel list={{ rows: [], marked: 0, markedBots: 0, minTesters: 5 }} onMark={() => undefined} />,
    )
    expect(html).toContain('아무도 아직 접속하지 않았다')
  })

  it('아직 안 읽었을 때도 그린다', () => {
    const html = renderToStaticMarkup(
      <TesterPanel list={undefined} onMark={() => undefined} />,
    )
    expect(html).toContain('사람 0명')
  })
})

describe('봇을 테스터로 표시했을 때 (2026-09-10)', () => {
  const WITH_BOT: TesterList = {
    rows: [BOT, JOINED, ANONYMOUS],
    marked: 1,
    markedBots: 1,
    minTesters: 5,
  }

  it('★ **두 수를 더하지 않는다** — 더하면 화면과 게이트가 갈린다', () => {
    // 봇은 표시돼도 G1 에 안 센다. 합쳐 적으면 화면은 기준을 채웠다고 하는데 게이트는
    // 안 채워진 상태가 되고, 그 어긋남은 판정할 때에야 드러난다.
    expect(formatTesterMeta(1, 3, 5, 12)).toBe('사람 1명 / 기준 5명 · 봇 3개(안 셈) · 계정 12개')
    expect(formatTesterMeta(4, 0, 5, 12)).toBe('사람 4명 / 기준 5명 · 계정 12개')
  })

  it('★ 봇 줄에 봇이라고 적는다 — 「표시가 안 먹었나」를 그 자리에서 끊는다', () => {
    const html = renderToStaticMarkup(<TesterPanel list={WITH_BOT} onMark={() => undefined} />)
    expect(html).toContain('adminrow__tag')
    // 「테스터」라 적으면 분모로 읽힌다.
    expect(html).toContain('표시(안 셈)')
  })

  it('★ 봇이 표시돼 있으면 위쪽에도 적는다 — 줄마다 적힌 것은 훑기 전엔 안 보인다', () => {
    const html = renderToStaticMarkup(<TesterPanel list={WITH_BOT} onMark={() => undefined} />)
    expect(html).toContain('G1 에는 안 센다')
  })
})
