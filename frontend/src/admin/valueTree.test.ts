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

import {
  applyValueAt,
  checkIsNote,
  checkMatches,
  formatItemLabel,
  parseLeafText,
  readLeafKind,
} from './valueTree'
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

describe('★ 목록 항목은 번호가 아니라 이름으로 부른다', () => {
  // 적 열넷이 `0 1 2 …` 로 서 있으면 고치려는 그 한 마리를 찾으려고 열넷을 다 열어
  // 봐야 한다 — 「뭔지 하나도 인지가 안 된다」는 신고가 그 자리였다. 절 안에 이미
  // 이름이 들어 있는데 화면이 그것을 안 읽고 있었다.
  it('id 와 한글 이름을 함께 적는다', () => {
    expect(formatItemLabel(3, { id: 'bomb_slime', label_ko: '폭탄 슬라임' })).toBe(
      '3 · bomb_slime · 폭탄 슬라임',
    )
  })

  it('id 가 없으면 다른 열쇠를 찾는다 — 파일마다 이름 칸이 다르다', () => {
    expect(formatItemLabel(0, { template_id: 'corridor' })).toBe('0 · corridor')
    expect(formatItemLabel(1, { kind_id: 'goblin_rusher' })).toBe('1 · goblin_rusher')
  })

  it('이름이 없으면 번호만 — 지어내지 않는다', () => {
    expect(formatItemLabel(2, { hp_max: 10 })).toBe('2')
    expect(formatItemLabel(5, 42)).toBe('5')
    expect(formatItemLabel(0, null)).toBe('0')
  })
})

describe('★ 설명은 접어 둔다', () => {
  // 밸런스 파일은 왜 그 값인지를 절 안에 적어 둔다 — 좋은 규율이지만, 편집기가 그것을
  // 값과 나란히 세우면 스무 줄짜리 산문이 첫 화면을 통째로 먹는다.
  it('밑줄로 시작하면 설명이다', () => {
    expect(checkIsNote('_comment')).toBe(true)
    expect(checkIsNote('_note')).toBe(true)
    expect(checkIsNote('hp_max')).toBe(false)
  })
})

describe('★ 찾기 — 값 300개에서 하나를 고른다', () => {
  const FILE = {
    player: { hp_max: 100, attack: 12 },
    enemies: [{ id: 'goblin_rusher', hp_max: 20 }],
  }

  it('빈 말은 전부 통과시킨다 — 안 찾을 때는 안 거른다', () => {
    expect(checkMatches('player', FILE.player, '')).toBe(true)
  })

  it('키 이름으로 걸린다', () => {
    expect(checkMatches('player', FILE.player, 'hp_max')).toBe(true)
    expect(checkMatches('player', FILE.player, 'defense')).toBe(false)
  })

  it('후손이 걸리면 조상도 남는다 — 안 그러면 걸린 것이 안 보인다', () => {
    expect(checkMatches('enemies', FILE.enemies, 'goblin')).toBe(true)
  })

  it('★ 값은 문자열만 본다 — 숫자까지 뒤지면 「12」에 절반이 걸린다', () => {
    expect(checkMatches('player', FILE.player, '12')).toBe(false)
    expect(checkMatches('enemies', FILE.enemies, 'rusher')).toBe(true)
  })
})
