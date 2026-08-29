/**
 * 프리셋과 규칙표를 JSON 절로 굽고 되읽는다 — `game/schemas/meta_save.py` 의 이식이다.
 *
 * 파이썬 정본과 **키 이름·생략 규칙까지** 같아야 한다. 우변이 `lhs_param` 없이 나가는 것,
 * 규칙 절이 `cpu_cost`·`set_flag` 로 적히는 것이 그 계약이다. 한쪽이 키 하나를 더 적으면
 * 공유 코드는 열리지만 규칙표가 미묘하게 달라진다 — 형식이 어긋나는 것보다 나쁘다.
 *
 * 읽는 쪽은 `core/schemas/ruleset.ts` 의 `parseRuleSet` 을 그대로 쓴다. 사본을 두면
 * 비교 연산자 목록 같은 것이 두 곳에서 갈린다.
 */
import type { Rhs, Rule, RuleSet, RawRuleSet, Term } from '../core/schemas'
import { isStatRef, parseRuleSet, RHS_STAT_KEY } from '../core/schemas'
import type { JsonObject, JsonValue } from './canonicalJson'

/** GDD §2.3 — 코드 라이브러리는 8슬롯이다. `meta_save.py` 의 MAX_PRESET_SLOTS 와 같은 값. */
export const MAX_PRESET_SLOTS = 8

/** 코드 라이브러리 한 슬롯. 이름 붙인 규칙표 하나다. */
export interface RulePreset {
  readonly name: string
  readonly ruleset: RuleSet
}

/**
 * 조건 우변을 JSON 값으로 되돌린다.
 *
 * @param rhs 리터럴이거나 스탯 참조인 우변.
 * @returns JSON 에 그대로 넣을 수 있는 값.
 */
export function buildRhsPayload(rhs: Rhs): JsonValue {
  return isStatRef(rhs) ? { [RHS_STAT_KEY]: rhs.stat } : rhs
}

/**
 * 조건 항 하나를 JSON 절로 되돌린다.
 *
 * @param term 되돌릴 항.
 * @returns `lhs_param` 이 없으면 그 키도 없는 절.
 */
export function buildTermPayload(term: Term): JsonObject {
  const payload: Record<string, JsonValue> = {
    lhs: term.lhs,
    cmp: term.comparison,
    rhs: buildRhsPayload(term.rhs),
  }
  if (term.lhsParam !== null) {
    payload.lhs_param = term.lhsParam
  }
  return payload
}

/**
 * 규칙 한 줄을 JSON 절로 되돌린다.
 *
 * @param rule 되돌릴 규칙.
 * @returns `parse_ruleset` 이 다시 읽을 수 있는 절.
 */
export function buildRulePayload(rule: Rule): JsonObject {
  return {
    priority: rule.priority,
    cpu_cost: rule.cpuCost,
    action: rule.action,
    target: rule.target,
    set_flag: rule.setFlag,
    conditions: {
      op: rule.conditions.op,
      terms: rule.conditions.terms.map(buildTermPayload),
    },
  }
}

/**
 * 규칙표를 JSON 절로 되돌린다.
 *
 * @param ruleset 되돌릴 규칙표.
 * @returns `parse_ruleset` 에 그대로 넣을 수 있는 절.
 */
export function buildRuleSetPayload(ruleset: RuleSet): JsonObject {
  return {
    ruleset_id: ruleset.rulesetId,
    version: ruleset.version,
    rules: ruleset.rules.map(buildRulePayload),
  }
}

/**
 * 프리셋 한 슬롯을 JSON 절로 되돌린다.
 *
 * @param preset 되돌릴 프리셋.
 * @returns `parse_preset` 이 다시 읽을 수 있는 절.
 */
export function buildPresetPayload(preset: RulePreset): JsonObject {
  return { name: preset.name, ruleset: buildRuleSetPayload(preset.ruleset) }
}

/**
 * JSON 절에서 규칙표를 읽는다. 절의 모양을 먼저 보고 코어의 파서에 넘긴다.
 *
 * @param raw 규칙표 절.
 * @returns 읽어 낸 규칙표.
 * @throws 절의 모양이 규칙표가 아닌 경우.
 */
export function parseRuleSetPayload(raw: unknown): RuleSet {
  if (typeof raw !== 'object' || raw === null) {
    throw new Error('규칙표 절이 객체가 아니다')
  }
  const record = raw as Record<string, unknown>
  if (typeof record.ruleset_id !== 'string' || typeof record.version !== 'number') {
    throw new Error('규칙표 절에 ruleset_id·version 이 없다')
  }
  if (!Array.isArray(record.rules)) {
    throw new Error('규칙표 절에 rules 배열이 없다')
  }
  return parseRuleSet(raw as RawRuleSet)
}

/**
 * JSON 절에서 프리셋 한 슬롯을 읽는다.
 *
 * @param raw name 과 ruleset 을 가진 절.
 * @returns 읽어 낸 프리셋.
 * @throws 이름이 없거나 규칙표 절이 깨진 경우.
 */
export function parsePresetPayload(raw: unknown): RulePreset {
  if (typeof raw !== 'object' || raw === null) {
    throw new Error('프리셋 절이 객체가 아니다')
  }
  const record = raw as Record<string, unknown>
  if (typeof record.name !== 'string') {
    throw new Error('프리셋 절에 name 이 없다')
  }
  return { name: record.name, ruleset: parseRuleSetPayload(record.ruleset) }
}
