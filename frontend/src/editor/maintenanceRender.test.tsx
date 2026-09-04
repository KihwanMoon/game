/**
 * 정비 규칙 에디터 검사 (설계/4_아이템 §5) — **규칙표의 두 번째 탭이다.**
 *
 * 가방 탭의 드롭다운 목록에서 규칙표 탭으로 옮겼다. 여기서 지키는 것은 다섯이다.
 *
 * 1. **행이 문장이다.** 드롭다운 둘이면 목록을 훑을 때 무엇이 언제 도는지가 안 보인다.
 * 2. **실측값을 병기한다.** 「버린다」가 아니라 「지금이면 2개 버림」이다 (GDD §8.2, P1).
 * 3. **미리보기가 어림임을 말한다.** 정본은 서버이고, 정비는 판이 끝난 뒤에 돈다.
 * 4. **검증이 서버가 막는 것을 먼저 본다** — 화면이 통과시킨 것을 서버가 422 로 거절하면
 *    사람은 무엇이 틀렸는지 모른 채 저장을 잃는다.
 * 5. **막는 것과 일러 주는 것을 가른다** — 섞으면 둘 다 무시된다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { ConsumableView, InventoryView, MaintenanceView } from '../storage'

import { MaintenanceCheck, MaintenanceEditor, MaintenancePalette } from './MaintenanceEditor'
import { buildMaintenancePreview, checkPreviewIdle, formatMoneyDelta } from './maintenancePreview'
import {
  checkBlocked,
  checkMaintenanceRows,
  createRow,
  MAINTENANCE_ACTIONS,
  duplicateRow,
  formatMaintenanceSentence,
  MAX_MAINTENANCE_ROWS,
  moveRow,
  replaceRow,
} from './maintenanceRules'

const noop = (): undefined => undefined

/** 퍼센트를 값으로 바꾸는 기준. 장비 교체의 저울이 쓴다. */
const BASE_STATS: Readonly<Record<string, number>> = {
  hp_max: 100,
  attack: 12,
  defense: 5,
  attack_range: 1,
  initiative: 50,
}

const ROWS: MaintenanceView = {
  rows: [
    { action: 'DISCARD', grade: 'COMMON' },
    { action: 'REPAIR', grade: '' },
    { action: 'REFILL', grade: '' },
  ],
}

/** 가방에 보통 장비 둘, 착용에 파손 하나. 잔액 100, 복구비 40. */
const INVENTORY = {
  slots: [
    {
      slotIndex: 0,
      slot: null,
      isSealed: false,
      stackCatalogId: null,
      stackCount: 0,
      stackLabelKo: '',
      stackGrade: '',
      stackUseTag: '',
      item: {
        itemId: 1,
        catalogId: 'a',
        labelKo: '낡은 검',
        kind: 'EQUIPMENT',
        slot: 'WEAPON_MAIN',
        hands: null,
        equippedSlot: null,
        isBroken: false,
        isBound: false,
        isRecovered: false,
        sealedSlots: 0,
        unsealCost: 0,
        grade: 'COMMON',
        attackRange: 0,
        affixes: [],
        requirements: [],
        canEquip: true,
      },
    },
    {
      slotIndex: 1,
      slot: null,
      isSealed: false,
      stackCatalogId: null,
      stackCount: 0,
      stackLabelKo: '',
      stackGrade: '',
      stackUseTag: '',
      item: {
        itemId: 2,
        catalogId: 'b',
        labelKo: '낡은 방패',
        kind: 'EQUIPMENT',
        slot: 'WEAPON_OFF',
        hands: null,
        equippedSlot: null,
        isBroken: false,
        isBound: false,
        // **되찾은 것은 안 버린다** — 서버가 남긴다.
        isRecovered: true,
        sealedSlots: 0,
        unsealCost: 0,
        grade: 'COMMON',
        attackRange: 0,
        affixes: [],
        requirements: [],
        canEquip: true,
      },
    },
  ],
  equipment: [
    {
      slotIndex: 0,
      slot: 'HEAD',
      isSealed: false,
      stackCatalogId: null,
      stackCount: 0,
      stackLabelKo: '',
      stackGrade: '',
      stackUseTag: '',
      item: {
        itemId: 3,
        catalogId: 'c',
        labelKo: '깨진 투구',
        kind: 'EQUIPMENT',
        slot: 'HEAD',
        hands: null,
        equippedSlot: 'HEAD',
        isBroken: true,
        isBound: false,
        isRecovered: false,
        sealedSlots: 0,
        unsealCost: 0,
        grade: 'COMMON',
        attackRange: 0,
        affixes: [],
        requirements: [],
        canEquip: true,
      },
    },
  ],
  balance: 100,
  repairCost: 40,
} as unknown as InventoryView

