/**
 * 계정 화면 검사.
 *
 * 여기서 지키는 것은 셋이다.
 *
 * 1. **가입이 손해가 아님을 화면이 말한다.** 승격이라 기록이 따라오는데 그것을 안 적으면
 *    사람은 "가입하면 처음부터" 로 읽고 가입하지 않는다.
 * 2. **로그인이 기록을 버릴 수 있음을 먼저 경고한다.** 되돌릴 수 없는 자리다.
 * 3. **모바일에서 입력 칸이 화면을 확대시키지 않는다.** iOS 는 16px 미만인 칸을 누르면
 *    확대하고, 확대된 화면은 사람이 손으로 되돌려야 한다.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { AccountPanel } from './AccountPanel'
import { createEmptyMeta } from '../core/schemas'

/** 아무것도 하지 않는 처리기. 렌더만 보는 검사라 호출되지 않는다. */
const noop = () => Promise.resolve('')

/**
 * 파일을 읽는다.
 *
 * @param relative 이 파일 기준 상대 경로.
 * @returns 파일 내용.
 */
function readText(relative: string): string {
  return readFileSync(fileURLToPath(new URL(relative, import.meta.url)), 'utf8')
}

describe('계정 패널 — 익명', () => {
  const markup = renderToStaticMarkup(
    <AccountPanel
      account={undefined}
      link="online"
      hasLocalProgress={false}
      onRegister={noop}
      onLogin={noop}
      onLogout={() => undefined}
    />,
  )

  it('익명이라고 말한다', () => {
    expect(markup).toContain('익명')
  })

  it('★ 가입해도 기록이 따라온다고 말한다', () => {
    // 승격이라는 사실이 화면에 없으면 사람은 가입하지 않는다.
    expect(markup).toContain('가입해도 지금까지의 기록은 그대로 따라온다')
  })

  it('가입과 로그인 둘 다 열려 있다', () => {
    expect(markup).toContain('가입')
    expect(markup).toContain('로그인')
  })
})

describe('계정 패널 — 로그인됨', () => {
  const markup = renderToStaticMarkup(
    <AccountPanel
      account={{ accountId: 7, handle: 'user_x', loginId: 'victor' }}
      link="online"
      hasLocalProgress
      onRegister={noop}
      onLogin={noop}
      onLogout={() => undefined}
    />,
  )

  it('누구로 들어와 있는지 적는다', () => {
    expect(markup).toContain('victor')
    expect(markup).toContain('동기화됨')
  })

  it('가입 버튼을 다시 보여주지 않는다', () => {
    expect(markup).toContain('다른 계정')
  })
})

describe('계정 패널 — 오프라인', () => {
  const markup = renderToStaticMarkup(
    <AccountPanel
      account={undefined}
      link="offline"
      hasLocalProgress={false}
      onRegister={noop}
      onLogin={noop}
      onLogout={() => undefined}
    />,
  )

  it('닿지 못했다고 말하고, 게임이 멈추지 않음을 함께 적는다', () => {
    expect(markup).toContain('서버에 닿지 못했다')
    expect(markup).toContain('이 기기에 남는다')
  })

  it('가입·로그인을 잠근다 — 눌러도 되지 않을 것을 열어 두지 않는다', () => {
    expect(markup).toContain('disabled')
  })
})

describe('입력 칸 — 반응형', () => {
  const tokens = readText('../../../design/tokens/spacing.css')
  const css = readText('./editor.css')

  it('★ 계정 입력 칸이 --fs-input 을 쓴다', () => {
    const block = css.slice(css.indexOf('.account__field'))
    expect(block.slice(0, block.indexOf('}'))).toContain('var(--fs-input)')
  })

  it('★ 터치 배치에서 16px 이상이다 — iOS 확대를 막는다', () => {
    // 브레이크포인트는 spacing.css 한 곳에만 있다. 세로 배치 블록을 --layout-mode 로 찾는다.
    const portrait = tokens.slice(tokens.indexOf('--layout-mode:portrait'))
    const block = portrait.slice(0, portrait.indexOf('}'))
    expect(block).toContain('--fs-input:16px')
  })

  it('가로 모바일에서도 16px 이다 — 확대는 높이가 아니라 글자가 부른다', () => {
    const landscape = tokens.slice(tokens.lastIndexOf('--btn-tap-sm-h:28px'))
    expect(landscape.slice(0, landscape.indexOf('}'))).toContain('--fs-input:16px')
  })

  it('입력 칸 높이가 터치 토큰을 쓴다', () => {
    const block = css.slice(css.indexOf('.account__field'))
    expect(block.slice(0, block.indexOf('}'))).toContain('var(--btn-tap-h)')
  })

  it('계정 CSS 에 생 hex 색이 없다', () => {
    const block = css.slice(css.indexOf('/* ── 계정 패널'))
    expect(block).not.toMatch(/#[0-9a-fA-F]{3,8}\b/)
  })

  it('계정 CSS 가 자체 미디어쿼리를 두지 않는다', () => {
    const block = css.slice(css.indexOf('/* ── 계정 패널'))
    expect(block).not.toContain('@media')
  })
})

describe('세이브 기준', () => {
  it('빈 세이브는 진행이 없는 것으로 읽힌다', () => {
    const empty = createEmptyMeta()
    expect(empty.bestFloor === 0 && empty.bestiary.length === 0).toBe(true)
  })
})

describe('로그아웃과 한 기기 규율 (2026-09-01)', () => {
  const signedIn = renderToStaticMarkup(
    <AccountPanel
      account={{ accountId: 7, handle: 'probe', loginId: 'sinindra' }}
      link="online"
      hasLocalProgress
      onRegister={async () => ''}
      onLogin={async () => ''}
      onLogout={() => undefined}
    />,
  )

  it('★ 로그인한 상태에 로그아웃이 있다 — 없으면 계정을 바꿀 방법이 없다', () => {
    // **글리프로 본다.** 그냥 "로그아웃" 을 찾으면 한 기기 안내 문구가 그 말을 담고
    // 있어 버튼을 지워도 검사가 통과한다 — 실제로 그렇게 통과했다.
    expect(signedIn).toContain('⏻')
  })

  it('★ 이 기기의 저장도 지워진다고 적는다 — 모르고 누르면 잃는다', () => {
    expect(signedIn).toContain('이 기기의 저장도 지워진다')
  })

  it('★ 한 기기 규율을 누르기 전에 말한다 — 튕긴 뒤에 알면 이미 늦다', () => {
    const html = renderToStaticMarkup(
      <AccountPanel
        account={undefined}
        link="online"
        hasLocalProgress={false}
        onRegister={async () => ''}
        onLogin={async () => ''}
        onLogout={() => undefined}
      />,
    )
    expect(html).toContain('다른 기기에서 로그인하면 이 기기는 로그아웃된다')
  })

  it('로그인 전에는 로그아웃이 없다', () => {
    const html = renderToStaticMarkup(
      <AccountPanel
        account={undefined}
        link="online"
        hasLocalProgress={false}
        onRegister={async () => ''}
        onLogin={async () => ''}
        onLogout={() => undefined}
      />,
    )
    expect(html).not.toContain('로그아웃한다')
  })
})
