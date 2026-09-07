/**
 * 앱 껍데기가 자식을 자르지 않는가.
 *
 * **상한이면 흐르는 배치가 갈 데가 없다.** 껍데기는 오래 `height:100dvh` +
 * `overflow:hidden` 인 고정 프레임이었는데, 세로 전투 화면은 반대로 흐른다
 * (`.battle--portrait` 는 `min-height:100dvh`·`overflow:visible`, 실제 피드백
 * 「상한을 걸지 말라니까」). 두 규칙이 함께 서면 적어도 하단 안전 영역만큼은 잘리고,
 * 잘리는 자리가 하단 바다.
 *
 * 브라우저 없이 잡을 수 있는 것은 규칙의 **글자**뿐이라 여기서 보는 것도 그것이다.
 * 실제로 잘리는지는 화면이 답하지만, 잘릴 수 있는 조합인지는 여기서 답한다.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const APP_CSS = readFileSync(fileURLToPath(new URL('./app.css', import.meta.url)), 'utf8')
const HUD_CSS = readFileSync(fileURLToPath(new URL('../hud/hud.css', import.meta.url)), 'utf8')

/**
 * CSS 규칙 하나의 본문을 읽는다.
 *
 * @param css 볼 파일 내용.
 * @param selector 선택자.
 * @returns 본문. 없으면 빈 문자열.
 */
function readRule(css: string, selector: string): string {
  const start = css.indexOf(`${selector} {`)
  return start < 0 ? '' : css.slice(start, css.indexOf('}', start))
}

describe('앱 껍데기는 상한이 아니라 바닥이다', () => {
  const shell = readRule(APP_CSS, '.app')

  it('★ 높이를 가두지 않는다 — 세로 전투가 흐를 수 있어야 한다', () => {
    expect(shell).toContain('min-block-size: 100dvh')
    expect(shell).not.toContain('height: 100dvh')
    expect(shell).not.toContain('overflow: hidden')
  })

  it('안전 영역 네 변을 모두 피한다 — 하단 바가 제스처 바 뒤로 들어가면 못 누른다', () => {
    for (const side of ['top', 'right', 'bottom', 'left']) {
      expect(shell).toContain(`env(safe-area-inset-${side}`)
    }
  })
})

describe('★ 덮는 패널은 뷰포트에 붙는다 — 껍데기가 흐르면 함께 늘어난다', () => {
  it('사후 분석과 재생이 같은 방식으로 덮는다', () => {
    // 하나만 fixed 면 껍데기가 길어졌을 때 다른 하나의 닫기 버튼이 화면 밖으로 나간다.
    expect(readRule(HUD_CSS, '.hud-post')).toContain('position: fixed')
    expect(readRule(APP_CSS, '.replay')).toContain('position: fixed')
  })
})