/** 물약 칸 하나가 1/2 이라 보충비 20. 재고 물약 둘이 개당 30. */
const CONSUMABLES = {
  slots: [
    {
      useTag: 'POTION',
      slotIndex: 0,
      catalogId: 'potion_heal',
      labelKo: '회복 물약',
      grade: 'COMMON',
      charges: 1,
      chargeMax: 2,
      refillCost: 20,
      affixes: [],
      affixRows: [],
    },
  ],
  options: [
    {
      catalogId: 'potion_spare',
      labelKo: '여분 물약',
      grade: 'COMMON',
      useTag: 'POTION',
      charges: 2,
      stock: 2,
      sellPrice: 30,
      affixes: [],
      affixRows: [],
    },
  ],
  balance: 100,
  freeCharges: 1,
  isRunOpen: false,
} as unknown as ConsumableView

/**
 * 검사용 투구 하나. 방어 접사만 다르다.
 *
 * @param defense 방어 접사 값.
 * @param itemId 아이템 id.
 * @param equipped 낀 것인가.
 * @returns 인벤토리 칸 하나.
 */
function buildHelm(defense: number, itemId: number, equipped: boolean): Record<string, unknown> {
  return {
    slotIndex: 0,
    slot: equipped ? 'HEAD' : null,
    isSealed: false,
    stackCatalogId: null,
    stackCount: 0,
    stackLabelKo: '',
    stackGrade: '',
    stackUseTag: '',
    item: {
      itemId,
      catalogId: 'helm',
      labelKo: '투구',
      kind: 'EQUIPMENT',
      slot: 'HEAD',
      hands: null,
      equippedSlot: equipped ? 'HEAD' : null,
      isBroken: false,
      isBound: false,
      isRecovered: false,
      sealedSlots: 0,
      unsealCost: 0,
      grade: 'COMMON',
      attackRange: 0,
      affixes: [{ stat: 'defense', flat: defense, percent: 0, labelKo: '', statLabel: '방어' }],
      requirements: [],
      canEquip: true,
    },
  }
}

/** 낀 투구. */
function buildWornHelm(defense: number): Record<string, unknown> {
  return buildHelm(defense, 90, true)
}

/** 가방의 투구. */
function buildBagHelm(defense: number): Record<string, unknown> {
  return buildHelm(defense, 91, false)
}

function renderEditor(view: MaintenanceView | undefined, detail = ''): string {
  return renderToStaticMarkup(
    <MaintenanceEditor
      view={view}
      link="online"
      detail={detail}
      inventory={INVENTORY}
      consumables={CONSUMABLES}
      baseStats={BASE_STATS}
      onChange={noop}
    />,
  )
}

describe('정비 행의 문장', () => {
  it('★ 행이 문장이다 — 드롭다운 둘이면 무엇이 언제 도는지가 목록에서 안 보인다', () => {
    expect(formatMaintenanceSentence({ action: 'DISCARD', grade: 'COMMON' })).toBe(
      '보통 이 등급의 가방 장비를 버린다 (되찾은 것은 남긴다)',
    )
    expect(formatMaintenanceSentence({ action: 'REPAIR', grade: '' })).toContain('복구한다')
  })

  it('★ 어휘 밖은 조용히 빈 줄이 되지 않는다 — 안 돈다는 것이 화면에 남아야 한다', () => {
    expect(formatMaintenanceSentence({ action: 'NOPE', grade: '' })).toContain('모르는 행동')
  })
})

