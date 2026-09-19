/**
 * 재주 칸 규격과 값 읽고 쓰기 (2026-09-19).
 *
 * **잠그는 대신 고를 수 있는 것을 줄였다.** 예전에는 `family`·`shape`·`target_faction`
 * 을 통째로 잠갔고 사유가 「실행기가 읽는 구조라 바꾸면 조용히 아무 일도 안 한다」였다.
 * 자유 입력이면 그 말이 맞지만 **고르개는 없는 값을 못 고른다** — 그래서 항목을
 * 구현된 것만 담고 잠금을 풀었다.
 *
 * 여기서 지키는 것은 셋이다.
 *
 * 1. **타입이 안 맞으면 절이 안 바뀐다.** 화면이 거절하는 것과 데이터가 망가지는 것은 다르다.
 * 2. **고르개는 모르는 값을 안 받는다.** 받으면 잠금을 푼 대가가 그대로 돌아온다.
 * 3. **고친 재주 말고는 원본 그대로다.** `_note` 처럼 사람이 적어 둔 것이 사라지면 안 된다.
 */
import { describe, expect, it } from 'vitest'

import {
  SKILL_COLUMNS,
  SKILL_FIELDS,
  buildSkillFile,
  parseFieldInput,
  readFieldText,
} from './skillFields'

const FILE = {
  skill_list_version: 12,
  skills: [
    {
      id: 'METEOR',
      label_ko: '메테오',
      family: 'ATTACK',
      shape: { kind: 'AREA', radius: 3 },
      target_faction: 'enemy',
      coef_pct: 220,
      cooldown: 16,
      range: 6,
      telegraph: 3,
      cast_act: 'LOCK',
      cancel_on_hit: false,
      tags: ['MAGIC', 'CAST', 'AOE'],
      _note: '사람이 적어 둔 것',
    },
    { id: 'ATTACK', shape: { kind: 'SINGLE' }, coef_pct: 100, range: null },
  ],
}

function pick(path: string) {
  const found = SKILL_FIELDS.find((one) => one.path === path)
  if (found === undefined) {
    throw new Error(`규격에 없는 칸이다: ${path}`)
  }
  return found
}

function readSkill(file: Record<string, unknown>, id: string) {
  return (file.skills as Record<string, unknown>[]).find((one) => one.id === id)!
}

describe('머리줄', () => {
  it('★ 머리줄과 칸 수가 같다 — 어긋나면 모든 값이 한 칸씩 밀린다', () => {
    expect(SKILL_COLUMNS.length).toBe(SKILL_FIELDS.length + 1)
  })

  it('★ 고르는 칸은 항목을 들고 있다 — 빈 고르개는 아무것도 못 고친다', () => {
    for (const field of SKILL_FIELDS.filter((one) => one.kind === 'select' || one.kind === 'tags')) {
      expect(field.options?.length ?? 0).toBeGreaterThan(0)
    }
  })
})

describe('값 읽기', () => {
  it('★ 중첩을 따라간다 — 반경은 `shape.radius` 에 있다', () => {
    const meteor = readSkill(FILE, 'METEOR')
    expect(readFieldText(meteor, pick('shape.kind'))).toBe('AREA')
    expect(readFieldText(meteor, pick('shape.radius'))).toBe('3')
  })

  it('★ 비어 있는 것과 0 을 가른다 — 사거리 null 은 「무기가 정한다」다', () => {
    expect(readFieldText(readSkill(FILE, 'ATTACK'), pick('range'))).toBe('')
    expect(readFieldText(readSkill(FILE, 'METEOR'), pick('telegraph'))).toBe('3')
  })

  it('복수 선택은 쉼표로 편다', () => {
    expect(readFieldText(readSkill(FILE, 'METEOR'), pick('tags'))).toBe('MAGIC,CAST,AOE')
  })
})

