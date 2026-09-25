/**
 * 방별 기록판 문구 (2026-09-25).
 *
 * **CPU 가 먼저다** — 순위를 가르는 순서(CPU → 틱 → 줄 수)를 글에서도 지킨다. 틱을 앞에
 * 두면 「빨리 깬 쪽이 위」로 읽힌다.
 */
import { describe, expect, it } from 'vitest'

import { formatRecordScore, formatRecordSummary, type RoomRecordRow } from './roomRecords'

const ROW: RoomRecordRow = {
  rank: 3,
  handle: '서생',
  cpu: 4,
  ticks: 41,
  ruleCount: 2,
  shareId: 'abc123def456',
  accountId: 7,
}

describe('방 기록판 문구', () => {
  it('★ CPU → 틱 → 줄 수 순서로 적는다', () => {
    expect(formatRecordScore(ROW)).toBe('CPU 4 · 41틱 · 2줄')
  })

  it('★ 서버에 못 닿으면 아무것도 안 적는다', () => {
    expect(formatRecordSummary(undefined)).toBe('')
  })

  it('★ 아직 아무도 없는 방에도 할 말이 있다', () => {
    const line = formatRecordSummary({ roomId: 'open_field', players: 0, rows: [], mine: undefined })
    expect(line).toContain('아직 아무도')
    expect(line).toContain('이기면')
  })

  it('★ 내 기록은 윗자리 밖이어도 순위와 함께 적는다', () => {
    const line = formatRecordSummary({ roomId: 'open_field', players: 30, rows: [], mine: { ...ROW, rank: 27 } })
    expect(line).toContain('CPU 4')
    expect(line).toContain('27위')
    expect(line).toContain('30명')
  })
})
