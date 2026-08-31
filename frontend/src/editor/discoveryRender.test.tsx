/**
 * 도감 화면 검사.
 *
 * 여기서 지키는 것은 셋이다.
 *
 * 1. **미해금도 자리를 보여준다.** 빼면 도감이 "내가 가진 것 목록" 이 되고, 무엇을 더
 *    찾아야 하는지가 사라진다.
 * 2. **이름은 가리지 않는다.** 목표가 안 보이면 찾아갈 이유도 안 생긴다.
 * 3. **미해금은 「불가」와 같은 해칭이다.** 새 표기를 만들지 않는다 — 뜻이 같다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { DiscoveryPanel, buildDiscoveryCells } from './DiscoveryPanel'
import type { DiscoveryView } from '../storage'

const DISCOVERY: DiscoveryView = {
  items: [
    {
      kind: 'ITEM',
      refId: 'helm_iron',
      labelKo: '철투구',
      category: 'HEAD',
      isFound: true,
      detail: '튼튼함 +8',
    },
    {
      kind: 'ITEM',
      refId: 'bow_long',
      labelKo: '장궁',
      category: 'WEAPON_MAIN',
      isFound: false,
      detail: '',
    },
  ],
  skills: [
    { kind: 'SKILL', refId: 'HEAL', labelKo: 'HEAL', category: 'HEAL', isFound: false, detail: '' },
  ],
  found: 1,
  total: 3,
}

const MARKUP = renderToStaticMarkup(<DiscoveryPanel discovery={DISCOVERY} isOnline />)

describe('도감', () => {
  it('★ 안 밝힌 것도 목록에 있다 — 빼면 무엇을 더 찾아야 하는지가 사라진다', () => {
    expect(MARKUP).toContain('<span class="ds-cell__name">장궁</span>')
  })

  it('★ 미해금은 「불가」와 같은 해칭을 쓴다', () => {
    expect(MARKUP).toContain('ds-thumb--locked')
    expect(MARKUP).toContain('⧅')
  })

  it('★ 밝힌 것은 해칭이 아니다 — 붙으면 표기가 뜻을 잃는다', () => {
    const found = buildDiscoveryCells(
      DISCOVERY.items.filter((row) => row.isFound),
      '',
    )
    const html = renderToStaticMarkup(<>{found.map((cell) => cell.thumb)}</>)
    expect(html).not.toContain('ds-thumb--locked')
    expect(html).toContain('HD')
  })

  it('★ 몇 개를 밝혔는지 적는다 — 진행도가 없으면 모으는 이유가 없다', () => {
    expect(MARKUP).toContain('1 / 3')
  })

  it('★ 서버가 없으면 그렇게 말한다 — 빈 도감과 못 불러온 도감은 다르다', () => {
    const html = renderToStaticMarkup(<DiscoveryPanel discovery={undefined} isOnline={false} />)
    expect(html).toContain('서버에 닿지 못했다')
  })

  it('안 밝힌 칸은 「아직 못 얻었다」로 적는다', () => {
    expect(MARKUP).toContain('아직 못 얻었다')
  })
})
