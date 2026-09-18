/**
 * 값 트리 편집기의 **구조**.
 *
 * 배치는 검사가 못 본다 — 폰에서 글자가 겹치는지는 눈으로 본다. 검사가 재는 것은
 * 넷이다.
 *
 * 1. **찾기 칸이 선다.** 값이 300개 가까운 파일에서 눈으로 훑지 않아도 된다.
 * 2. **찾은 것이 보인다.** 걸린 가지가 접혀 있거나 속이 비어 있으면, 찾기는 「몇 개
 *    걸렸는지만 알려주는 기능」이 된다 — 있는데 안 되는 것이 없는 것보다 나쁘다.
 * 3. **줄을 끊을 자리가 있다.** `cpu_cost_by_term_count` 는 브라우저에게 한 낱말이라,
 *    끊을 자리가 없으면 폰에서 절 전체가 옆으로 밀린다.
 * 4. **여기는 목록이 아니라 편집기다.** 「더 보기」로 줄을 감추지 않는다 — 고치던 줄이
 *    사라진다.
 *
 * `defaultQuery` 는 DOM 없이 도는 검사가 거른 결과를 볼 수 있는 유일한 문이다
 * (`DataList.defaultQuery` 와 같은 뜻).
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { ValueTree, checkOpenByDefault, readChildNeedle, splitKeyParts } from './ValueTree'

const noop = () => undefined

/** 깊이 3까지 있는 절. 실제 밸런스 파일이 이 모양이다. */
const FILE: Record<string, unknown> = {
  player: { hp_max: 30, attack: 3 },
  enemies: [
    { id: 'bomb_slime', label_ko: '폭탄 슬라임', hp_max: 8, contact_damage: 2 },
    { id: 'goblin_rusher', label_ko: '돌격 고블린', hp_max: 12, contact_damage: 1 },
  ],
  rules: { cpu: { cpu_cost_by_term_count: [1, 2, 3] } },
  _note: { why: '왜 이 값인지를 절 안에 적어 둔다' },
}

/**
 * 트리를 정적 마크업으로 그린다.
 *
 * @param query 첫 질의. 빈 말이면 안 거른다.
 * @returns 마크업.
 */
function render(query?: string): string {
  return renderToStaticMarkup(
    <ValueTree
      file={FILE}
      title="밸런스"
      onSave={noop}
      {...(query === undefined ? {} : { defaultQuery: query })}
    />,
  )
}

/** 끊을 자리를 지운 글자. 사람이 읽는 것은 이쪽이다. */
function readText(markup: string): string {
  return markup.replaceAll('<wbr/>', '')
}

describe('값 트리 — 찾기', () => {
  it('★ 찾기 칸이 선다', () => {
    expect(render()).toContain('aria-label="키 이름으로 찾기"')
  })

  it('★ 안 걸린 절은 사라진다 — 그러라고 있는 칸이다', () => {
    const markup = render('contact_damage')
    expect(markup).toContain('aria-label="enemies.0.contact_damage"')
    expect(markup).not.toContain('aria-label="enemies.0.hp_max"')
    expect(markup).not.toContain('aria-label="player.hp_max"')
  })

  it('★ 깊은 곳에 걸려도 펴진 채로 뜬다 — 접혀 있으면 찾은 것이 안 보인다', () => {
    // `rules › cpu › cpu_cost_by_term_count` 는 깊이 2라 평소에는 접혀 있다.
    const markup = render('cpu_cost_by_term')
    expect(markup).toContain('aria-label="rules.cpu.cpu_cost_by_term_count.0"')
    expect(markup).not.toContain('aria-expanded="false"')
  })

  it('★ 가지 이름이 걸리면 그 아래가 통째로 보인다 — 찾아 놓고 못 고치면 안 된다', () => {
    // 몬스터 이름으로 찾으면 그 한 마리의 스탯이 전부 서야 한다. 걸린 잎 하나만
    // 남기면 `id` 칸만 뜨고 고치려던 hp 는 안 보인다.
    const markup = render('bomb_slime')
    expect(markup).toContain('aria-label="enemies.0.hp_max"')
    expect(markup).toContain('aria-label="enemies.0.contact_damage"')
    expect(markup).not.toContain('aria-label="enemies.1.hp_max"')
  })

  it('★ 한 축으로 찾으면 그 축만 나란히 선다 — 이름이 안 걸리면 거르기가 산다', () => {
    const markup = render('hp_max')
    expect(markup).toContain('aria-label="enemies.0.hp_max"')
    expect(markup).toContain('aria-label="enemies.1.hp_max"')
    expect(markup).not.toContain('aria-label="enemies.0.contact_damage"')
  })

  it('걸리는 절이 없으면 그렇다고 적는다 — 빈 화면은 고장으로 읽힌다', () => {
    expect(render('zzz')).toContain('를 품은 절이 없다')
  })

  it('★ 아직 못 읽은 파일은 「없다」가 아니라 「아직 안 읽었다」다', () => {
    const markup = renderToStaticMarkup(
      <ValueTree file={undefined} title="밸런스" onSave={noop} />,
    )
    expect(markup).toContain('아직 안 읽었다')
    expect(markup).not.toContain('를 품은 절이 없다')
  })
})

