/**
 * 클립보드 쓰기 하나. 텍스트 뷰와 코드 라이브러리가 같은 것을 쓴다.
 *
 * 클립보드가 없는 환경(테스트·구형 브라우저·비보안 컨텍스트)에서 조용히 아무 일도 하지
 * 않는다. 복사가 안 된다고 화면이 죽으면 안 되고, 코드는 어차피 화면에 글자로 떠 있어
 * 손으로도 집을 수 있다.
 */

/**
 * 텍스트를 클립보드에 넣는다.
 *
 * @param text 넣을 문자열.
 */
export function writeClipboard(text: string): void {
  const clipboard: Clipboard | undefined = navigator.clipboard
  if (clipboard === undefined) {
    return
  }
  clipboard.writeText(text).catch(() => undefined)
}
