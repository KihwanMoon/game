/**
 * 힘·민첩·지능을 전투 스탯으로 옮긴다 (결정 #51).
 *
 * **파이썬 `game/app/progression/attributes.py` 의 이식이다.** 실제 전투 입력은 서버가
 * 계산해 티켓에 실어 보내므로 이 사본은 **찍기 전에 보여 주는 미리보기**에만 쓰인다.
 * 그래도 갈라지면 안 된다 — 유저는 찍기 전에 본 숫자를 믿고 찍는다. 골든의
 * `attributes` 절이 두 사본을 묶는다.
 *
 * 축마다 여는 것이 다르다. 세 축이 모두 공격력으로 수렴하면 배분이 선택이 아니라
 * 계산이 되고, 그러면 포인트를 주는 의미가 사라진다 (P3).
 */

/** 힘 1점이 여는 것. */
export const ATTACK_PER_STR = 1
export const HP_MAX_PER_STR = 4

/** 민첩 1점이 여는 것. */
export const INITIATIVE_PER_DEX = 2
export const DEFENSE_PER_DEX = 1

/** 지능. CPU 는 3점당 1이며 표현력이므로 상한이 있다. */
export const INT_PER_CPU = 3
export const MAX_CPU_FROM_INT = 8

/** 지능 1점당 스킬위력 퍼센트. 정수 퍼센트로만 다룬다 (R5). */
export const SKILL_POWER_PCT_PER_INT = 2

/** 스킬위력의 기준값. 100 이 "계수 그대로" 다. */
export const BASE_SKILL_POWER_PCT = 100

/** 배분한 능력치가 만들어 내는 전투 스탯 가산분. */
export interface AttributeBonus {
  readonly attack: number
  readonly hpMax: number
  readonly initiative: number
  readonly defense: number
  readonly cpuBudget: number
  readonly skillPowerPct: number
}

/**
 * 배분표를 전투 스탯 가산분으로 바꾼다.
 *
 * 음수 배분은 0 으로 본다. 저장된 값이 손상돼도 스탯이 깎이지는 않아야 한다.
 *
 * @param stats 축에서 배분 점수로의 대응표.
 * @returns 가산분.
 */
export function buildAttributeBonus(stats: Readonly<Record<string, number>>): AttributeBonus {
  const strength = Math.max(0, Math.trunc(stats.str ?? 0))
  const dexterity = Math.max(0, Math.trunc(stats.dex ?? 0))
  const intellect = Math.max(0, Math.trunc(stats.int ?? 0))
  return {
    attack: strength * ATTACK_PER_STR,
    hpMax: strength * HP_MAX_PER_STR,
    initiative: dexterity * INITIATIVE_PER_DEX,
    defense: dexterity * DEFENSE_PER_DEX,
    cpuBudget: Math.min(MAX_CPU_FROM_INT, Math.floor(intellect / INT_PER_CPU)),
    skillPowerPct: BASE_SKILL_POWER_PCT + intellect * SKILL_POWER_PCT_PER_INT,
  }
}
