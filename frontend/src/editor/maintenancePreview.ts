/**
 * 정비 규칙의 미리보기 — **지금 이대로면 무엇이 일어나는가** (설계/4_아이템 §5).
 *
 * 정비는 티켓이 닫힐 때 서버가 조용히 돌린다. 그래서 예전에는 규칙을 켜 놓고 판을 한 번
 * 돌고 나서야 무엇이 사라졌는지 알았고, 「왜 돈이 줄었지」·「내 장비 어디 갔지」가 됐다.
 * 조용한 자동화의 값은 그것이다.
 *
 * **행마다 한 줄로 답한다.** 「보통 장비를 버린다」가 아니라 「지금이면 2개 버림」이다 —
 * 조건문에 각 항의 실측값을 병기하는 것과 같은 규칙이며(GDD §8.2, P1), 규칙표가 그렇게
 * 적기 때문에 그 형제인 정비도 그렇게 적어야 한다.
 *
 * **어림이라고 화면이 말한다.** 정본은 서버이고, 이 줄은 *지금* 가방으로 잰 것이다 —
 * 정비가 실제로 도는 것은 판이 끝난 뒤이므로 그 사이에 가방도 잔액도 바뀐다. 어림을
 * 확정처럼 적으면 틀렸을 때 화면이 거짓말한 것이 된다.
 *
 * 순수 값이다. 계산은 `game/api/maintenance_service.py` 의 순서를 그대로 따른다 — 행을
 * 위에서 아래로 돌리며 **잔액을 이어서 깎는다.** 각 행을 따로 재면 「셋 다 도는데 돈은
 * 한 번치만 있는」 배치가 전부 도는 것으로 보인다.
 */
import type { ConsumableView, InventoryView, MaintenanceRowView } from '../storage'

import { DISCARD_ALL } from './maintenanceRules'
import {
  listSealedWorn,
  runUnseal,
  runUpgradeConsumable,
  runUpgradeGear,
} from './maintenanceUpgrade'

/** 미리보기 한 줄. */
export interface PreviewRow {
  /** 몇 번째 행인가. */
  readonly index: number
  /** 무엇이 일어나는가. 할 일이 없으면 그렇게 적는다. */
  readonly text: string
  /** 이 행이 잔액을 얼마나 움직이는가. 음수면 나간다. */
  readonly moneyDelta: number
  /** 이 행이 실제로 하는 일이 있는가. 없으면 화면이 명도로 가른다. */
  readonly isActive: boolean
}

/** 미리보기 전체. */
export interface MaintenancePreview {
  readonly rows: readonly PreviewRow[]
  /** 잔액이 얼마나 움직이는가. */
  readonly moneyDelta: number
  /** 지금 잔액. */
  readonly balance: number
  /** 정비가 끝났을 때의 잔액. */
  readonly balanceAfter: number
  /** 잔액이 말라 못 한 일이 있는가. 있으면 화면이 그 사실을 적는다. */
  readonly isShort: boolean
}

/** 행 하나를 돌린 결과. */
interface RowOutcome {
  readonly text: string
  readonly money: number
  /**
   * 실제로 한 일이 있는가.
   *
   * **문구에서 알아내지 않는다.** 「지금이면」으로 시작하는지를 보고 판정하면, 문구를
   * 한 글자 고치는 순간 화면의 명도가 조용히 뒤집힌다 — 판정과 표기가 같은 문자열을
   * 나눠 쓰면 안 된다.
   */
  readonly isActive: boolean
}

/** 가방에 있는 장비 하나 — 버리기가 보는 두 축만 담는다. */
interface PreviewBagItem {
  readonly grade: string
  readonly isRecovered: boolean
}

