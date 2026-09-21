/**
 * 재주 도트 고르기 (2026-09-21 요청).
 *
 * **몬스터 쪽과 같은 규약이라 묻는 것도 같다** — 재주 전수에 그림이 다 있는가.
 * 그 실패는 조용하다: 그림이 없어도 칸은 이름으로 멀쩡히 그려지고, 한 장만 글자로 남은
 * 것은 재주 격자를 끝까지 내려 본 사람만 본다.
 *
 * **적 전용 재주도 본다.** 도면 위 HUD 에는 안 뜨지만 이문록이 적의 규칙표를 펴서
 * 보여 줄 때 이름이 나오고, 관리 화면은 전수를 건드린다.
 */
import skillsRaw from '@resources/balance/skills.json'
import { describe, expect, it } from 'vitest'

import { findSkillArt, listSkillArtIds } from './skillArt'

interface RawSkill {
  id: string
}

const SKILLS = (skillsRaw as unknown as { skills: RawSkill[] }).skills

describe('재주 도트', () => {
  it('★ 재주 전수에 그림이 있다 — 한 장이라도 빠지면 그 칸만 글자로 남는다', () => {
    expect(SKILLS.filter((one) => findSkillArt(one.id) === undefined).map((one) => one.id)).toEqual(
      [],
    )
  })

  it('★ 그림에 대응하는 재주가 다 있다 — 재주가 사라지면 그림도 지운다', () => {
    const known = new Set(SKILLS.map((one) => one.id.toLowerCase()))
    expect(listSkillArtIds().filter((id) => !known.has(id))).toEqual([])
  })

  it('★ 재주마다 제 그림이다 — 접두사로 골랐다면 `hex_` 일곱이 한 장이 된다', () => {
    const arts = SKILLS.map((one) => findSkillArt(one.id))
    expect(new Set(arts).size).toBe(SKILLS.length)
  })

  it('id 의 대소문자를 안 가린다 — 정본은 대문자고 파일 이름은 소문자다', () => {
    expect(findSkillArt('HEX_FIRE')).toBe(findSkillArt('hex_fire'))
  })

  it('★ 모르는 id 는 undefined 다 — 없는 그림을 지어내면 엉뚱한 재주가 그려진다', () => {
    expect(findSkillArt('SKILL_9')).toBeUndefined()
    expect(findSkillArt('')).toBeUndefined()
  })
})
