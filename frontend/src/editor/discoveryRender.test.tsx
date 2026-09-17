/**
 * 도감 화면 검사.
 *
 * 여기서 지키는 것은 넷이다.
 *
 * 1. **미해금도 자리를 보여준다.** 빼면 도감이 "내가 가진 것 목록" 이 되고, 무엇을 더
 *    찾아야 하는지가 사라진다.
 * 2. **이름은 가리지 않는다.** 목표가 안 보이면 찾아갈 이유도 안 생긴다.
 * 3. **미해금은 「불가」와 같은 해칭이다.** 새 표기를 만들지 않는다 — 뜻이 같다.
 * 4. **격자는 가방과 같은 것이다** (2026-09-16). 도면 격자로 옮기면서 「무엇을 해
 *    주는가」 한 줄을 얻었다 — 밝힌 물건이 무엇을 해 주는지 칸에서 보인다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { DiscoveryDetail, DiscoveryPanel } from './DiscoveryPanel'
import { buildDiscoveryCells } from './discoveryCells'
import { findItemArt } from '../content/itemArt'
import type { DiscoveryRow, DiscoveryView } from '../storage'

const DISCOVERY: DiscoveryView = {
  items: [
    {
      kind: 'ITEM',
      refId: 'helm_iron',
      labelKo: '철투구',
      category: 'HEAD',
      isFound: true,
      detail: '튼튼함 +8',
      hands: '',
      useTag: '',
    },
    {
      kind: 'ITEM',
      refId: 'bow_long',
      labelKo: '장궁',
      category: 'WEAPON_MAIN',
      isFound: false,
      detail: '',
      hands: 'TWO',
      useTag: '',
    },
  ],
  skills: [
    {
      kind: 'SKILL',
      refId: 'HEAL',
      labelKo: 'HEAL',
      category: 'HEAL',
      isFound: false,
      detail: '',
      hands: '',
      useTag: '',
    },
  ],
  found: 1,
  total: 3,
}

/**
 * 마크업에 실제로 붙은 그림 주소들.
 *
 * **주소를 날것으로 찾으면 안 잡힌다.** 그림이 data URI 라 안에 작은따옴표가 들어 있고,
 * React 가 그것을 `&#x27;` 로 적는다 — 그래서 제대로 붙어 있어도 `toContain` 이 못 찾는다.
 */
function listArt(html: string): string[] {
  return [...html.matchAll(/class="invg__art" src="([^"]*)"/g)].map((hit) =>
    (hit[1] ?? '').replaceAll('&#x27;', "'"),
  )
}

/**
 * 칸에 실제로 그려진 이름들.
 *
 * **그냥 문자열을 찾으면 안 된다.** 칸의 `aria-label` 이 같은 이름을 담고 있어, 눈에
 * 보이는 이름을 지워도 통과한다 (카탈로그에서 실제로 그랬다).
 */
