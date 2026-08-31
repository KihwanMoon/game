/**
 * 런 티켓과 제출 계약이 파이썬 정본과 같은지 본다 (docs/설계/7_변조방지 §4).
 *
 * 이 파일의 존재 이유는 검사 하나다 — **제출에 결과 필드가 생기는 것을 막는다.**
 * 파이썬 `tests/test_run_ticket.py` 의 같은 검사와 짝이며, 한쪽만 지키면 소용이 없다.
 */
import { describe, expect, it } from 'vitest'

import {
  ENGINE_VERSION,
  MAX_SEED,
  LOCAL_TICKET_PREFIX,
  buildCoreVersion,
  buildSubmission,
  checkRanked,
  createLocalTicket,
  listSubmissionKeys,
} from './runTicket'
import type { RunMode } from './runTicket'
import { parseRuleSet } from './ruleset'
import golden from '../__golden__/run_ticket.json'

const CORE_VERSION = 'b4.v3.e1'
const EMPTY_RULESET = parseRuleSet({ ruleset_id: 'r', version: 1, rules: [] })

describe('제출 계약', () => {
  it('제출은 입력만 담는다 — 결과·시드·스냅샷을 받을 자리가 없다', () => {
    // 이 검사가 붉어지면 열쇠를 지우기 전에 docs/설계/7_변조방지 §4 를 먼저 읽는다.
    const ticket = createLocalTicket(1, 'room', CORE_VERSION)
    expect(listSubmissionKeys(buildSubmission(ticket, EMPTY_RULESET))).toEqual([
      'coreVersion',
      'ruleset',
      'ticketId',
    ])
  })

  it('제출은 시드를 티켓에서 가져오고 다시 싣지 않는다', () => {
    const ticket = createLocalTicket(99, 'room_a', CORE_VERSION)
    const submission = buildSubmission(ticket, EMPTY_RULESET)
    expect(submission.ticketId).toBe(ticket.ticketId)
    expect(Object.keys(submission)).not.toContain('seed')
  })
})

describe('로컬 티켓', () => {
  it.each<RunMode>(['RANKED', 'DAILY'])('%s 는 로컬이 만들 수 없다', (mode) => {
    // 로컬이 순위 티켓을 만들 수 있으면 시드 서버 발급이 아무것도 막지 못한다.
    expect(() => createLocalTicket(1, 'room', CORE_VERSION, 1, mode)).toThrow('서버가 발급')
  })

  it('연습 티켓은 로컬이 만든다', () => {
    const ticket = createLocalTicket(12345, 'room_a', CORE_VERSION)
    expect(ticket.ticketId.startsWith(LOCAL_TICKET_PREFIX)).toBe(true)
    expect(ticket.mode).toBe('PRACTICE')
    expect(checkRanked(ticket)).toBe(false)
  })

  it('같은 입력이 같은 티켓을 낸다 — 시간도 난수도 쓰지 않는다', () => {
    // 쓰면 같은 시드가 같은 티켓을 내지 않아 리플레이가 깨진다 (R5).
    expect(createLocalTicket(7, 'room_a', CORE_VERSION)).toEqual(
      createLocalTicket(7, 'room_a', CORE_VERSION),
    )
  })

  it('시드가 다르면 티켓도 다르다', () => {
    expect(createLocalTicket(7, 'a', CORE_VERSION).ticketId).not.toBe(
      createLocalTicket(8, 'a', CORE_VERSION).ticketId,
    )
  })
})

describe('시드 범위 — 이식 제약', () => {
  it('상한 그 자체는 받는다', () => {
    expect(createLocalTicket(MAX_SEED, 'a', CORE_VERSION).seed).toBe(MAX_SEED)
  })

  it('★ 상한을 넘는 시드를 거부한다', () => {
    // number 는 53비트다. 넘는 값은 반올림되어 파이썬과 다른 난수를 내고, 골든이 작은
    // 시드만 쓰므로 G3 도 그것을 보지 못한다.
    expect(() => createLocalTicket(MAX_SEED + 2, 'a', CORE_VERSION)).toThrow('이식 범위')
  })

  it('음수와 소수를 거부한다', () => {
    expect(() => createLocalTicket(-1, 'a', CORE_VERSION)).toThrow('이식 범위')
    expect(() => createLocalTicket(1.5, 'a', CORE_VERSION)).toThrow('이식 범위')
  })
})

describe('코어 버전', () => {
  it('★ 여섯 자산과 엔진을 모두 담는다 — 하나라도 빠지면 그 축이 시즌을 안 가른다', () => {
    // 자산마다 다른 값을 준다. 같은 값을 쓰면 축 하나를 다른 축에 붙여 놓아도 통과한다.
    const versions = { blocks: 4, balance: 3, items: 2, skills: 5, rooms: 6, enemies: 7 }
    expect(buildCoreVersion(versions)).toBe(`b4.v3.i2.s5.r6.a7.e${String(ENGINE_VERSION)}`)
  })
})

describe('파이썬 정본 대조', () => {
  it('코어 버전 문자열이 같다 — ENGINE_VERSION 이 갈리면 여기서 드러난다', () => {
    expect(buildCoreVersion(golden.versions)).toBe(golden.core_version)
  })

  it.each(golden.cases.map((item) => [item.ticket_id, item] as const))(
    '티켓 id 가 같다: %s',
    (_id, item) => {
      // id 형식이 갈리면 서버가 붙는 날 "티켓을 못 알아본다" 로 드러난다. 그때는 이미
      // 발급된 티켓이 있어 형식을 바꿀 수 없다.
      const ticket = createLocalTicket(item.seed, item.room_id, golden.core_version, item.floor)
      expect(ticket.ticketId).toBe(item.ticket_id)
      expect(ticket.mode).toBe(item.mode)
    },
  )
})
