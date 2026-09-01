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

import { InventoryPanel, ListingRow, formatAffix, formatGradeClass } from './InventoryPanel'
import type { AffixView as InventoryAffix, InventoryView } from '../storage'

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
    // **장비 자리를 비운다.** 안 비우면 낀 대검의 봉인 칸이 마크업에 섞여, 가방 쪽을
    // 보는 검사가 무엇을 보고 통과했는지 알 수 없다 — 실제로 그렇게 빨개졌다.
    equipment: [],
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
    attackRange: 0,
        affixes: [{ stat: 'hp_max', flat: 8, percent: 0, labelKo: '튼튼함', statLabel: '최대체력' }],
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
    {
      slotIndex: 1,
      slot: 'WEAPON_MAIN',
      isSealed: false,
      stackCatalogId: null,
      stackCount: 0,
      item: {
        itemId: 2,
        catalogId: 'sword_great',
        labelKo: '대검',
        kind: 'EQUIPMENT',
        slot: 'WEAPON_MAIN',
        hands: 'TWO',
        equippedSlot: 'WEAPON_MAIN',
        isBroken: false,
        isBound: false,
        isRecovered: false,
        sealedSlots: 2,
        unsealCost: 120,
        grade: 'RELIC',
        attackRange: 1,
        affixes: [
          { stat: 'attack', flat: 5, percent: 0, labelKo: '묵직함', statLabel: '공격력' },
        ],
        canEquip: true,
        requirements: [],
      },
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
    expect(
      formatAffix({ stat: 'defense', flat: -3, percent: 0, labelKo: '저주', statLabel: '방어력' }),
    ).toBe('저주 · 방어력 -3')
    expect(
      formatAffix({ stat: 'attack', flat: 0, percent: 12, labelKo: '예리함', statLabel: '공격력' }),
    ).toBe('예리함 · 공격력 +12%')
  })

  it('★ 무엇을 올리는지 병기한다 — 「튼튼함 +8」 만으로는 8 이 무엇의 8 인지 모른다', () => {
    expect(
      formatAffix({ stat: 'hp_max', flat: 8, percent: 0, labelKo: '튼튼함', statLabel: '최대체력' }),
    ).toBe('튼튼함 · 최대체력 +8')
  })

  it('★ 이름이 없으면 능력치 이름만 쓴다 — 영어 키가 그대로 새던 자리다', () => {
    expect(
      formatAffix({ stat: 'hp_max', flat: 5, percent: 0, labelKo: '', statLabel: '최대체력' }),
    ).toBe('최대체력 +5')
  })

  it('이름이 능력치를 되풀이하면 한 번만 쓴다 — 「공격력 · 공격력 +3」 은 군더더기다', () => {
    expect(
      formatAffix({ stat: 'attack', flat: 3, percent: 0, labelKo: 'attack', statLabel: '공격력' }),
    ).toBe('공격력 +3')
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
    attackRange: 0,
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


describe('무기 사거리 (설계/4_아이템 §2.2)', () => {
  /**
   * 무기 하나가 든 가방을 그린다.
   *
   * @param attackRange 무기가 정하는 사거리.
   * @returns 마크업.
   */
  function drawBow(attackRange: number, affixes: InventoryAffix[] = []): string {
    return renderToStaticMarkup(
      <InventoryPanel
        inventory={{
          ...INVENTORY,
          // 장비 칸을 비운다. 안 비우면 낀 대검의 사거리가 마크업에 섞여, 가방 쪽을
          // 보는 이 검사가 무엇을 보고 통과했는지 알 수 없다.
          equipment: [],
          slots: [
            {
              slotIndex: 0,
              slot: null,
              isSealed: false,
              stackCatalogId: null,
              stackCount: 0,
              item: {
                itemId: 91,
                catalogId: 'bow_long',
                labelKo: '장궁',
                kind: 'EQUIPMENT',
                slot: 'WEAPON_MAIN',
                hands: 'TWO',
                equippedSlot: null,
                isBroken: false,
                isBound: false,
                isRecovered: false,
                sealedSlots: 0,
                unsealCost: 0,
                grade: 'COMMON',
                attackRange,
                affixes,
                canEquip: true,
                requirements: [],
              },
            },
          ],
        }}
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
  }

  it('★ 무기의 사거리가 가방에서 보인다 — 접사에서 필드로 옮기며 한 번 안 보이게 됐다', () => {
    expect(drawBow(4)).toContain('사거리 4')
  })

  it('★ 사거리를 안 정하는 것에는 안 적는다 — 「사거리 0」 은 못 때리는 무기로 읽힌다', () => {
    // **접사를 하나 얹는다.** 접사가 없으면 함수가 먼저 빠져나가 안쪽 조건을 안 지나고,
    // 그러면 이 검사가 조건을 지워도 통과한다 — 실제로 그렇게 통과했다.
    const affix = { stat: 'attack', flat: 2, percent: 0, labelKo: '날', statLabel: '공격력' }
    expect(drawBow(0, [affix])).not.toContain('사거리')
    expect(drawBow(0, [affix])).toContain('날 · 공격력 +2')
  })
})


/**
 * 기본 픽스처로 패널을 그린다.
 *
 * @returns 마크업.
 */
function drawPanel(): string {
  return renderToStaticMarkup(
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
}

describe('등급 표기 (설계/4_아이템 §15.4)', () => {
  it('★ 등급마다 다른 색을 준다 — 보통·상급·유물', () => {
    expect(formatGradeClass('COMMON')).toContain('common')
    expect(formatGradeClass('FINE')).toContain('fine')
    expect(formatGradeClass('RELIC')).toContain('relic')
  })

  it('★ 모르는 등급에는 색을 안 입힌다 — 아무 색이나 주면 등급이 있는 것처럼 보인다', () => {
    expect(formatGradeClass('')).toBe('')
    expect(formatGradeClass('MYTHIC')).toBe('')
  })

  it('★ 이름표를 함께 적는다 — 색만으로 가르면 색을 못 가르는 사람에게 등급이 없다', () => {
    expect(drawPanel()).toContain('보통')
  })

  it('★ 가방이 등급을 말한다 — 서버는 보내는데 화면이 버리고 있었다', () => {
    expect(drawPanel()).toContain('inv__name--common')
  })
})

describe('낀 장비가 무엇을 주는가', () => {
  it('★ 장비 칸에서 능력치를 볼 수 있다 — 없어서 「가방 것이 적용된다」로 읽혔다', () => {
    // 합산은 예나 지금이나 `equipment_slot` 만 본다. 문제는 **낀 것의 효과를 볼 데가
    // 아예 없었다**는 것이다 — 능력치 줄이 가방 칸에만 붙어 있었다.
    expect(drawPanel()).toContain('능력치')
    // 낀 대검의 접사가 실제로 적혀야 한다. 접었다 펴는 요소라 마크업에는 늘 들어 있다.
    expect(drawPanel()).toContain('묵직함 · 공격력 +5')
  })

  it('★ 낀 것의 등급도 보인다 — 유물을 끼고도 보통과 같아 보이면 등급이 뜻을 잃는다', () => {
    expect(drawPanel()).toContain('inv__name--relic')
    expect(drawPanel()).toContain('유물')
  })
})


describe('낀 채로 고치고 연다', () => {
  /**
   * 장비 한 자리만 둔 가방을 그린다.
   *
   * @param isBroken 파손 여부.
   * @param sealedSlots 남은 봉인 칸.
   * @returns 마크업.
   */
  function drawEquipped(isBroken: boolean, sealedSlots: number) {
    // `null` 도 걸러야 한다. `undefined` 만 보면 아이템이 없는 자리가 그대로 퍼져서
    // 모든 칸이 선택 항목이 된다.
    const base = INVENTORY.equipment[1]?.item
    if (base === undefined || base === null) {
      throw new Error('픽스처가 비었다')
    }
    const item = { ...base, isBroken, sealedSlots }
    return renderToStaticMarkup(
      <InventoryPanel
        inventory={{
          ...INVENTORY,
          slots: [],
          equipment: [
            {
              slotIndex: 1,
              slot: 'WEAPON_MAIN',
              isSealed: false,
              stackCatalogId: null,
              stackCount: 0,
              item,
            },
          ],
        }}
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
  }

  it('★ 낀 장비가 파손됐으면 그 자리에서 복구한다 — 벗었다 끼는 사이 스탯이 흔들린다', () => {
    expect(drawEquipped(true, 0)).toContain('복구')
  })

  it('★ 낀 장비의 봉인도 그 자리에서 연다 — 서버는 처음부터 낀 것도 받았다', () => {
    expect(drawEquipped(false, 2)).toContain('봉인 해제')
  })

  it('★ 멀쩡하면 복구 버튼을 안 그린다 — 늘 떠 있으면 파손이 눈에 안 띈다', () => {
    expect(drawEquipped(false, 0)).not.toContain('복구')
  })

  it('★ 열 봉인이 없으면 해제 버튼을 안 그린다 — 눌러도 거절당하는 버튼은 거짓말이다', () => {
    expect(drawEquipped(false, 0)).not.toContain('봉인 해제')
  })
})


describe('등급 색이 실제로 이기는가', () => {
  const css = readText('./editor.css')

  it('★ 등급 규칙이 `.inv__name` **뒤에** 있다 — 같은 우선순위라 순서가 이긴다', () => {
    // 처음에는 규칙을 `styles/app.css` 에 뒀는데, 그 파일이 `editor.css` 보다 먼저
    // 로드되므로 여기 있는 `.inv__name { color }` 이 등급색을 통째로 덮었다.
    // 화면에는 아무 색도 안 나왔고, 배포 확인은 "클래스가 CSS 에 있다" 만 보고 통과했다.
    const base = css.indexOf('.inv__name {')
    const fine = css.indexOf('.inv__name--fine')
    expect(base).toBeGreaterThan(-1)
    expect(fine).toBeGreaterThan(base)
  })

  it('★ 세 등급이 서로 다른 값을 쓴다 — 같은 값이면 색으로 가른 것이 아니다', () => {
    const read = (name: string) =>
      new RegExp(`\\.inv__name--${name}\\s*\\{[^}]*color:\\s*([^;]+);`).exec(css)?.[1]?.trim()
    const picked = [read('common'), read('fine'), read('relic')]
    expect(picked.every((value) => value !== undefined)).toBe(true)
    expect(new Set(picked).size).toBe(3)
  })

  it('★ 이름표에도 같은 색을 쓴다 — 이름과 이름표가 다른 색이면 무엇이 등급인지 흐려진다', () => {
    expect(css).toContain('.inv__grade--relic')
  })

  it('★ 색 말고 글리프도 가른다 — 색이 유일한 채널이면 색을 못 가르는 사람에게 등급이 없다', () => {
    const html = drawPanel()
    expect(html).toContain('◆')
    expect(html).toContain('·')
  })
})
