/**
 * 소모품 칸 검사 (설계/4_아이템 §5).
 *
 * **가방과 다른 화면이다.** 가방은 「가진 것」이고 칸은 「들고 갈 것」이다. 예전에는 가방을
 * 통째로 세서 들고 갔고, 그래서 「몇 개를 들고 갈까」가 선택이 아니었다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { ConsumableSlotView, ConsumableView } from '../storage'

import {
  ConsumablePanel,
  formatCharges,
  formatRefillLabel,
  findFreeConsumableSlot,
  formatSlotName,
  listSlotOptions,
} from './ConsumablePanel'

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
    ...over,
  }
}

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
      }),
      buildSlot({ slotIndex: 1 }),
      buildSlot({ useTag: 'SCROLL' }),
    ],
    options: [
      {
        catalogId: 'potion_elixir',
        labelKo: '영약',
        grade: 'RELIC',
        useTag: 'POTION',
        charges: 7,
        stock: 2,
        sellPrice: 630,
        affixes: ['든든함 · 최대체력 +25'],
      },
    ],
    balance: 1240,
    freeCharges: 1,
    isRunOpen: false,
    ...over,
  }
}

describe('소모품 칸', () => {
  it('★ 칸 이름을 1부터 센다 — 0번 칸이라고 적으면 사람이 세는 방식과 어긋난다', () => {
    expect(formatSlotName(buildSlot({ slotIndex: 1 }))).toBe('물약 2')
    expect(formatSlotName(buildSlot({ useTag: 'SCROLL' }))).toBe('주문서 1')
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

  it('★ 칸에 안 맞는 후보는 안 보인다 — 보이면 눌러서 409 를 받는다', () => {
    const options = buildView().options
    expect(listSlotOptions(options, 'POTION')).toHaveLength(1)
    expect(listSlotOptions(options, 'SCROLL')).toHaveLength(0)
  })

  it('★ 빈 칸도 그린다 — 안 그리면 「칸이 없다」와 「비었다」를 구분할 수 없다', () => {
    const html = renderToStaticMarkup(
      <ConsumablePanel
        view={buildView()}
        isOnline
        detail=""
        onLoadStock={() => undefined}
        onClear={() => undefined}
        onRefill={() => undefined}
        onSell={() => undefined}
      />,
    )
    expect(html).toContain('물약 2')
    expect(html).toContain('주문서 1')
    expect(html).toContain('공짜')
  })

  it('★ 등급을 색·글리프·이름 셋으로 적는다 — 색만으로는 못 가르는 사람이 있다', () => {
    const html = renderToStaticMarkup(
      <ConsumablePanel
        view={buildView()}
        isOnline
        detail=""
        onLoadStock={() => undefined}
        onClear={() => undefined}
        onRefill={() => undefined}
        onSell={() => undefined}
      />,
    )
    expect(html).toContain('inv__name--relic')
    expect(html).toContain('◆')
    expect(html).toContain('유물')
  })

  it('★ 런 중에도 잠그지 않는다 — 잠그면 방 사이에 규칙 고치는 내내 칸을 못 건드린다', () => {
    const html = renderToStaticMarkup(
      <ConsumablePanel
        view={buildView({ isRunOpen: true })}
        isOnline
        detail=""
        onLoadStock={() => undefined}
        onClear={() => undefined}
        onRefill={() => undefined}
        onSell={() => undefined}
      />,
    )
    // 지금 채운 것이 이번 런에 안 실린다는 것은 **말한다.** 막지 않을 뿐이다.
    expect(html).toContain('다음 런부터 실린다')
    expect(html).not.toContain('disabled')
  })

  it('★ 실패 사유를 그대로 띄운다 — 삼키면 「서버는 아는데 화면이 말하지 않는다」가 된다', () => {
    const html = renderToStaticMarkup(
      <ConsumablePanel
        view={buildView()}
        isOnline
        detail="240 이 필요하다"
        onLoadStock={() => undefined}
        onClear={() => undefined}
        onRefill={() => undefined}
        onSell={() => undefined}
      />,
    )
    expect(html).toContain('240 이 필요하다')
  })

  it('★ 서버에 못 닿으면 그 사실을 적는다 — 빈 패널은 「칸이 없다」로 읽힌다', () => {
    const html = renderToStaticMarkup(
      <ConsumablePanel
        view={undefined}
        isOnline={false}
        detail=""
        onLoadStock={() => undefined}
        onClear={() => undefined}
        onRefill={() => undefined}
        onSell={() => undefined}
      />,
    )
    expect(html).toContain('서버에 닿지 못했다')
  })

  it('★ 끼우면 무엇이 붙는지 적는다 — 안 적으면 부가 옵션이 있다는 것을 알 길이 없다', () => {
    const html = renderToStaticMarkup(
      <ConsumablePanel
        view={buildView()}
        isOnline
        detail=""
        onLoadStock={() => undefined}
        onClear={() => undefined}
        onRefill={() => undefined}
        onSell={() => undefined}
      />,
    )
    expect(html).toContain('든든함 · 최대체력 +4')
    expect(html).toContain('든든함 · 최대체력 +25')
  })

  it('★ 다 쓴 칸은 옵션도 안 적는다 — 효과는 사라졌는데 화면이 남기면 거짓말이 된다', () => {
    const spent = buildSlot({
      catalogId: 'potion_heal',
      labelKo: '회복 물약',
      grade: 'COMMON',
      charges: 0,
      chargeMax: 2,
      refillCost: 40,
      affixes: [],
    })
    const html = renderToStaticMarkup(
      <ConsumablePanel
        view={buildView({ slots: [spent], options: [] })}
        isOnline
        detail=""
        onLoadStock={() => undefined}
        onClear={() => undefined}
        onRefill={() => undefined}
        onSell={() => undefined}
      />,
    )
    expect(html).toContain('0 / 2')
    expect(html).not.toContain('든든함')
  })

  it('★ 남는 것을 파는 값을 적는다 — 드롭이 곧 보충 비용이라는 것이 여기서 보인다', () => {
    const html = renderToStaticMarkup(
      <ConsumablePanel
        view={buildView()}
        isOnline
        detail=""
        onLoadStock={() => undefined}
        onClear={() => undefined}
        onRefill={() => undefined}
        onSell={() => undefined}
      />,
    )
    expect(html).toContain('팔기 630')
    expect(html).toContain('가방 2개')
  })
})

describe('가방에서 칸으로', () => {
  it('★ 빈 칸을 고른다 — 찬 칸을 덮으면 남의 충전이 되돌릴 수 없이 날아간다', () => {
    const picked = findFreeConsumableSlot(buildView(), 'potion_elixir')
    // 0번 칸은 이미 회복 물약이 차 있다. 1번이 빈 칸이다.
    expect(picked?.slotIndex).toBe(1)
  })

  it('★ 쓰임새가 맞는 칸만 고른다 — 물약이 주문서 칸에 들어가면 규칙표가 엉뚱한 것을 쓴다', () => {
    const scrollOnly = buildView({
      slots: [buildSlot({ useTag: 'SCROLL' })],
    })
    expect(findFreeConsumableSlot(scrollOnly, 'potion_elixir')).toBeUndefined()
  })

  it('★ 빈 칸이 없으면 안 고른다 — 조용히 덮으면 「왜 물약이 바뀌었지」가 된다', () => {
    const full = buildView({
      slots: [
        buildSlot({ catalogId: 'potion_heal', charges: 2, chargeMax: 2 }),
        buildSlot({ slotIndex: 1, catalogId: 'potion_heal', charges: 2, chargeMax: 2 }),
      ],
    })
    expect(findFreeConsumableSlot(full, 'potion_elixir')).toBeUndefined()
  })

  it('★ 칸을 못 읽었으면 안 고른다 — 서버에 못 닿았는데 끼운 척하면 안 된다', () => {
    expect(findFreeConsumableSlot(undefined, 'potion_elixir')).toBeUndefined()
  })
})
