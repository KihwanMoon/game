/**
 * 소모품 칸·재고 격자의 셀 모델 (설계/4_아이템 §5).
 *
 * **가방과 같은 형식이다.** 예전에는 여기만 카드 목록이었다 — 칸 하나가 머리·눈금·옵션
 * 줄들·도구줄로 네 덩이라, 칸 넷이면 화면 한 장을 넘겼고 「어느 물약이 더 좋은가」는
 * 위아래로 오가며 읽어야 했다. 가방이 도면 격자로 답한 질문과 같은 질문인데 답하는
 * 모양이 달랐다.
 *
 * **두 격자다.** 위는 「들고 갈 것」(칸), 아래는 「가진 것」(재고). 이 구분이 이 화면의
 * 존재 이유이므로 한 격자로 합치지 않는다 — 합치면 예전처럼 주운 만큼이 답이 된다.
 *
 * 순수 값이다. 렌더 검사가 훅 없이 셀 배치를 볼 수 있어야 한다.
 */
import type { ConsumableOptionView, ConsumableSlotView, ConsumableView } from '../storage'

import type { CellFace } from './gridCell'
import { clipCellLabel, pickHeadlineFromAffixes } from './inventoryCells'

/** 칸 쓰임새의 한글 이름. 상세와 머리글이 쓴다. */
export const USE_TAG_LABELS: ReadonlyMap<string, string> = new Map([
  ['POTION', '물약'],
  ['SCROLL', '주문서'],
])

/**
 * 쓰임새의 두 글자 도식 코드.
 *
 * 장비 칸이 부위 코드(`WM`·`HD`)를 다는 것과 같은 자리다 — 칸 구석은 **어디에 들어가는
 * 것인가**를 말한다. 물약을 주문서 칸에 끼울 수 없으므로 이것이 곧 그 칸의 자리다.
 */
export const USE_TAG_CODES: ReadonlyMap<string, string> = new Map([
  ['POTION', 'PO'],
  ['SCROLL', 'SC'],
])

/**
 * 소모품 격자 칸 하나.
 *
 * 겉면은 가방과 같고(`CellFace`), 알맹이가 둘로 갈린다 — 끼운 칸이거나 가방 재고다.
 * **한 필드에 합치지 않는다.** 조작이 갈리기 때문이다: 칸은 보충·빼기, 재고는
 * 끼우기·팔기이며, 그것을 섞으면 「빼기」가 재고를 지우는 사고가 난다.
 */
export interface ConsumableCell extends CellFace {
  /** 끼운 칸인가 가방 재고인가. */
  readonly kind: 'slot' | 'stock'
  /** 끼운 칸. `kind` 가 `slot` 일 때만 있다. */
  readonly slot: ConsumableSlotView | undefined
  /** 가방 재고. `kind` 가 `stock` 일 때만 있다. */
  readonly option: ConsumableOptionView | undefined
}

/**
 * 칸 이름을 적는다.
 *
 * @param slot 칸.
 * @returns `물약 1` 같은 한 줄.
 */
export function formatSlotName(slot: ConsumableSlotView): string {
  const label = USE_TAG_LABELS.get(slot.useTag) ?? slot.useTag
  return `${label} ${String(slot.slotIndex + 1)}`
}

/**
 * 칸 구석에 적을 코드.
 *
 * **번호까지 적는다.** 물약 칸이 둘 이상일 수 있고(접사가 칸을 늘린다), 그때 `PO` 만
 * 적으면 두 칸이 구별되지 않아 「어느 칸을 비웠지」를 답할 수 없다.
 *
 * @param useTag 쓰임새.
 * @param slotIndex 그 쓰임새 안에서의 자리.
 * @returns `PO1` 꼴.
 */
export function formatSlotCode(useTag: string, slotIndex: number): string {
  return `${USE_TAG_CODES.get(useTag) ?? 'CS'}${String(slotIndex + 1)}`
}

/**
 * 끼운 칸들을 격자 칸으로 만든다.
 *
 * **빈 칸도 그린다.** 안 그리면 「칸이 없다」와 「비었다」를 구분할 수 없고, 빈 칸이
 * 출격할 때 공짜로 충전을 받는다는 사실이 어디에도 안 적힌다.
 *
 * @param view 소모품 칸 화면. 없으면 빈 배열.
 * @returns 서버가 준 순서 그대로의 칸들.
 */
