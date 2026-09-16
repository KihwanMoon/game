/**
 * 옵션 줄 목록 검사 — **네 화면이 베껴 쓰던 것을 한 틀로 모은 뒤에도 셋이 지켜지는가.**
 *
 * 셋 다 모으기 전에 실제로 깨졌던 것이고, 셋 다 「보기 나쁘다」가 아니라 **거짓을 말하는**
 * 종류다.
 *
 * 1. **값이 중복돼도 줄이 다 그려진다.** 접사는 같은 줄이 둘 나올 수 있다(서버에서 실제로
 *    나온다). 값만으로 키를 만들면 React 가 같은 줄로 보고 하나를 지운다 — 사람은 안 붙은
 *    옵션을 보고 판단한다.
 * 2. **비면 아무것도 안 그린다.** 「옵션이 없다」를 적으면 상세에 뜻 없는 줄이 하나 는다.
 * 3. **거르기·페이지가 안 선다.** 줄 오른쪽 단추는 **접사의 자리**로 서버에 말하므로,
 *    보이는 줄이 줄면 누른 줄과 갈리는 줄이 어긋나 **옆 줄이 갈린다**.
 *
 * 셋째는 틀만 봐서는 끝이 아니라, 그 단추를 실제로 붙이는 화면(`InventoryDetail`)까지
 * 내려가서 **첨자가 어긋나지 않는지**를 본다 — 활자를 내고 되돌릴 수 없는 자리다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { ItemView, SlotView } from '../storage'

import { AffixList } from './AffixList'
import type { AffixLine } from './AffixList'
import { InventoryDetail } from './InventoryDetail'

const noop = (): undefined => undefined

/**
 * 그려진 줄 수를 센다.
 *
 * 클래스가 아니라 `<li>` 를 센다 — 이름은 바뀌어도 줄은 줄이다.
 *
 * @param markup 정적 마크업.
 * @returns `<li>` 개수.
 */
function countRows(markup: string): number {
  return markup.match(/<li[\s>]/g)?.length ?? 0
}

/**
 * 줄들을 마크업으로 굽는다.
 *
 * @param lines 그릴 줄들.
 * @param role 역할 이름. 안 주면 안 붙는다.
 * @returns 정적 마크업.
 */
function renderLines(lines: readonly AffixLine[], role?: string): string {
  return renderToStaticMarkup(
    <AffixList lines={lines} {...(role === undefined ? {} : { role })} />,
  )
}

describe('옵션 줄 목록 — 무엇이 그려지는가', () => {
  it('★ 값이 중복돼도 줄이 다 그려진다 — 키에 자리가 든다', () => {
    // 서버가 같은 접사를 둘 실어 보낸다. 값만으로 키를 만들면 하나가 사라진다.
    const markup = renderLines([{ text: '예리함 · 공격력 +3' }, { text: '예리함 · 공격력 +3' }])
    expect(countRows(markup)).toBe(2)
  })

  it('★ 비면 아무것도 안 그린다 — 「없다」는 여기서 적을 말이 아니다', () => {
    // 목록이 실제로 서는 것은 위 검사가 보증한다. 여기서는 빈 상자도 문구도 없어야 한다.
    const markup = renderLines([])
    expect(markup).toBe('')
  })

  it('★ 거르기도 「더 보기」도 안 선다 — 보이는 줄이 줄면 첨자가 어긋난다', () => {
    const many: readonly AffixLine[] = Array.from({ length: 12 }, (_unused, index) => ({
      text: `옵션 ${String(index)}`,
    }))
    const markup = renderLines(many)
    expect(countRows(markup)).toBe(12)
    expect(markup).not.toContain('더 보기')
    expect(markup).not.toContain('거르기')
  })

  it('줄 오른쪽 것은 그 줄에만 붙는다', () => {
    const markup = renderLines([
      { text: '사거리 3' },
      { text: '단단함 · 방어력 +2', trail: <button type="button">다시 찍기</button> },
    ])
    expect(countRows(markup)).toBe(2)
    // 단추가 둘째 줄 안에 있다 — 첫 줄(사거리)과 둘째 줄 값 뒤에 온다.
    expect(markup.indexOf('사거리 3')).toBeLessThan(markup.indexOf('다시 찍기'))
    expect(markup.indexOf('방어력 +2')).toBeLessThan(markup.indexOf('다시 찍기'))
  })

  it('역할 이름은 줄 때만 붙는다 — 소모품은 끼면 / 쓰면 / 자동을 갈라야 한다', () => {
    const named = renderLines([{ text: '든든함 · 최대체력 +25' }], '끼면')
    const plain = renderLines([{ text: '든든함 · 최대체력 +25' }])
    expect(named).toContain('끼면')
    expect(plain).not.toContain('끼면')
    expect(plain).toContain('최대체력 +25')
  })
})

