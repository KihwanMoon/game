/**
 * 값 트리 편집.
 *
 * 여기서 지키는 것은 넷이다.
 *
 * 1. **모양이 안 깨진다.** 값만 바꾸므로 키가 늘거나 줄지 않는다.
 * 2. **지나가는 길만 새로 만든다.** 통째로 복사하면 주석 같은 필드가 살아남는지 아무도
 *    확신하지 못한다.
 * 3. **숫자 칸이 숫자가 아니면 안 바꾼다.** 반쯤 친 글자가 값을 지우면 고치는 중에 절이
 *    깨진 상태로 저장될 수 있다.
 * 4. **없는 자리는 안 만든다.** 만들면 로더가 못 읽는 절이 생긴다.
 */
import { describe, expect, it } from 'vitest'

import { applyValueAt, parseLeafText, readLeafKind } from './valueTree'
import balanceRaw from '@resources/balance/balance.json'

const BALANCE = balanceRaw as unknown as Record<string, unknown>

describe('값 트리', () => {
  it('★ 값만 바뀌고 키는 그대로다', () => {
    const next = applyValueAt(BALANCE, ['player', 'attack'], 99) as Record<string, unknown>
    expect(Object.keys(next)).toEqual(Object.keys(BALANCE))
    const player = next.player as Record<string, unknown>
    expect(Object.keys(player)).toEqual(Object.keys(BALANCE.player as object))
    expect(player.attack).toBe(99)
  })

  it('★ 안 지나간 가지는 원본 객체 그대로다', () => {
    const next = applyValueAt(BALANCE, ['player', 'attack'], 99) as Record<string, unknown>
    expect(next.enemies).toBe(BALANCE.enemies)
    expect(next.anti_abuse).toBe(BALANCE.anti_abuse)
  })

  it('★ 배열 안도 자리로 찾아간다 — 몬스터 스탯이 거기 있다', () => {
    const next = applyValueAt(BALANCE, ['enemies', 0, 'hp_max'], 7) as Record<string, unknown>
    const rows = next.enemies as Record<string, unknown>[]
    expect(rows[0]?.hp_max).toBe(7)
    expect(rows[1]).toBe((BALANCE.enemies as unknown[])[1])
  })

  it('★ 없는 자리는 안 만든다 — 만들면 로더가 못 읽는 절이 생긴다', () => {
    expect(applyValueAt(BALANCE, ['no_such_key'], 1)).toBe(BALANCE)
    expect(applyValueAt(BALANCE, ['enemies', 999, 'hp_max'], 1)).toBe(BALANCE)
  })

  it('★ 숫자 칸이 숫자가 아니면 안 바꾼다', () => {
    expect(parseLeafText('number', 'abc', 5)).toBe(5)
    expect(parseLeafText('number', '', 5)).toBe(5)
    expect(parseLeafText('number', '12', 5)).toBe(12)
  })

  it('★ 비운 null 자리는 다시 null 이다 — range 가 null 이면 엔티티가 사거리를 정한다', () => {
    expect(parseLeafText('null', '', null)).toBeNull()
    expect(parseLeafText('null', '3', null)).toBe(3)
  })

  it('잎과 가지를 가른다', () => {
    expect(readLeafKind(1)).toBe('number')
    expect(readLeafKind('a')).toBe('string')
    expect(readLeafKind(true)).toBe('boolean')
    expect(readLeafKind(null)).toBe('null')
    expect(readLeafKind({})).toBeUndefined()
    expect(readLeafKind([])).toBeUndefined()
  })
})
