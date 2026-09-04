/**
 * 소모품 칸 검사 (설계/4_아이템 §5) — **가방과 같은 형식이다.**
 *
 * **가방과 다른 화면이되 같은 모양이다.** 가방은 「가진 것」이고 칸은 「들고 갈 것」이다.
 * 그 구분은 지키고, 그리는 모양은 가방의 도면 격자와 맞춘다 — 예전에는 여기만 카드
 * 목록이었고, 같은 질문(「어느 게 더 좋은가」)에 두 화면이 다른 모양으로 답했다.
 *
 * 여기서 지키는 것은 다섯이다.
 *
 * 1. **빈 칸도 그린다** — 안 그리면 「칸이 없다」와 「비었다」를 구분할 수 없다.
 * 2. **칸은 상태만, 조작은 상세에.** 칸 안에 버튼이 생기면 되돌아간 것이다.
 * 3. **견줌이 맞는 칸 전부와 붙는다** — 칸 수가 고정이 아니다(접사가 칸을 늘린다).
 * 4. **런 중에도 안 잠근다** — 잠그면 방 사이에 규칙 고치는 내내 칸을 못 건드린다.
 * 5. **다 써도 옵션은 남는다** — 사라지면 안 마시는 것이 이득이 되고, 그것은 물약의
 *    존재 이유와 정반대다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { ConsumableOptionView, ConsumableSlotView, ConsumableView } from '../storage'

import { compareToSlots, pickFromOption, pickFromSlot } from './compareConsumables'
import {
  buildConsumableSlotCells,
  buildConsumableStockCells,
  findFreeConsumableSlot,
  formatCharges,
  formatRefillLabel,
  formatSlotCode,
  formatSlotName,
} from './consumableCells'
import { ConsumableDetail } from './ConsumableDetail'
import { ConsumablePanel } from './ConsumablePanel'

const noop = () => undefined

function buildSlot(over: Partial<ConsumableSlotView> = {}): ConsumableSlotView {
  return {
    useTag: 'POTION',
    slotIndex: 0,
    catalogId: '',
    labelKo: '',
    grade: '',
    charges: 0,
    chargeMax: 0,
    refillCost: 0,
    affixes: [],
    affixRows: [],
    ...over,
  }
}

function buildOption(over: Partial<ConsumableOptionView> = {}): ConsumableOptionView {
  return {
    catalogId: 'potion_elixir',
    labelKo: '영약',
    grade: 'RELIC',
    useTag: 'POTION',
    charges: 7,
    stock: 2,
    sellPrice: 630,
    affixes: ['든든함 · 최대체력 +25'],
    affixRows: [{ stat: 'hp_max', flat: 25, percent: 0, labelKo: '든든함', statLabel: '최대체력' }],
    ...over,
  }
}

/** 0번 칸에 회복 물약이 차 있고, 1번 물약 칸과 주문서 칸이 비어 있다. */
function buildView(over: Partial<ConsumableView> = {}): ConsumableView {
  return {
    slots: [
      buildSlot({
        catalogId: 'potion_heal',
        labelKo: '회복 물약',
        grade: 'COMMON',
        charges: 1,
        chargeMax: 2,
        refillCost: 20,
        affixes: ['든든함 · 최대체력 +4'],
        affixRows: [
          { stat: 'hp_max', flat: 4, percent: 0, labelKo: '든든함', statLabel: '최대체력' },
        ],
      }),
      buildSlot({ slotIndex: 1 }),
      buildSlot({ useTag: 'SCROLL' }),
    ],
    options: [buildOption()],
    balance: 1240,
    freeCharges: 1,
    isRunOpen: false,
    ...over,
  }
}

function renderPanel(view: ConsumableView | undefined, detail = '', link = 'online'): string {
  return renderToStaticMarkup(
    <ConsumablePanel
      view={view}
      link={link as 'online'}
      detail={detail}
      onLoadStock={noop}
      onClear={noop}
      onRefill={noop}
      onSell={noop}
    />,
  )
}

