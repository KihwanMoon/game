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
 * 설명문 한 덩어리를 문단으로 만든다.
 *
 * @param note 자산의 설명문. 비어 있으면 빈 문자열.
 * @returns `<p>` 들.
 */
export function buildNote(note: string): string {
  const trimmed = note.trim()
  if (trimmed === '') {
    return ''
  }
  return trimmed
    .split(/\n{2,}/)
    .map((block) => `<p>${markStrong(escapeHtml(block.trim()))}</p>`)
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
