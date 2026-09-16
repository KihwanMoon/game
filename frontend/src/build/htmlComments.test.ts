/**
 * 내보내는 HTML 에 주석이 안 실리는가.
 *
 * **저장소에는 남고 산출물에는 안 남는 것이 규칙이다.** 이 저장소는 「왜」를 주석으로
 * 적는데, HTML 주석은 묶는 도구가 안 걷어서 **소스 보기 한 번이면 그대로 읽힌다** —
 * 실제로 공개 도메인의 `index.html` 이 구글 인증 반려 이력과 설계 사유를 여섯 덩어리
 * 내보내고 있었다 (2026-09-16, 쓰는 사람이 보고했다).
 *
 * 검사가 진짜 `index.html` 을 함께 본다. 규칙만 시험하면 **규칙은 맞는데 플러그인이
 * 안 꽂힌 상태**를 못 잡는다.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { stripHtmlComments } from './htmlComments'

describe('HTML 주석 걷기', () => {
  it('★ HTML 주석을 지운다', () => {
    expect(stripHtmlComments('<p>가</p>\n    <!-- 왜 이렇게 했는가 -->\n<p>나</p>')).toBe(
      '<p>가</p>\n<p>나</p>',
    )
  })

  it('★ 여러 줄짜리도 지운다 — 이 저장소의 주석은 대체로 길다', () => {
    const html = '<head>\n  <!-- 첫 줄\n       둘째 줄\n       셋째 줄 -->\n  <title>가</title>\n</head>'
    expect(stripHtmlComments(html)).not.toContain('둘째 줄')
    expect(stripHtmlComments(html)).toContain('<title>가</title>')
  })

  it('★ 인라인 `<style>` 안의 CSS 주석도 지운다 — 첫 화면 스타일이 거기 있다', () => {
    const html = '<style>\n  /* 왜 값을 직접 쓰는가 */\n  .boot { gap: 12px; }\n</style>'
    const out = stripHtmlComments(html)
    expect(out).not.toContain('왜 값을 직접 쓰는가')
    // **스타일 자체는 살아야 한다.** 주석만 지우는 것이지 블록을 지우는 것이 아니다.
    expect(out).toContain('.boot { gap: 12px; }')
  })

  it('조건부 주석은 남긴다 — 주석 모양이지만 지우면 뜻이 바뀐다', () => {
    const html = '<!--[if IE]><p>옛 브라우저</p><![endif]-->'
    expect(stripHtmlComments(html)).toContain('[if IE]')
  })

  it('지울 것이 없으면 그대로 둔다', () => {
    expect(stripHtmlComments('<p>가</p>')).toBe('<p>가</p>')
  })
})

describe('진짜 산출물', () => {
  /**
   * 구운 HTML 을 읽는다.
   *
   * @param name 파일 이름.
   * @returns 내용. 아직 안 구웠으면 빈 문자열.
   */
  function readBuilt(name: string): string {
    try {
      return readFileSync(fileURLToPath(new URL(`../../dist/${name}`, import.meta.url)), 'utf8')
    } catch {
      // 구운 적이 없으면 볼 것이 없다. `npm run build` 뒤에 다시 돌면 본다.
      return ''
    }
  }

  const BUILT = ['index.html', 'admin.html', 'privacy.html', 'terms.html']

  it('★ 구운 HTML 에 주석이 없다 — 규칙이 맞아도 플러그인이 안 꽂히면 그대로 나간다', () => {
    for (const name of BUILT) {
      const html = readBuilt(name)
      if (html === '') {
        continue
      }
      expect(html, `${name} 에 HTML 주석이 남았다`).not.toContain('<!--')
      expect(html, `${name} 에 CSS 주석이 남았다`).not.toContain('/*')
    }
  })

  it('★ 확인용 페이지는 안 구워진다 — 공개 도메인에 내부가 서 있었다', () => {
    // `/ds.html`(부품 카탈로그)·`/battle.html`(렌더러)·`/hud.html`(되감기)이 공개
    // 도메인에 그대로 열려 있었다 (2026-09-16 실측). 보안 구멍은 아니지만 부품 이름과
    // 렌더러 조작부까지 내부가 드러난다.
    //
    // **막는 규칙이 아니라 안 굽는 쪽으로 정했다** — 규칙은 다음 사람이 풀 수 있지만
    // 없는 파일은 못 연다. 개발 서버에서는 그대로 열린다(vite 가 루트 html 을 서빙).
    for (const name of ['ds.html', 'battle.html', 'hud.html']) {
      expect(readBuilt(name), `${name} 이 산출물에 들어 있다`).toBe('')
    }
    // 구운 적이 없으면 위가 전부 참이라 통과한다. 제품 화면이 실제로 구워졌는지 함께 본다.
    const index = readBuilt('index.html')
    if (index !== '') {
      expect(index).toContain('<title>')
    }
  })

  it('★ 그래도 페이지는 온전하다 — 주석만 지우는 것이지 태그를 지우는 것이 아니다', () => {
    const html = readBuilt('index.html')
    if (html === '') {
      return
    }
    expect(html).toContain('<title>Sealed Stacks</title>')
    expect(html).toContain('class="boot"')
    expect(html).toContain('/privacy.html')
  })
})
