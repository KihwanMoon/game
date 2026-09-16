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
  use_tag?: string
}

const ITEMS = (itemsRaw as unknown as { items: RawItem[] }).items

/**
 * 화면이 그 아이템을 그릴 때 실제로 넘기는 세 값.
 *
 * **셋을 다 넘겨야 한다.** `use_tag` 를 빼고 부르면 부적 여섯이 전부 `scroll` 한 장으로
 * 뭉치고, 그러면 아래 전수 검사가 `blink`·`flame`·`focus` 를 「필요한 것」 목록에
 * 올리지 못한다 — 그 셋이 안 그려져 있는데도 초록이던 자리가 여기였다.
 */
function readShape(item: RawItem): string {
  return readArtName(item.id, item.hands ?? '', item.use_tag ?? '')
}

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
    const missing = ITEMS.filter((item) => readShape(item) === '').map((item) => item.id)
    expect(missing).toEqual([])
  })

  it('★ 카탈로그의 모든 형태가 그려져 있다 — 하나라도 없으면 그 칸만 글자로 남는다', () => {
    const wanted = new Set(ITEMS.map(readShape))
    const drawn = new Set(listArtNames())

    // **어느 것이 없는지 이름으로 말한다.** 개수만 세면 「셋이 없다」는 알아도 무엇을
    // 그려야 하는지는 파일을 뒤져야 한다.
    expect([...wanted].filter((name) => !drawn.has(name)).sort()).toEqual([])
  })

  it('★ 쓰임새 갈래가 실제로 갈린다 — 안 갈리면 위 검사가 조용히 헐거워진다', () => {
    const charms = ITEMS.filter((item) => item.id.startsWith('scroll_'))
    expect(charms.length).toBeGreaterThan(1)

    // **먼저 뭉쳐 있음을 보인다.** 쓰임새를 안 넘기면 여섯이 한 이름이다. 위 전수
    // 검사가 세 장을 빠뜨린 채 통과하던 까닭이 이 한 줄이고, 그래서 여기 남긴다.
    expect(new Set(charms.map((item) => readArtName(item.id))).size).toBe(1)

    // 쓰임새 하나에 그림 하나. 값이 겹치면 두 소모품이 가방에서 같아 보인다.
    const byUseTag = new Map(charms.map((item) => [item.use_tag ?? '', readShape(item)]))
    expect(new Set(byUseTag.values()).size).toBe(byUseTag.size)

    const drawn = new Set(listArtNames())
    expect([...byUseTag.values()].filter((name) => !drawn.has(name)).sort()).toEqual([])
  })
})
