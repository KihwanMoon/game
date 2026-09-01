/**
 * 스킬 표와 룸 격자 편집기.
 *
 * 여기서 지키는 것은 다섯이다.
 *
 * 1. **실행기가 읽는 구조는 못 고친다.** 바꾸면 코어 코드가 함께 바뀌어야 하고, 안
 *    바뀌면 그 스킬이 조용히 아무 일도 안 한다.
 * 2. **고친 것만 바뀐다.** 통째로 다시 쓰면 `_note` 처럼 사람이 적어 둔 것이 사라진다.
 * 3. **룸은 줄 길이가 안 바뀐다.** 텍스트 편집이 못 지키던 것이 이것이다 — 12x9 에서 한
 *    글자 모자란 줄은 읽을 때가 아니라 판이 설 때 드러난다.
 * 4. **지형 종류는 legend 가 정한다.** 화면이 목록을 따로 들면 두 곳이 갈린다.
 * 5. **저장은 초안이다.**
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { RoomGrid, applyPaint, buildRoomFile } from './RoomGrid'
import { LOCKED_FIELDS, SkillTable, buildSkillFile } from './SkillTable'
import roomsRaw from '@resources/rooms/templates.json'
import skillsRaw from '@resources/balance/skills.json'

const SKILLS = skillsRaw as unknown as Record<string, unknown>
const ROOMS = roomsRaw as unknown as Record<string, unknown>
const noop = () => undefined

describe('스킬 표', () => {
  it('★ 못 고치는 필드를 못 고친다고 적는다', () => {
    const html = renderToStaticMarkup(<SkillTable file={SKILLS} onSave={noop} />)
    for (const field of LOCKED_FIELDS) {
      expect(html).toContain(field)
    }
    expect(html).toContain('실행기가 읽는 구조')
  })

  it('★ 고친 스킬만 바뀌고 나머지는 원본 객체 그대로다', () => {
    const rows = SKILLS.skills as Record<string, unknown>[]
    const next = buildSkillFile(SKILLS, 'SKILL_1', 'coef_pct', '200')
    const changed = (next.skills as Record<string, unknown>[]).find((row) => row.id === 'SKILL_1')
    expect(changed?.coef_pct).toBe(200)
    const other = (next.skills as Record<string, unknown>[]).find((row) => row.id === 'ATTACK')
    expect(other).toBe(rows.find((row) => row.id === 'ATTACK'))
  })

  it('★ 빈 칸은 null 이다 — range 가 null 이면 사거리를 엔티티가 정한다', () => {
    const next = buildSkillFile(SKILLS, 'SKILL_1', 'range', '')
    const changed = (next.skills as Record<string, unknown>[]).find((row) => row.id === 'SKILL_1')
    expect(changed?.range).toBeNull()
  })

  it('숫자가 아니면 값을 안 바꾼다 — 반쯤 친 글자가 값을 지우면 안 된다', () => {
    const before = (SKILLS.skills as Record<string, unknown>[]).find((row) => row.id === 'SKILL_1')
    const next = buildSkillFile(SKILLS, 'SKILL_1', 'coef_pct', 'abc')
    const changed = (next.skills as Record<string, unknown>[]).find((row) => row.id === 'SKILL_1')
    expect(changed?.coef_pct).toBe(before?.coef_pct)
  })
})

describe('룸 격자', () => {
  const rows = ['####', '#..#', '####']
  const glyphs = ['.', '#', 'D']

  it('★ 칸을 칠해도 줄 길이가 안 바뀐다 — 격자가 어긋날 수 없다', () => {
    const next = applyPaint(rows, 1, 1, glyphs)
    expect(next.map((line) => line.length)).toEqual(rows.map((line) => line.length))
    expect(next[1]).toBe('##.#')
  })

  it('★ 다음 지형으로 넘어간다 — 마지막이면 처음으로 돈다', () => {
    expect(applyPaint(['D'], 0, 0, glyphs)[0]).toBe('.')
  })

  it('격자 밖은 그대로다', () => {
    expect(applyPaint(rows, 9, 9, glyphs)).toBe(rows)
  })

  it('★ 지형 종류를 legend 에서 읽는다 — 화면이 목록을 들면 두 곳이 갈린다', () => {
    const html = renderToStaticMarkup(<RoomGrid file={ROOMS} onSave={noop} />)
    const names = ROOMS.legend_ko as Record<string, string>
    expect(html).toContain(names['#'])
    expect(html).toContain(names.D)
  })

  it('★ 고친 방만 바뀌고 나머지는 원본 객체 그대로다', () => {
    const templates = ROOMS.templates as Record<string, unknown>[]
    const first = templates[0]
    const next = buildRoomFile(ROOMS, String(first?.id), ['####'])
    const list = next.templates as Record<string, unknown>[]
    expect(list[0]?.rows).toEqual(['####'])
    expect(list[1]).toBe(templates[1])
  })
})
