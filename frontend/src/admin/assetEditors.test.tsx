/**
 * 스킬 표와 룸 격자 편집기.
 *
 * 여기서 지키는 것은 일곱이다.
 *
 * 1. **실행기가 읽는 구조는 못 고친다.** 바꾸면 코어 코드가 함께 바뀌어야 하고, 안
 *    바뀌면 그 스킬이 조용히 아무 일도 안 한다.
 * 2. **고친 것만 바뀐다.** 통째로 다시 쓰면 `_note` 처럼 사람이 적어 둔 것이 사라진다.
 * 3. **룸은 줄 길이가 안 바뀐다.** 텍스트 편집이 못 지키던 것이 이것이다 — 12x9 에서 한
 *    글자 모자란 줄은 읽을 때가 아니라 판이 설 때 드러난다.
 * 4. **지형 종류는 legend 가 정한다.** 화면이 목록을 따로 들면 두 곳이 갈린다.
 * 5. **저장은 초안이다.**
 * 6. **방 고르기가 공용 목록 틀 위에 선다** — 찾기 칸과 한 장이 있고, 「아직 못 읽었다」가
 *    「없다」로 안 적힌다. 마흔 곳을 한꺼번에 세우면 폰에서 단추 줄이 화면을 덮는다.
 * 7. **스킬 표는 머리줄과 값줄의 칸 수가 같다.** 둘은 서로 다른 격자라(머리줄은 `.skl` 의
 *    자식, 값줄은 목록 틀의 `<li>`) 칸 수가 어긋나면 어떤 폭을 줘도 라벨과 값이 안 맞는다.
 *    재주 쪽에도 찾기 칸이 서고, 줄은 하나도 감추지 않는다 — 고치는 표다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { ROOM_PAGE, RoomGrid, applyPaint, buildRoomFile, roomSearchText } from './RoomGrid'
import {
  EDITABLE_FIELDS,
  LOCKED_FIELDS,
  SKILL_COLUMNS,
  SkillTable,
  buildSkillFile,
  skillSearchText,
} from './SkillTable'
import roomsRaw from '@resources/rooms/templates.json'
import skillsRaw from '@resources/balance/skills.json'

const SKILLS = skillsRaw as unknown as Record<string, unknown>
const ROOMS = roomsRaw as unknown as Record<string, unknown>
const noop = () => undefined

/**
 * 한 줄 안에서 **격자가 칸으로 세는 것**의 개수를 센다.
 *
 * 태그를 다 세면 안 된다 — `ValueExpr` 는 span 안에 span 을 낳으므로 그것까지 세면
 * 값줄이 머리줄보다 항상 많다. 깊이 0 에 선 것만 센다.
 *
 * @param fragment 줄 하나의 안쪽 마크업.
 * @returns 맨 바깥에 선 요소 수.
 */
function countGridCells(fragment: string): number {
  let depth = 0
  let cells = 0
  for (const tag of fragment.match(/<\/?[a-zA-Z]+[^>]*>/g) ?? []) {
    if (tag.startsWith('</')) {
      depth -= 1
      continue
    }
    if (depth === 0) {
      cells += 1
    }
    if (!tag.endsWith('/>')) {
      depth += 1
    }
  }
  return cells
}

/**
 * 여는 태그와 닫는 태그 사이를 떼어 낸다.
 *
 * @param markup 정적 마크업.
 * @param open 여는 태그 전체.
 * @param close 닫는 태그.
 * @returns 그 사이의 마크업. 못 찾으면 빈 글자.
 */
