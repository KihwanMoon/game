/**
 * 도감 정적 페이지의 껍데기 — **크롤러가 읽는 유일한 본문이다.**
 *
 * 게임 본체는 SPA 라 크롤러가 받아 가는 글자가 부트 화면 68자뿐이다. 구글은 JS 를
 * 돌려 주지만 느리고 인색하고, **네이버(Yeti)는 사실상 안 돌린다** — 국내 유입을
 * 바란다면 읽을 것을 따로 구워 두어야 한다.
 *
 * **빌드가 굽는다.** 서버 렌더링을 들이지 않는 이유는 이 페이지들이 자산 파일에서만
 * 나오고 런타임에 안 바뀌기 때문이다 — 돌지 않는 것을 서버에 얹으면 장애 자리만 는다.
 *
 * 성격은 `legal.css` 와 같다: 앱 토큰을 별칭으로 못 읽으므로 값을 손으로 옮겨 적고,
 * 바뀔 일이 거의 없는 것만 쓴다.
 */

/** 구운 페이지 하나. */
export interface CodexPage {
  /** `/` 로 시작하는 경로. 사이트맵이 이것을 그대로 쓴다. */
  readonly path: string
  readonly html: string
}

/** 페이지 껍데기가 받는 것. */
export interface PageShell {
  /** `<title>`. 뒤에 사이트 이름이 붙는다. */
  readonly title: string
  /** 검색 결과에 뜨는 한 줄. */
  readonly description: string
  /** 이 페이지의 정식 주소. */
  readonly path: string
  /** `<main>` 안에 들어갈 조각. */
  readonly body: string
}

export const SITE_NAME = 'Sealed Stacks'
export const SITE_ORIGIN = 'https://sealedstacks.com'

/**
 * HTML 에서 뜻을 갖는 글자를 막는다.
 *
 * 자산의 설명문에 `<` 나 `&` 가 들어 있으면 페이지가 깨진다. **그림(SVG)에는 쓰지
 * 않는다** — 그쪽은 우리가 구운 마크업이라 그대로 실어야 한다.
 *
 * @param raw 넣을 문자열.
 * @returns 막은 문자열.
 */
export function escapeHtml(raw: string): string {
  return raw
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/**
 * 자산 설명문의 강조 표시를 HTML 로 옮긴다.
 *
 * 설명문은 `**굵게**` 를 쓴다 — 저장소 전체가 주석에 그렇게 적고, 자산의 `_note` 도
 * 같은 버릇으로 쓰였다. 별표를 그대로 두면 사람이 읽을 때 걸린다.
 *
 * **막은 뒤에 부른다.** 순서가 뒤집히면 우리가 넣은 `<strong>` 이 다시 막힌다.
 *
 * @param escaped 이미 막아 둔 문자열.
 * @returns 강조가 태그로 바뀐 문자열.
 */
export function markStrong(escaped: string): string {
  return escaped.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
}

/**
 * 내부 문서 참조를 알아보는 꼴.
 *
 * `설계/5_스킬 §10.6`·`GDD §5`·`결정 #12`·`docs/05`·`R5`·`W6` 같은 것들이다. 자산의
 * 설명문은 원래 **다음 사람에게 남기는 글**이라 이런 참조가 섞여 있는데, 공개 페이지에서는
 * 읽는 사람이 따라갈 수 없는 자리를 가리킨다.
 */
const DOC_REF =
  /(?:설계|기획|참고|결정)\/[0-9]+_[^\s)」]*|docs\/[^\s)」]+|(?:GDD|TDD)\s*§\s?[0-9][0-9.]*|§\s?[0-9][0-9.]*|결정\s?#[0-9]+|\b[RGTUWP][0-9]+\b/

/** 괄호에 든 참조. `(GDD §5)` 처럼 통째로 걷어도 문장이 그대로 산다. */
const PAREN_REF = /\s*\((?:[^()]*)\)/g

