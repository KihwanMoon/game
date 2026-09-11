/**
 * 고른 층 보상을 개체에 얹는다 — `game/app/simulation/floor_rewards.py` 의 이식.
 *
 * **두 코어가 같은 자리에서 같은 만큼 얹어야 한다.** 전투는 브라우저가 돌리고 재시뮬은
 * 서버가 하므로, 한쪽만 얹으면 같은 티켓이 두 결과를 낸다 (G3).
 *
 * **그 층에 들어가기 전까지 고른 것만 산다.** 보상은 층을 깬 뒤에 고르는 것이라, 같은
 * 층에 소급되면 이미 끝난 전투가 다르게 재현된다.
 */

import { STAT_HP_MAX, countChargeBonus, countFloorBonus } from '../schemas/reward'
import type { Entity } from './state'

/**
 * 보상이 만질 수 있는 개체 축. **표에 없는 축은 조용히 무시한다** — 카탈로그가 앞서
 * 나갔을 때 엉뚱한 필드를 만드는 것보다 안 얹고 넘어가는 편이 낫다.
 */
const ENTITY_STATS: ReadonlyMap<string, keyof Entity> = new Map([
  ['attack', 'attack'],
  ['defense', 'defense'],
  [STAT_HP_MAX, 'hpMax'],
  ['cpu_budget', 'cpuBudget'],
])

/**
 * 이 층에 들어가는 개체에 지금까지 고른 보상을 얹는다.
 *
 * **최대 HP 는 현재 HP 도 함께 올린다.** 그러지 않으면 고른 그 순간에는 아무 일도 안
 * 일어나 보상으로 안 읽힌다.
 *
 * @param entity 이 층을 도는 개체.
 * @param taken 층에서 보상 id 로.
 * @param floor 지금 들어가는 층.
 */
export function applyFloorRewards(
  entity: Entity,
  taken: ReadonlyMap<number, string>,
  floor: number,
): void {
  const bonus = countFloorBonus(taken, floor)
  for (const stat of [...bonus.keys()].sort()) {
    const field = ENTITY_STATS.get(stat)
    const amount = bonus.get(stat) ?? 0
    if (field === undefined) {
      continue
    }
    // 수치 축만 만진다. 표가 가리키는 것이 수가 아니면 얹을 자리가 아니다.
    const current = entity[field]
    if (typeof current === 'number') {
      ;(entity[field] as number) = current + amount
    }
  }
  const vitality = bonus.get(STAT_HP_MAX) ?? 0
  if (vitality > 0) {
    entity.hp += vitality
  }
  const charges = countChargeBonus(taken, floor)
  for (const useTag of [...charges.keys()].sort()) {
    entity.consumables.set(useTag, (entity.consumables.get(useTag) ?? 0) + (charges.get(useTag) ?? 0))
  }
}

/**
 * 층을 넘으며 새로 얻은 최대 HP. **인계 HP 에 얹을 값이다.**
 *
 * @param taken 층에서 보상 id 로.
 * @param floor 지금 들어가는 층.
 * @param previousFloor 직전 방의 층.
 * @returns 더할 HP. 없으면 0.
 */
export function countHpGain(
  taken: ReadonlyMap<number, string>,
  floor: number,
  previousFloor: number,
): number {
  const now = countFloorBonus(taken, floor).get(STAT_HP_MAX) ?? 0
  const before = countFloorBonus(taken, previousFloor).get(STAT_HP_MAX) ?? 0
  return Math.max(0, now - before)
}
