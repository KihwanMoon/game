/**
 * 산출물 HTML 에서 주석을 걷어 낸다.
 *
 * **저장소의 주석과 내보내는 주석은 다른 물건이다.** 이 저장소는 「왜 그렇게 했는가」를
 * 주석으로 적는 것을 규율로 삼는데(`.claude/rules/python-style.md`), HTML 주석만은
 * **묶는 도구가 안 걷어 내서 그대로 브라우저에 실려 간다** — 소스 보기 한 번이면 구글
 * 인증을 몇 번 반려당했는지, 무엇을 왜 그렇게 정했는지가 전부 보인다. 별도 JS·CSS 파일은
 * 이미 걷힌다.
 *
 * 그래서 파일에는 남기고 내보낼 때만 지운다. 지우는 것이 아니라 **안 싣는 것이다.**
 *
 * 여기 있는 이유는 검사가 닿아야 하기 때문이다 — `vite.config.ts` 안에 두면 이 규칙이
 * 조용히 풀려도 아무도 모른다.
 */

/**
 * 주석 하나. **제 줄의 들여쓰기와 줄바꿈까지 함께 먹는다** — 안 그러면 주석이 있던
 * 자리에 빈 들여쓰기 줄이 남아, 지운 자리가 오히려 눈에 띈다.
 *
 * **주석 모양이지만 주석이 아닌 것 둘은 뺀다.** 지우면 뜻이 바뀐다.
 *   - `<!--[if ...]>` — 옛 IE 용 분기
 *   - `<!--email_off-->` / `<!--email_on-->` — Cloudflare 에게 이 자리는 메일 주소를
 *     난독화하지 말라고 이르는 지시문이다. 방침의 연락처가 난독화되면 **스크립트가
 *     돌아야만 보이는 연락처**가 되는데, 법이 적으라 한 것을 그렇게 둘 수는 없다
 */
const COMMENT = /[ \t]*<!--(?!\[if |email_off|email_on)[\s\S]*?-->\n?/g

/** 인라인 `<style>` 한 덩어리. 첫 화면 스타일이 여기 있다. */
const STYLE_BLOCK = /(<style[^>]*>)([\s\S]*?)(<\/style>)/g

/** CSS 주석. */
const CSS_COMMENT = /\/\*[\s\S]*?\*\//g

/**
 * HTML 한 장에서 주석을 걷어 낸다.
 *
 * @param html 원본 HTML.
 * @returns 주석이 빠진 HTML. 조건부 주석은 남는다.
 */
export function stripHtmlComments(html: string): string {
  const stripped = html.replace(COMMENT, '')
  // 인라인 `<style>` 안의 CSS 주석도 함께 간다. 별도 CSS 파일은 묶는 도구가 걷어 내지만
  // **HTML 안에 박힌 것은 안 걷는다.**
  return stripped.replace(
    STYLE_BLOCK,
    (_whole, open: string, body: string, close: string) =>
      `${open}${body.replace(CSS_COMMENT, '')}${close}`,
  )
}