describe('소모품 칸의 말', () => {
  it('★ 칸 이름을 1부터 센다 — 0번 칸이라고 적으면 사람이 세는 방식과 어긋난다', () => {
    expect(formatSlotName(buildSlot({ slotIndex: 1 }))).toBe('물약 2')
    expect(formatSlotName(buildSlot({ useTag: 'SCROLL' }))).toBe('주문서 1')
  })

  it('★ 칸 코드에 번호가 붙는다 — 칸 수가 늘면 PO 하나로는 두 칸을 못 가른다', () => {
    expect(formatSlotCode('POTION', 0)).toBe('PO1')
    expect(formatSlotCode('POTION', 2)).toBe('PO3')
    expect(formatSlotCode('SCROLL', 0)).toBe('SC1')
  })

  it('★ 남은 것과 한도를 함께 적는다 — 남은 수만 적으면 채울 게 있는지 모른다 (P1)', () => {
    expect(formatCharges(buildSlot({ catalogId: 'x', charges: 1, chargeMax: 4 }), 1)).toBe('1 / 4')
  })

  it('★ 빈 칸이 공짜로 찬다는 것을 적는다 — 안 적으면 새 계정이 빈손으로 보인다', () => {
    expect(formatCharges(buildSlot(), 1)).toContain('공짜')
  })

  it('★ 보충 값을 버튼에 적는다 — 누르고 나서 얼마 나갔는지 아는 것은 늦다', () => {
    expect(formatRefillLabel(buildSlot({ catalogId: 'x', refillCost: 60 }))).toBe('보충 60')
  })

  it('★ 가득 찬 칸에는 보충을 안 띄운다 — 누를 수 있으면 눌러 보게 된다', () => {
    expect(formatRefillLabel(buildSlot({ catalogId: 'x', refillCost: 0 }))).toBe('')
    expect(formatRefillLabel(buildSlot({ refillCost: 20 }))).toBe('')
  })
})

describe('소모품 셀 모델', () => {
  const slotCells = buildConsumableSlotCells(buildView())
  const stockCells = buildConsumableStockCells(buildView())

  it('★ 빈 칸도 칸으로 그린다 — 안 그리면 「칸이 없다」와 「비었다」가 같아 보인다', () => {
    expect(slotCells).toHaveLength(3)
    expect(slotCells[1]?.label).toBe('')
    expect(slotCells[2]?.code).toBe('SC1')
  })

  it('★ 칸이 충전을 남은/전체로 적는다 (P1)', () => {
    expect(slotCells[0]?.countText).toBe('1/2')
    // 빈 칸은 적을 충전이 없다 — 0/0 은 「다 썼다」로 읽힌다.
    expect(slotCells[1]?.countText).toBe('')
  })

  it('★ 칸이 대표 접사를 적는다 — 없으면 어느 게 나은지 칸에서 짐작조차 못 한다', () => {
    expect(slotCells[0]?.fact).toBe('체+4')
    expect(stockCells[0]?.fact).toBe('체+25')
  })

  it('★ 다 쓴 칸에 글리프가 붙는다 — 못 마신다는 뜻이지 못 쓰는 물건이라는 뜻이 아니다', () => {
    const spent = buildConsumableSlotCells(
      buildView({ slots: [buildSlot({ catalogId: 'x', labelKo: '회복 물약', charges: 0, chargeMax: 2 })] }),
    )
    expect(spent[0]?.marks).toContain('◈')
  })

  it('재고는 개수를 적는다 — 몇 개 남았는지가 「팔까 끼울까」의 입력이다', () => {
    expect(stockCells[0]?.countText).toBe('x2')
  })

  it('재고에는 빈 칸을 덧대지 않는다 — 없는 자리를 그리면 정해진 칸 수로 읽힌다', () => {
    expect(stockCells).toHaveLength(1)
  })
})

describe('★ 견줌이 맞는 칸 전부와 붙는다', () => {
  // **칸 수가 고정이 아니다.** 접사(`potion_slots`)가 물약 칸을 늘리므로, 하나만 골라
  // 견주면 사람이 갈아 끼우려던 칸이 견줌에서 빠진다.
  const view = buildView({
    slots: [
      buildSlot({
        catalogId: 'potion_heal',
        labelKo: '회복 물약',
        grade: 'COMMON',
        charges: 1,
        chargeMax: 2,
        affixRows: [
          { stat: 'hp_max', flat: 4, percent: 0, labelKo: '든든함', statLabel: '최대체력' },
        ],
      }),
      buildSlot({ slotIndex: 1 }),
      buildSlot({ slotIndex: 2, useTag: 'SCROLL' }),
    ],
  })

  it('물약 칸 둘 다와 견준다 — 하나만 견주면 나머지 칸은 화면에서 사라진다', () => {
    const compares = compareToSlots(pickFromOption(buildOption()), view.slots)
    expect(compares).toHaveLength(2)
    expect(compares[0]?.slot.slotIndex).toBe(0)
    expect(compares[1]?.slot.slotIndex).toBe(1)
  })

  it('★ 쓰임새가 다른 칸은 안 견준다 — 물약을 주문서 칸에 못 끼운다', () => {
    const compares = compareToSlots(pickFromOption(buildOption()), view.slots)
    expect(compares.every((one) => one.slot.useTag === 'POTION')).toBe(true)
  })

  it('★ 스탯별 차이를 낸다 — 점수 하나로 접으면 기준을 코드가 정하게 된다', () => {
    const rows = compareToSlots(pickFromOption(buildOption()), view.slots)[0]?.rows ?? []
    const hp = rows.find((row) => row.stat === 'hp_max')
    expect(hp?.flatDelta).toBe(21)
    expect(hp?.label).toBe('최대체력')
  })

  it('★ 충전 용량도 견준다 — 「몇 번 마실 수 있나」는 붙는 옵션만큼 중요하다', () => {
    const rows = compareToSlots(pickFromOption(buildOption()), view.slots)[0]?.rows ?? []
    const charge = rows.find((row) => row.stat === 'charge_max')
    // 영약 7충전 vs 회복 물약 2충전.
    expect(charge?.flatDelta).toBe(5)
  })

  it('빈 칸은 빈 칸이라고 표시한다 — 차이가 전부 이득인 것이 맞다', () => {
    const compares = compareToSlots(pickFromOption(buildOption()), view.slots)
    expect(compares[1]?.isEmpty).toBe(true)
  })

  it('★ 자기 자신과는 안 견준다 — 차이가 없는 것이 당연하고, 그 줄이 진짜 견줌을 민다', () => {
    const slot = view.slots[0]
    const compares = compareToSlots(pickFromSlot(slot!), view.slots)
    expect(compares.every((one) => one.slot.slotIndex !== 0)).toBe(true)
  })
})

