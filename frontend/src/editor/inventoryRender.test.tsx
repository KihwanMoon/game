/**
 * 인벤토리 화면 검사 (D단계).
 *
 * 여기서 지키는 것은 넷이다.
 *
 * 1. **요구조건에 실측값을 병기한다.** "장착할 수 없습니다" 만으로는 무엇이 얼마나
 *    모자란지 알 수 없다 (P1).
 * 2. **등급을 색으로 칠하지 않는다.** 의미색 셋이 이미 배정됐고 색은 정보의 유일한
 *    채널이 될 수 없다.
 * 3. **봉인은 「불가」와 같은 해칭을 쓴다.** 뜻이 같다 — 해당 없음.
 * 4. **서버가 없으면 그렇게 말한다.** 아이템은 서버가 발급하므로 빈 화면과 구분돼야 한다.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { InventoryPanel, ListingRow, formatAffix } from './InventoryPanel'
import type { InventoryView } from '../storage'

const noop = () => undefined

/**
 * 가방에 장비 하나만 있는 인벤토리를 만든다.
 *
 * @param overrides 그 아이템에 덮어쓸 값들.
 * @returns 인벤토리 뷰.
 */
function buildInventory(overrides: Partial<InventoryView['slots'][number]['item'] & object>) {
  const base = INVENTORY.slots[0]
  return {
    ...INVENTORY,
    slots: [{ ...base, item: { ...base?.item, ...overrides } }],
  } as InventoryView
}

/** 요구조건을 못 채운 장갑 하나가 가방에 있다. */
const INVENTORY: InventoryView = {
  slots: [
    {
      slotIndex: 0,
      slot: null,
      isSealed: false,
      stackCatalogId: null,
      stackCount: 0,
      item: {
        itemId: 1,
        catalogId: 'gloves_core',
        labelKo: '연산 장갑',
        kind: 'EQUIPMENT',
        slot: 'HANDS',
        hands: null,
        equippedSlot: null,
        isBroken: false,
        isBound: false,
        isRecovered: false,
    sealedSlots: 0,
    unsealCost: 0,
    grade: 'COMMON',
        affixes: [{ stat: 'hp_max', flat: 8, percent: 0, labelKo: '튼튼함' }],
        canEquip: false,
        requirements: [{ stat: 'cpu_budget', actual: 4, minimum: 6, isMet: false }],
      },
    },
  ],
  equipment: [
    {
      slotIndex: 0,
      slot: 'WEAPON_OFF',
      isSealed: true,
      stackCatalogId: null,
      stackCount: 0,
      item: null,
    },
  ],
  balance: 250,
  repairCost: 120,
}

/**
 * 파일을 읽는다.
 *
 * @param relative 이 파일 기준 상대 경로.
 * @returns 파일 내용.
 */
function readText(relative: string): string {
  return readFileSync(fileURLToPath(new URL(relative, import.meta.url)), 'utf8')
}

describe('인벤토리 패널', () => {
  const markup = renderToStaticMarkup(
    <InventoryPanel
      inventory={INVENTORY}
      isOnline
      detail=""
      onEquip={noop}
      onUnequip={noop}
      onDiscard={noop}
      onRepair={noop}
      onList={noop}
      feePercent={5}
      onUnseal={() => undefined}
    />,
  )

  it('★ 요구조건에 실측값을 병기한다', () => {
    // 규칙 에디터의 조건문 표기와 같은 규약이다 (GDD §8.2).
    expect(markup).toContain('cpu_budget(4) &gt;= 요구(6)')
  })

  it('못 채운 요구조건이면 착용을 잠근다', () => {
    expect(markup).toContain('disabled')
  })

  it('★ 봉인된 자리는 「불가」와 같은 해칭을 쓴다', () => {
    // 새 표기를 만들지 않는다 — 뜻이 같다(해당 없음).
    expect(markup).toContain('ds-glyph--blocked')
    expect(markup).toContain('양손 점유')
  })

  it('여섯 슬롯을 모두 보여준다', () => {
    for (const label of ['주무기', '보조', '투구', '갑옷', '신발', '장갑']) {
      expect(markup).toContain(label)
    }
  })

  it('화폐를 적는다', () => {
    expect(markup).toContain('250')
  })
})

describe('인벤토리 패널 — 서버 없음', () => {
  it('★ 빈 가방과 구분해서 말한다 — 아이템은 서버가 발급한다', () => {
    const markup = renderToStaticMarkup(
      <InventoryPanel
        inventory={undefined}
        isOnline={false}
        detail=""
        onEquip={noop}
        onUnequip={noop}
        onDiscard={noop}
        onRepair={noop}
        onList={noop}
        feePercent={5}
        onUnseal={() => undefined}
      />,
    )
    expect(markup).toContain('서버에 닿지 못했다')
    expect(markup).toContain('서버가 발급한다')
  })
})

