/**
 * 초점 테두리는 **초점만의 채널이다** (design/README.md).
 *
 * 두 가지가 그것을 뺏고 있었다.
 *
 * 1. `.account__field:focus { outline: none }` — 키보드로 옮겨 온 사람에게 지금 어디에
 *    치고 있는지가 괘선 색 하나로만 남았다. 그것도 아이디와 비밀번호 칸에서.
 * 2. `.invg__cell--picked { outline: ... }` — 고른 칸에 초점이 오면 같은 속성이라
 *    둘 중 하나가 통째로 사라진다. **고름은 데이터의 상태이고 초점은 입력 장치의
 *    상태다** — 채널이 달라야 한다.
 *
 * 그래서 규칙 하나를 검사로 굳힌다: `outline` 은 `:focus-visible` 안에서만 쓴다.
 * 그림자를 대신 쓰는 길도 없다 — 시스템에 그림자가 없다.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

/** 검사할 스타일시트. 앱이 싣는 것 전부다. */
const SHEETS = [
  '../ds/ds.css',
  '../editor/editor.css',
  '../editor/catalog.css',
  '../hud/hud.css',
  './app.css',
]

/**
 * 주석을 걷어낸 CSS 를 읽는다.
 *
 * 주석 안의 `outline 을 쓰지 않는다` 같은 설명글을 위반으로 세지 않기 위해서다.
 *
 * @param name 이 파일 기준 상대 경로.
 * @returns 주석 없는 본문.
 */
function readStrippedCss(name: string): string {
  const path = fileURLToPath(new URL(name, import.meta.url))
  return readFileSync(path, 'utf-8').replace(/\/\*[\s\S]*?\*\//g, '')
}

/**
 * `outline` 을 선언한 규칙의 선택자를 모은다.
 *
 * @param css 주석 없는 본문.
 * @returns 선택자들. 하나도 없으면 빈 배열.
 */
export function listOutlineSelectors(css: string): string[] {
  const found: string[] = []
  for (const match of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (/(^|[;\s])outline\s*:/.test(match[2] ?? '')) {
      found.push((match[1] ?? '').trim().replace(/\s+/g, ' '))
    }
  }
  return found
}

describe('초점 테두리는 초점만 쓴다', () => {
  it.each(SHEETS)('%s — outline 은 :focus-visible 안에서만', (name) => {
    const wrong = listOutlineSelectors(readStrippedCss(name)).filter(
      (selector) => !selector.includes(':focus-visible'),
    )
    expect(wrong).toEqual([])
  })

  it('★ 초점을 지우는 선언이 없다', () => {
    for (const name of SHEETS) {
      expect(readStrippedCss(name)).not.toMatch(/outline\s*:\s*(none|0)\b/)
    }
  })

  it('그림자로 대신하지도 않는다 — 시스템에 그림자가 없다', () => {
    for (const name of SHEETS) {
      const shadows = readStrippedCss(name).match(/box-shadow\s*:\s*([^;}]+)/g) ?? []
      for (const line of shadows) {
        expect(line).toContain('--shadow-none')
      }
    }
  })
})