export function buildConsumableSlotCells(
  view: ConsumableView | undefined,
): readonly ConsumableCell[] {
  return (view?.slots ?? []).map((slot) => ({
    key: `cslot:${slot.useTag}:${String(slot.slotIndex)}`,
    code: formatSlotCode(slot.useTag, slot.slotIndex),
    label: slot.catalogId === '' ? '' : clipCellLabel(slot.labelKo),
    grade: slot.grade,
    // 다 쓴 칸. **파손된 장비와 같은 것이 아니다** — 다 쓴 물약 칸은 여전히 그 물약을
    // 차고 있고 부가 옵션도 그대로 붙는다 (`list_loaded_consumables`). 못 하는 것은
    // **마시는 것 하나**이며, 이 글리프가 말하는 것도 그것이다.
    marks: slot.catalogId !== '' && slot.charges <= 0 ? ['◈'] : [],
    // **충전은 남은/전체다.** `2` 만 적으면 채울 것이 있는지 알 수 없다 (P1).
    countText: slot.catalogId === '' ? '' : `${String(slot.charges)}/${String(slot.chargeMax)}`,
    fact: pickHeadlineFromAffixes(slot.affixRows),
    isSealedSlot: false,
    kind: 'slot',
    slot,
    option: undefined,
  }))
}

/**
 * 가방 재고를 격자 칸으로 만든다.
 *
 * **빈 칸을 덧대지 않는다.** 칸과 달리 재고에는 정해진 자리 수가 없다 — 없는 자리를
 * 그리면 「가방이 스무 칸이다」로 읽힌다.
 *
 * @param view 소모품 칸 화면. 없으면 빈 배열.
 * @returns 서버가 준 순서(카탈로그 id 순) 그대로의 칸들.
 */
export function buildConsumableStockCells(
  view: ConsumableView | undefined,
): readonly ConsumableCell[] {
  return (view?.options ?? []).map((option) => ({
    key: `cstock:${option.catalogId}`,
    code: USE_TAG_CODES.get(option.useTag) ?? 'CS',
    label: clipCellLabel(option.labelKo),
    grade: option.grade,
    marks: [],
    countText: `x${String(option.stock)}`,
    fact: pickHeadlineFromAffixes(option.affixRows),
    isSealedSlot: false,
    kind: 'stock',
    slot: undefined,
    option,
  }))
}

/**
 * 충전 상태를 적는다.
 *
 * **실측값을 병기한다** — `2/4` 처럼 남은 것과 한도를 함께 적어야 「채울 게 있는가」가
 * 눈에 보인다. 규칙 에디터가 `적거리(2) <= 사거리(3)` 을 적는 것과 같은 이유다 (P1).
 *
 * @param slot 칸.
 * @param freeCharges 빈 칸이 출격 때 받는 공짜 충전.
 * @returns 화면에 적을 한 줄.
 */
export function formatCharges(slot: ConsumableSlotView, freeCharges: number): string {
  if (slot.catalogId === '') {
    return `빈 칸 — 출격 시 ${String(freeCharges)}개가 공짜로 찬다`
  }
  return `${String(slot.charges)} / ${String(slot.chargeMax)}`
}

/**
 * 빼기 버튼에 적을 말.
 *
 * **가득 찬 칸은 가방으로 돌아가고, 쓴 칸은 남은 충전이 버려진다.** 그 차이를 누르기
 * 전에 말해야 한다 — 눌러 보고 알게 하면 「아이템이 사라졌다」가 된다(실제 신고).
 *
 * @param slot 칸.
 * @returns 버튼 글자.
 */
export function formatClearLabel(slot: ConsumableSlotView): string {
  if (slot.charges >= slot.chargeMax) {
    return '빼기 (가방으로)'
  }
  return `빼기 (남은 ${String(slot.charges)}충전 버려짐)`
}

/**
 * 보충 버튼에 적을 말.
 *
 * @param slot 칸.
 * @returns 버튼 글자. 채울 것이 없으면 빈 문자열이다.
 */
export function formatRefillLabel(slot: ConsumableSlotView): string {
  if (slot.catalogId === '' || slot.refillCost <= 0) {
    return ''
  }
  return `보충 ${String(slot.refillCost)}`
}

/**
 * 이 소모품을 끼울 칸을 고른다.
 *
 * **빈 칸이 먼저다.** 찬 칸을 먼저 고르면 끼우는 순간 남의 충전이 날아가고, 그것은
 * 되돌릴 수 없다. 빈 칸이 없으면 undefined 를 돌려 부르는 쪽이 말하게 한다 — 조용히
 * 아무 칸이나 덮으면 「왜 물약이 바뀌었지」가 된다.
 *
 * @param view 소모품 칸 화면. 없으면 고를 수 없다.
 * @param catalogId 끼울 소모품.
 * @returns 끼울 칸. 맞는 빈 칸이 없으면 undefined.
 */
export function findFreeConsumableSlot(
  view: ConsumableView | undefined,
  catalogId: string,
): ConsumableSlotView | undefined {
  const option = view?.options.find((entry) => entry.catalogId === catalogId)
  if (view === undefined || option === undefined) {
    return undefined
  }
  return view.slots.find((slot) => slot.useTag === option.useTag && slot.catalogId === '')
}