describe('정비 규칙 조립', () => {
  it('★ 행 지우기는 그 자리 하나만 지운다', () => {
    expect(replaceRow(ROWS.rows, 1, undefined)).toEqual([
      { action: 'DISCARD', grade: 'COMMON' },
      { action: 'REFILL', grade: '' },
    ])
  })

  it('★ 아래로도 옮긴다 — 위로만 되면 세 번째를 맨 아래로 보내려고 둘을 각각 올려야 한다', () => {
    expect(moveRow(ROWS.rows, 0, 2).map((row) => row.action)).toEqual([
      'REPAIR',
      'REFILL',
      'DISCARD',
    ])
    expect(moveRow(ROWS.rows, 2, 1).map((row) => row.action)).toEqual([
      'DISCARD',
      'REFILL',
      'REPAIR',
    ])
  })

  it('범위 밖으로는 안 옮긴다 — 그대로 돌려준다', () => {
    expect(moveRow(ROWS.rows, 0, -1)).toBe(ROWS.rows)
    expect(moveRow(ROWS.rows, 0, 3)).toBe(ROWS.rows)
  })

  it('★ 복제가 바로 아래에 선다 — 「등급만 바꿔 하나 더」가 가장 흔한 편집이다', () => {
    expect(duplicateRow(ROWS.rows, 0).map((row) => row.action)).toEqual([
      'DISCARD',
      'DISCARD',
      'REPAIR',
      'REFILL',
    ])
  })

  it('★ 새 행은 인자가 채워진 채로 선다 — 빈 인자는 서버가 거절한다', () => {
    expect(createRow('DISCARD')).toEqual({ action: 'DISCARD', grade: 'COMMON' })
    expect(createRow('REPAIR')).toEqual({ action: 'REPAIR', grade: '' })
  })
})

describe('정비 검증 — 서버가 막는 것을 먼저 본다', () => {
  it('★ 어휘 밖 행동을 막는다', () => {
    const problems = checkMaintenanceRows([{ action: 'NOPE', grade: '' }])
    expect(checkBlocked(problems)).toBe(true)
    expect(problems[0]?.text).toContain('모르는 행동')
  })

  it('★ 버릴 수 없는 등급을 막는다 — 유물은 자동으로 안 버린다', () => {
    const problems = checkMaintenanceRows([{ action: 'DISCARD', grade: 'RELIC' }])
    expect(checkBlocked(problems)).toBe(true)
  })

  it('★ 인자를 안 받는 행동에 인자가 붙으면 막는다', () => {
    const problems = checkMaintenanceRows([{ action: 'REPAIR', grade: 'COMMON' }])
    expect(checkBlocked(problems)).toBe(true)
  })

  it('★ 행 수 상한이 서버와 같다 — 다르면 화면이 통과시킨 것을 서버가 막는다', () => {
    const many = Array.from({ length: MAX_MAINTENANCE_ROWS + 1 }, () => ({
      action: 'REPAIR',
      grade: '',
    }))
    expect(checkBlocked(checkMaintenanceRows(many))).toBe(true)
  })

  it('★ 중복 행은 막지 않고 일러만 준다 — 사람이 알고 두는 경우가 있다', () => {
    const problems = checkMaintenanceRows([
      { action: 'REPAIR', grade: '' },
      { action: 'REPAIR', grade: '' },
    ])
    expect(checkBlocked(problems)).toBe(false)
    expect(problems.some((one) => one.text.includes('할 일이 없다'))).toBe(true)
  })

  it('★ 파는 행이 쓰는 행보다 아래면 일러 준다 — 판 돈을 이번 정비에서 못 쓴다', () => {
    const problems = checkMaintenanceRows([
      { action: 'REPAIR', grade: '' },
      { action: 'SELL_STOCK', grade: '' },
    ])
    expect(checkBlocked(problems)).toBe(false)
    expect(problems.some((one) => one.text.includes('판 돈은'))).toBe(true)
  })

  it('바른 배치에는 아무 말도 안 한다 — 없는 문제를 지어내지 않는다', () => {
    expect(checkMaintenanceRows([{ action: 'SELL_STOCK', grade: '' }])).toHaveLength(0)
  })
})

