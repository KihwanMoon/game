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
import { readFileSync, readdirSync } from 'node:fs'
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

  it('★ 한 열로 못 박혔다 — 애매하게 늘어난 열은 「만들다 말았다」로 읽힌다', () => {
    expect(shell).toContain('max-inline-size: var(--app-max)')
    expect(shell).toContain('margin-inline: auto')
    // 그림자 없이 1px 괘선 하나. 성격이 기계 도면이라 그림자를 안 쓴다.
    expect(shell).toContain('border-inline: var(--bw) solid var(--line)')
    expect(shell).not.toContain('box-shadow')
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

  it('★ 덮는 패널도 같은 한 열 안이다 — 폭이 다르면 다른 화면처럼 보인다', () => {
    for (const rule of [readRule(HUD_CSS, '.hud-post'), readRule(APP_CSS, '.replay')]) {
      expect(rule).toContain('max-inline-size: var(--app-max)')
      expect(rule).toContain('margin-inline: auto')
    }
  })
})

describe('★ 데스크톱 3열을 세우는 CSS 가 하나도 없다', () => {
  // **이 검사가 없어서 두 화면이 조용히 깨졌다.** 데스크톱 배치를 지우면서
  // `--col-rules`·`--col-log` 가 100% 가 됐는데, `/hud.html` 과 `/ds.html` 이 그 값으로
  // 3열 격자를 계속 세우고 있었다 — `100% 1px 1fr 1px 100%` 는 화면 폭의 두 배다.
  const FLIPPED = ['--col-rules', '--col-log']

  /**
   * `src` 아래의 스타일 시트를 전부 읽는다.
   *
   * @param dir 훑을 디렉터리.
   * @returns 경로와 내용 쌍들.
   */
  function listStyles(dir: string): readonly (readonly [string, string])[] {
    const found: (readonly [string, string])[] = []
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = `${dir}/${entry.name}`
      if (entry.isDirectory()) {
        found.push(...listStyles(full))
      } else if (entry.name.endsWith('.css')) {
        found.push([full, readFileSync(full, 'utf8')])
      }
    }
    return found
  }

  const SHEETS = listStyles(fileURLToPath(new URL('..', import.meta.url)))

  it('시트를 실제로 읽었다 — 0개를 훑고 통과하면 검사가 아니다', () => {
    expect(SHEETS.length).toBeGreaterThan(3)
  })

  it('★ 열 폭 토큰으로 격자를 세우지 않는다 — 그 값은 이제 100% 다', () => {
    for (const [path, css] of SHEETS) {
      const stripped = css.replace(/\/\*[\s\S]*?\*\//g, '')
      for (const rule of stripped.split('}')) {
        if (!rule.includes('grid-template-columns')) {
          continue
        }
        for (const token of FLIPPED) {
          expect(rule.includes(token), `${path} 이 ${token} 으로 열을 세운다`).toBe(false)
        }
      }
    }
  })
})