describe('값 트리 — 접힘', () => {
  it('★ 안 찾을 때는 깊은 가지가 접혀 있다 — 다 펴면 스크롤 싸움이다', () => {
    const markup = render()
    expect(markup).toContain('aria-expanded="false"')
    expect(markup).not.toContain('aria-label="rules.cpu.cpu_cost_by_term_count.0"')
  })

  it('★ 설명 가지는 접혀 있다 — 스무 줄짜리 산문이 첫 화면을 먹는다', () => {
    expect(render()).not.toContain('aria-label="_note.why"')
  })

  it('접힘 상태가 마크업에 적힌다 — 색으로만 적으면 보조 기술이 못 읽는다', () => {
    expect(render()).toContain('aria-expanded="true"')
  })
})

describe('값 트리 — 폰에서 줄이 끊긴다', () => {
  it('★ 긴 키에 끊을 자리가 있다 — 한 낱말이면 줄이 화면 밖으로 나간다', () => {
    const markup = render('cpu_cost_by_term')
    expect(markup).toContain('cpu_<wbr/>cost_')
  })

  it('★ 끊을 자리를 심어도 글자는 그대로다 — 배치만 고치는 일이다', () => {
    expect(readText(render('cpu_cost_by_term'))).toContain('cpu_cost_by_term_count')
  })

  it('★ 이름과 값이 각자 칸에 든다 — 한 칸에 붙어 있으면 폭을 줄 자리가 없다', () => {
    const markup = render('player')
    expect(markup).toContain('class="vtr__key"')
    expect(markup).toContain('class="vtr__val"')
  })

  it('★ 가지 이름도 제 칸에 든다 — 글자만 두면 개수 뱃지를 밀어낸다', () => {
    expect(render()).toContain('class="vtr__name"')
  })
})

describe('값 트리 — 줄을 하나도 감추지 않는다', () => {
  it('★ 「더 보기」가 없다 — 고치는 화면에서 그것은 고친 줄을 숨긴다', () => {
    expect(render()).not.toContain('더 보기')
  })
})

describe('splitKeyParts', () => {
  it('밑줄 뒤에서 끊는다 — 낱말의 경계가 거기다', () => {
    expect(splitKeyParts('hp_max')).toEqual(['hp_', 'max'])
    expect(splitKeyParts('cpu_cost_by_term_count')).toEqual([
      'cpu_',
      'cost_',
      'by_',
      'term_',
      'count',
    ])
  })

  it('끊을 자리가 없으면 통째로 한 조각이다', () => {
    expect(splitKeyParts('enemies')).toEqual(['enemies'])
    expect(splitKeyParts('')).toEqual([''])
  })

  it('끝에 붙은 밑줄로는 안 끊는다 — 빈 조각이 남는다', () => {
    expect(splitKeyParts('_note')).toEqual(['_', 'note'])
    expect(splitKeyParts('note_')).toEqual(['note_'])
  })
})

describe('checkOpenByDefault', () => {
  it('★ 찾을 때는 펴 둔다', () => {
    expect(checkOpenByDefault(4, false, 'hp')).toBe(true)
    expect(checkOpenByDefault(4, true, 'hp')).toBe(true)
  })

  it('안 찾을 때는 얕은 가지만 펴 둔다', () => {
    expect(checkOpenByDefault(0, false, '')).toBe(true)
    expect(checkOpenByDefault(1, false, '')).toBe(true)
    expect(checkOpenByDefault(2, false, '')).toBe(false)
  })

  it('설명은 얕아도 접어 둔다', () => {
    expect(checkOpenByDefault(0, true, '')).toBe(false)
  })
})

describe('readChildNeedle', () => {
  it('★ 이름이 걸린 가지는 아래를 안 거른다', () => {
    expect(readChildNeedle('enemies', 'enemies')).toBe('')
    expect(readChildNeedle('0 · bomb_slime · 폭탄 슬라임', 'bomb_slime')).toBe('')
  })

  it('안 걸린 가지는 그대로 물려준다', () => {
    expect(readChildNeedle('enemies', 'hp_max')).toBe('hp_max')
  })

  it('안 찾을 때는 빈 말 그대로다', () => {
    expect(readChildNeedle('enemies', '')).toBe('')
  })
})