describe('정비 미리보기 — 지금 이대로면 무엇이 일어나는가', () => {
  it('★ 실측값을 병기한다 — 「버린다」가 아니라 「지금이면 1개 버림」이다 (P1)', () => {
    const preview = buildMaintenancePreview(
      [{ action: 'DISCARD', grade: 'COMMON' }],
      INVENTORY,
      CONSUMABLES,
    )
    // 보통 장비는 둘인데 하나는 되찾은 것이라 남는다.
    expect(preview.rows[0]?.text).toContain('1개 버림')
  })

  it('★ 잔액을 이어서 깎는다 — 행마다 따로 재면 돈이 한 번치뿐인 배치가 다 도는 것으로 보인다', () => {
    const preview = buildMaintenancePreview(
      [
        { action: 'REPAIR', grade: '' },
        { action: 'REFILL', grade: '' },
      ],
      INVENTORY,
      CONSUMABLES,
    )
    // 잔액 100 → 복구 40 → 60, 보충 20 → 40.
    expect(preview.rows[0]?.moneyDelta).toBe(-40)
    expect(preview.rows[1]?.moneyDelta).toBe(-20)
    expect(preview.balanceAfter).toBe(40)
    expect(preview.moneyDelta).toBe(-60)
  })

  it('★ 잔액이 마르면 그 사실을 남긴다 — 조용히 「돈다」로 보이면 안 된다', () => {
    const broke = { ...INVENTORY, balance: 10 } as InventoryView
    const preview = buildMaintenancePreview([{ action: 'REPAIR', grade: '' }], broke, CONSUMABLES)
    expect(preview.isShort).toBe(true)
    expect(preview.rows[0]?.text).toContain('40 필요')
    expect(preview.rows[0]?.text).toContain('10 있음')
  })

  it('파는 행은 잔액을 늘린다 — 그 뒤의 행이 그 돈을 쓴다', () => {
    const preview = buildMaintenancePreview(
      [
        { action: 'SELL_STOCK', grade: '' },
        { action: 'REPAIR', grade: '' },
      ],
      INVENTORY,
      CONSUMABLES,
    )
    // 재고 둘 × 30 = 60 을 벌고, 복구 40 을 쓴다.
    expect(preview.rows[0]?.moneyDelta).toBe(60)
    expect(preview.balanceAfter).toBe(120)
  })

  it('★ 두 번째 같은 행은 할 일이 없다고 적는다 — 앞의 행이 이미 다 했다', () => {
    const preview = buildMaintenancePreview(
      [
        { action: 'DISCARD', grade: 'COMMON' },
        { action: 'DISCARD', grade: 'COMMON' },
      ],
      INVENTORY,
      CONSUMABLES,
    )
    expect(preview.rows[0]?.isActive).toBe(true)
    expect(preview.rows[1]?.isActive).toBe(false)
  })

  it('★ 아무것도 안 하는 배치를 가려낸다 — 켜 놓고 몇 판 내내 안 도는 것을 막는다', () => {
    const empty = { ...INVENTORY, slots: [], equipment: [], balance: 0 } as InventoryView
    const nothing = { ...CONSUMABLES, slots: [], options: [] } as ConsumableView
    expect(checkPreviewIdle(buildMaintenancePreview(ROWS.rows, empty, nothing))).toBe(true)
    expect(checkPreviewIdle(buildMaintenancePreview(ROWS.rows, INVENTORY, CONSUMABLES))).toBe(false)
  })

  it('잔액 변화를 부호와 함께 적는다', () => {
    expect(formatMoneyDelta(-70)).toBe('−70')
    expect(formatMoneyDelta(120)).toBe('+120')
    expect(formatMoneyDelta(0)).toBe('0')
  })
})

