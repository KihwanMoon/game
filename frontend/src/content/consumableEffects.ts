/**
 * 소모품이 **무엇을 하는가** — 화면이 적는 말 (2026-09-11 요청).
 *
 * 소모품 한 칸에는 성격이 다른 셋이 겹쳐 있다.
 *
 *     끼면   끼고 있는 동안 붙는 옵션 (등급이 정한다)
 *     쓰면   한 장을 태울 때 일어나는 일
 *     자동   규칙 줄 없이 저절로 터지는 조건
 *
 * 셋을 다 안 적으면 「무엇을 들고 갈까」를 고를 근거가 없다 — 실제 요청이 그것이었다.
 *
 * **숫자를 여기 손으로 적지 않는다.** 코어 상수와 스킬 절에서 읽어 문장을 만든다. 값을
 * 고친 날 화면만 옛말을 하는 것이 이 저장소가 여러 번 겪은 사고다.
 */

import { SKILLS } from '../core/resources'
import { POTION_HEAL_DIVISOR } from '../core/sim/abilities'
import { GUARD_SKILL_ID } from '../core/sim/plan'
import {
  BLINK_STEPS,
  FLAME_COEF_PCT,
  FLAME_RADIUS,
  FOCUS_RANGE_BONUS,
  FOCUS_TICKS,
  GUARD_HP_PCT,
  SURROUNDED_COUNT,
} from '../core/sim/scrolls'
import { findSkill, loadSkillDefs, type RawSkill } from '../core/skills/catalog'

/** 방어 태세의 감소율과 유지 틱. 보호 주문서가 스킬과 같은 값을 쓴다. */
function readGuard(): { readonly pct: number; readonly ticks: number } {
  const guard = findSkill(loadSkillDefs(SKILLS.skills as readonly RawSkill[]), GUARD_SKILL_ID)
  return { pct: guard.guardPct, ticks: guard.guardTicks }
}

/**
 * 한 장을 태우면 무엇이 일어나는가.
 *
 * @param useTag 소모품 태그.
 * @returns 화면에 적을 한 줄. 모르는 태그면 빈 문자열 — 지어내지 않는다.
 */
export function formatUseEffect(useTag: string): string {
  if (useTag === 'POTION') {
    return `최대 체력의 1/${String(POTION_HEAL_DIVISOR)} 를 채운다`
  }
  if (useTag === 'SCROLL') {
    const guard = readGuard()
    return `방어 태세 — ${String(guard.ticks)}틱 동안 받는 피해 ${String(guard.pct)}% 감소`
  }
  if (useTag === 'BLINK') {
    return `적에게서 ${String(BLINK_STEPS)}칸까지 물러선다 — 이동은 한 칸씩이라 포위를 푼다`
  }
  if (useTag === 'FLAME') {
    return `반경 ${String(FLAME_RADIUS)} 안의 적에게 공격력의 ${String(FLAME_COEF_PCT)}% — 예고 없음`
  }
  if (useTag === 'FOCUS') {
    return `${String(FOCUS_TICKS)}틱 동안 사거리 +${String(FOCUS_RANGE_BONUS)}`
  }
  return ''
}

/**
 * **언제 저절로 터지는가** — `core/sim/scrolls.TRIGGERS` 를 사람 말로 옮긴 것.
 *
 * 규칙 줄 없이 터지므로, 조건을 화면이 못 적으면 들고 가는 사람에게는 「언젠가 사라지는
 * 물건」이 된다. 여기도 **숫자를 손으로 안 적는다** — 문턱을 고친 날 화면만 옛말을 한다.
 *
 * @param useTag 소모품 태그.
 * @returns 화면에 적을 한 줄. 자동 발동이 없는 태그(물약)면 빈 문자열.
 */
export function formatTrigger(useTag: string): string {
  if (useTag === 'SCROLL') {
    return `체력 ${String(GUARD_HP_PCT)}% 아래에서 적이 붙어 있으면`
  }
  if (useTag === 'BLINK' || useTag === 'FLAME') {
    return `인접한 적이 ${String(SURROUNDED_COUNT)} 이상이면 (포위)`
  }
  if (useTag === 'FOCUS') {
    return `적이 ${String(FOCUS_RANGE_BONUS)}칸 차이로 안 닿으면`
  }
  return ''
}
