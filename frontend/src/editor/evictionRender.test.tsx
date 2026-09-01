/**
 * 튕김 안내.
 *
 * 여기서 지키는 것은 셋이다.
 *
 * 1. **서버가 죽은 것과 내가 튕긴 것은 다르다.** 앞엣것은 기다리면 되고 뒤엣것은 다시
 *    로그인해야 한다 — 둘 다 "오프라인" 으로 보이면 사람은 기다린다.
 * 2. **무엇을 해야 하는지 말한다.** "연결이 끊겼다" 만으로는 다음 행동을 모른다.
 * 3. **안 튕겼으면 아무것도 안 그린다.** 늘 떠 있으면 그 표시가 뜻을 잃는다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { EVICTION_TEXT, EvictionNotice } from './EvictionNotice'

describe('튕김 안내', () => {
  const shown = renderToStaticMarkup(<EvictionNotice isEvicted />)

  it('★ 왜 끊겼는지 말한다 — 오프라인과 구별돼야 한다', () => {
    expect(shown).toContain('다른 기기에서 로그인했다')
  })

  it('★ 무엇을 하면 되는지 말한다', () => {
    expect(shown).toContain('다시 로그인하면')
  })

  it('★ 이 기기의 규칙표는 그대로라고 말한다 — 튕긴 것은 내가 고른 일이 아니다', () => {
    expect(shown).toContain('규칙표는 그대로')
    expect(EVICTION_TEXT).not.toContain('지워')
  })

  it('★ 안 튕겼으면 아무것도 안 그린다 — 늘 떠 있으면 뜻을 잃는다', () => {
    expect(renderToStaticMarkup(<EvictionNotice isEvicted={false} />)).toBe('')
  })
})