describe('값 쓰기', () => {
  it('★ 한글 이름을 고친다 — 판정에 안 닿으므로 자유 입력이다', () => {
    const next = buildSkillFile(FILE, 'METEOR', pick('label_ko'), '큰 별똥')
    expect(readSkill(next, 'METEOR').label_ko).toBe('큰 별똥')
  })

  it('★ 중첩 칸을 고쳐도 형태 절의 나머지가 남는다', () => {
    const next = buildSkillFile(FILE, 'METEOR', pick('shape.radius'), '5')
    expect(readSkill(next, 'METEOR').shape).toEqual({ kind: 'AREA', radius: 5 })
  })

  it('★ 숫자 칸에 글자를 넣으면 절이 안 바뀐다 — 화면이 거절하는 것과 데이터가 망가지는 것은 다르다', () => {
    expect(buildSkillFile(FILE, 'METEOR', pick('coef_pct'), '많이')).toBe(FILE)
  })

  it('★ 비울 수 없는 칸은 비워도 안 바뀐다 — 예고가 사라지면 그 재주가 딴것이 된다', () => {
    expect(buildSkillFile(FILE, 'METEOR', pick('telegraph'), '')).toBe(FILE)
  })

  it('★ 비울 수 있는 칸만 null 이 된다 — 사거리는 무기가 정할 수 있다', () => {
    const next = buildSkillFile(FILE, 'METEOR', pick('range'), '')
    expect(readSkill(next, 'METEOR').range).toBeNull()
  })

  it('★ 고르개는 모르는 값을 안 받는다 — 잠금을 푼 대가가 여기로 돌아온다', () => {
    expect(buildSkillFile(FILE, 'METEOR', pick('cast_act'), 'NOPE')).toBe(FILE)
    expect(parseFieldInput(pick('shape.kind'), 'SPIRAL')).toBeUndefined()
  })

  it('★ 아는 값은 받는다', () => {
    const next = buildSkillFile(FILE, 'METEOR', pick('cast_act'), 'FREE')
    expect(readSkill(next, 'METEOR').cast_act).toBe('FREE')
  })

  it('★ 켬/끔은 불리언으로 들어간다 — 글자 "false" 가 참이 되면 안 된다', () => {
    const off = buildSkillFile(FILE, 'METEOR', pick('cancel_on_hit'), 'false')
    const on = buildSkillFile(FILE, 'METEOR', pick('cancel_on_hit'), 'true')
    expect(readSkill(off, 'METEOR').cancel_on_hit).toBe(false)
    expect(readSkill(on, 'METEOR').cancel_on_hit).toBe(true)
  })

  it('★ 고친 재주 말고는 원본 그대로다 — `_note` 가 사라지면 안 된다', () => {
    const next = buildSkillFile(FILE, 'METEOR', pick('coef_pct'), '300')
    expect(readSkill(next, 'METEOR')._note).toBe('사람이 적어 둔 것')
    expect(readSkill(next, 'ATTACK')).toBe(readSkill(FILE, 'ATTACK'))
    expect(next.skill_list_version).toBe(12)
  })
})

describe('배열 칸 (effects)', () => {
  it('★ 상태를 읽는다 — 중첩 배열을 따라간다', () => {
    const withEffect = {
      ...FILE,
      skills: [{ ...FILE.skills[0], effects: [{ kind: 'STATUS', status: 'SLOW', duration: 4 }] }],
    }
    expect(readFieldText(readSkill(withEffect, 'METEOR'), pick('effects.0.status'))).toBe('SLOW')
    expect(readFieldText(readSkill(withEffect, 'METEOR'), pick('effects.0.duration'))).toBe('4')
  })

  it('★ 고쳐도 배열이 배열로 남는다 — 객체로 펴면 코어가 못 읽는다', () => {
    const withEffect = {
      ...FILE,
      skills: [{ ...FILE.skills[0], effects: [{ kind: 'STATUS', status: 'SLOW', duration: 4 }] }],
    }
    const next = buildSkillFile(withEffect, 'METEOR', pick('effects.0.duration'), '7')
    const effects = readSkill(next, 'METEOR').effects
    expect(Array.isArray(effects)).toBe(true)
    expect(effects).toEqual([{ kind: 'STATUS', status: 'SLOW', duration: 7 }])
  })

  it('★ 상태가 없던 재주에 처음 달 수 있다 — 빈 자리를 열어 준다', () => {
    const next = buildSkillFile(FILE, 'METEOR', pick('effects.0.status'), 'POISON')
    const effects = readSkill(next, 'METEOR').effects as Record<string, unknown>[]
    expect(Array.isArray(effects)).toBe(true)
    expect(effects[0]?.status).toBe('POISON')
  })

  it('★ 기절은 고를 수 없다 — 엔진이 안 읽어서 걸어도 아무 일이 없다', () => {
    const values = (pick('effects.0.status').options ?? []).map((one) => one.value)
    expect(values).not.toContain('STUN')
    expect(values).toContain('SLOW')
  })
})
