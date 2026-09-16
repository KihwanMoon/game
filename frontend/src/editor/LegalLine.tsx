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

/**
 * 세계의 이름과 그 뜻.
 *
 * **이름이 아니라 뜻풀이다.** 인증이 보는 이름 칸(`<title>`·og·매니페스트·각인 alt)은
 * `Sealed Stacks` 하나로 두고, 한자는 이 줄에서만 산다 — 이름 칸에 두 이름이 서면
 * 동의 화면과의 대조가 어긋나고, 그것이 세 번 반려된 바로 그 검사다.
 *
 * 祕閣 은 임금의 서고다. 碑閣(비석을 덮은 집)이 아닌데 현대 한국어에서는 그쪽으로
 * 읽히므로 한자를 안 붙이면 다른 뜻이 된다.
 *
 * **뜻풀이는 안 적는다** (2026-09-16). 한동안 「— 잠근 서가」를 붙여 두었는데, 이름 옆에
 * 설명이 서면 그 줄이 이름이 아니라 각주로 읽힌다. 뜻이 궁금한 사람은 한자를 보면 되고,
 * 영문 이름(`Sealed Stacks`)이 이미 같은 말을 하고 있다 — 祕(잠근)+閣(서가)이 그대로
 * `closed stacks`(열람 제한 서고)다.
 */
const WORLD_NAME = '비각 祕閣'

/**
 * 권리 표시.
 *
 * **저작권은 만든 순간 생기지만 표시는 별개다.** 적어 두면 「누구 것인지 몰랐다」는
 * 말을 막고, 분쟁이 생겼을 때 언제부터 누구의 것이었는지를 가리키는 자리가 된다.
 * 약관 §6·§11 과 같은 이름이어야 한다 — 어긋나면 어느 쪽이 맞는지 알 수 없다.
 */
const COPYRIGHT = '© 2026 Kihwan Moon'

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
      <span className="legal__world">
        {WORLD_NAME}
        <span className="legal__sep" aria-hidden="true">
          {' · '}
        </span>
        {COPYRIGHT}
      </span>
    </footer>
  )
}
