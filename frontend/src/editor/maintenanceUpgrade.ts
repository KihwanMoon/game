/**
 * 「더 좋게 만든다」 셋의 미리보기 (설계/4_아이템 §5).
 *
 * `maintenancePreview` 에서 갈라 나왔다 — 서버가 `maintenance_upgrade.py` 로 가른 것과
 * 같은 자리다. 저쪽 넷은 판단이 없고(파손이면 고치고, 빈 충전이면 채운다) 여기 셋은
 * **무엇이 더 좋은지를 골라야** 한다.
 *
 * **화면이 고르지는 않는다.** 「더 좋은 장비」의 저울은 서버에 있고(`bots/upgrade` 의
 * 무게표), 그것을 여기로 베끼면 밸런스 표가 두 벌이 된다 — 한쪽을 고치면 다른 쪽이
 * 조용히 옛 값으로 남고, 그때 미리보기는 **서버가 안 할 일을 할 것처럼** 적는다.
 *
 * **장비 교체의 저울은 파일 하나를 함께 읽는다.** `gear_priority.json` 을 파이썬과
 * 브라우저가 각자 직접 읽으므로(사본이 아니다), 미리보기가 세는 수와 서버가 실제로 바꾸는
 * 수가 같다. 예전에는 여기서 **후보만** 셌고, 그래서 「후보 3개」라 적어 놓고 서버는 하나만
 * 바꾸는 일이 있었다 — 실측값을 적는 화면이 실측이 아니었다.
 *
 * 남은 둘은 여전히 덜 센다.
 *
 * | 행동 | 세는 것 | 안 세는 것 |
 * |:--|:--|:--|
 * | 봉인 해제 | 값을 아는 첫 칸들 (`unsealCost`) | 그 뒤 칸 — 값이 오르는 폭은 서버가 안다 |
 * | 소모품 교체 | 충전이 확실히 더 큰 칸 | 충전이 같을 때 접사로 끊는 것 |
 *
 * 덜 세는 쪽으로 틀리게 두었다. 미리보기가 실제보다 크게 말하면 「한다더니 안 했다」가
 * 되고, 작게 말하면 「생각보다 더 했다」가 된다 — 조용한 자동화에서는 앞쪽이 더 나쁘다.
 */
import priorityFile from '@resources/balance/gear_priority.json'

import type { AffixView, ConsumableView, InventoryView, ItemView } from '../storage'

/** 퍼센트를 값으로 바꾸는 나눗셈 밑. 파이썬 `PERCENT_BASE` 와 같다. */
const PERCENT_BASE = 100

/** 양손무기가 보조 칸을 봉인하므로 두 칸을 함께 봐야 한다 — 파일이 정한다. */
const TWO_HANDED_SLOTS: ReadonlySet<string> = new Set(priorityFile.two_handed_slots)

/** 이만큼은 이겨야 바꾼다. 서버와 **같은 파일에서** 온다. */
const UPGRADE_MARGIN: number = priorityFile.margin

/**
 * 우선순위 하나의 저울.
 *
 * `_why` 처럼 숫자가 아닌 항목은 뺀다 — 파일이 자기 근거를 함께 들고 있어서다.
 *
 * @param priority 고른 우선순위.
 * @returns 스탯에서 무게로. 모르는 우선순위면 빈 표.
 */
function readWeights(priority: string): Readonly<Record<string, number>> {
  const table = (priorityFile.priorities as Record<string, Record<string, unknown>>)[priority]
  if (table === undefined) {
    return {}
  }
  return Object.fromEntries(
    Object.entries(table).filter((pair): pair is [string, number] => typeof pair[1] === 'number'),
  )
}

