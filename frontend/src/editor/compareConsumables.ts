/**
 * 고른 소모품을 **끼운 칸 전부**와 견준다 (설계/4_아이템 §5).
 *
 * 가방은 자리가 하나라 견줄 상대가 하나다 — 주무기 칸에 낀 것 하나. 소모품은 그렇지
 * 않다. **칸 수가 고정이 아니다**: 접사(`potion_slots`·`scroll_slots`)가 칸을 늘리므로
 * 물약 칸이 하나일 수도 셋일 수도 있다. 그 상태에서 「지금 낀 것」 하나만 골라 견주면,
 * 화면이 고른 그 하나가 사람이 갈아 끼우려던 칸이라는 보장이 없다 — 나머지 칸은 견줌에서
 * 사라지고, 사람은 다시 칸을 하나씩 눌러 봐야 한다.
 *
 * 그래서 **맞는 칸 전부와 견준다.** 어느 칸을 비울지는 견줌을 보고 사람이 정한다.
 *
 * 견줌의 규칙은 가방과 같다 (`compareItems`) — **점수 하나로 접지 않고** 스탯별 차이까지만
 * 낸다. 같은 질문에 두 화면이 다른 방식으로 답하면 어느 쪽을 믿을지가 또 문제가 된다.
 */
import type { AffixView, ConsumableOptionView, ConsumableSlotView } from '../storage'

import { compareToWorn, type CompareRow } from './compareItems'

/**
 * 충전 용량의 스탯 키.
 *
 * 접사가 아니라 **등급이 정하는 값**이라 서버가 접사 절로 보내지 않는다. 그런데 물약을
 * 고를 때 「몇 번 마실 수 있나」는 붙는 옵션만큼 중요하다 — 접사 줄과 같은 모양으로
 * 끼워 넣어 한 곳에서 읽게 한다.
 */
export const CHARGE_STAT = 'charge_max'

/** 충전 용량 줄의 이름. 서버 접사가 아니므로 여기서 붙인다. */
export const CHARGE_LABEL = '충전 용량'

/** 한 칸과의 견줌. */
export interface SlotCompare {
  /** 견준 상대 칸. */
  readonly slot: ConsumableSlotView
  /** 그 칸이 비어 있었는가. 비었으면 차이가 전부 이득이다. */
  readonly isEmpty: boolean
  /** 스탯별 차이. 같으면 빈 배열. */
  readonly rows: readonly CompareRow[]
}

/** 견줄 것 하나 — 재고 한 종류이거나 이미 끼운 칸 하나다. */
export interface ComparePick {
  /** 무엇을 견주는지 화면에 적을 이름. */
  readonly label: string
  readonly useTag: string
  readonly affixes: readonly AffixView[]
  /** 가득 찼을 때의 충전 수. */
  readonly chargeMax: number
  /**
   * 이것이 이미 끼운 칸이라면 그 칸의 열쇠. 자기 자신과는 안 견준다 — 차이가 없는 것이
   * 당연하고, 그 줄이 있으면 진짜 견줌이 한 칸 밀린다.
   */
  readonly selfKey: string
}

/**
 * 칸을 가리키는 열쇠. 쓰임새와 자리로 만든다.
 *
 * @param slot 칸.
 * @returns `POTION:0` 꼴.
 */
export function buildSlotKey(slot: ConsumableSlotView): string {
  return `${slot.useTag}:${String(slot.slotIndex)}`
}

/**
 * 재고 한 종류를 견줄 것으로 만든다.
 *
 * @param option 가방 재고.
 * @returns 견줄 것.
 */
export function pickFromOption(option: ConsumableOptionView): ComparePick {
  return {
    label: option.labelKo,
    useTag: option.useTag,
    affixes: option.affixRows,
    chargeMax: option.charges,
    selfKey: '',
  }
}

/**
 * 이미 끼운 칸을 견줄 것으로 만든다.
 *
 * @param slot 칸.
 * @returns 견줄 것.
 */
export function pickFromSlot(slot: ConsumableSlotView): ComparePick {
  return {
    label: slot.labelKo,
    useTag: slot.useTag,
    affixes: slot.affixRows,
    chargeMax: slot.chargeMax,
    selfKey: buildSlotKey(slot),
  }
}

/**
 * 충전 용량 차이를 접사 줄과 같은 모양으로 만든다.
 *
 * **퍼센트는 안 쓴다.** 충전은 개수라 퍼센트가 뜻이 없다.
 *
 * @param pickedMax 고른 것의 충전 용량.
 * @param wornMax 그 칸에 낀 것의 충전 용량. 빈 칸이면 0 이다.
 * @returns 견줌 한 줄. 같으면 undefined.
 */
export function buildChargeRow(pickedMax: number, wornMax: number): CompareRow | undefined {
  if (pickedMax === wornMax) {
    return undefined
  }
  return {
    stat: CHARGE_STAT,
    label: CHARGE_LABEL,
    pickedFlat: pickedMax,
    pickedPercent: 0,
    wornFlat: wornMax,
    wornPercent: 0,
    flatDelta: pickedMax - wornMax,
    percentDelta: 0,
  }
}

/**
 * 고른 소모품을 맞는 칸 전부와 견준다.
 *
 * **쓰임새가 맞는 칸만 본다.** 물약을 주문서 칸에 끼울 수 없으므로, 그 칸과의 차이는
 * 답이 아니라 소음이다.
 *
 * **차이가 없는 칸도 낸다.** 「이 칸과는 같다」가 답인 경우가 있고, 그 칸이 목록에서
 * 통째로 사라지면 「그 칸은 왜 안 나오지」가 된다 — 빈 자리와 구별이 안 된다.
 *
 * **정렬은 서버가 준 칸 순서 그대로다.** 견줌의 좋고 나쁨으로 다시 세우지 않는다 —
 * 무엇이 좋은지를 코드가 정하는 순간 화면이 틀린 답을 자신 있게 말하게 되고, 그것이
 * 스탯별 차이까지만 내기로 한 이유다 (`compareItems`).
 *
 * @param picked 고른 것.
 * @param slots 끼운 칸 전부.
 * @returns 칸마다의 견줌. 맞는 칸이 없으면 빈 배열.
 */
export function compareToSlots(
  picked: ComparePick,
  slots: readonly ConsumableSlotView[],
): readonly SlotCompare[] {
  return slots
    .filter((slot) => slot.useTag === picked.useTag && buildSlotKey(slot) !== picked.selfKey)
    .map((slot) => {
      const isEmpty = slot.catalogId === ''
      const charge = buildChargeRow(picked.chargeMax, isEmpty ? 0 : slot.chargeMax)
      return {
        slot,
        isEmpty,
        rows: [
          ...compareToWorn(picked.affixes, isEmpty ? [] : slot.affixRows),
          ...(charge === undefined ? [] : [charge]),
        ],
      }
    })
}
