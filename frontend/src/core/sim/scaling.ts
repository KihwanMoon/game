/**
 * 층 깊이 스케일 — `game/app/simulation/scaling.py` 의 이식.
 *
 * ## 무엇을 값 매기는가
 *
 * `pressure.ts` 의 층 체류 스케일과 **다른 축**이다. 이쪽은 "몇 층까지 내려왔는가" 를
 * 개체를 만들 때 한 번 값 매기고, 저쪽은 "이 층에서 몇 틱을 끌었는가" 를 매 틱 다시
 * 값 매긴다.
 *
 * ## 곱인가 합인가 — 곱이다
 *
 * 체류 스케일은 기준 공격력(`PressureTracker.baseAttacks`)에 퍼센트를 얹는데, 그 기준이
 * 이미 층 깊이로 스케일된 값이므로 두 축은 곱해진다. 시간을 끄는 대가가 "지금 이 적이
 * 가진 힘의 몇 %" 여야 깊은 층에서 압력이 희석되지 않기 때문이다 (docs/04 P-1).
 *
 * ## 층 1 이 기준이다
 *
 * 보너스는 `pctPerFloor * (floor - 1)` 이다. 층 1 에서 아무것도 곱하지 않아야
 * balance.json 의 적 스탯이 "층 1 의 그 적" 이라는 뜻을 그대로 갖는다. 전부 정수 퍼센트
 * 연산이며 내림 나눗셈으로 접는다 (R5).
 */

import { FIRST_FLOOR } from '../schemas'

export const DEFAULT_HP_PCT_PER_FLOOR = 25
export const DEFAULT_ATTACK_PCT_PER_FLOOR = 20

// 층 번호의 시작값은 schemas/room 이 정본이다 — min_floor 의 기본값과 같은 값이어야
// 하므로 여기서 다시 적지 않는다. 층 1 의 보너스는 0 이다.

const PERCENT_BASE = 100

/** balance.json 의 floor_scale 절을 그대로 담는 값. */
export interface FloorScale {
  readonly hpPctPerFloor: number
  readonly attackPctPerFloor: number
}

/** balance.json 의 floor_scale 절 원시 형태. */
export interface RawFloorScale {
  readonly enemy_hp_pct_per_floor?: number
  readonly enemy_attack_pct_per_floor?: number
}

/** 절이 통째로 빠졌을 때의 안전망. 값을 바꿀 자리가 아니다. */
export const DEFAULT_FLOOR_SCALE: FloorScale = {
  hpPctPerFloor: DEFAULT_HP_PCT_PER_FLOOR,
  attackPctPerFloor: DEFAULT_ATTACK_PCT_PER_FLOOR,
}

/**
 * floor_scale 절을 규칙 값으로 옮긴다.
 *
 * @param floorScale balance.json 의 floor_scale 절. 없으면 기본값을 쓴다.
 * @returns 읽어들인 규칙.
 * @throws 퍼센트가 음수인 경우. 층이 깊어질수록 적이 약해지면 층 진행이 난이도가 아니라
 *   보상이 된다.
 */
export function buildFloorScale(floorScale: RawFloorScale | undefined): FloorScale {
  const hpPct = floorScale?.enemy_hp_pct_per_floor ?? DEFAULT_HP_PCT_PER_FLOOR
  const attackPct = floorScale?.enemy_attack_pct_per_floor ?? DEFAULT_ATTACK_PCT_PER_FLOOR
  if (hpPct < 0 || attackPct < 0) {
    throw new RangeError(`층 스케일 퍼센트는 0 이상이어야 한다: ${hpPct}, ${attackPct}`)
  }
  return { hpPctPerFloor: hpPct, attackPctPerFloor: attackPct }
}

/**
 * 층 깊이가 만드는 보너스 퍼센트.
 *
 * @param pctPerFloor 한 층 내려갈 때마다 얹을 퍼센트.
 * @param floor 현재 층. 1 이 첫 층이다.
 * @returns 보너스 퍼센트. 층 1 에서는 0 이다.
 */
export function calculateDepthBonusPct(pctPerFloor: number, floor: number): number {
  return Math.max(0, floor - FIRST_FLOOR) * pctPerFloor
}

/**
 * 층 깊이 보너스를 얹은 능력치.
 *
 * @param base balance.json 에 적힌 층 1 기준값.
 * @param pctPerFloor 한 층 내려갈 때마다 얹을 퍼센트.
 * @param floor 현재 층.
 * @returns 내림 정수로 접은 능력치.
 */
export function calculateScaledStat(base: number, pctPerFloor: number, floor: number): number {
  const bonusPct = calculateDepthBonusPct(pctPerFloor, floor)
  return Math.floor((base * (PERCENT_BASE + bonusPct)) / PERCENT_BASE)
}

/** 층 스케일을 거친 최대 HP 와 공격력. */
export interface ScaledEnemyStats {
  readonly hpMax: number
  readonly attack: number
}

/** 스케일 대상이 되는 능력치. balance.json 의 적 항목이 이 모양을 만족한다. */
export interface ScalableStats {
  readonly hp_max: number
  readonly attack: number
}

/**
 * 적 한 종류의 층 스케일된 최대 HP 와 공격력.
 *
 * 개체를 만드는 모든 자리(방 배치·소환·추격자)가 이 함수를 거쳐야 한다. 한 자리라도
 * 빠뜨리면 같은 층에 서로 다른 기준의 적이 섞여, 도감이 적은 수치와 실제가 갈린다.
 *
 * @param stats balance.json 의 그 종류 항목.
 * @param scale 층 스케일 규칙.
 * @param floor 현재 층.
 * @returns 스케일된 최대 HP 와 공격력.
 */
export function getScaledEnemyStats(
  stats: ScalableStats,
  scale: FloorScale,
  floor: number,
): ScaledEnemyStats {
  return {
    hpMax: calculateScaledStat(stats.hp_max, scale.hpPctPerFloor, floor),
    attack: calculateScaledStat(stats.attack, scale.attackPctPerFloor, floor),
  }
}