/** 미리보기가 돌리는 동안의 상태. 원본을 안 건드린다. */
interface PreviewState {
  balance: number
  /**
   * 아직 안 버린 가방 장비.
   *
   * **등급별 개수가 아니라 물건 목록이다.** 「전부 버리기」가 생기면서 세는 축이 둘이
   * 됐기 때문이다 — 등급으로 버릴 때는 되찾은 것을 빼고 세고, 전부 버릴 때는 그것까지
   * 센다. 개수 두 벌을 나란히 들면 한 행이 버린 것이 다른 축에서 안 줄어든다.
   */
  bagItems: readonly PreviewBagItem[]
  /** 아직 안 고친 파손 착용 장비 수. */
  brokenCount: number
  repairCost: number
  /** 아직 안 채운 칸들 — (모자란 충전, 값). */
  readonly refills: { missing: number; cost: number }[]
  /** 아직 안 판 재고 — (개수, 하나 값). */
  readonly stock: { count: number; price: number }[]
  isShort: boolean
  /**
   * 「더 좋게 만든다」 셋이 읽는 원본.
   *
   * 저쪽은 **덜어 내는 일이 아니라 고르는 일**이라 개수만으로는 못 센다 — 봉인은 값이
   * 아이템마다 다르고, 교체는 어느 자리에 무엇이 끼워져 있는지를 봐야 한다.
   */
  readonly inventory: InventoryView | undefined
  readonly consumables: ConsumableView | undefined
  /** 퍼센트 접사를 값으로 바꾸는 기준. 장비 교체의 저울이 쓴다. */
  readonly baseStats: Readonly<Record<string, number>>
}

/**
 * 지금 상태에서 미리보기가 돌릴 판을 짠다.
 *
 * @param inventory 가방·장비. 없으면 버리기·복구가 할 일이 없다.
 * @param consumables 소모품 칸. 없으면 보충·팔기가 할 일이 없다.
 * @returns 돌릴 판.
 */
function buildState(
  inventory: InventoryView | undefined,
  consumables: ConsumableView | undefined,
  baseStats: Readonly<Record<string, number>>,
): PreviewState {
  // 되찾음 표시를 **버리지 않고 담아 둔다.** 등급으로 버릴 때는 서버가 그것을 남기고
  // (`apply_discard_rule`), 「전부」일 때는 그 보호를 함께 내려놓는다 — 여기서 미리
  // 걸러 내면 두 경우를 한 상태로 못 그린다.
  const bagItems: PreviewBagItem[] = []
  for (const entry of inventory?.slots ?? []) {
    const item = entry.item
    if (item === null) {
      continue
    }
    bagItems.push({ grade: item.grade, isRecovered: item.isRecovered })
  }
  const brokenCount = (inventory?.equipment ?? []).filter(
    (entry) => entry.item?.isBroken === true,
  ).length
  const refills = (consumables?.slots ?? [])
    .filter((slot) => slot.catalogId !== '' && slot.charges < slot.chargeMax && slot.refillCost > 0)
    .map((slot) => ({ missing: slot.chargeMax - slot.charges, cost: slot.refillCost }))
  const stock = (consumables?.options ?? [])
    .filter((option) => option.stock > 0)
    .map((option) => ({ count: option.stock, price: option.sellPrice }))
  return {
    // 잔액의 정본은 가방 쪽이다 — 둘 다 같은 지갑을 보지만, 소모품 화면은 가방보다
    // 늦게 읽힐 수 있다. 하나를 골라 두지 않으면 줄마다 다른 잔액을 보게 된다.
    balance: inventory?.balance ?? consumables?.balance ?? 0,
    bagItems,
    brokenCount,
    repairCost: inventory?.repairCost ?? 0,
    refills,
    stock,
    isShort: false,
    inventory,
    consumables,
    baseStats,
  }
}

/**
 * 이 인자가 이 물건을 버리는가. **서버의 판정과 같은 식이어야 한다.**
 *
 * 여기서 갈리면 미리보기가 서버와 다른 수를 세고, 그때 사람은 화면을 믿고 규칙을 짠다.
 *
 * @param item 가방의 물건.
 * @param grade 버리기의 인자. `DISCARD_ALL` 이면 등급도 되찾음도 안 본다.
 * @returns 버리면 참.
 */
function checkDiscarded(item: PreviewBagItem, grade: string): boolean {
  if (grade === DISCARD_ALL) {
    return true
  }
  return item.grade === grade && !item.isRecovered
}

