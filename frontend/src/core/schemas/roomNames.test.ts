/**
 * 방마다 이름이 있는가 — 파이썬 쪽 `tests/test_room_names.py` 와 같은 질문이다.
 *
 * **id 가 화면에 나오고 있었다** (2026-09-14 신고). 상단 바가 `4층 · pillars` 라고 적었고,
 * 방 고르는 목록도 영문 id 서른한 줄이었다. 데이터에 이름 칸이 없었으므로 화면이 적을
 * 것이 그것뿐이었다 — **없는 것은 안 보이는 것이 아니라 id 로 보인다.**
 *
 * 양쪽에 같은 시험을 두는 이유는 정본이 같은 파일이기 때문이다. 한쪽만 두면 다른 코어가
 * 파싱을 빠뜨렸을 때 아무도 안 잡는다 (게이트 G3).
 */
import { describe, expect, it } from 'vitest'

import { ROOM_TEMPLATES } from '../resources'
import { readRoomTitle, findRoomTitle } from './room'

describe('방 이름', () => {
  it('★ 이름 없는 방은 화면에 id 로 나온다', () => {
    const missing = ROOM_TEMPLATES.filter((one) => one.labelKo === '').map((one) => one.templateId)
    expect(missing, `이름이 없다: ${missing.join(', ')}`).toEqual([])
  })

  it('★ 두 방이 같은 이름이면 고르는 사람이 어느 쪽인지 알 수 없다', () => {
    const seen = new Map<string, string>()
    for (const template of ROOM_TEMPLATES) {
      const clash = seen.get(template.labelKo)
      expect(clash, `「${template.labelKo}」 를 ${clash ?? ''} 와 ${template.templateId} 가 함께 쓴다`).toBeUndefined()
      seen.set(template.labelKo, template.templateId)
    }
  })

  it('★ 이름이 없어도 빈 칸이 아니라 id 가 보인다', () => {
    for (const template of ROOM_TEMPLATES) {
      expect(readRoomTitle(template)).not.toBe('')
    }
    // 팩에 없는 방이 저장에 남아 있을 수 있다. 그때 빈 칸을 보이면 「방이 사라졌다」다.
    expect(findRoomTitle(ROOM_TEMPLATES, 'no_such_room')).toBe('no_such_room')
  })

  it('★ 파이썬과 같은 이름을 읽는다 (G3)', () => {
    // 이름은 시뮬레이션에 안 쓰이지만 **같은 파일에서 온다.** 한쪽 파서만 칸을
    // 빠뜨리면 화면 둘이 다른 말을 하고, 그것은 재시뮬 대조로는 안 잡힌다.
    expect(findRoomTitle(ROOM_TEMPLATES, 'open_field')).toBe('너른 마당')
    expect(findRoomTitle(ROOM_TEMPLATES, 'boss_hall')).toBe('장승 마당')
  })
})
