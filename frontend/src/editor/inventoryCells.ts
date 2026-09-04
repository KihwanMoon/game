/**
 * 가방·장비 격자의 셀 모델 (도면 그리드).
 *
 * **행 목록이 아니라 칸 도식이다.** 예전에는 아이템마다 한 행에 모든 조작이 펴져 있어
 * 좁은 화면에서 행 하나가 서너 줄로 꺾였다 — 칸은 상태만 그리고, 조작은 고른 칸의
 * 상세 한 곳에 모은다. 도면의 성격이다: 칸은 데이터, 조작은 한 곳.
 *
 * 순수 값이다. 렌더 검사가 훅 없이 셀 배치를 볼 수 있어야 한다.
 */
import type { AffixView, InventoryView, ItemView, SlotView } from '../storage'

import type { CellFace } from './gridCell'

/** 가방 칸 수. 서버의 `INVENTORY_SIZE` 와 같은 값이다 — 다르면 있는 칸이 안 그려진다. */
export const BAG_CELL_COUNT = 20

/** 사거리를 대체하는 자리. **주무기 하나다** (`items/loadout.replace_range`). */
export const RANGE_SLOT = 'WEAPON_MAIN'

/** 장비 슬롯 순서. 파이썬 `SLOT_ORDER` 와 같아야 화면과 합산이 같은 순서를 본다. */
export const EQUIP_CELL_ORDER: readonly string[] = [
  'WEAPON_MAIN',
  'WEAPON_OFF',
  'HEAD',
  'BODY',
  'FEET',
  'HANDS',
]

/** 슬롯의 두 글자 도식 코드. 셀이 좁아 한글 이름은 상세에서 편다. */
export const EQUIP_CELL_CODES: ReadonlyMap<string, string> = new Map([
  ['WEAPON_MAIN', 'WM'],
  ['WEAPON_OFF', 'WO'],
  ['HEAD', 'HD'],
  ['BODY', 'BD'],
  ['FEET', 'FT'],
  ['HANDS', 'HN'],
])

/** 슬롯의 한글 이름. 상세가 쓴다. */
export const EQUIP_CELL_LABELS: ReadonlyMap<string, string> = new Map([
  ['WEAPON_MAIN', '주무기'],
  ['WEAPON_OFF', '보조'],
  ['HEAD', '머리'],
  ['BODY', '갑옷'],
  ['FEET', '신발'],
  ['HANDS', '장갑'],
])

/**
 * 가방·장비 격자 칸 하나.
 *
 * 겉면(`CellFace`)은 소모품 칸·경매장과 함께 쓰고, 여기서 더하는 것은 **알맹이 하나**다 —
 * 이 칸이 인벤토리의 어느 자리를 가리키는가.
 */
export interface GridCell extends CellFace {
  /** 이 칸이 가리키는 원본. 빈 칸이면 undefined. */
  readonly entry: SlotView | undefined
}

/**
 * 칸에 적을 스탯의 한 글자 표기.
 *
 * **가방 칸은 54px 다** (320px 열 · 안쪽 288 · 5열). 「공격력 +5」는 안 들어가고, 안
 * 들어가는 것을 적으면 잘려서 아무 말도 안 하게 된다 — 도면 말이 두 글자 표기를 쓰는
 * 것과 같은 이유이며, 거기서는 셀 폭 64px 이 한계였다.
 *
 * 표에 없는 스탯은 칸에 안 적는다. 상세가 전체 이름으로 답한다.
 */
export const SHORT_STAT_LABELS: ReadonlyMap<string, string> = new Map([
  ['hp_max', '체'],
  ['attack', '공'],
  ['defense', '방'],
  ['attack_range', '사'],
  ['initiative', '선'],
  ['cpu_budget', 'cpu'],
  ['potion_slots', '물'],
  ['scroll_slots', '주'],
])

/**
 * 칸에 적을 대표 접사 한 줄을 고른다.
 *
 * **가장 큰 것 하나다.** 크기는 고정값과 퍼센트의 절대값 중 큰 쪽으로 재고, 같으면
 * 스탯 이름 순으로 끊는다 — 순서가 흔들리면 같은 물건이 볼 때마다 다른 줄을 보인다.
 *
 * 여기서 **좋고 나쁨을 판단하지 않는다.** 저주 접사(음수)가 가장 클 수도 있고, 그때는
 * 그것이 그 물건에 대해 말할 가장 중요한 사실이다.
 *
 * @param affixes 볼 접사들. 비어 있으면 빈 문자열.
 * @returns `공+5` 꼴. 적을 것이 없으면 빈 문자열.
 */
export function pickHeadlineFromAffixes(affixes: readonly AffixView[]): string {
  if (affixes.length === 0) {
    return ''
  }
  const weigh = (affix: AffixView) => Math.max(Math.abs(affix.flat), Math.abs(affix.percent))
  const best = [...affixes]
    .filter((affix) => SHORT_STAT_LABELS.has(affix.stat))
    .sort((left, right) => weigh(right) - weigh(left) || left.stat.localeCompare(right.stat))[0]
  if (best === undefined) {
    return ''
  }
  const head = SHORT_STAT_LABELS.get(best.stat) ?? ''
  // 고정값이 있으면 그것을, 없으면 퍼센트를. 둘 다 적으면 54px 를 넘는다.
  if (best.flat !== 0) {
    return `${head}${best.flat > 0 ? '+' : '−'}${String(Math.abs(best.flat))}`
  }
  return `${head}${best.percent > 0 ? '+' : '−'}${String(Math.abs(best.percent))}%`
}

