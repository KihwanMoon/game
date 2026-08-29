/**
 * 전투 수식 — `game/app/combat/damage.py` 의 이식 (TDD §8, GDD §6.4).
 *
 * 전량 정수 연산이다. TDD §8 은 계수를 실수로 적었지만 TDD §12 R5 는 정수 연산 원칙을
 * 요구한다. 충돌하므로 정수 쪽을 택했다 — 부동소수는 플랫폼마다 결과가 갈려 골든
 * 리플레이를 무너뜨린다. 계수는 balance.json 에 정수 퍼센트로 들어 있다.
 *
 * 나눗셈은 전부 `divideFloor` 를 거친다. 자바스크립트의 `/` 는 실수 나눗셈이라 그대로
 * 두면 HP 가 소수점을 갖는다.
 */

/** 퍼센트의 기준값. */
const PERCENT_BASE = 100

/** damage_formula 절이 담고 있는 상수들. */
export interface DamageRules {
  readonly softCapBase: number
  readonly softCapPerFloor: number
  readonly surroundStepPct: number
  readonly surroundCapPct: number
  readonly minDamage: number
}

/** balance.json 의 damage_formula 절 원시 형태. */
export interface RawDamageFormula {
  readonly soft_cap_base: number
  readonly soft_cap_per_floor: number
  readonly surround_step_pct: number
  readonly surround_cap_pct: number
  readonly min_damage: number
}

/**
 * 파이썬 `//` 와 같은 내림 나눗셈.
 *
 * @param numerator 나뉠 값.
 * @param denominator 나눌 값.
 * @returns 몫을 음의 무한대 쪽으로 내린 정수.
 */
export function divideFloor(numerator: number, denominator: number): number {
  return Math.floor(numerator / denominator)
}

/**
 * balance.json 의 damage_formula 절에서 상수를 뽑는다.
 *
 * @param raw damage_formula 객체.
 * @returns 수식 상수 묶음.
 */
export function buildDamageRules(raw: RawDamageFormula): DamageRules {
  return {
    softCapBase: raw.soft_cap_base,
    softCapPerFloor: raw.soft_cap_per_floor,
    surroundStepPct: raw.surround_step_pct,
    surroundCapPct: raw.surround_cap_pct,
    minDamage: raw.min_damage,
  }
}

/** `calculateDamage` 가 받는 값들. 인자가 여섯이라 이름으로 받는다. */
export interface DamageInput {
  /** 공격자의 최종 공격력. */
  readonly attack: number
  /** 스킬 계수. 정수 퍼센트다 (100 = 1.0배). */
  readonly skillCoefPct: number
  /** 피격자의 최종 방어력. */
  readonly defense: number
  /** 현재 층. 1 부터 센다. */
  readonly floor: number
  /** 피격자에게 인접한 적 수. 1 이면 가산 없음. */
  readonly adjacentEnemies: number
  /** 수식 상수. */
  readonly rules: DamageRules
}

/**
 * 한 번의 타격이 주는 피해를 계산한다.
 *
 * 방어력은 감쇠식을 쓰고 층 항을 포함한다 — 층이 오를수록 방어 효율이 낮아져 스탯
 * 뭉개기가 억제된다 (GDD §7).
 *
 * @param input 공격자·피격자·층·포위 상황.
 * @returns 최소 minDamage 이상의 피해량.
 */
export function calculateDamage(input: DamageInput): number {
  const { attack, skillCoefPct, defense, floor, adjacentEnemies, rules } = input
  const denominator = defense + rules.softCapBase + rules.softCapPerFloor * floor
  const raw = divideFloor(attack * skillCoefPct * (denominator - defense), PERCENT_BASE * denominator)
  const surroundPct = Math.min(
    rules.surroundCapPct,
    PERCENT_BASE + rules.surroundStepPct * (Math.max(1, adjacentEnemies) - 1),
  )
  return Math.max(rules.minDamage, divideFloor(raw * surroundPct, PERCENT_BASE))
}
