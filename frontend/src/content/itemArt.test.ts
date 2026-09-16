/**
 * 아이템 도트 고르기 (2026-09-16).
 *
 * **새 필드를 안 판 대가로 규약이 생겼다.** `catalog_id` 의 접두사가 형태를 말하므로,
 * 이름을 규약 밖으로 지으면 그림이 조용히 안 뜬다 — 그 규약을 여기서 지킨다.
 */
import itemsRaw from '@resources/balance/items.json'
import { describe, expect, it } from 'vitest'

import { listArtNames, readArtName } from './itemArt'

interface RawItem {
  id: string
  hands?: string | null
  tags?: string[]
}

const ITEMS = (itemsRaw as unknown as { items: RawItem[] }).items

describe('도트 고르기', () => {
  it('★ 접두사가 형태다 — 새 필드를 안 파는 근거가 이것이다', () => {
    expect(readArtName('sword_short')).toBe('sword')
    expect(readArtName('sword_saber')).toBe('sword')
    expect(readArtName('bow_storm')).toBe('bow')
  })

  it('★ 같은 `sword` 라도 양손은 협도다 — 형태가 거짓말하면 안 된다', () => {
    expect(readArtName('sword_great', 'TWO')).toBe('glaive')
    expect(readArtName('sword_short', 'ONE')).toBe('sword')
  })

  it('★ 부적 여섯은 쓰임새로 갈린다 — 접두사가 전부 `scroll` 이다', () => {
    expect(readArtName('scroll_shield', '', 'SCROLL')).toBe('scroll')
    expect(readArtName('scroll_blink', '', 'BLINK')).toBe('blink')
    expect(readArtName('scroll_flame', '', 'FLAME')).toBe('flame')
  })

  it('★ 카탈로그 id 가 없어도 안 터진다 — 관리자 봇 가방이 그것을 안 싣는다', () => {
    expect(readArtName(undefined)).toBe('')
    expect(readArtName('')).toBe('')
  })

  it('★ 모든 아이템이 이름을 얻는다 — 하나라도 빈 이름이면 그 칸은 영영 글자다', () => {
    const missing = ITEMS.filter(
      (item) => readArtName(item.id, item.hands ?? '') === '',
    ).map((item) => item.id)
    expect(missing).toEqual([])
  })

  it('★ 카탈로그의 모든 형태가 그려져 있다 — 하나라도 없으면 그 칸만 글자로 남는다', () => {
    const wanted = new Set(ITEMS.map((item) => readArtName(item.id, item.hands ?? '')))
    const drawn = new Set(listArtNames())

    // **어느 것이 없는지 이름으로 말한다.** 개수만 세면 「셋이 없다」는 알아도 무엇을
    // 그려야 하는지는 파일을 뒤져야 한다.
    expect([...wanted].filter((name) => !drawn.has(name)).sort()).toEqual([])
  })
})