function sliceInner(markup: string, open: string, close: string): string {
  const start = markup.indexOf(open)
  if (start < 0) {
    return ''
  }
  const from = start + open.length
  const end = markup.indexOf(close, from)
  return end < 0 ? '' : markup.slice(from, end)
}

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

  it('★ 머리줄과 값줄의 칸 수가 같다 — 다르면 어떤 폭을 줘도 라벨과 값이 어긋난다', () => {
    // 머리줄과 값줄은 **서로 다른 격자**다. 머리줄은 `.skl` 의 자식이고 값줄은 목록 틀이
    // 그리는 `<li>` 라, 폭을 맞추는 일은 CSS 가 하더라도 칸 수가 같다는 것은 여기서
    // 지켜야 한다 — 한 칸이 모자라면 그 뒤의 모든 값이 한 칸씩 밀린 채로 읽힌다.
    const html = renderToStaticMarkup(<SkillTable file={SKILLS} onSave={noop} />)
    const head = countGridCells(sliceInner(html, '<div class="skl__head">', '</div>'))
    const row = countGridCells(sliceInner(html, '<li class="skl__row">', '</li>'))
    expect(head).toBe(SKILL_COLUMNS.length)
    expect(row).toBe(head)
  })

  it('★ 고칠 수치가 늘면 머리줄도 함께 는다 — 칸 이름을 두 곳에 적지 않는다', () => {
    expect(SKILL_COLUMNS.slice(-EDITABLE_FIELDS.length)).toEqual([...EDITABLE_FIELDS])
  })

  it('★ 재주를 이름과 id 둘 다로 거른다 — id 로만 거르면 「불 굿」을 못 찾는다', () => {
    const first = (SKILLS.skills as Record<string, unknown>[])[0]
    const key = skillSearchText(first ?? {})
    expect(key).toContain(String(first?.id))
    expect(key).toContain(String(first?.label_ko))
  })

  it('★ 찾기 칸이 선다 — 열네 줄을 눈으로 훑고 있었다', () => {
    const html = renderToStaticMarkup(<SkillTable file={SKILLS} onSave={noop} />)
    expect(html).toContain('이름·id 로 찾기')
  })

  it('★ 줄을 하나도 감추지 않는다 — 고치는 표에서 「더 보기」는 고친 것을 숨긴다', () => {
    const html = renderToStaticMarkup(<SkillTable file={SKILLS} onSave={noop} />)
    const total = (SKILLS.skills as Record<string, unknown>[]).length
    expect(html.match(/<li[\s>]/g)?.length ?? 0).toBe(total)
    expect(html).not.toContain('더 보기')
  })

  it('★ 고칠 재주가 없는 파일에는 빈 목록 문구를 적는다', () => {
    const html = renderToStaticMarkup(<SkillTable file={{ ...SKILLS, skills: [] }} onSave={noop} />)
    expect(html).toContain('고칠 재주가 없다')
  })

  it('★ 파일을 아직 못 읽었으면 「없다」가 아니라 「불러오는 중」이라고 적는다', () => {
    // 부정 검사를 혼자 두면 찾는 글자가 썩는 날 조용히 통과한다 — 바로 위 검사가 그 문구가
    // 살아 있다는 것을 보증한다.
    const html = renderToStaticMarkup(<SkillTable file={undefined} onSave={noop} />)
    expect(html).toContain('불러오는 중')
    expect(html).not.toContain('고칠 재주가 없다')
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

  it('★ 방을 이름과 장으로 거른다 — id 로만 거르면 「너른 마당」을 못 찾는다', () => {
    // 화면에 적히는 것은 id 한 줄이지만, 사람이 방을 떠올리는 이름은 `label_ko` 이고
    // 고를 때 드는 기준은 「몇 장짜리인가」다. 거르기가 그 둘을 못 보면 찾기 칸이 서 있어도
    // 브라우저 찾기와 다르지 않다.
    const first = (ROOMS.templates as Record<string, unknown>[])[0]
    const key = roomSearchText(first ?? {})
    expect(key).toContain(String(first?.id))
    expect(key).toContain(String(first?.label_ko))
    expect(key).toContain(`${String(first?.min_floor)}장`)
  })

  it('★ 찾기 칸이 선다 — 마흔 곳에서 방 하나를 눈으로 찾고 있었다', () => {
    const html = renderToStaticMarkup(<RoomGrid file={ROOMS} onSave={noop} />)
    expect(html).toContain('이름·장으로 찾기')
  })

  it('★ 한 장만 세우고 나머지는 「더 보기」 뒤에 둔다', () => {
    // 줄은 클래스가 아니라 `<li>` 로 센다 — 줄에 무슨 클래스를 주든 줄은 줄이라
    // 이름이 바뀌어도 이 검사는 안 흔들린다.
    const html = renderToStaticMarkup(<RoomGrid file={ROOMS} onSave={noop} />)
    const total = (ROOMS.templates as Record<string, unknown>[]).length
    expect(total).toBeGreaterThan(ROOM_PAGE)
    expect(html.match(/<li[\s>]/g)?.length ?? 0).toBe(ROOM_PAGE)
    expect(html).toContain('더 보기')
  })

  it('★ 방이 없는 파일에는 빈 목록 문구를 적는다', () => {
    const html = renderToStaticMarkup(<RoomGrid file={{ ...ROOMS, templates: [] }} onSave={noop} />)
    expect(html).toContain('고칠 방이 없다')
  })

  it('★ 파일을 아직 못 읽었으면 「없다」가 아니라 「불러오는 중」이라고 적는다', () => {
    // 그 문구가 실제로 살아 있다는 것은 바로 위 검사가 보증한다 — 부정 검사를 혼자 두면
    // 찾는 글자가 썩는 날 조용히 통과한다.
    const html = renderToStaticMarkup(<RoomGrid file={undefined} onSave={noop} />)
    expect(html).toContain('불러오는 중')
    expect(html).not.toContain('고칠 방이 없다')
  })
})