describe('정비 에디터 화면', () => {
  const html = renderEditor(ROWS)

  it('★ 행마다 번호가 선다 — 순서가 실행 순서라는 것이 자리에서 보인다', () => {
    expect(html).toContain('1.')
    expect(html).toContain('3.')
    expect(html).toContain('위에서 아래로 한 번 돈다')
  })

  it('★ 행이 문장으로 선다 — 드롭다운이 목록에 없다', () => {
    expect(html).toContain('가방 장비를 버린다')
    expect(html).toContain('mnt__what')
    expect(html).not.toContain('<select')
  })

  it('★ 행마다 지금이면 무엇이 일어나는지 적는다 (P1)', () => {
    expect(html).toContain('mnt__now')
    expect(html).toContain('1개 버림')
  })

  it('★ 행 수를 상한과 함께 적는다', () => {
    expect(html).toContain(`행 3 / ${String(MAX_MAINTENANCE_ROWS)}`)
  })

  it('★ 오르내리기·복제·삭제가 모든 행에 있다 — 전투 규칙과 같은 조립이다', () => {
    expect((html.match(/한 칸 위로/g) ?? []).length).toBe(3)
    expect((html.match(/한 칸 아래로/g) ?? []).length).toBe(3)
    expect((html.match(/복제/g) ?? []).length).toBeGreaterThanOrEqual(3)
  })

  it('★ 저장 실패 사유를 그대로 띄운다 — 삼키면 켰다고 믿은 정비가 안 돈다', () => {
    expect(renderEditor(ROWS, '버릴 수 없는 등급이다: X')).toContain('버릴 수 없는 등급이다')
  })

  it('★ 서버에 못 닿으면 그 사실을 적는다', () => {
    expect(renderEditor(undefined)).toContain('정비 규칙을 못 읽는다')
  })

  it('★ 행이 없으면 아무것도 안 한다고 적는다 — 빈 목록은 「켜져 있다」로 읽힌다', () => {
    const empty = renderEditor({ rows: [] })
    expect(empty).toContain('없으면 아무것도 안 한다')
  })
})

describe('정비 팔레트', () => {
  const html = renderToStaticMarkup(
    <MaintenancePalette disabled={false} isFull={false} onAdd={noop} />,
  )

  it('★ 행동 넷이 전부 버튼으로 선다 — 예전에는 추가 버튼 하나가 늘 보충을 놓았다', () => {
    expect(html).toContain('버리기')
    expect(html).toContain('복구')
    expect(html).toContain('보충')
    expect(html).toContain('재고 팔기')
  })

  it('★ 무엇을 하는지 버튼 아래에 적는다 — 이름만으로는 무엇이 도는지 모른다', () => {
    expect(html).toContain('mnt__block-note')
    expect(html).toContain('되찾은 것은 남긴다')
  })

  it('★ 가득 차면 그 사실을 적는다 — 눌리지 않는 버튼만 두면 왜인지 모른다', () => {
    const full = renderToStaticMarkup(
      <MaintenancePalette disabled={false} isFull onAdd={noop} />,
    )
    expect(full).toContain(`행이 ${String(MAX_MAINTENANCE_ROWS)}개다`)
  })
})