describe('인벤토리 스타일', () => {
  const css = readText('./editor.css')
  const block = css.slice(css.indexOf('/* ── 인벤토리·장비 패널'))

  it('★ 등급 색을 새로 쓰지 않는다', () => {
    expect(block).not.toMatch(/#[0-9a-fA-F]{3,8}\b/)
  })

  it('자체 미디어쿼리를 두지 않는다 — 브레이크포인트는 한 곳에만 있다', () => {
    expect(block).not.toContain('@media')
  })

  it('터치 높이 토큰을 쓴다', () => {
    expect(block).toContain('var(--btn-tap-sm-h)')
  })
})

describe('귀속 표시 (결정 #07)', () => {
  it('★ 귀속된 아이템은 가방에서 그것이 보인다', () => {
    // 걸기 전에 보여야 한다 — 모르면 걸다가 거절당하고, 그때는 이미 "왜 안 되지" 를
    // 겪은 뒤다.
    const html = renderToStaticMarkup(
      <InventoryPanel
        inventory={buildInventory({ isBound: true })}
        isOnline
        detail=""
        onEquip={() => undefined}
        onUnequip={() => undefined}
        onDiscard={() => undefined}
        onRepair={() => undefined}
        onList={() => undefined}
        feePercent={5}
        onUnseal={() => undefined}
      />,
    )
    expect(html).toContain('귀속')
  })

  it('주운 아이템에는 안 붙는다 — 붙으면 팔 수 있는 것까지 못 팔 것처럼 보인다', () => {
    const html = renderToStaticMarkup(
      <InventoryPanel
        inventory={buildInventory({ isBound: false })}
        isOnline
        detail=""
        onEquip={() => undefined}
        onUnequip={() => undefined}
        onDiscard={() => undefined}
        onRepair={() => undefined}
        onList={() => undefined}
        feePercent={5}
        onUnseal={() => undefined}
      />,
    )
    expect(html).not.toContain('귀속')
  })
})

describe('아이템이 주는 것 (기존 화면 보완)', () => {
  it('★ 끼기 전에 무엇을 주는지 보인다', () => {
    // 모르고 끼우면 캐릭터 시트를 보고 나서야 알게 되고, 그때는 이미 다른 것을 벗은 뒤다.
    const html = renderToStaticMarkup(
      <InventoryPanel
        inventory={INVENTORY}
        isOnline
        detail=""
        onEquip={() => undefined}
        onUnequip={() => undefined}
        onDiscard={() => undefined}
        onRepair={() => undefined}
        onList={() => undefined}
        feePercent={5}
        onUnseal={() => undefined}
      />,
    )
    expect(html).toContain('튼튼함')
    expect(html).toContain('+8')
  })

  it('★ 저주 접사는 부호가 붙는다 — 「방어 -3」과 「방어 3」이 같아 보이면 안 된다', () => {
    expect(formatAffix({ stat: 'defense', flat: -3, percent: 0, labelKo: '저주' })).toBe('저주 -3')
    expect(formatAffix({ stat: 'attack', flat: 0, percent: 12, labelKo: '예리함' })).toBe(
      '예리함 +12%',
    )
  })

  it('접사 이름이 없으면 스탯 이름을 쓴다 — 빈 줄을 그리지 않는다', () => {
    expect(formatAffix({ stat: 'hp_max', flat: 5, percent: 0, labelKo: '' })).toBe('hp_max +5')
  })
})

describe('소모품 스택 (#54)', () => {
  const html = renderToStaticMarkup(
    <InventoryPanel
      inventory={
        {
          ...INVENTORY,
          slots: [{ slotIndex: 0, slot: null, isSealed: false, stackCatalogId: 'potion_small', stackCount: 3, item: null }],
        } as InventoryView
      }
      isOnline
      detail=""
      onEquip={noop}
      onUnequip={noop}
      onDiscard={noop}
      onRepair={noop}
      onList={noop}
      feePercent={5}
      onUnseal={() => undefined}
    />,
  )

  it('★ 개수를 적는다 — 물약 한 칸과 세 칸은 규칙표가 달라진다', () => {
    expect(html).toContain('x3')
  })

  it('★ 빈 칸이 아니라고 말한다 — 이름이 있어야 무엇을 들었는지 안다', () => {
    expect(html).toContain('potion_small')
  })
})

describe('되찾음 (`설계/6_몬스터` §5)', () => {
  it('★ 빼앗겼다가 되찾은 것을 그렇게 말한다', () => {
    // 잃은 것과 되찾은 것이 가방에서 같아 보이면 되찾으러 간 런이 흔적을 남기지
    // 않는다. World Loop 의 동기가 도감에만 있고 가방에는 없게 된다.
    const html = renderToStaticMarkup(
      <InventoryPanel
        inventory={buildInventory({ isRecovered: true })}
        isOnline
        detail=""
        onEquip={noop}
        onUnequip={noop}
        onDiscard={noop}
        onRepair={noop}
        onList={noop}
        feePercent={5}
        onUnseal={() => undefined}
      />,
    )
    expect(html).toContain('되찾음')
  })

  it('평범한 아이템에는 안 붙는다 — 붙으면 표시가 뜻을 잃는다', () => {
    const html = renderToStaticMarkup(
      <InventoryPanel
        inventory={buildInventory({ isRecovered: false })}
        isOnline
        detail=""
        onEquip={noop}
        onUnequip={noop}
        onDiscard={noop}
        onRepair={noop}
        onList={noop}
        feePercent={5}
        onUnseal={() => undefined}
      />,
    )
    expect(html).not.toContain('되찾음')
  })
})

describe('경매 등록 (서버에는 있었는데 화면에 없던 길)', () => {
  const ITEM = {
    itemId: 7,
    catalogId: 'helm_iron',
    labelKo: '철 투구',
    kind: 'EQUIPMENT',
    slot: 'HEAD',
    hands: null,
    equippedSlot: null,
    isBroken: false,
    isBound: false,
    isRecovered: false,
    sealedSlots: 0,
    unsealCost: 0,
    grade: 'COMMON',
    affixes: [],
    canEquip: true,
    requirements: [],
  }

  it('★ 팔 길이 화면에 있다 — 없으면 경제의 절반이 안 돈다', () => {
    const html = renderToStaticMarkup(
      <ListingRow item={ITEM} feePercent={5} onList={() => undefined} />,
    )
    expect(html).toContain('걸기')
    expect(html).toContain('호가')
  })

  it('★ 수수료율을 호가 적기 전에 적는다 — 걸고 나서 알면 이미 나간 뒤다', () => {
    const html = renderToStaticMarkup(
      <ListingRow item={ITEM} feePercent={5} onList={() => undefined} />,
    )
    expect(html).toContain('수수료 5%')
  })

  it('★ 귀속된 것에는 줄 자체를 안 그린다 — 눌러 봐야 거절이다', () => {
    const html = renderToStaticMarkup(
      <ListingRow item={{ ...ITEM, isBound: true }} feePercent={5} onList={() => undefined} />,
    )
    expect(html).toBe('')
  })

  it('★ 파손품도 못 건다 — 복구비용을 남에게 떠넘기는 것이 최적이 된다', () => {
    const html = renderToStaticMarkup(
      <ListingRow item={{ ...ITEM, isBroken: true }} feePercent={5} onList={() => undefined} />,
    )
    expect(html).toBe('')
  })

  it('★ 호가가 비면 버튼이 잠긴다 — 0 원 매물은 원장만 더럽힌다', () => {
    const html = renderToStaticMarkup(
      <ListingRow item={ITEM} feePercent={5} onList={() => undefined} />,
    )
    expect(html).toContain('disabled')
  })
})

describe('봉인된 옵션 (설계/4_아이템 §17)', () => {
  const build = (patch: Record<string, unknown>) =>
    renderToStaticMarkup(
      <InventoryPanel
        inventory={buildInventory(patch)}
        isOnline
        detail=""
        onEquip={() => undefined}
        onUnequip={() => undefined}
        onDiscard={() => undefined}
        onRepair={() => undefined}
        onList={() => undefined}
        feePercent={5}
        onUnseal={() => undefined}
      />,
    )

  it('★ 남은 칸 수가 보인다 — 등급이 무엇을 줬는지가 가방에 있어야 한다', () => {
    expect(build({ sealedSlots: 2, unsealCost: 180 })).toContain('봉인 2칸')
  })

  it('★ 여는 값이 서버가 준 값이다 — 화면이 다시 계산하면 두 곳이 갈린다', () => {
    expect(build({ sealedSlots: 2, unsealCost: 180 })).toContain('해제 180')
  })

  it('★ 무엇이 나올지는 안 적는다 — 적으면 열 이유가 사라진다', () => {
    expect(build({ sealedSlots: 1, unsealCost: 120 })).toContain('열어야 안다')
  })

  it('★ 칸이 없으면 버튼도 없다', () => {
    expect(build({ sealedSlots: 0 })).not.toContain('봉인 해제')
  })
})