/**
 * 접사가 붙은 아이템 하나.
 *
 * @param over 바꿀 것.
 * @returns 아이템.
 */
function buildItem(over: Partial<ItemView> = {}): ItemView {
  return {
    itemId: 1,
    catalogId: 'sword_short',
    labelKo: '단검',
    kind: 'EQUIPMENT',
    slot: 'WEAPON_MAIN',
    hands: 'ONE',
    equippedSlot: null,
    isBroken: false,
    isBound: false,
    isRecovered: false,
    sealedSlots: 0,
    unsealCost: 0,
    recastFrom: 0,
    grade: 'COMMON',
    attackRange: 3,
    affixes: [],
    requirements: [],
    canEquip: true,
    grantsSkill: '',
    ...over,
  }
}

/**
 * 고른 칸 하나.
 *
 * @param item 든 아이템.
 * @returns 칸.
 */
function buildSlot(item: ItemView): SlotView {
  return {
    slotIndex: 0,
    item,
    slot: null,
    isSealed: false,
    stackCatalogId: null,
    stackCount: 0,
    stackLabelKo: '',
    stackGrade: '',
    stackUseTag: '',
  }
}

/**
 * 상세 안에서 **옵션 줄만** 센다.
 *
 * `<li>` 를 통째로 세면 견줌 표의 줄까지 딸려 온다 — 그러면 이 검사가 옵션 줄이 아니라
 * 견줌이 바뀔 때 빨개진다.
 *
 * @param markup 상세 마크업.
 * @returns 옵션 줄 수.
 */
function countAffixRows(markup: string): number {
  return (markup.match(/invd__affix"/g) ?? []).length
}

/**
 * 가방 상세를 굽는다.
 *
 * @param item 고른 아이템.
 * @returns 정적 마크업.
 */
function renderDetail(item: ItemView): string {
  return renderToStaticMarkup(
    <InventoryDetail
      choice={{ kind: 'bag', slot: '', entry: buildSlot(item) }}
      link="online"
      worn={undefined}
      repairCost={120}
      letters={99}
      recastCost={1}
      feePercent={5}
      onEquip={noop}
      onUnequip={noop}
      onDiscard={noop}
      onRepair={noop}
      onUnseal={noop}
      onRecast={noop}
      onList={noop}
    />,
  )
}

describe('옵션 줄 목록 — 다시 찍기가 걸린 첨자', () => {
  /** 봉인에서 나온 것은 둘째 줄부터다(`recastFrom`). 드롭이 달고 나온 첫 줄에는 안 붙는다. */
  const ARMED = buildItem({
    recastFrom: 1,
    affixes: [
      { stat: 'attack', flat: 3, percent: 0, labelKo: '예리함', statLabel: '공격력' },
      { stat: 'defense', flat: 2, percent: 0, labelKo: '단단함', statLabel: '방어력' },
      { stat: 'hp_max', flat: 8, percent: 0, labelKo: '튼튼함', statLabel: '최대체력' },
    ],
  })

  it('★ 단추 수가 봉인에서 나온 줄 수와 같다 — 사거리·드롭 접사에는 안 붙는다', () => {
    const html = renderDetail(ARMED)
    // 사거리 한 줄 + 접사 셋 = 네 줄. 단추는 그중 둘(첨자 1·2)에만 선다.
    expect(countAffixRows(html)).toBe(4)
    expect((html.match(/다시 찍기/g) ?? []).length).toBe(2)
  })

  it('★ 첫 단추는 첫 접사가 아니라 둘째 접사 줄에 선다 — 어긋나면 옆 줄이 갈린다', () => {
    const html = renderDetail(ARMED)
    const first = html.indexOf('다시 찍기')
    expect(first).toBeGreaterThan(html.indexOf('공격력 +3'))
    expect(first).toBeGreaterThan(html.indexOf('방어력 +2'))
    // 셋째 줄 값보다는 앞이다 — 둘째 줄 안에 있다는 뜻이다.
    expect(first).toBeLessThan(html.indexOf('최대체력 +8'))
  })

  it('사거리는 접사가 아니라 필드라 목록 맨 위에 서고 단추가 없다', () => {
    const html = renderDetail(buildItem({ attackRange: 3 }))
    expect(html).toContain('사거리 3')
    expect(html).not.toContain('다시 찍기')
    expect(countAffixRows(html)).toBe(1)
  })
})