describe('소모품 격자', () => {
  const html = renderPanel(buildView())

  it('★ 가방과 같은 격자를 쓴다 — 같은 질문에 두 모양으로 답하지 않는다', () => {
    expect(html).toContain('invg')
    expect(html).toContain('invg__cell')
  })

  it('★ 「들고 갈 것」과 「가진 것」을 가른다 — 이 구분이 이 화면의 존재 이유다', () => {
    expect(html).toContain('들고 갈 것')
    expect(html).toContain('가진 것')
  })

  it('★ 조작이 칸 안에 없다 — 칸은 상태만 그리고 조작은 상세 한 곳에 모인다', () => {
    const grid = html.slice(html.indexOf('invg'), html.lastIndexOf('invg__cell'))
    expect(grid).not.toContain('팔기')
    expect(grid).not.toContain('끼우기')
    expect(grid).not.toContain('보충')
  })

  it('★ 빈 칸도 그린다 — 안 그리면 「칸이 없다」와 「비었다」를 구분할 수 없다', () => {
    // 물약 2칸 + 주문서 1칸이 전부 칸으로 선다.
    expect(html).toContain('PO2')
    expect(html).toContain('SC1')
    expect(html).toContain('칸 1 / 3')
  })

  it('★ 런 중에도 잠그지 않는다 — 잠그면 방 사이에 규칙 고치는 내내 칸을 못 건드린다', () => {
    const running = renderPanel(buildView({ isRunOpen: true }))
    // 지금 채운 것이 이번 런에 안 실린다는 것은 **말한다.** 막지 않을 뿐이다.
    expect(running).toContain('다음 런부터 실린다')
    expect(running).not.toContain('disabled')
  })

  it('★ 실패 사유를 그대로 띄운다 — 삼키면 「서버는 아는데 화면이 말하지 않는다」가 된다', () => {
    expect(renderPanel(buildView(), '240 이 필요하다')).toContain('240 이 필요하다')
  })

  it('★ 서버에 못 닿으면 그 사실을 적는다 — 빈 패널은 「칸이 없다」로 읽힌다', () => {
    const html2 = renderPanel(undefined, '', 'offline')
    expect(html2).toContain('서버에 닿지 못했다')
    expect(html2).toContain('소모품 칸은 서버가 안다')
  })

  it('재고가 없으면 그렇게 적는다 — 빈 격자는 「불러오는 중」과 구별되지 않는다', () => {
    expect(renderPanel(buildView({ options: [] }))).toContain('가방에 소모품이 없다')
  })
})