/**
 * 장비 하나가 이 저울에서 얼마나 값하는가.
 *
 * **파이썬 `compute_weighted_score` 와 같은 식이다** — 퍼센트를 실제 합산식과 같은
 * 방식으로(`기본값 × % / 100`) 값으로 바꾸고, 곱한 뒤에 나눈다. 정수만 쓴다 (R5).
 *
 * @param affixes 굴린 접사들.
 * @param attackRange 무기가 정하는 사거리. 접사가 아니라 필드다 (§2.2).
 * @param weights 스탯에서 무게로.
 * @param baseStats 퍼센트를 값으로 바꾸는 기준.
 * @returns 점수. 저주 접사가 있으면 음수일 수 있다.
 */
export function computeGearScore(
  affixes: readonly AffixView[],
  attackRange: number,
  weights: Readonly<Record<string, number>>,
  baseStats: Readonly<Record<string, number>>,
): number {
  let total = 0
  for (const affix of affixes) {
    const weight = weights[affix.stat] ?? 0
    if (weight === 0) {
      continue
    }
    total += weight * (affix.flat + Math.trunc(((baseStats[affix.stat] ?? 0) * affix.percent) / PERCENT_BASE))
  }
  return total + (weights.attack_range ?? 0) * attackRange
}

/** 한 행을 돌린 결과. `maintenancePreview` 의 것과 같은 모양이다. */
export interface UpgradeOutcome {
  readonly text: string
  readonly money: number
  readonly isActive: boolean
  /**
   * 잔액이 말라 못 한 일이 있는가.
   *
   * **문구에서 알아내지 않는다.** 「잔액」으로 시작하는지를 보고 판정하면, 문구를 한 글자
   * 고치는 순간 경고가 조용히 사라진다 — 판정과 표기가 같은 문자열을 나눠 쓰면 안 된다.
   */
  readonly isShort: boolean
}

/** 봉인 해제가 볼 것 하나. */
interface SealedItem {
  readonly cost: number
  readonly left: number
}

/**
 * 착용 장비 중 봉인이 남은 것들을 값 순으로 모은다.
 *
 * @param inventory 가방·장비.
 * @returns 값이 싼 것부터.
 */
export function listSealedWorn(inventory: InventoryView | undefined): readonly SealedItem[] {
  return (inventory?.equipment ?? [])
    .map((entry) => entry.item)
    .filter((item): item is ItemView => item !== null && item.sealedSlots > 0 && item.unsealCost > 0)
    .map((item) => ({ cost: item.unsealCost, left: item.sealedSlots }))
    .sort((one, two) => one.cost - two.cost)
}

/**
 * 봉인 해제를 돌려 본다.
 *
 * **아이템마다 한 칸씩만 센다.** 서버는 잔액이 마를 때까지 계속 열지만, 두 번째 칸의
 * 값은 첫 칸보다 비싸고 그 폭은 서버가 정한다(`compute_unseal_cost`). 값을 지어내
 * 세느니 **덜 세고 그렇게 적는다.**
 *
 * @param sealed 봉인이 남은 착용 장비들.
 * @param balance 지금 잔액.
 * @returns 무슨 일이 있었는지.
 */
export function runUnseal(sealed: readonly SealedItem[], balance: number): UpgradeOutcome {
  if (sealed.length === 0) {
    return { text: '지금이면 열 봉인이 없다', money: 0, isActive: false, isShort: false }
  }
  let left = balance
  let opened = 0
  let paid = 0
  for (const item of sealed) {
    if (left < item.cost) {
      continue
    }
    left -= item.cost
    paid += item.cost
    opened += 1
  }
  if (opened === 0) {
    const cheapest = sealed[0]?.cost ?? 0
    return {
      text: `잔액이 모자라 못 연다 (${String(cheapest)} 필요 · ${String(balance)} 있음)`,
      money: 0,
      isActive: false,
      isShort: true,
    }
  }
  // 아직 남은 칸이 있으면 그 사실을 적는다 — 서버는 잔액이 되는 만큼 더 연다.
  const rest = sealed.reduce((sum, item) => sum + item.left, 0) - opened
  const tail = rest > 0 ? ` · ${String(rest)}칸은 값이 올라 이 어림에서 뺐다` : ''
  return {
    text: `지금이면 ${String(opened)}칸 해제 (-${String(paid)})${tail}`,
    money: -paid,
    isActive: true,
    isShort: false,
  }
}