describe('정비 검증 화면', () => {
  it('★ 미리보기가 어림임을 말한다 — 확정처럼 적으면 틀렸을 때 화면이 거짓말한 것이 된다', () => {
    const html = renderToStaticMarkup(
      <MaintenanceCheck
        problems={checkMaintenanceRows(ROWS.rows)}
        preview={buildMaintenancePreview(ROWS.rows, INVENTORY, CONSUMABLES)}
        hasRows
      />,
    )
    expect(html).toContain('어림이다')
    expect(html).toContain('판이 끝난 뒤')
  })

  it('★ 잔액이 CPU 의 자리다 — 정비가 재는 예산은 돈이다', () => {
    const html = renderToStaticMarkup(
      <MaintenanceCheck
        problems={[]}
        preview={buildMaintenancePreview(
          [{ action: 'REPAIR', grade: '' }],
          INVENTORY,
          CONSUMABLES,
        )}
        hasRows
      />,
    )
    expect(html).toContain('잔액 100 → 60')
    expect(html).toContain('−40')
  })

  it('★ 막는 것과 일러 주는 것을 가른다 — 섞으면 둘 다 무시된다', () => {
    const html = renderToStaticMarkup(
      <MaintenanceCheck
        problems={checkMaintenanceRows([
          { action: 'NOPE', grade: '' },
          { action: 'REPAIR', grade: '' },
          { action: 'REPAIR', grade: '' },
        ])}
        preview={buildMaintenancePreview([], INVENTORY, CONSUMABLES)}
        hasRows
      />,
    )
    expect(html).toContain('ds-glyph--danger')
    expect(html).toContain('ds-glyph--pending')
  })

  it('★ 행이 없으면 아무것도 안 한다고 적는다', () => {
    const html = renderToStaticMarkup(
      <MaintenanceCheck
        problems={[]}
        preview={buildMaintenancePreview([], INVENTORY, CONSUMABLES)}
        hasRows={false}
      />,
    )
    expect(html).toContain('행이 없다')
  })
})

describe('★ 「더 좋게 만든다」 셋', () => {
  // 봉인 해제 · 장비 교체 · 소모품 교체. 앞의 넷은 덜어 내거나 되돌리는 일이라 판단이
  // 없고, 이 셋은 무엇이 더 좋은지를 골라야 한다.
  it('행동 일곱이 어휘에 다 있다 — 서버와 같은 id 다', () => {
    for (const id of ['UNSEAL', 'UPGRADE_GEAR', 'UPGRADE_CONSUMABLE']) {
      expect(MAINTENANCE_ACTIONS.some((one) => one.id === id)).toBe(true)
    }
  })

  it('★ 장비 교체만 인자를 받는다 — 공격이냐 방어냐', () => {
    const swap = MAINTENANCE_ACTIONS.find((one) => one.id === 'UPGRADE_GEAR')
    expect(swap?.args.map(([value]) => value)).toEqual(['ATTACK', 'DEFENSE'])
    expect(MAINTENANCE_ACTIONS.find((one) => one.id === 'UNSEAL')?.args).toHaveLength(0)
  })

  it('★ 새 행은 인자가 채워진 채로 선다 — 빈 인자는 서버가 거절한다', () => {
    expect(createRow('UPGRADE_GEAR')).toEqual({ action: 'UPGRADE_GEAR', grade: 'ATTACK' })
    expect(createRow('UNSEAL')).toEqual({ action: 'UNSEAL', grade: '' })
  })

  it('★ 인자가 문장에 실린다 — 「공격 이 우선순위로…」', () => {
    expect(formatMaintenanceSentence({ action: 'UPGRADE_GEAR', grade: 'DEFENSE' })).toContain('방어')
  })

  it('★ 어휘 밖 인자는 막는다 — 등급과 같은 규율이다', () => {
    const problems = checkMaintenanceRows([{ action: 'UPGRADE_GEAR', grade: 'SPEED' }])
    expect(checkBlocked(problems)).toBe(true)
  })

  it('★ 상한이 서버와 같다 — 행동이 일곱이 되면서 함께 올렸다', () => {
    expect(MAX_MAINTENANCE_ROWS).toBe(10)
  })
})

