/**
 * 둔갑 권유 카드 (2026-09-25).
 *
 * **대가와 얻는 것을 한 장에 적는다.** 얻는 것만 적으면 켜는 사람이 모르고 해답을 공개하게
 * 되고, 그것이 기본을 꺼 둔 이유다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { DoppelInviteCard } from './DoppelInviteCard'

describe('둔갑 권유 카드', () => {
  const html = renderToStaticMarkup(<DoppelInviteCard onChoose={() => undefined} />)

  it('★ 얻는 것(활자)과 내주는 것(해답이 읽힌다)을 함께 적는다', () => {
    expect(html).toContain('활자')
    expect(html).toContain('해답을 어느 정도 읽게 된다')
  })

  it('★ 두 갈래가 다 있다 — 세우는 쪽만 있으면 권유가 아니라 유도다', () => {
    expect(html).toContain('세운다')
    expect(html).toContain('안 세운다')
  })

  it('★ 나중에 바꿀 수 있다고 말한다', () => {
    expect(html).toContain('서생 탭')
  })
})
