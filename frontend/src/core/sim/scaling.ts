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

export const DEFAULT_MULT_PCT_PER_FLOOR = 120

// 층 번호의 시작값은 schemas/room 이 정본이다 — min_floor 의 기본값과 같은 값이어야
// 하므로 여기서 다시 적지 않는다. 층 1 의 보너스는 0 이다.

const PERCENT_BASE = 100

/** balance.json 의 floor_scale 절을 그대로 담는 값. */
export interface FloorScale {
  readonly multPctPerFloor: number
  /**
   * 선공에 더할 값. **층이 아니라 플레이어를 따라간다** — 파일에서 오지 않고 판을 짤 때
   * 계산된다 (`services/runBattle.buildEngine`). 여기 얹어 두는 이유는 개체를 만드는 세
   * 자리가 이미 이 값을 들고 다니기 때문이고, 따로 실어 나르면 언젠가 한 자리가 빠진다.
   */
  readonly initiativeShift: number
}

/** balance.json 의 floor_scale 절 원시 형태. */
export interface RawFloorScale {
  readonly enemy_mult_pct_per_floor?: number
  /** 층을 깰 때 돌려주는 최대체력의 퍼센트. 파이썬 `read_floor_heal_pct` 와 같은 자리다. */
  readonly floor_heal_pct?: number
}

/** 절이 통째로 빠졌을 때의 안전망. 값을 바꿀 자리가 아니다. */
export const DEFAULT_FLOOR_SCALE: FloorScale = {
  multPctPerFloor: DEFAULT_MULT_PCT_PER_FLOOR,
  initiativeShift: 0,
}

/**
 * floor_scale 절을 규칙 값으로 옮긴다.
 *
 * @param floorScale balance.json 의 floor_scale 절. 없으면 기본값을 쓴다.
 * @returns 읽어들인 규칙.
 * @throws 퍼센트가 음수인 경우. 층이 깊어질수록 적이 약해지면 층 진행이 난이도가 아니라
 *   보상이 된다.
 */
export function buildFloorScale(
  floorScale: RawFloorScale | undefined,
  initiativeShift = 0,
): FloorScale {
  const mult = Math.trunc(Number(floorScale?.enemy_mult_pct_per_floor ?? DEFAULT_MULT_PCT_PER_FLOOR))
  if (mult < PERCENT_BASE) {
    throw new Error(`층 스케일 배율은 100 이상이어야 한다: ${String(mult)}`)
  }
  return { multPctPerFloor: mult, initiativeShift }
}

/**
 * 층 깊이를 복리로 얹은 능력치 (e3).
 *
 * **층마다 내림으로 접는다** — 파이썬과 같은 줄이다. 거듭제곱을 한 번에 계산하면
 * 부동소수가 끼어 두 코어가 마지막 자리에서 갈린다 (R5).
 *
 * @param base 층 1 기준값.
 * @param multPctPerFloor 한 층 내려갈 때마다 곱할 퍼센트 (110 = ×1.1).
 * @param floor 현재 층.
 * @returns 내림 정수로 접은 능력치.
 */
export function calculateScaledStat(base: number, multPctPerFloor: number, floor: number): number {
  let value = base
  for (let step = 0; step < Math.max(0, floor - FIRST_FLOOR); step += 1) {
    value = Math.floor((value * multPctPerFloor) / PERCENT_BASE)
  }
  return value
}

/** 조정을 거친 최대 HP · 공격력 · 선공. */
export interface ScaledEnemyStats {
  readonly hpMax: number
  readonly attack: number
  readonly initiative: number
}

/** 조정 대상이 되는 능력치. balance.json 의 적 항목이 이 모양을 만족한다. */
export interface ScalableStats {
  readonly hp_max: number
  readonly attack: number
  readonly initiative: number
}

/**
 * 플레이어를 따라 옮긴 선공 (2026-09-14) — 파이썬 `get_shifted_initiative` 의 이식.
 *
 * **선공은 절대값이 아니라 밴드다.** 적 선공은 20~78 로 고정인데 플레이어 선공은
 * `50 + 2×민첩` 으로 한계 없이 자란다. 그래서 민첩을 올린 캐릭터에게는 5층부터 모든 적이
 * 느려지고, 레벨 20 을 넘기면 전 층에서 그렇게 된다 — 그 상태에서 `적 선공 > 내 선공` 은
 * 영영 거짓인 항이고, 그것을 읽는 규칙은 cpu 만 먹는다.
 *
 * @param base balance.json 에 적힌 그 종류의 선공.
 * @param scale 옮길 양을 담은 규칙.
 * @returns 옮긴 선공. 0 아래로는 안 내려간다.
 */
export function getShiftedInitiative(base: number, scale: FloorScale): number {
  return Math.max(0, base + scale.initiativeShift)
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
    hpMax: calculateScaledStat(stats.hp_max, scale.multPctPerFloor, floor),
    attack: calculateScaledStat(stats.attack, scale.multPctPerFloor, floor),
    initiative: getShiftedInitiative(stats.initiative, scale),
  }
}
