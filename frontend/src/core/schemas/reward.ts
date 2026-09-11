/**
 * 층 보상 계약 — `game/schemas/reward.py` 의 이식 (GDD §2.2·§6.2).
 *
 * **핵심 고리의 한 칸이다.** GDD 가 적어 둔 고리는 `방 입장 → 전투 → 클리어 → 보상 선택
 * → 규칙 편집 → 다음 방` 인데 제품에는 보상 선택이 없었다 (2026-09-11 실제 신고:
 * 「5층 이후에 보상이 안 들어온거같아」 — 재 보니 층과 무관하게 원래 그랬다).
 *
 * **두 코어가 같은 표를 본다.** 전투는 브라우저가 돌리고 재시뮬은 서버가 하므로, 보상이
 * 바꾼 스탯을 양쪽이 같은 순서로 같은 만큼 얹지 않으면 같은 티켓이 두 결과를 낸다 (G3).
 *
 * **후보는 시드에서 나온다.** 화면이 스스로 굴려 그리고, 서버는 받은 선택이 그 층의
 * 후보였는지 되굴려 확인한다 — 없는 보상을 적어 보낼 자리가 없다 (설계/7 §4).
 */

import { DeterministicRng } from '../rng'

/** 한 번에 제시할 후보 수. 파이썬 `REWARD_OPTION_COUNT` 와 같아야 한다. */
export const REWARD_OPTION_COUNT = 3

/** 최대 HP 를 올리는 보상은 현재 HP 도 함께 올린다. */
export const STAT_HP_MAX = 'hp_max'

export const REWARD_MODULE = 'MODULE'
export const REWARD_STAT_AFFIX = 'STAT_AFFIX'
export const REWARD_RULE_SLOT = 'RULE_SLOT'
export const REWARD_POTION = 'POTION'

/** 보상 후보 하나. `targetStat` 은 바꿀 축의 이름이다. */
export interface RewardOption {
  readonly rewardId: string
  readonly kind: string
  readonly labelKo: string
  readonly targetStat: string
  readonly amount: number
}

/**
 * 파이썬 `REWARD_CATALOG` 와 **같은 순서**여야 한다. 굴림이 이 순서에서 뽑으므로, 줄을
 * 넣거나 옮기면 같은 시드가 다른 후보를 낸다.
 */
export const REWARD_CATALOG: readonly RewardOption[] = [
  { rewardId: 'module_slot', kind: REWARD_MODULE, labelKo: '확장 슬롯', targetStat: 'rule_slots', amount: 1 },
  { rewardId: 'module_core', kind: REWARD_MODULE, labelKo: '연산 코어', targetStat: 'cpu_budget', amount: 3 },
  { rewardId: 'affix_attack', kind: REWARD_STAT_AFFIX, labelKo: '예리함', targetStat: 'attack', amount: 2 },
  { rewardId: 'affix_defense', kind: REWARD_STAT_AFFIX, labelKo: '견고함', targetStat: 'defense', amount: 1 },
  { rewardId: 'affix_vitality', kind: REWARD_STAT_AFFIX, labelKo: '활력', targetStat: STAT_HP_MAX, amount: 10 },
  { rewardId: 'potion_pair', kind: REWARD_POTION, labelKo: '포션 꾸러미', targetStat: 'POTION', amount: 2 },
  { rewardId: 'rule_slot', kind: REWARD_RULE_SLOT, labelKo: '규칙 슬롯', targetStat: 'rule_slots', amount: 1 },
]

/** 굴림 축의 이름. 층마다 갈라야 앞 층의 굴림이 뒷 층 후보를 흔들지 않는다 (R5). */
const REWARD_STREAM = 'reward'

/**
 * id 로 후보를 찾는다.
 *
 * @param rewardId 보상 id.
 * @returns 찾은 후보. 없으면 undefined.
 */
