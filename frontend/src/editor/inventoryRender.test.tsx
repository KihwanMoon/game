/**
 * 인벤토리 도면 격자 검사.
 *
 * **행 목록이 아니라 칸 도식이다.** 예전에는 아이템마다 한 행에 모든 조작이 펴져 있어
 * 좁은 화면에서 행 하나가 서너 줄로 꺾였다 — 칸은 상태만 그리고, 조작은 고른 칸의
 * 상세 한 곳에 모은다.
 *
 * 여기서 지키는 것은 다섯이다.
 *
 * 1. **장비는 늘 여섯 칸, 가방은 늘 스무 칸이다.** 빈 칸이 보여야 남은 자리를 안다.
 * 2. **칸은 등급을 색·글리프 두 채널로 적고, 상세가 이름까지 세 채널을 채운다.**
 * 3. **조작은 상세에만 있다.** 격자 칸 안에 버튼이 생기면 되돌아간 것이다.
 * 4. **소모품 칸에는 조작이 없다** — 끼우기·팔기의 집은 소모품 칸 패널이다 (두 집 금지).
 * 5. **파손·봉인·귀속이 칸에서도 상세에서도 보인다.**
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { InventoryView, ItemView, SlotView } from '../storage'

import { InventoryDetail } from './InventoryDetail'
import {
  BAG_CELL_COUNT,
  buildBagCells,
  buildEquipCells,
  clipCellLabel,
} from './inventoryCells'
import { InventoryGrid } from './InventoryGrid'
import { InventoryPanel } from './InventoryPanel'

const noop = (): undefined => undefined

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
    grade: 'COMMON',
    attackRange: 1,
    affixes: [],
    requirements: [],
    canEquip: true,
    ...over,
  }
}

function buildSlot(over: Partial<SlotView> = {}): SlotView {
  return {
    slotIndex: 0,
    slot: null,
    isSealed: false,
    stackCatalogId: null,
    stackCount: 0,
    stackLabelKo: '',
    stackGrade: '',
    stackUseTag: '',
    item: null,
    ...over,
  }
}

const INVENTORY: InventoryView = {
  slots: [
    buildSlot({ slotIndex: 0, item: buildItem({ grade: 'RELIC', labelKo: '유물 단검' }) }),
    buildSlot({
      slotIndex: 3,
      stackCatalogId: 'potion_greater',
      stackCount: 2,
      stackLabelKo: '큰 회복 물약',
      stackGrade: 'FINE',
      stackUseTag: 'POTION',
    }),
  ],
  equipment: [
    buildSlot({ slot: 'BODY', item: buildItem({ labelKo: '판금 갑옷', grade: 'FINE', slot: 'BODY' }) }),
    buildSlot({ slot: 'WEAPON_OFF', isSealed: true }),
  ],
  balance: 500,
  repairCost: 120,
}

describe('셀 모델', () => {
  it('★ 장비는 늘 여섯 칸이다 — 빈 슬롯도 칸으로 그려야 어디가 비었는지 보인다', () => {
    const cells = buildEquipCells(INVENTORY)
    expect(cells).toHaveLength(6)
    expect(cells.map((cell) => cell.code)).toEqual(['WM', 'WO', 'HD', 'BD', 'FT', 'HN'])
  })

  it('★ 가방은 늘 스무 칸이다 — 차 있는 칸만 그리면 남은 자리를 셀 수 없다', () => {
    const cells = buildBagCells(INVENTORY)
    expect(cells).toHaveLength(BAG_CELL_COUNT)
    expect(cells.filter((cell) => cell.entry !== undefined)).toHaveLength(2)
  })

  it('★ 양손 점유가 칸에 표시된다', () => {
    const cells = buildEquipCells(INVENTORY)
    expect(cells.find((cell) => cell.code === 'WO')?.isSealedSlot).toBe(true)
  })

  it('★ 소모품 칸은 개수를 적는다 — 1개인지 9개인지 모르고 규칙표를 짜면 안 된다 (#54)', () => {
    const stack = buildBagCells(INVENTORY).find((cell) => cell.countText !== '')
    expect(stack?.countText).toBe('x2')
    expect(stack?.label).toBe('큰회')
    expect(stack?.grade).toBe('FINE')
  })

  it('★ 파손·봉인·귀속이 칸 글리프로 남는다', () => {
    const marked = buildBagCells({
      ...INVENTORY,
      slots: [
        buildSlot({
          slotIndex: 0,
          item: buildItem({ isBroken: true, sealedSlots: 2, isBound: true }),
        }),
      ],
    })[0]
    expect(marked?.marks).toEqual(['◈', '◇2', '▨'])
  })

  it('★ 장비 칸은 번호가 아니라 부위 코드를 적는다 — 번호는 아무것도 말해 주지 않는다', () => {
    const cells = buildBagCells(INVENTORY)
    // 0번 칸의 유물 단검은 주무기다 — 칸 구석에 WM 이 선다.
    expect(cells[0]?.code).toBe('WM')
    // 소모품은 부위가 없다.
    expect(cells[3]?.code).toBe('CS')
    // 빈 칸은 번호 그대로다 — 부위가 없는데 코드를 지어내면 거짓말이다.
    expect(cells[1]?.code).toBe('2')
  })

  it('칸 글자는 공백을 빼고 두 자다 — 도면 말의 두 글자 표기와 같은 규칙이다', () => {
    expect(clipCellLabel('큰 회복 물약')).toBe('큰회')
    expect(clipCellLabel('단검')).toBe('단검')
  })
})

describe('격자 렌더', () => {
  const html = renderToStaticMarkup(
    <InventoryPanel
      inventory={INVENTORY}
      link="online"
      detail=""
      onEquip={noop}
      onUnequip={noop}
      onDiscard={noop}
      onRepair={noop}
      onList={noop}
      feePercent={5}
      onUnseal={noop}
    />,
  )

  it('★ 채운 수를 머리에 적는다 — 가방이 얼마나 남았는지 세지 않고 안다', () => {
    expect(html).toContain('가방 2 / 20')
  })

  it('★ 칸이 등급 색을 입는다', () => {
    expect(html).toContain('inv__name--relic')
    expect(html).toContain('inv__name--fine')
  })

  it('★ 격자 칸 안에 조작 버튼이 없다 — 조작은 고른 칸의 상세 한 곳에 산다', () => {
    // 격자 칸(invg__cell)은 그 자체가 버튼 하나다. 안에 또 버튼이 있으면 되돌아간 것.
    expect(html).not.toContain('착용')
    expect(html).not.toContain('버리기')
    expect(html).not.toContain('끼우기')
  })

  it('★ 고르기 전에는 안내가 뜬다', () => {
    expect(html).toContain('칸을 고르면')
  })

  it('★ 서버에 못 닿으면 그 사실을 적는다', () => {
    const offline = renderToStaticMarkup(
      <InventoryPanel
        inventory={undefined}
        link="offline"
        detail=""
        onEquip={noop}
        onUnequip={noop}
        onDiscard={noop}
        onRepair={noop}
        onList={noop}
        feePercent={5}
        onUnseal={noop}
      />,
    )
    expect(offline).toContain('서버에 닿지 못했다')
  })
})

function renderDetail(kind: 'equip' | 'bag', entry: SlotView, slot = 'BODY'): string {
  return renderToStaticMarkup(
    <InventoryDetail
      choice={{ kind, slot, entry }}
      link="online"
      repairCost={120}
      feePercent={5}
      onEquip={noop}
      onUnequip={noop}
      onDiscard={noop}
      onRepair={noop}
      onUnseal={noop}
      onList={noop}
    />,
  )
}

describe('상세와 도구줄', () => {
  it('★ 장비 칸 상세에는 벗기만 있고 버리기·경매가 없다 — 낀 채로 버리면 스탯이 유령이 된다', () => {
    const html = renderDetail('equip', buildSlot({ slot: 'BODY', item: buildItem({ slot: 'BODY' }) }))
    expect(html).toContain('벗기')
    expect(html).toContain('착용 중')
    expect(html).not.toContain('버리기')
    expect(html).not.toContain('호가')
  })

  it('★ 가방 칸 상세에는 착용·버리기·경매가 있다', () => {
    const html = renderDetail('bag', buildSlot({ item: buildItem() }))
    expect(html).toContain('착용')
    expect(html).toContain('버리기')
    expect(html).toContain('호가')
    expect(html).toContain('수수료 5%')
  })

  it('★ 파손이면 착용 대신 복구가 뜬다 — 파손은 효과가 없으므로 끼워 봐야 헛것이다', () => {
    const html = renderDetail('bag', buildSlot({ item: buildItem({ isBroken: true }) }))
    expect(html).toContain('복구 120')
    expect(html).not.toContain('착용')
  })

  it('★ 봉인이 있으면 해제 값이 뜬다 — 무엇이 나올지는 서버가 정한다', () => {
    const html = renderDetail(
      'bag',
      buildSlot({ item: buildItem({ sealedSlots: 1, unsealCost: 260 }) }),
    )
    expect(html).toContain('봉인 해제 260')
  })

  it('★ 귀속이면 경매 줄이 없다 — 걸어 보고 거절당하게 두지 않는다 (결정 #07)', () => {
    const html = renderDetail('bag', buildSlot({ item: buildItem({ isBound: true }) }))
    expect(html).toContain('귀속')
    expect(html).not.toContain('호가')
  })

  it('★ 옵션 하나에 한 줄이다 — 가운뎃점으로 이으면 어디까지가 한 옵션인지 눈으로 갈라야 한다', () => {
    const html = renderDetail(
      'bag',
      buildSlot({
        item: buildItem({
          affixes: [
            { stat: 'attack', flat: 3, percent: 0, labelKo: '예리함', statLabel: '공격력' },
            { stat: 'defense', flat: 2, percent: 0, labelKo: '단단함', statLabel: '방어력' },
          ],
        }),
      }),
    )
    const rows = html.match(/invd__affix"/g) ?? []
    // 사거리 1 + 접사 둘 = li 세 줄. 한 줄로 이으면 여기 하나만 남는다.
    expect(rows.length).toBe(3)
    expect(html).not.toContain('예리함 · 공격력 +3 · 단단함')
  })

  it('★ 가방 상세가 부위를 말한다 — 격자 코드 두 글자의 온전한 이름이다', () => {
    const html = renderDetail('bag', buildSlot({ item: buildItem({ slot: 'BODY' }) }))
    expect(html).toContain('부위 · 갑옷')
  })

  it('★ 요구조건에 실측값을 병기한다 (P1)', () => {
    const html = renderDetail(
      'bag',
      buildSlot({
        item: buildItem({
          requirements: [{ stat: 'attack', actual: 8, minimum: 12, isMet: false }],
        }),
      }),
    )
    expect(html).toContain('attack(8) &gt;= 요구(12)')
  })

  it('★ 소모품 칸 상세에는 조작이 없고 집을 가리킨다 — 두 집에 살면 어느 쪽이 진짜인지 모른다', () => {
    const html = renderDetail(
      'bag',
      buildSlot({
        stackCatalogId: 'potion_heal',
        stackCount: 3,
        stackLabelKo: '회복 물약',
        stackGrade: 'COMMON',
        stackUseTag: 'POTION',
      }),
    )
    expect(html).toContain('소모품 칸에서 한다')
    // 상급 물약에 봉인 해제가 없는 것은 설계다 — 화면이 말해야 「없는데?」가 안 나온다.
    expect(html).toContain('봉인 칸은 장비의 것')
    expect(html).not.toContain('버리기')
    expect(html).not.toContain('호가')
  })
})

describe('초점과 고름은 다른 채널이다', () => {
  // 예전에는 고른 칸이 `outline` 을 썼다. 초점 테두리와 **같은 속성**이라 고른 칸에
  // 초점이 오면 둘 중 하나가 통째로 사라진다 — 고름은 데이터의 상태이고 초점은 입력
  // 장치의 상태라 채널이 달라야 한다.
  it('★ 고른 칸을 보조 기술이 읽을 수 있다', () => {
    const markup = renderToStaticMarkup(
      <InventoryGrid inventory={INVENTORY} pickedKey="bag:0" onPick={() => undefined} />,
    )
    expect(markup).toContain('aria-pressed="true"')
    expect(markup).toContain('aria-pressed="false"')
  })
})
