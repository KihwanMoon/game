/**
 * 방 고르기 목록 — id 만 늘어놓지 않는다.
 *
 * 이 화면이 답해야 하는 질문은 「어느 방이 내 규칙표를 시험하는가」다. 영문 id 서른한
 * 줄로는 그것에 답할 수 없고, 그러면 대부분은 맨 위 것을 그냥 쓴다 — **데이터에 뜻과
 * 층이 이미 있는데 화면이 하나도 안 쓰고 있었다.**
 */
import { describe, expect, it } from 'vitest'

import { ROOM_TEMPLATES } from '../core/resources'

import { buildRoomGroups, clipPurpose, PURPOSE_CLIP } from './roomChoices'

describe('층으로 묶는다', () => {
  const groups = buildRoomGroups(ROOM_TEMPLATES)

  it('★ 방 하나도 안 빠진다 — 묶다가 잃으면 못 고르는 방이 생긴다', () => {
    const total = groups.reduce((count, group) => count + group.rooms.length, 0)
    expect(total).toBe(ROOM_TEMPLATES.length)
  })

  it('★ 얕은 층부터 선다 — 층이 데이터가 이미 정한 난이도 축이다', () => {
    const floors = groups.map((group) => group.minFloor)
    expect(floors).toEqual([...floors].sort((left, right) => left - right))
  })

  it('★ 같은 층 안은 id 순이다 — 데이터 순서에 기대면 방을 더할 때 목록이 뒤바뀐다', () => {
    for (const group of groups) {
      const ids = group.rooms.map((room) => room.templateId)
      expect(ids).toEqual([...ids].sort((left, right) => left.localeCompare(right)))
    }
  })

  it('★ 한 줄이 id 와 뜻을 함께 적는다', () => {
    const corridor = groups
      .flatMap((group) => group.rooms)
      .find((room) => room.templateId === 'corridor')
    expect(corridor?.label).toContain('corridor')
    expect(corridor?.label).toContain('좁은 통로')
  })

  it('전문은 자르지 않고 title 로 남긴다 — 목록은 훑는 곳이고 전문은 확인하는 곳이다', () => {
    for (const room of groups.flatMap((group) => group.rooms)) {
      const source = ROOM_TEMPLATES.find((item) => item.templateId === room.templateId)
      expect(room.title).toBe(source?.purpose)
    }
  })
})

describe('뜻 줄이기', () => {
  it('첫 문장만 쓴다 — 뒤는 부연이라 고르는 데 필요하지 않다', () => {
    expect(clipPurpose('좁은 통로가 유일한 경로다. 유인해 1:1 구도를 만든다.')).toBe(
      '좁은 통로가 유일한 경로다',
    )
  })

  it('★ 긴 줄은 자르고 말줄임을 붙인다 — 안 자르면 한 줄이 목록을 밀어낸다', () => {
    const clipped = clipPurpose('가'.repeat(PURPOSE_CLIP + 10))
    expect(clipped).toHaveLength(PURPOSE_CLIP + 1)
    expect(clipped.endsWith('…')).toBe(true)
  })

  it('뜻이 없으면 빈 문자열이다 — 그때는 id 만 적는다', () => {
    expect(clipPurpose('')).toBe('')
  })
})