describe('소모품 상세 — 재고 칸', () => {
  const view = buildView()
  const cell = buildConsumableStockCells(view)[0]!
  const html = renderToStaticMarkup(
    <ConsumableDetail
      cell={cell}
      view={view}
      link="online"
      onClear={noop}
      onRefill={noop}
      onSell={noop}
      onLoadStock={noop}
    />,
  )

  it('★ 등급을 색·글리프·이름 셋으로 적는다 — 색만으로는 못 가르는 사람이 있다', () => {
    expect(html).toContain('inv__name--relic')
    expect(html).toContain('◆')
    expect(html).toContain('유물')
  })

  it('★ 끼우면 무엇이 붙는지 적는다 — 안 적으면 부가 옵션이 있다는 것을 알 길이 없다', () => {
    expect(html).toContain('든든함 · 최대체력 +25')
  })

  it('★ 남는 것을 파는 값을 적는다 — 드롭이 곧 보충 비용이라는 것이 여기서 보인다', () => {
    expect(html).toContain('팔기 630')
    expect(html).toContain('x2 · 7충전')
  })

  it('★ 등급이 충전 용량을 정한다고 적는다 — 봉인 칸이 없는 것은 빠진 것이 아니다', () => {
    expect(html).toContain('등급은 충전 용량을 정한다')
  })

  it('★ 조작이 여기 있다 — 끼우기·팔기의 집은 하나다', () => {
    expect(html).toContain('끼우기')
  })

  it('★ 맞는 칸 전부와 견준다', () => {
    expect(html).toContain('물약 1 · 회복 물약 와 견줌')
    expect(html).toContain('물약 2 · 빈 칸 와 견줌')
    // 주문서 칸과는 안 견준다.
    expect(html).not.toContain('주문서 1 ·')
  })
})

describe('소모품 상세 — 끼운 칸', () => {
  it('★ 다 써도 옵션은 남는다 — 사라지면 안 마시는 것이 이득이 된다', () => {
    // 처음에는 파손된 장비에 빗대 「다 쓰면 사라진다」로 뒀는데 그 비유가 틀렸다 —
    // 다 쓴 물약 칸은 **여전히 그 물약을 차고 있는 상태**다 (`list_loaded_consumables`).
    // 못 하는 것은 마시는 것 하나이고, 화면은 그 하나만 말해야 한다.
    const spent = buildSlot({
      catalogId: 'potion_heal',
      labelKo: '회복 물약',
      grade: 'COMMON',
      charges: 0,
      chargeMax: 2,
      refillCost: 40,
      affixes: ['든든함 · 최대체력 +4'],
      affixRows: [
        { stat: 'hp_max', flat: 4, percent: 0, labelKo: '든든함', statLabel: '최대체력' },
      ],
    })
    const view = buildView({ slots: [spent], options: [] })
    const html = renderToStaticMarkup(
      <ConsumableDetail
        cell={buildConsumableSlotCells(view)[0]!}
        view={view}
        link="online"
        onClear={noop}
        onRefill={noop}
        onSell={noop}
        onLoadStock={noop}
      />,
    )
    expect(html).toContain('다 씀')
    // 옵션은 그대로 선다 — 보충은 능력치를 되찾으려고가 아니라 다시 마시려고 하는 것이다.
    expect(html).toContain('든든함 · 최대체력 +4')
    expect(html).toContain('옵션은 그대로')
    expect(html).toContain('보충 40')
  })

  it('★ 빼기가 무엇을 버리는지 누르기 전에 말한다', () => {
    const view = buildView()
    const html = renderToStaticMarkup(
      <ConsumableDetail
        cell={buildConsumableSlotCells(view)[0]!}
        view={view}
        link="online"
        onClear={noop}
        onRefill={noop}
        onSell={noop}
        onLoadStock={noop}
      />,
    )
    // 1/2 이라 가득 차지 않았다 — 남은 충전이 버려진다고 적어야 한다.
    expect(html).toContain('남은 1충전 버려짐')
  })

  it('빈 칸에는 조작도 견줌도 없다 — 견줄 상대도 뺄 것도 없다', () => {
    const view = buildView()
    const html = renderToStaticMarkup(
      <ConsumableDetail
        cell={buildConsumableSlotCells(view)[1]!}
        view={view}
        link="online"
        onClear={noop}
        onRefill={noop}
        onSell={noop}
        onLoadStock={noop}
      />,
    )
    expect(html).toContain('공짜')
    expect(html).not.toContain('빼기')
    expect(html).not.toContain('와 견줌')
  })
})

describe('가방에서 칸으로', () => {
  it('★ 빈 칸을 고른다 — 찬 칸을 덮으면 남의 충전이 되돌릴 수 없이 날아간다', () => {
    const picked = findFreeConsumableSlot(buildView(), 'potion_elixir')
    // 0번 칸은 이미 회복 물약이 차 있다. 1번이 빈 칸이다.
    expect(picked?.slotIndex).toBe(1)
  })

  it('★ 쓰임새가 맞는 칸만 고른다 — 물약이 주문서 칸에 들어가면 규칙표가 엉뚱한 것을 쓴다', () => {
    const scrollOnly = buildView({ slots: [buildSlot({ useTag: 'SCROLL' })] })
    expect(findFreeConsumableSlot(scrollOnly, 'potion_elixir')).toBeUndefined()
  })
})
