/**
 * 발행 바 (설계/4_아이템 §18).
 *
 * 여기서 지키는 것은 넷이다.
 *
 * 1. **편집과 갈라져 있다.** 발행은 순위표 시즌을 가르는 행위다.
 * 2. **세대를 손으로 적어야 눌린다.** 자동이면 모르는 값으로 시즌이 갈린다.
 * 3. **사유가 없으면 안 눌린다.** 서버도 막지만, 눌러 보고 거절당하면 늦다.
 * 4. **낼 것이 없으면 안 눌린다.**
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { PublishBar } from './PublishBar'

const noop = () => undefined

describe('발행 바', () => {
  it('★ 시즌이 갈린다는 것을 누르기 전에 말한다', () => {
    const html = renderToStaticMarkup(<PublishBar token="t" drafts={2} onDone={noop} />)
    expect(html).toContain('순위표 시즌이 갈린다')
    expect(html).toContain('초안 2건')
  })

  it('★ 세대와 사유가 비면 잠긴다 — 눌러 보고 거절당하면 늦다', () => {
    const html = renderToStaticMarkup(<PublishBar token="t" drafts={2} onDone={noop} />)
    expect(html).toContain('disabled')
  })

  it('★ 낼 초안이 없으면 그렇게 말한다', () => {
    const html = renderToStaticMarkup(<PublishBar token="t" drafts={0} onDone={noop} />)
    expect(html).toContain('낼 초안이 없다')
    expect(html).toContain('disabled')
  })

  it('★ 세대 칸이 있다 — 자동으로 올리면 관리자가 모르는 값으로 시즌이 갈린다', () => {
    const html = renderToStaticMarkup(<PublishBar token="t" drafts={1} onDone={noop} />)
    expect(html).toContain('발행 세대')
  })
})