/**
 * 문장 하나에서 괄호에 든 참조만 걷는다.
 *
 * **괄호 안에 참조가 있을 때만 걷는다.** 괄호를 다 걷으면 「(1층 60런 46% → 35%)」
 * 같은 실측값까지 사라진다 — 그쪽은 읽는 사람이 제일 궁금해하는 숫자다.
 *
 * @param sentence 문장 하나.
 * @returns 괄호 참조가 빠진 문장.
 */
export function dropParenRefs(sentence: string): string {
  return sentence
    .replace(PAREN_REF, (found) => (DOC_REF.test(found) ? '' : found))
    // 괄호가 빠진 자리에 남는 공백을 접는다 — 「요구한다 .」 가 되면 안 된다.
    .replace(/\s+([.,:;、。」])/g, '$1')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

/**
 * 설명문에서 내부 문서 참조를 걷는다.
 *
 * **두 단계다.** 괄호에 붙은 참조는 걷고 문장을 살린다. 그러고도 참조가 남으면 그것은
 * **문장의 주어 자리**에 있다는 뜻이라(「설계/5_스킬 §10.6 이 … 되묻는 자리다」) 걷는
 * 것만으로는 말이 깨진다 — 그 문장은 통째로 뺀다.
 *
 * 성한 문장을 지키려고 이렇게 한다. 통째로 빼기만 하면 「강함의 대가가 희귀도가 아니라
 * 예고다」 처럼 읽는 사람에게 제일 필요한 줄까지 함께 사라진다.
 *
 * @param note 자산의 설명문.
 * @returns 참조가 빠진 설명문.
 */
export function stripDocRefs(note: string): string {
  return note
    .split(/\n{2,}/)
    .map((block) =>
      block
        .split(/(?<=다\.)\s+|(?<=\.)\s+(?=[가-힣A-Z*「])/)
        .map((sentence) => dropParenRefs(sentence))
        .filter((sentence) => sentence !== '' && !DOC_REF.test(sentence))
        .join(' '),
    )
    .filter((block) => block.trim() !== '')
    .join('\n\n')
}

/**
 * 역따옴표로 감싼 것을 `<code>` 로 옮긴다.
 *
 * 설명문은 게임 안의 이름을 `` `CASTER` `` 처럼 적는다. 그대로 두면 따옴표가 글자로
 * 보인다 — **막은 뒤에 부른다**, `markStrong` 과 같은 이유다.
 *
 * @param escaped 이미 막아 둔 문자열.
 * @returns 코드가 태그로 바뀐 문자열.
 */
export function markCode(escaped: string): string {
  return escaped.replace(/`([^`]+)`/g, '<code>$1</code>')
}

/**
 * 설명문 한 덩어리를 문단으로 만든다.
 *
 * 내부 문서 참조는 여기서 걷는다 — 공개 페이지가 읽는 사람이 못 따라갈 자리를
 * 가리키면 안 된다.
 *
 * @param note 자산의 설명문. 비어 있으면 빈 문자열.
 * @returns `<p>` 들.
 */
export function buildNote(note: string): string {
  const trimmed = stripDocRefs(note.trim())
  if (trimmed === '') {
    return ''
  }
  return trimmed
    .split(/\n{2,}/)
    .map((block) => `<p>${markCode(markStrong(escapeHtml(block.trim())))}</p>`)
    .join('\n      ')
}

/**
 * 이름·값 쌍을 표로 만든다.
 *
 * **표로 두는 이유.** 크롤러가 「이름 다음에 값」이라는 관계를 읽는다 — 같은 내용을
 * 문장으로 풀면 그 관계가 사라지고, 사람도 수치를 못 훑는다.
 *
 * @param rows 이름과 값 쌍들.
 * @returns `<table>`.
 */
export function buildStatTable(rows: readonly (readonly [string, string])[]): string {
  const body = rows
    .map(([name, value]) => `<tr><th scope="row">${escapeHtml(name)}</th><td>${escapeHtml(value)}</td></tr>`)
    .join('\n          ')
  return `<table class="cx__stats">\n        <tbody>\n          ${body}\n        </tbody>\n      </table>`
}

/**
 * 다른 도감 페이지로 가는 고리 목록.
 *
 * **안쪽 고리가 곧 색인이다.** 사이트맵이 주소를 알려 주더라도, 서로 안 이어진 페이지
 * 스물셋은 크롤러에게 「중요하지 않은 낱장 스물셋」으로 보인다.
 *
 * @param links 주소와 이름 쌍들.
 * @returns `<ul>`. 비면 빈 문자열.
 */
export function buildLinkList(links: readonly (readonly [string, string])[]): string {
  if (links.length === 0) {
    return ''
  }
  const items = links
    .map(([path, name]) => `<li><a href="${escapeHtml(path)}">${escapeHtml(name)}</a></li>`)
    .join('\n          ')
  return `<ul class="cx__links">\n          ${items}\n        </ul>`
}

/**
 * SVG 원문을 `data:` 주소로 싼다.
 *
 * **`#` 을 꼭 막는다.** 도트의 색이 전부 `#2C3849` 꼴이라, 안 막으면 주소가 첫 색에서
 * 조각 참조로 잘리고 그림이 통째로 안 뜬다.
 *
 * `<`·`>` 까지 막는 것은 vite 의 인라이너와 같은 꼴을 쓰기 위해서다 — 속성 안의 날
 * 꺾쇠는 법으로는 되지만, 막아 두면 「본문의 태그인가 주소의 글자인가」를 읽는 쪽이
 * 안 헷갈린다.
 *
 * @param svg 구운 SVG 원문 한 줄.
 * @returns `data:image/svg+xml,...` 주소.
 */
export function buildDataUri(svg: string): string {
  const packed = svg
    .replace(/%/g, '%25')
    .replace(/#/g, '%23')
    .replace(/"/g, '%22')
    .replace(/&/g, '%26')
    .replace(/</g, '%3C')
    .replace(/>/g, '%3E')
    .replace(/\s*\n\s*/g, ' ')
  return `data:image/svg+xml,${packed}`
}

/** 그림이 붙은 고리 하나. */
export interface ArtLink {
  readonly path: string
  readonly name: string
  /** 그림(SVG 원문). 아직 안 그린 것은 생략하고, 그 고리만 글자로 선다. */
  readonly art?: string | undefined
}

/**
 * 그림이 붙은 고리 목록. 첫 장이 쓴다.
 *
 * **글자만 있는 목록은 마흔 줄에서 훑어지지 않는다.** 도감 첫 장은 몬스터 스물셋과
 * 재주 열일곱이 한 장에 서는 자리라, 실루엣이 있으면 눈이 이름을 안 읽고도 자리를
 * 잡는다 — 낱장에 이미 그림이 있으므로 새 자산도 아니다.
 *
 * **그림을 받아서 쓴다.** 주소에서 id 를 되파내던 것을 고쳤다 — 그 배선은 주소 꼴을
 * 바꾸는 날 조용히 그림만 사라지고, 사라진 것은 아무 검사도 안 본다.
 *
 * **여기서는 `<img>` 로 싣는다.** 낱장은 그림이 한 장이라 마크업을 그대로 박지만,
 * 첫 장은 마흔 장이 한꺼번에 서서 `<rect>` 가 2532개가 됐다 — Lighthouse 가 DOM
 * 1400 마디에서 경고하는 자리다. 바이트는 같고(둘 다 본문에 박힌다) 마디만 마흔으로
 * 준다.
 *
 * @param links 고리들.
 * @returns 목록 마크업. 고리가 없으면 빈 문자열.
 */
export function buildArtLinkList(links: readonly ArtLink[]): string {
  if (links.length === 0) {
    return ''
  }
  const items = links
    .map((link) => {
      const mark =
        link.art === undefined
          ? ''
          : `<img class="cx__ico" src="${buildDataUri(link.art)}" alt="" width="32" height="32" />`
      return `<li>${mark}<a href="${escapeHtml(link.path)}">${escapeHtml(link.name)}</a></li>`
    })
    .join('\n          ')
  return `<ul class="cx__grid">\n          ${items}\n        </ul>`
}

/** 한글 음절이 시작하는 코드포인트. 받침 판정에 쓴다. */
const HANGUL_BASE = 0xac00
/** 한 초성·중성 묶음이 갖는 종성 가짓수. 나머지가 0 이면 받침이 없다. */
const FINAL_COUNT = 28

/**
 * 받침이 있는 낱말인지 본다.
 *
 * **자산 이름으로 문장을 만들기 때문에 필요하다.** 「일격은」과 「메테오는」이 갈리고,
 * 틀리면 그 문장만 외국인이 쓴 것처럼 읽힌다 — 실제로 「대상 하나을」이 찍혔다.
 *
 * 한글이 아닌 글자로 끝나면 받침이 있는 것으로 본다. 영문 id 가 그대로 나오는 자리는
 * 정본에 이름이 없다는 뜻이고, 그때는 어느 쪽이든 어색하다.
 *
 * @param word 볼 낱말.
 * @returns 받침이 있으면 true.
 */
export function checkHasFinal(word: string): boolean {
  const last = word.trim().slice(-1)
  const code = last.charCodeAt(0)
  if (Number.isNaN(code) || code < HANGUL_BASE || code > 0xd7a3) {
    return true
  }
  return (code - HANGUL_BASE) % FINAL_COUNT !== 0
}

/**
 * 낱말 뒤에 조사를 붙인다.
 *
 * @param word 앞말.
 * @param withFinal 받침이 있을 때 쓸 조사 (`은`·`을`·`이`).
 * @param withoutFinal 받침이 없을 때 쓸 조사 (`는`·`를`·`가`).
 * @returns 조사가 붙은 말.
 */
export function attachParticle(word: string, withFinal: string, withoutFinal: string): string {
  return `${word}${checkHasFinal(word) ? withFinal : withoutFinal}`
}

/**
 * 페이지 하나를 완성한다.
 *
 * **`index, follow` 를 명시한다.** 기본값이긴 하지만, 이 페이지들은 색인되라고 만든
 * 것이므로 의도를 글로 남긴다 — `admin.html` 과 갈리는 자리다.
 *
 * @param shell 제목·설명·주소·본문.
 * @returns HTML 전문.
 */
export function renderPage(shell: PageShell): string {
  const full = `${shell.title} · ${SITE_NAME}`
  return `<!doctype html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="theme-color" content="#0E131C" />
    <meta name="robots" content="index, follow" />
    <title>${escapeHtml(full)}</title>
    <meta name="description" content="${escapeHtml(shell.description)}" />
    <link rel="canonical" href="${escapeHtml(SITE_ORIGIN + shell.path)}" />
    <link rel="icon" href="/brand/favicon.ico" sizes="16x16 32x32 48x48" />
    <link rel="stylesheet" href="/codex.css" />
    <meta property="og:type" content="article" />
    <meta property="og:site_name" content="${SITE_NAME}" />
    <meta property="og:title" content="${escapeHtml(full)}" />
    <meta property="og:description" content="${escapeHtml(shell.description)}" />
    <meta property="og:url" content="${escapeHtml(SITE_ORIGIN + shell.path)}" />
    <meta property="og:locale" content="ko_KR" />
  </head>
  <body>
    <nav class="cx__nav">
      <a href="/">비각</a> · <a href="/codex/">도감</a>
    </nav>
    <main>
      ${shell.body}
    </main>
    <footer class="cx__foot">
      <p><a href="/">게임 하러 가기</a></p>
      <p><a href="/privacy.html">개인정보처리방침</a> · <a href="/terms.html">이용약관</a></p>
    </footer>
  </body>
</html>
`
}
