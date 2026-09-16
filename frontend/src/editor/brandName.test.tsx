/**
 * 홈페이지가 앱 이름과 약관을 실제로 내보이는가.
 *
 * **이것은 취향이 아니라 요건이다.** 구글 OAuth 브랜드 인증이 홈페이지에서 두 가지를
 * 본다 — 동의 화면과 같은 앱 이름, 그리고 개인정보처리방침으로 가는 링크. 어긋나면
 * 구글 로그인이 아예 안 켜진다.
 *
 * 세 번 반려됐고 **세 번 다 원인이 달랐다** (2026-09-16).
 *
 * 1. 본문이 비어 있었다(`<div id="root"></div>`). SPA 라 첫 응답에 글자가 없었다
 * 2. 첫 화면 블록을 넣었더니 **React 가 그것을 갈아 끼웠다.** 수집기가 보는 것은 갈아
 *    끼운 뒤라 남은 이름이 각인의 낡은 alt 하나뿐이었다
 * 3. 이름을 맞췄더니, 이번에는 렌더된 페이지에 **링크가 한 개도 없었다**(`a[href]` 0개).
 *    약관 링크도 첫 화면 블록에 있었기 때문이다
 *
 * 공통 원인은 하나다 — **`index.html` 에 적은 것은 앱이 붙는 순간 사라진다.** 그래서
 * 이름과 약관은 앱이 그리는 화면(`LegalLine`)에 있어야 하고, 이 검사는 그것이 거기
 * 있는지와 **여러 곳에 적힌 이름이 한 이름인지**를 함께 본다. 이름이 여러 곳에 적혀
 * 있다는 것이 이 결함의 뿌리다.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { LegalLine } from './LegalLine'

/**
 * 저장소 파일을 읽는다.
 *
 * @param relative 이 파일 기준 상대 경로.
 * @returns 파일 내용.
 */
function readText(relative: string): string {
  return readFileSync(fileURLToPath(new URL(relative, import.meta.url)), 'utf8')
}

/** 동의 화면에 적은 이름. 여기를 바꾸면 구글 콘솔도 함께 바꿔야 한다. */
const APP_NAME = 'Sealed Stacks'

const MARKUP = renderToStaticMarkup(<LegalLine />)
const INDEX = readText('../../index.html')
const MANIFEST = JSON.parse(readText('../../public/site.webmanifest')) as Record<string, string>

describe('바닥 글', () => {
  it('★ 앱 이름이 눈에 보이는 글자로 있다 — 낭독기 전용 글자는 보이는 이름이 아니다', () => {
    expect(MARKUP).toContain(APP_NAME)
    // `ds-sr` 은 화면에서 지워 놓고 낭독기에만 읽히는 클래스다. 여기서 쓰면 2번 반려로
    // 되돌아간다 — 이름이 있는데 안 보이는 상태.
    expect(MARKUP).not.toContain('ds-sr')
  })

  it('★ 개인정보처리방침과 이용약관으로 가는 링크가 있다 — 없으면 인증이 반려된다', () => {
    expect(MARKUP).toContain('href="/privacy.html"')
    expect(MARKUP).toContain('href="/terms.html"')
  })

  it('★ 그 문서들이 실제로 있다 — 404 로 가는 링크는 링크가 없는 것과 같다', () => {
    for (const name of ['privacy.html', 'terms.html']) {
      expect(readText(`../../public/${name}`).length).toBeGreaterThan(0)
    }
  })
})

describe('이름이 한 이름이다', () => {
  // 이름이 적힌 자리가 넷이고, **한 곳만 고치면 반려된다**. 2번 반려가 정확히 그랬다 —
  // `<title>` 은 고쳤는데 각인 alt 가 두 판 전 이름이었다.
  it('★ `<title>` 이 같다', () => {
    expect(INDEX).toContain(`<title>${APP_NAME}</title>`)
  })

  it('★ og:site_name·og:title 이 같다', () => {
    expect(INDEX).toContain(`property="og:site_name" content="${APP_NAME}"`)
    expect(INDEX).toContain(`property="og:title" content="${APP_NAME}"`)
  })

  it('★ 매니페스트의 name·short_name 이 같다', () => {
    expect(MANIFEST['name']).toBe(APP_NAME)
    expect(MANIFEST['short_name']).toBe(APP_NAME)
  })

  it('★ 머리줄 각인의 alt 가 같다 — 그림이 곧 이름이라 여기가 접근성 이름이 된다', () => {
    const shell = readText('./RuleEditMobile.tsx')
    const alts = [...shell.matchAll(/className="edit-m__mark"[\s\S]{0,200}?alt="([^"]*)"/g)].map(
      (hit) => hit[1],
    )
    // 두 갈래 화면이 각각 머리줄을 그린다. 하나만 고치면 화면에 따라 이름이 달라진다.
    expect(alts.length).toBe(2)
    expect(alts).toEqual([APP_NAME, APP_NAME])
  })
})
