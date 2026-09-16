/**
 * 껍데기 맨 아래의 바닥 글 — 앱 이름과 약관 두 줄.
 *
 * **이것은 장식이 아니라 요건이다** (2026-09-16). 구글 OAuth 브랜드 인증은 홈페이지에서
 * 두 가지를 본다: 동의 화면과 **같은 앱 이름**, 그리고 **개인정보처리방침으로 가는 링크**.
 * `index.html` 의 첫 화면(`.boot`)에 둘 다 적어 뒀었는데, **React 가 붙으면서 그 블록을
 * 통째로 갈아 끼운다** — 수집기가 보는 것은 갈아 끼운 뒤이므로, 실측해 보니 렌더된
 * 홈페이지에 링크가 **한 개도** 없었다(`a[href]` 0개). 이름도 `ds-sr`(낭독기 전용) 안에만
 * 있어서 눈에 보이는 글자로는 없는 것과 같았다.
 *
 * 그래서 앱 안에 둔다. 첫 화면이 아니라 **앱이 그리는 화면**에 있어야 살아남는다.
 */
import React from 'react'

/** 동의 화면·매니페스트·`<title>` 과 같은 이름이어야 한다. 어긋나면 인증이 반려된다. */
const APP_NAME = 'Sealed Stacks'

/** 약관 문서들. 같은 도메인에 있어야 한다 — 구글이 그것도 본다. */
const DOCS: readonly { readonly href: string; readonly text: string }[] = [
  { href: '/privacy.html', text: '개인정보처리방침' },
  { href: '/terms.html', text: '이용약관' },
]

/**
 * 바닥 글을 그린다.
 *
 * @returns 이름과 약관 링크가 든 한 줄.
 */
export function LegalLine(): React.JSX.Element {
  return (
    <footer className="legal">
      <span className="legal__name">{APP_NAME}</span>
      {DOCS.map((doc) => (
        <React.Fragment key={doc.href}>
          {/* 가름표는 글이 아니다. 낭독기에게는 이름과 링크만 이어서 들리면 된다. */}
          <span className="legal__sep" aria-hidden="true">
            ·
          </span>
          <a className="legal__link" href={doc.href}>
            {doc.text}
          </a>
        </React.Fragment>
      ))}
    </footer>
  )
}