function listCellLabels(html: string): string[] {
  return [...html.matchAll(/class="invg__label[^"]*">([^<]*)</g)].map((hit) => hit[1] ?? '')
}

const MARKUP = renderToStaticMarkup(<DiscoveryPanel discovery={DISCOVERY} link="online" />)

describe('도감', () => {
  it('★ 안 밝힌 것도 목록에 있다 — 빼면 무엇을 더 찾아야 하는지가 사라진다', () => {
    // 칸 이름은 두 글자로 자른다(도면 격자의 규약). 전체 이름은 고른 칸의 상세가 낸다.
    expect(listCellLabels(MARKUP)).toEqual(['철투', '장궁'])
  })

  it('★ 미해금은 「불가」와 같은 해칭을 쓴다', () => {
    expect(MARKUP).toContain('⧅')
    // 색·글리프에 명도까지 셋이다 — 색 하나면 못 가르는 사람에게 사라진다.
    expect(MARKUP).toContain('invg__cell--off')
  })

  it('★ 밝힌 것은 해칭이 아니다 — 붙으면 표기가 뜻을 잃는다', () => {
    const found = buildDiscoveryCells(DISCOVERY.items.filter((row) => row.isFound))
    expect(found.map((cell) => cell.marks)).toEqual([[]])
    expect(found.map((cell) => cell.isOff)).toEqual([false])
    // 예전에는 분류 코드(`HD`)가 있는지를 봤다. 그림이 붙으면서 코드 자리를 그림이
    // 차지했으므로, 「밝힌 것은 무엇인지 보인다」를 그림 쪽에서 확인한다.
    expect(found.map((cell) => cell.art)).toEqual([findItemArt('helm_iron')])
  })

  it('★ 몇 개를 밝혔는지 적는다 — 진행도가 없으면 모으는 이유가 없다', () => {
    expect(MARKUP).toContain('1 / 3')
  })

  it('★ 서버가 없으면 그렇게 말한다 — 빈 도감과 못 불러온 도감은 다르다', () => {
    const html = renderToStaticMarkup(<DiscoveryPanel discovery={undefined} link="offline" />)
    expect(html).toContain('서버에 닿지 못했다')
  })

  it('안 밝힌 칸은 못 얻었다고 글자로도 적는다 — 글리프 하나에 안 맡긴다', () => {
    expect(MARKUP).toContain('못 얻음')
    const row = DISCOVERY.items.find((entry) => !entry.isFound) as DiscoveryRow
    expect(renderToStaticMarkup(<DiscoveryDetail row={row} />)).toContain('아직 못 얻었다')
  })

  it('★ 밝힌 물건은 무엇을 해 주는지 칸에서 보인다 — 도면 격자로 옮겨 얻은 줄이다', () => {
    // 예전 격자(`ds/CellGrid`)에는 이 줄이 들어갈 자리가 없어, 칸을 하나씩 눌러야
    // 「이게 뭘 해 주지」를 알 수 있었다.
    expect(MARKUP).toContain('튼튼함 +8')
  })

  it('★ 밝힌 아이템에는 그림이 붙는다 — `ref_id` 가 곧 카탈로그 id 다', () => {
    // 주소까지 못 박는다. 클래스 이름만 보면 아무 그림이나 붙어도 통과한다.
    // 목록이 하나인 것도 함께 본다 — 안 밝힌 `bow_long` 이 여기 끼면 해칭이 뚫린 것이다.
    expect(listArt(MARKUP)).toEqual([findItemArt('helm_iron')])
  })

  it('★ 안 밝힌 것은 그림도 안 준다 — 실루엣이 새면 해칭이 뜻을 잃는다', () => {
    const locked = buildDiscoveryCells(DISCOVERY.items.filter((row) => !row.isFound))
    // `bow_long` 은 그려 둔 형태(`bow`)라, 안 가리면 여기서 그림이 나온다.
    expect(findItemArt('bow_long')).toBeDefined()
    expect(locked.map((cell) => cell.art)).toEqual([undefined])
  })

  it('★ 재주에는 아이템 그림을 안 붙인다 — `ref_id` 가 거기서는 스킬 id 다', () => {
    const skills = buildDiscoveryCells(
      DISCOVERY.skills.map((row) => ({ ...row, isFound: true, refId: 'bow_long' })),
    )
    // 스킬 id 가 아이템 접두사와 겹치는 날이 오면 재주 칸에 활이 그려진다. 그 날을
    // 여기서 미리 만들어 둔다 — 지금 안 겹치는 것은 우연이지 규칙이 아니다.
    expect(skills.map((cell) => cell.art)).toEqual([undefined])
  })

  it('★ 손 수와 쓰임새가 그림까지 간다 — 접두사만 보면 둘이 한 그림이 된다', () => {
    // **서버는 줄곧 싣고 있었고 화면이 버리고 있었다** (2026-09-16). 그 사이 도감의
    // 양손 협도가 직검으로, 축지·눈밝이·불의 부적 셋이 보통 부적으로 떠 있었다.
    // 접두사가 같은 이 둘만이 그 경로를 밟으므로, 여기를 못 박아 둔다.
    const two = { ...(DISCOVERY.items[0] as DiscoveryRow), refId: 'sword_great', hands: 'TWO' }
    const one = { ...two, hands: '' }
    const cells = buildDiscoveryCells([two, one])
    expect(cells.map((cell) => cell.art)).toEqual([findItemArt('glaive'), findItemArt('sword')])
    expect(cells[0]?.art).not.toBe(cells[1]?.art)

    const flame = { ...(DISCOVERY.items[0] as DiscoveryRow), refId: 'scroll_flame', useTag: 'FLAME' }
    const plain = { ...flame, useTag: '' }
    const scrolls = buildDiscoveryCells([flame, plain])
    expect(scrolls.map((cell) => cell.art)).toEqual([findItemArt('flame'), findItemArt('scroll')])
    expect(scrolls[0]?.art).not.toBe(scrolls[1]?.art)
  })

  it('물건과 재주의 칸 key 가 갈린다 — 탭을 옮겼을 때 엉뚱한 칸이 열리지 않는다', () => {
    const items = buildDiscoveryCells([{ ...(DISCOVERY.items[0] as DiscoveryRow), refId: 'HEAL' }])
    const skills = buildDiscoveryCells(DISCOVERY.skills)
    expect(items[0]?.key).not.toBe(skills[0]?.key)
  })
})

describe('도감 찾기', () => {
  // **쉰 칸이 한 번에 깔린다** (2026-09-17 실측). 격자로 옮기면서 그림과 「무엇을 해
  // 주는가」는 얻었는데 찾기가 없어, 원하는 것을 눈으로 훑어야 했다.
  const MANY: DiscoveryView = {
    ...DISCOVERY,
    items: [
      ...DISCOVERY.items,
      { kind: 'ITEM', refId: 'boots_swift', labelKo: '날랜 신발', category: 'FEET', isFound: true, detail: '', hands: '', useTag: '' },
    ],
  }

  /**
   * 도감을 그린다.
   *
   * @param view 도감.
   * @returns 마크업.
   */
  function drawDiscovery(view: DiscoveryView): string {
    return renderToStaticMarkup(<DiscoveryPanel discovery={view} link="online" />)
  }

  it('★ 찾기 칸이 선다 — 길이가 변하는 격자다', () => {
    expect(drawDiscovery(MANY)).toContain('이름·분류로 찾기')
  })

  it('★ 잘린 이름이 아니라 원래 이름으로 건다', () => {
    // 칸에 뜨는 글자는 두 글자로 잘려 있다(`날랜`). 그것으로만 걸면 「신발」이 안 걸린다.
    const cells = buildDiscoveryCells(MANY.items)
    const names = cells.map((cell) => cell.label)
    expect(names).not.toContain('날랜 신발')
    const row = MANY.items.find((one) => one.refId === 'boots_swift')
    expect(row?.labelKo).toContain('신발')
  })
})