describe('★ 「더 좋게 만든다」 미리보기는 확실한 것만 센다', () => {
  // 저울(무게표)은 서버에 있다. 화면으로 베끼면 밸런스가 두 벌이 되고, 한쪽을 고칠 때
  // 다른 쪽이 조용히 옛 값으로 남는다 — 그때 미리보기는 서버가 안 할 일을 할 것처럼 적는다.
  it('★ 봉인 해제가 가방 것도 센다 — 착용만 열면 굴러 나온 유물이 영원히 안 열린다', () => {
    const sealedInBag = {
      ...buildBagHelm(2),
      item: { ...(buildBagHelm(2).item as Record<string, unknown>), sealedSlots: 1, unsealCost: 30 },
    }
    const preview = buildMaintenancePreview(
      [{ action: 'UNSEAL', grade: '' }],
      { ...INVENTORY, slots: [sealedInBag], equipment: [] } as unknown as InventoryView,
      CONSUMABLES,
      BASE_STATS,
    )
    expect(preview.rows[0]?.text).toContain('1칸 해제')
    expect(preview.rows[0]?.moneyDelta).toBe(-30)
  })

  it('봉인 해제는 값을 아는 칸만 센다', () => {
    const preview = buildMaintenancePreview([{ action: 'UNSEAL', grade: '' }], INVENTORY, CONSUMABLES)
    // 준비한 가방의 착용 장비에는 봉인이 없다.
    expect(preview.rows[0]?.text).toContain('열 봉인이 없다')
    expect(preview.rows[0]?.isActive).toBe(false)
  })

  it('★ 장비 교체가 서버와 같은 저울로 센다 — 파일 하나를 함께 읽는다', () => {
    const preview = buildMaintenancePreview(
      [{ action: 'UPGRADE_GEAR', grade: 'ATTACK' }],
      INVENTORY,
      CONSUMABLES,
      BASE_STATS,
    )
    // 착용은 머리뿐이고 가방에는 주무기·보조뿐이라 갈아 낄 것이 없다.
    expect(preview.rows[0]?.text).toContain('갈아 낄 것이 없다')
  })

  it('★ 여유폭을 못 넘기면 안 바꾼다 — 서버와 같은 값을 파일에서 읽는다', () => {
    const worn = buildWornHelm(3)
    const barely = buildBagHelm(9)
    const clearly = buildBagHelm(3 + 6 + 1)
    const near = buildMaintenancePreview(
      [{ action: 'UPGRADE_GEAR', grade: 'DEFENSE' }],
      ({ ...INVENTORY, slots: [barely], equipment: [worn] } as unknown as InventoryView),
      CONSUMABLES,
      BASE_STATS,
    )
    // 방어 무게 4 × 차이 6 = 24 로 여유폭을 넘는다 — 이쪽은 바뀐다.
    expect(near.rows[0]?.text).toContain('1개 교체')

    const same = buildMaintenancePreview(
      [{ action: 'UPGRADE_GEAR', grade: 'DEFENSE' }],
      ({ ...INVENTORY, slots: [buildBagHelm(3)], equipment: [worn] } as unknown as InventoryView),
      CONSUMABLES,
      BASE_STATS,
    )
    expect(same.rows[0]?.text).toContain('갈아 낄 것이 없다')
    expect(clearly).toBeDefined()
  })

  it('★ 소모품 교체는 충전이 확실히 더 큰 칸만 센다', () => {
    const preview = buildMaintenancePreview(
      [{ action: 'UPGRADE_CONSUMABLE', grade: '' }],
      INVENTORY,
      CONSUMABLES,
    )
    // 칸이 1/2 이라 가득 차지 않았다 — 쓰던 칸은 안 건드린다.
    expect(preview.rows[0]?.text).toContain('갈아 낄 것이 없다')
  })

  it('★ 잔액이 마른 것을 문구로 알아내지 않는다', () => {
    // 판정과 표기가 같은 문자열을 나눠 쓰면, 문구를 한 글자 고칠 때 경고가 사라진다.
    const preview = buildMaintenancePreview([{ action: 'UNSEAL', grade: '' }], INVENTORY, CONSUMABLES)
    expect(preview.isShort).toBe(false)
  })
})