/**
 * 아이템의 대표 접사 한 줄.
 *
 * @param item 볼 아이템. 없으면 빈 문자열.
 * @returns `공+5` 꼴. 적을 것이 없으면 빈 문자열.
 */
export function pickHeadlineAffix(item: ItemView | undefined): string {
  return pickHeadlineFromAffixes(item?.affixes ?? [])
}

/**
 * 칸 가운데에 들어갈 글자를 자른다.
 *
 * @param name 아이템 이름.
 * @returns 앞 두 글자. 도면 말의 두 글자 표기와 같은 규칙이다.
 */
export function clipCellLabel(name: string): string {
  return [...name.replace(/\s/g, '')].slice(0, 2).join('')
}

/**
 * 아이템의 상태 글리프들을 모은다.
 *
 * @param entry 칸의 원본.
 * @returns 글리프 목록. 없으면 빈 배열.
 */
export function listCellMarks(entry: SlotView): readonly string[] {
  const marks: string[] = []
  if (entry.item?.isBroken === true) {
    marks.push('◈')
  }
  if ((entry.item?.sealedSlots ?? 0) > 0) {
    marks.push(`◇${String(entry.item?.sealedSlots ?? 0)}`)
  }
  if (entry.item?.isBound === true) {
    marks.push('▨')
  }
  return marks
}

/**
 * 장비 여섯 칸을 만든다. **늘 여섯이다** — 빈 슬롯도 칸으로 그려야 「어디가 비었는가」가
 * 보인다.
 *
 * @param inventory 서버가 준 인벤토리.
 * @returns 슬롯 순서대로 여섯 칸.
 */
export function buildEquipCells(inventory: InventoryView | undefined): readonly GridCell[] {
  const bySlot = new Map<string, SlotView>(
    (inventory?.equipment ?? []).map((entry) => [entry.slot ?? '', entry]),
  )
  return EQUIP_CELL_ORDER.map((slot) => {
    const entry = bySlot.get(slot)
    return {
      key: `equip:${slot}`,
      code: EQUIP_CELL_CODES.get(slot) ?? slot,
      label: entry?.item ? clipCellLabel(entry.item.labelKo) : '',
      grade: entry?.item?.grade ?? '',
      marks: entry === undefined ? [] : listCellMarks(entry),
      countText: '',
      fact: pickHeadlineAffix(entry?.item ?? undefined),
      entry,
      isSealedSlot: entry?.isSealed ?? false,
    }
  })
}

/**
 * 가방 스무 칸을 만든다. **차 있는 칸만이 아니라 스무 칸 전부다** — 빈 칸이 보여야
 * 「가방이 얼마나 남았는가」를 세지 않고 안다.
 *
 * @param inventory 서버가 준 인벤토리.
 * @returns 칸 번호 순서대로 스무 칸.
 */
export function buildBagCells(inventory: InventoryView | undefined): readonly GridCell[] {
  const byIndex = new Map<number, SlotView>(
    (inventory?.slots ?? []).map((entry) => [entry.slotIndex, entry]),
  )
  return Array.from({ length: BAG_CELL_COUNT }, (_, index) => {
    const entry = byIndex.get(index)
    if (entry?.item) {
      return {
        key: `bag:${String(index)}`,
        // **칸 번호가 아니라 부위 코드다.** 「이게 어디에 끼는 물건인가」가 칸에서 바로
        // 보여야 한다 — 번호는 아무것도 말해 주지 않는다(실제 요청).
        code: EQUIP_CELL_CODES.get(entry.item.slot ?? '') ?? 'IT',
        label: clipCellLabel(entry.item.labelKo),
        grade: entry.item.grade,
        marks: listCellMarks(entry),
        countText: '',
        fact: pickHeadlineAffix(entry.item),
        entry,
        isSealedSlot: false,
      }
    }
    if (entry !== undefined && entry.stackCatalogId !== null) {
      return {
        key: `bag:${String(index)}`,
        // 소모품은 부위가 없다 — 쓰임새 그대로 CS 다.
        code: 'CS',
        label: clipCellLabel(entry.stackLabelKo === '' ? entry.stackCatalogId : entry.stackLabelKo),
        grade: entry.stackGrade,
        marks: [],
        countText: `x${String(entry.stackCount)}`,
        // 소모품 더미에는 접사가 없다. 빈 줄이 남지만 칸 높이가 안 흔들리는 편이
        // 격자를 훑는 데 낫다 — 줄 수가 칸마다 다르면 눈이 세로로 못 간다.
        fact: '',
        entry,
        isSealedSlot: false,
      }
    }
    return {
      key: `bag:${String(index)}`,
      code: String(index + 1),
      label: '',
      grade: '',
      marks: [],
      countText: '',
      fact: '',
      entry: undefined,
      isSealedSlot: false,
    }
  })
}