/**
 * 장비 교체를 돌려 본다.
 *
 * **후보만 센다.** 어느 것이 더 나은지는 서버의 저울이 정한다 — 그 무게표를 화면으로
 * 베끼면 밸런스가 두 벌이 되고, 한쪽을 고칠 때 다른 쪽이 조용히 옛 값으로 남는다.
 *
 * @param inventory 가방·장비.
 * @param priority 고른 우선순위. 화면에 그대로 적는다.
 * @returns 무슨 일이 있었는지.
 */
export function runUpgradeGear(
  inventory: InventoryView | undefined,
  priority: string,
  baseStats: Readonly<Record<string, number>>,
): UpgradeOutcome {
  const weights = readWeights(priority)
  const worn = new Map<string, ItemView>()
  for (const entry of inventory?.equipment ?? []) {
    if (entry.item !== null && !entry.item.isBroken && entry.slot !== null) {
      worn.set(entry.slot, entry.item)
    }
  }
  // 자리마다 제일 나은 후보 하나. 서버도 그렇게 고른다 — 같은 자리에 둘을 끼울 수 없다.
  const best = new Map<string, number>()
  for (const entry of inventory?.slots ?? []) {
    const item = entry.item
    if (
      item === null ||
      item.slot === null ||
      item.isBroken ||
      !item.canEquip ||
      item.hands === 'TWO' ||
      TWO_HANDED_SLOTS.has(item.slot)
    ) {
      continue
    }
    const current = worn.get(item.slot)
    if (current === undefined) {
      // 빈 자리는 교체가 아니다 — 낀 것이 있어야 「갈아 낀다」가 성립한다.
      continue
    }
    const gain =
      computeGearScore(item.affixes, item.attackRange, weights, baseStats) -
      computeGearScore(current.affixes, current.attackRange, weights, baseStats)
    if (gain < UPGRADE_MARGIN) {
      continue
    }
    best.set(item.slot, Math.max(best.get(item.slot) ?? 0, gain))
  }
  if (best.size === 0) {
    return { text: '지금이면 갈아 낄 것이 없다', money: 0, isActive: false, isShort: false }
  }
  const label = priority === 'DEFENSE' ? '방어' : '공격'
  return {
    text: `지금이면 ${label} 기준 ${String(best.size)}개 교체`,
    money: 0,
    isActive: true,
    isShort: false,
  }
}

/**
 * 소모품 교체를 돌려 본다.
 *
 * **충전이 확실히 더 큰 것만 센다.** 서버의 저울은 충전 용량이 먼저이고 같으면 접사로
 * 끊는데(§5), 뒤쪽까지 흉내 내면 같은 규칙이 두 곳에 살게 된다 — 앞쪽만 세고 그렇게
 * 적는다.
 *
 * **가득 찬 칸만 본다.** 쓰던 칸을 갈면 남은 충전이 사라지므로 서버도 건너뛴다.
 *
 * @param consumables 소모품 칸.
 * @returns 무슨 일이 있었는지.
 */
export function runUpgradeConsumable(consumables: ConsumableView | undefined): UpgradeOutcome {
  const options = consumables?.options ?? []
  let swapped = 0
  for (const slot of consumables?.slots ?? []) {
    if (slot.catalogId === '' || slot.charges < slot.chargeMax) {
      continue
    }
    const better = options.some(
      (option) =>
        option.useTag === slot.useTag && option.stock > 0 && option.charges > slot.chargeMax,
    )
    if (better) {
      swapped += 1
    }
  }
  if (swapped === 0) {
    return { text: '지금이면 갈아 낄 것이 없다', money: 0, isActive: false, isShort: false }
  }
  return {
    text: `지금이면 ${String(swapped)}칸 교체 (밀려난 것은 가방으로)`,
    money: 0,
    isActive: true,
    isShort: false,
  }
}
