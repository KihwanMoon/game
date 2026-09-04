/**
 * 에디터 골격이 화면 안에 들어오는가.
 *
 * **겹침은 대부분 "안 들어오는 것" 의 증상이다.** 폭이 넘치면 열이 서로 밀고, 높이가
 * 넘치면 바 위로 내용이 올라온다. 그래서 여기서는 색이나 모양이 아니라 **치수의 합**을
 * 본다 — 브라우저 없이 잡을 수 있는 것은 그것이고, 실제로 그 합이 틀려 있었다.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const DESIGN_DIR = fileURLToPath(new URL('../../../design/', import.meta.url))
const EDITOR_CSS = fileURLToPath(new URL('./editor.css', import.meta.url))
const DECIMAL_RADIX = 10

const TOKENS = readFileSync(`${DESIGN_DIR}tokens/spacing.css`, 'utf8')

/** 세로 블록. 폭 리터럴이 아니라 `--layout-mode:portrait` 로 찾는다. */
const PORTRAIT_MEDIA =
  /@media[^{]*(?=\{[^}]*--layout-mode:\s*portrait)/.exec(TOKENS)?.[0]?.trimEnd() ?? ''

/**
 * 토큰 하나를 읽는다.
 *
 * @param name 토큰 이름.
 * @param media 읽을 미디어쿼리의 머리. 생략하면 :root.
 * @returns 값 문자열. 없으면 빈 문자열.
 */
function readToken(name: string, media?: string): string {
  const block =
    media === undefined
      ? (TOKENS.split('@media')[0] ?? '')
      : TOKENS.slice(TOKENS.indexOf(media), TOKENS.indexOf('}\n}', TOKENS.indexOf(media)))
  return new RegExp(`${name}:\\s*([^;]+);`).exec(block)?.[1]?.trim() ?? ''
}

/**
 * CSS 규칙 하나의 본문을 읽는다.
 *
 * @param selector 선택자.
 * @returns 본문. 없으면 빈 문자열.
 */
function readRule(selector: string): string {
  const css = readFileSync(EDITOR_CSS, 'utf8')
  const start = css.indexOf(`${selector} {`)
  return start < 0 ? '' : css.slice(start, css.indexOf('}', start))
}

describe('가로 — 세 열이 화면 안에 들어온다', () => {
  it('★ 열 폭의 합이 데스크톱 골격 안이다', () => {
    // 320 + 1 + (본문) + 1 + 300 이 841px 부터 성립한다는 것이 토큰 주석의 실측이다.
    const rules = Number.parseInt(readToken('--col-rules'), DECIMAL_RADIX)
    const log = Number.parseInt(readToken('--col-log'), DECIMAL_RADIX)
    expect(rules + log).toBeLessThan(841)
  })
})

describe('세로 — 열이 없다', () => {
  it('★ 토큰이 세로에서 열을 100% 로 만든다', () => {
    // 이 값 자체는 의도된 것이다. 문제는 아래에서 본다.
    expect(readToken('--col-rules', PORTRAIT_MEDIA)).toBe('100%')
    expect(readToken('--col-log', PORTRAIT_MEDIA)).toBe('100%')
  })

  it('★ **세로에서 3열 그리드를 세우면 안 된다**', () => {
    // 열이 100% 씩이므로 `--col-rules 1px 1fr 1px --col-log` 는 화면 폭의 2배가 넘는다.
    // 그러면 열이 서로 밀려 내용이 겹치고 가로 스크롤이 생긴다.
    //
    // 토큰은 「세로에는 열이 없다」고 적어 두었는데 에디터 CSS 가 그 모드를 구현한 적이
    // 없었다 — 토큰만 있고 그것을 읽는 쪽이 없는 상태였다.
    //
    // **고치는 자리는 토큰이다.** 화면 CSS 는 미디어쿼리를 스스로 적지 않는다 —
    // 브레이크포인트가 한 곳에만 있어야 세 화면이 같은 경계에서 함께 바뀐다.
    expect(readToken('--editor-cols', PORTRAIT_MEDIA)).toBe('minmax(0, 1fr)')
    expect(readToken('--editor-cols')).toContain('--col-rules')
  })

  it('★ 격자가 토큰을 읽는다 — 값만 바꾸고 아무도 안 읽으면 그대로다', () => {
    expect(readRule('.editor__body')).toContain('var(--editor-cols)')
  })

  it('★ 세로에서 열 사이 괘선을 감춘다 — 쌓이면 1px 짜리 빈 줄이 된다', () => {
    expect(readToken('--rule-line', PORTRAIT_MEDIA)).toBe('none')
    expect(readRule('.editor__rule-line')).toContain('var(--rule-line)')
  })

  it('★ 세로에서는 격자가 스크롤한다 — 열마다 스크롤하면 어디를 밀지 모른다', () => {
    expect(readToken('--editor-overflow', PORTRAIT_MEDIA)).toBe('auto')
    expect(readRule('.editor__body')).toContain('var(--editor-overflow)')
  })
})

describe('세로 바 높이의 합', () => {
  it('★ 상·하단 바가 화면 높이를 다 먹지 않는다', () => {
    // .editor 는 100vh 에 `상단 1fr 하단` 이다. 바 둘이 화면을 다 먹으면 가운데가 0 이
    // 되어 내용이 바 위로 올라온다 — 그것이 "버튼끼리 겹친다" 로 보인다.
    const top = Number.parseInt(readToken('--bar-top', PORTRAIT_MEDIA), DECIMAL_RADIX)
    const bottom = Number.parseInt(readToken('--bar-bottom', PORTRAIT_MEDIA), DECIMAL_RADIX)
    // 폰 세로 최소 높이는 568(iPhone SE)이다.
    expect(top + bottom).toBeLessThan(568 / 2)
  })
})

describe('가운데가 넘치면 스크롤한다', () => {
  it('★ 본문이 자기 높이를 넘길 때 바깥으로 새지 않는다', () => {
    // grid 자식은 기본 min-height:auto 라 내용만큼 부풀고, 그러면 100vh 격자를 밀어
    // 하단 바가 화면 밖으로 나간다.
    expect(readRule('.editor__body')).toContain('min-height')
    expect(readRule('.editor__col')).toContain('min-height')
  })
})

describe('바가 넘칠 때 무엇을 버리는가', () => {
  it('★ 좁아지면 키보드 안내부터 버린다 — 터치 화면에서 Alt+↑ 는 뜻이 없다', () => {
    expect(readToken('--bar-hint', PORTRAIT_MEDIA)).toBe('none')
    expect(readToken('--bar-hint')).toBe('inline')
    expect(readRule('.editor__hint')).toContain('var(--bar-hint)')
  })

  it('★ 바가 넘쳐도 밖으로 새지 않는다', () => {
    // 고정 높이라 줄바꿈을 못 한다. 넘치는 것을 그냥 두면 아래 격자 위로 겹친다.
    expect(readRule('.editor__top,\n.editor__bottom')).toContain('overflow: hidden')
  })

  it('★ 버튼은 줄지 않는다 — 줄면 글자가 잘려 무슨 버튼인지 모른다', () => {
    expect(readRule('.editor__top > .ds-button,\n.editor__bottom > .ds-button')).toContain(
      'flex: 0 0 auto',
    )
  })

  it('★ 제목만 줄어든다 — 나머지는 값이라 잘리면 뜻이 달라진다', () => {
    expect(readRule('.editor__title')).toContain('text-overflow: ellipsis')
  })
})

describe('높이 사슬 — 팔레트 열의 아래 칸이 0 으로 접히지 않는가', () => {
  it('★ **패널 body 가 사슬을 잇는다**', () => {
    // `Panel` 의 기본 body 는 flex 를 걸지 않아 `flex: 0 1 auto` 로 남는다. 그대로 두면
    // 아래 칸의 `flex: 1 …` 이 잡을 높이가 없어 0 으로 접히고, **머리만 남고 내용이
    // 사라진다** — 실제로 그렇게 배포됐다 (그때는 서랍이었다).
    const rule = readRule('.editor__col--palette > .ds-panel + .ds-panel > .ds-panel__body')
    expect(rule).toContain('display: flex')
    expect(rule).toContain('flex: 1 1 var(--sp-0)')
  })
})

describe('화면 탭 줄 — 규칙표와 곁다리가 동위다', () => {
  // 예전에는 탭 줄이 둘이었다. 규칙표 탭(전투·정비)이 상단 바에 있고, 곁다리 패널들은
  // 「서랍」이라는 또 하나의 탭 줄 안에 갇혀 있었다 — 가방에 가려면 어느 탭 안의 어느
  // 탭인지를 외워야 했다.
  it('★ 서랍이 없다 — 탭 줄은 하나다', () => {
    expect(readFileSync(EDITOR_CSS, 'utf8')).not.toContain('.drw')
  })

  it('★ 탭 줄이 제 행을 쓴다 — 머리 바에 두면 출격 버튼부터 밀려 나간다', () => {
    // 머리 바는 고정 높이라 넘치는 것을 감춘다(`editor__top`). 탭 아홉을 거기 넣으면
    // 가장 중요한 것(출격·CPU)이 먼저 사라진다.
    const rows = readRule('.editor')
    expect(rows).toContain('grid-template-rows')
    // 머리 · 탭 · 본문 · 하단 네 칸이다.
    expect(rows).toContain('var(--bar-top) auto minmax(var(--sp-0), 1fr) var(--bar-bottom)')
  })

  it('★ 탭 줄은 접힌다 — 잘린 탭은 없는 탭과 구별되지 않는다', () => {
    expect(readRule('.editor__tabs')).toContain('flex-wrap: wrap')
  })

  it('★ 본문 하나뿐인 탭은 열을 하나만 쓴다 — 빈 열 둘을 세우지 않는다', () => {
    expect(readRule('.editor__body--single')).toContain('grid-template-columns')
  })

  it('★ 그 한 열도 폭을 다 쓰지 않는다 — 가방 격자는 320px 열에 맞춘 표기를 쓴다', () => {
    const rule = readRule('.editor__col--single')
    expect(rule).toContain('max-inline-size')
    expect(rule).toContain('var(--col-rules)')
    expect(rule).toContain('margin-inline: auto')
  })
})