export function findReward(rewardId: string): RewardOption | undefined {
  return REWARD_CATALOG.find((one) => one.rewardId === rewardId)
}

/**
 * 그 층이 제시할 후보 셋을 굴린다. 같은 티켓·같은 층이면 언제나 같은 셋이다.
 *
 * @param seed 티켓 시드.
 * @param floor 보상을 제시할 층.
 * @returns 후보들.
 */
export function buildFloorOffers(seed: number, floor: number): readonly RewardOption[] {
  const rng = new DeterministicRng(BigInt(seed)).createStream(`${REWARD_STREAM}/${String(floor)}`)
  const pool = [...REWARD_CATALOG]
  const picked: RewardOption[] = []
  const count = Math.min(REWARD_OPTION_COUNT, pool.length)
  for (let index = 0; index < count; index += 1) {
    picked.push(...pool.splice(rng.getBelow(pool.length), 1))
  }
  return picked
}

/**
 * 그 층에 들어가기 **전까지** 고른 보상들.
 *
 * **자기 층의 보상은 안 센다.** 보상은 그 층을 깬 뒤에 고르는 것이라, 같은 층에
 * 소급되면 재시뮬이 브라우저와 다른 판을 돈다 (G3).
 *
 * @param taken 층에서 보상 id 로.
 * @param beforeFloor 지금 들어가는 층.
 * @returns 층 번호 순의 보상들.
 */
export function listTakenBefore(
  taken: ReadonlyMap<number, string>,
  beforeFloor: number,
): readonly RewardOption[] {
  const found: RewardOption[] = []
  for (const floor of [...taken.keys()].sort((left, right) => left - right)) {
    if (floor >= beforeFloor) {
      continue
    }
    const option = findReward(taken.get(floor) ?? '')
    if (option !== undefined) {
      found.push(option)
    }
  }
  return found
}

/**
 * 그 층에 들어가기 전까지 고른 **스탯** 보상의 합.
 *
 * @param taken 층에서 보상 id 로.
 * @param beforeFloor 지금 들어가는 층.
 * @returns 축에서 더할 값으로.
 */
export function countFloorBonus(
  taken: ReadonlyMap<number, string>,
  beforeFloor: number,
): ReadonlyMap<string, number> {
  const bonus = new Map<string, number>()
  for (const option of listTakenBefore(taken, beforeFloor)) {
    if (option.kind === REWARD_POTION) {
      continue
    }
    bonus.set(option.targetStat, (bonus.get(option.targetStat) ?? 0) + option.amount)
  }
  return bonus
}

/**
 * 그 층에 들어가기 전까지 고른 **소모품** 보상의 합. 얹는 자리가 스탯과 다르다.
 *
 * @param taken 층에서 보상 id 로.
 * @param beforeFloor 지금 들어가는 층.
 * @returns 소모품 태그에서 더할 충전 수로.
 */
export function countChargeBonus(
  taken: ReadonlyMap<number, string>,
  beforeFloor: number,
): ReadonlyMap<string, number> {
  const bonus = new Map<string, number>()
  for (const option of listTakenBefore(taken, beforeFloor)) {
    if (option.kind !== REWARD_POTION) {
      continue
    }
    bonus.set(option.targetStat, (bonus.get(option.targetStat) ?? 0) + option.amount)
  }
  return bonus
}

/**
 * 서버가 보낸 절을 층→보상 id 표로 읽는다.
 *
 * @param raw 저장된 절. `{"3": "module_slot"}` 모양.
 * @returns 층에서 보상 id 로. 못 읽는 값은 버린다.
 */
export function readTaken(raw: unknown): ReadonlyMap<number, string> {
  const taken = new Map<number, string>()
  if (raw === null || typeof raw !== 'object') {
    return taken
  }
  for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
    const floor = Number(key)
    if (typeof value === 'string' && Number.isInteger(floor)) {
      taken.set(floor, value)
    }
  }
  return taken
}