/**
 * 버리기 한 행을 돌린다.
 *
 * @param state 지금 판.
 * @param grade 버릴 등급. `DISCARD_ALL` 이면 가방의 장비 전부다.
 * @returns 무슨 일이 있었는지와 잔액 변화.
 */
function runDiscard(state: PreviewState, grade: string): RowOutcome {
  const kept = state.bagItems.filter((item) => !checkDiscarded(item, grade))
  const count = state.bagItems.length - kept.length
  if (count === 0) {
    return { text: '지금이면 버릴 것이 없다', money: 0, isActive: false }
  }
  state.bagItems = kept
  // 버리기는 돈이 안 된다 — 파는 것이 아니라 없애는 것이다. 그 사실을 적어 둔다,
  // 「버리면 돈이 되겠지」로 짜는 사람이 있기 때문이다.
  const what = grade === DISCARD_ALL ? '가방을 비운다 · ' : ''
  return {
    text: `지금이면 ${what}${String(count)}개 버림 (값은 안 받는다)`,
    money: 0,
    isActive: true,
  }
}

/**
 * 복구 한 행을 돌린다. 잔액이 마르면 거기서 멈춘다 — 서버와 같다.
 *
 * @param state 지금 판.
 * @returns 무슨 일이 있었는지와 잔액 변화.
 */
function runRepair(state: PreviewState): RowOutcome {
  if (state.brokenCount === 0) {
    return { text: '지금이면 파손된 착용 장비가 없다', money: 0, isActive: false }
  }
  if (state.repairCost <= 0) {
    return { text: '복구 값을 못 읽었다 — 서버가 정한다', money: 0, isActive: false }
  }
  const affordable = Math.min(state.brokenCount, Math.floor(state.balance / state.repairCost))
  if (affordable === 0) {
    state.isShort = true
    return {
      text: `잔액이 모자라 못 고친다 (${String(state.repairCost)} 필요 · ${String(state.balance)} 있음)`,
      money: 0,
      isActive: false,
    }
  }
  const paid = affordable * state.repairCost
  state.balance -= paid
  const left = state.brokenCount - affordable
  state.brokenCount = left
  if (left > 0) {
    state.isShort = true
  }
  const tail = left > 0 ? ` · 잔액이 말라 ${String(left)}개는 남는다` : ''
  return {
    text: `지금이면 ${String(affordable)}개 복구 (-${String(paid)})${tail}`,
    money: -paid,
    isActive: true,
  }
}

/**
 * 보충 한 행을 돌린다.
 *
 * **서버는 반쯤 채우지 않는다** — 한 칸을 가득 채울 돈이 없으면 그 칸을 건너뛴다
 * (`apply_refill_rule`). 건너뛰기라 뒤 칸은 계속 본다.
 *
 * @param state 지금 판.
 * @returns 무슨 일이 있었는지와 잔액 변화.
 */
function runRefill(state: PreviewState): RowOutcome {
  if (state.refills.length === 0) {
    return { text: '지금이면 채울 칸이 없다', money: 0, isActive: false }
  }
  let filled = 0
  let paid = 0
  let skipped = 0
  for (const slot of state.refills) {
    if (state.balance < slot.cost) {
      skipped += 1
      continue
    }
    state.balance -= slot.cost
    paid += slot.cost
    filled += slot.missing
    slot.missing = 0
    slot.cost = 0
  }
  if (filled === 0) {
    state.isShort = true
    return { text: `잔액이 모자라 못 채운다 (${String(state.balance)} 있음)`, money: 0, isActive: false }
  }
  if (skipped > 0) {
    state.isShort = true
  }
  const tail = skipped > 0 ? ` · 잔액이 말라 ${String(skipped)}칸은 건너뛴다` : ''
  return {
    text: `지금이면 ${String(filled)}충전 보충 (-${String(paid)})${tail}`,
    money: -paid,
    isActive: true,
  }
}

/**
 * 재고 팔기 한 행을 돌린다.
 *
 * @param state 지금 판.
 * @returns 무슨 일이 있었는지와 잔액 변화.
 */
