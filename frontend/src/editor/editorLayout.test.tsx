/**
 * 에디터 골격이 화면 안에 들어오는가.
 *
 * **여기가 재는 것은 토큰과 `.editor` 껍데기뿐이다.** 데스크톱 배치(`.editor__body`·
 * `.editor__col*`·바 셋)를 지우면서 그것을 읽던 단언도 함께 걷었다 — 아무것도 안 그리는
 * CSS 를 검사가 붙들고 있으면 다음 사람이 그것을 산 것으로 읽는다. 실제로 그려지는
 * 세로 골격(`.edit-m__*`)의 치수는 `mobileEditor.test.tsx` 가 잰다.
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

/** 가로 블록. 폭 리터럴이 아니라 `--layout-mode:landscape` 로 찾는다. */
const LANDSCAPE_MEDIA =
  /@media[^{]*(?=\{[^}]*--layout-mode:\s*landscape)/.exec(TOKENS)?.[0]?.trimEnd() ?? ''

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

// **데스크톱 3열을 지키던 검사 셋을 걷었다** (2026-09-18). 그 배치는 2026-09-07 에
// 사라졌고, 그것을 재던 토큰 다섯(`--col-rules`·`--col-log`·`--editor-cols`·
// `--editor-overflow`·`--bar-hint`)도 이번에 정본에서 걷었다 — `var()` 호출이 저장소
// 전량에서 0건이었다.
//
// 검사들이 스스로 그 사실을 적고 있었다: "토큰만 있고 그것을 읽는 쪽이 없는 상태였다".
// 없는 것을 지키는 단언은 통과 개수만 늘리고, 「이 축이 아직 산다」는 착각을 준다.
//
// 아래 「세로 바 높이의 합」은 남는다 — 그쪽은 지금도 실재하는 값을 잰다.

describe('세로 바 높이의 합', () => {
  it('★ 상·하단 바가 화면 높이를 다 먹지 않는다', () => {
    // .editor 는 100vh 에 `상단 1fr 하단` 이다. 바 둘이 화면을 다 먹으면 가운데가 0 이
    // 되어 내용이 바 위로 올라온다 — 그것이 "버튼끼리 겹친다" 로 보인다.
    const top = Number.parseInt(readToken('--bar-top', LANDSCAPE_MEDIA), DECIMAL_RADIX)
    const bottom = Number.parseInt(readToken('--bar-bottom', LANDSCAPE_MEDIA), DECIMAL_RADIX)
    // 폰 세로 최소 높이는 568(iPhone SE)이다.
    expect(top + bottom).toBeLessThan(568 / 2)
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
    // 머리 바는 고정 높이라 넘치는 것을 감춘다. 탭 아홉을 거기 넣으면 가장 중요한
    // 것(출격·CPU)이 먼저 사라진다.
    const rows = readRule('.editor')
    expect(rows).toContain('grid-template-rows')
    // 머리 · 탭 · 본문 · 하단 네 칸이다.
    expect(rows).toContain('var(--bar-top) auto minmax(var(--sp-0), 1fr) var(--bar-bottom)')
  })
})