function runSell(state: PreviewState): RowOutcome {
  let sold = 0
  let earned = 0
  for (const entry of state.stock) {
    sold += entry.count
    earned += entry.count * entry.price
    entry.count = 0
  }
  if (sold === 0) {
    return { text: '지금이면 팔 재고가 없다', money: 0, isActive: false }
  }
  state.balance += earned
  return {
    text: `지금이면 ${String(sold)}개 판매 (+${String(earned)})`,
    money: earned,
    isActive: true,
  }
}

/**
 * 행 하나를 돌린다.
 *
 * @param state 지금 판.
 * @param row 돌릴 행.
 * @returns 무슨 일이 있었는지와 잔액 변화.
 */
function runRow(state: PreviewState, row: MaintenanceRowView): RowOutcome {
  switch (row.action) {
    case 'DISCARD':
      return runDiscard(state, row.grade)
    case 'REPAIR':
      return runRepair(state)
    case 'REFILL':
      return runRefill(state)
    case 'SELL_STOCK':
      return runSell(state)
    case 'UNSEAL': {
      const outcome = runUnseal(listSealedWorn(state.inventory), state.balance)
      state.balance += outcome.money
      state.isShort = state.isShort || outcome.isShort
      return outcome
    }
    case 'UPGRADE_GEAR':
      return runUpgradeGear(state.inventory, row.grade, state.baseStats)
    case 'UPGRADE_CONSUMABLE':
      return runUpgradeConsumable(state.consumables)
    default:
      // 어휘 밖이다. 검증이 이미 막고 있으므로 여기서는 「안 돈다」만 말한다.
      return { text: '모르는 행동이라 안 돈다', money: 0, isActive: false }
  }
}

/**
 * 정비 규칙을 지금 상태에 돌려 본다.
 *
 * **서버를 안 부른다.** 정비 실행 라우트는 없고, 있어서도 안 된다 — 열면 「런 중에
 * 정비를 돌려 가방을 바꾸는」 길이 생긴다 (`routes/maintenance`). 그래서 이것은 화면이
 * 같은 규칙을 다시 계산한 **어림**이고, 화면이 그렇게 적는다.
 *
 * @param rows 정비 행들.
 * @param inventory 지금 가방·장비.
 * @param consumables 지금 소모품 칸.
 * @returns 행마다 한 줄과 잔액 변화.
 */
export function buildMaintenancePreview(
  rows: readonly MaintenanceRowView[],
  inventory: InventoryView | undefined,
  consumables: ConsumableView | undefined,
  baseStats: Readonly<Record<string, number>> = {},
): MaintenancePreview {
  const state = buildState(inventory, consumables, baseStats)
  const balance = state.balance
  const previewRows = rows.map((row, index) => {
    const outcome = runRow(state, row)
    return {
      index,
      text: outcome.text,
      moneyDelta: outcome.money,
      isActive: outcome.isActive,
    }
  })
  return {
    rows: previewRows,
    moneyDelta: state.balance - balance,
    balance,
    balanceAfter: state.balance,
    isShort: state.isShort,
  }
}

/**
 * 정비가 아무것도 안 한다는 것을 한 줄로.
 *
 * @param preview 미리보기.
 * @returns 하는 일이 하나도 없으면 참.
 */
export function checkPreviewIdle(preview: MaintenancePreview): boolean {
  return preview.rows.every((row) => !row.isActive)
}

/**
 * 잔액 변화를 부호와 함께 적는다.
 *
 * @param delta 잔액 변화.
 * @returns `-70` · `+120` · `0`.
 */
export function formatMoneyDelta(delta: number): string {
  if (delta === 0) {
    return '0'
  }
  return `${delta > 0 ? '+' : '−'}${String(Math.abs(delta))}`
}

/** 정비 행이 안 실린 미리보기가 있어야 할 자리. 부르는 쪽이 이것을 쓴다. */
export const EMPTY_PREVIEW: MaintenancePreview = {
  rows: [],
  moneyDelta: 0,
  balance: 0,
  balanceAfter: 0,
  isShort: false,
}
