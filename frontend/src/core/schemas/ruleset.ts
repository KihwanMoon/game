/**
 * 규칙 DSL 의 직렬화 형식 (TDD §3.3, GDD §3.1). `game/schemas/ruleset.py` 의 이식이다.
 *
 * `[우선순위 N] IF <조건식> THEN <행동> [TARGET <셀렉터>] [SET <플래그>]`
 *
 * 우변(`rhs`)은 리터럴이거나 자기 스탯 참조다 (F-2). 스탯 참조는 `{"stat": "attack_range"}`
 * 형태이며, 객체 한 겹으로 감싼 덕에 여기서 `typeof rhs === 'object'` 만으로 분기한다 —
 * 파이썬 쪽 주석이 예고한 그 분기가 이 파일이다.
 */

export const OP_SINGLE = 'SINGLE'
export const OP_AND = 'AND'
export const OP_OR = 'OR'

/** 조건식을 묶는 연산자. */
export type ConditionOp = typeof OP_SINGLE | typeof OP_AND | typeof OP_OR

/** 허용된 조건 연산자 전량. 검증기가 편집 중인 값을 이 목록과 대조한다. */
export const CONDITION_OPS: readonly ConditionOp[] = [OP_SINGLE, OP_AND, OP_OR]

/** 항의 비교 연산자. */
export type Comparison = '<' | '<=' | '>' | '>=' | '==' | '!='

/** 허용된 비교 연산자 전량. 검증기가 편집 중인 값을 이 목록과 대조한다. */
export const COMPARISONS: readonly Comparison[] = ['<', '<=', '>', '>=', '==', '!=']

/** GDD §3.1 — 조건식은 최대 3항이다. §3.6 의 CPU 비용표도 3항까지만 값을 갖는다. */
export const MAX_TERMS = 3

/** 스탯 참조 우변을 알아보는 키. 허용 스탯의 닫힌 목록은 blocks.json 의 rhs_stats 다. */
export const RHS_STAT_KEY = 'stat'

/** 조건 우변이 가리키는 자기 스탯 (F-2). `사거리` 처럼 값이 런타임에 정해진다. */
export interface StatRef {
  readonly stat: string
}

/** 조건 우변. 리터럴이거나 스탯 참조다. */
export type Rhs = number | boolean | StatRef

/**
 * 우변이 스탯 참조인지 본다.
 *
 * @param rhs 검사할 우변.
 * @returns 스탯 참조이면 true.
 */
export function isStatRef(rhs: Rhs): rhs is StatRef {
  return typeof rhs === 'object'
}

/** 조건 한 항. `적거리 <= 3` 하나에 해당한다. */
export interface Term {
  readonly lhs: string
  readonly comparison: Comparison
  readonly rhs: Rhs
  readonly lhsParam: string | null
}

/** 조건식. 항 여러 개를 AND/OR 로 묶는다. */
export interface Condition {
  readonly op: ConditionOp
  readonly terms: readonly Term[]
}

/** 규칙 한 줄. */
export interface Rule {
  readonly priority: number
  readonly conditions: Condition
  readonly action: string
  readonly target: string | null
  readonly setFlag: string | null
  readonly cpuCost: number
}

/** 한 엔티티의 규칙표 전체. */
export interface RuleSet {
  readonly rulesetId: string
  readonly version: number
  readonly rules: readonly Rule[]
}

/** rulesets JSON 의 원시 형태. */
export interface RawTerm {
  readonly lhs: string
  readonly cmp: string
  readonly rhs: unknown
  readonly lhs_param?: string | null
}

export interface RawCondition {
  readonly op: string
  readonly terms: readonly RawTerm[]
}

export interface RawRule {
  readonly priority: number
  readonly cpu_cost: number
  readonly action: string
  readonly target?: string | null
  readonly set_flag?: string | null
  readonly conditions: RawCondition
}

export interface RawRuleSet {
  readonly ruleset_id: string
  readonly version: number
  readonly rules: readonly RawRule[]
}

export interface RawRuleSetFile {
  readonly rulesets: readonly RawRuleSet[]
}

/**
 * 스냅샷에서 항의 값을 찾을 키를 만든다. 파이썬 `Term.key` 와 같은 문자열이다.
 *
 * @param term 키를 만들 항.
 * @returns `lhs` 또는 `lhs[param]`.
 */
export function getTermKey(term: Term): string {
  return term.lhsParam === null ? term.lhs : `${term.lhs}[${term.lhsParam}]`
}

/**
 * 조건 항의 우변을 읽는다. 리터럴이거나 스탯 참조다 (F-2).
 *
 * 파이썬은 `bool` 이 `int` 의 하위형이라 검사 하나로 둘을 받는다. 자바스크립트는 둘이
 * 별개 타입이므로 여기서는 명시적으로 갈라 받는다. 실수는 양쪽 다 거부한다 — 부동소수는
 * 코어에 들어오지 않는다.
 *
 * @param raw term 의 rhs 절.
 * @returns 리터럴 그대로, 또는 스탯 참조.
 * @throws 객체 우변에 stat 문자열이 없거나 우변 형식을 알 수 없는 경우.
 */
export function parseRhs(raw: unknown): Rhs {
  if (typeof raw === 'object' && raw !== null && !Array.isArray(raw)) {
    const stat = (raw as Record<string, unknown>)[RHS_STAT_KEY]
    if (typeof stat !== 'string') {
      throw new Error(`우변 객체에는 ${RHS_STAT_KEY} 문자열이 있어야 한다: ${JSON.stringify(raw)}`)
    }
    return { stat }
  }
  if (typeof raw === 'boolean') {
    return raw
  }
  if (typeof raw === 'number' && Number.isInteger(raw)) {
    return raw
  }
  throw new Error(`우변은 정수·불리언이거나 스탯 참조여야 한다: ${JSON.stringify(raw)}`)
}

/**
 * 비교 연산자를 읽는다.
 *
 * @param raw term 의 cmp 절.
 * @returns 허용된 비교 연산자.
 * @throws 목록에 없는 연산자인 경우.
 */
function parseComparison(raw: string): Comparison {
  const found = COMPARISONS.find((candidate) => candidate === raw)
  if (found === undefined) {
    throw new Error(`알 수 없는 비교 연산자다: ${raw}`)
  }
  return found
}

/**
 * 조건 연산자를 읽는다.
 *
 * @param raw conditions 의 op 절.
 * @returns 허용된 조건 연산자.
 * @throws 목록에 없는 연산자인 경우.
 */
function parseConditionOp(raw: string): ConditionOp {
  const found = CONDITION_OPS.find((candidate) => candidate === raw)
  if (found === undefined) {
    throw new Error(`알 수 없는 조건 연산자다: ${raw}`)
  }
  return found
}

/**
 * 원시 절에서 조건 항을 만든다.
 *
 * @param raw term 절.
 * @returns 만들어진 항.
 */
export function parseTerm(raw: RawTerm): Term {
  return {
    lhs: raw.lhs,
    comparison: parseComparison(raw.cmp),
    rhs: parseRhs(raw.rhs),
    lhsParam: raw.lhs_param ?? null,
  }
}

/**
 * 원시 절에서 규칙표를 만든다.
 *
 * 우선순위 오름차순으로 정렬해 둔다. 실행이 위에서부터 평가하는 것을 전제하므로
 * (TDD §5.2) 정렬을 로드 시점에 끝내면 매 틱 다시 정렬할 필요가 없다. 자바스크립트의
 * `sort` 는 ES2019 부터 안정 정렬이라 파이썬 `sorted` 와 같은 순서가 나온다.
 *
 * @param raw ruleset 절.
 * @returns 우선순위 순으로 정렬된 규칙표.
 */
export function parseRuleSet(raw: RawRuleSet): RuleSet {
  const rules = raw.rules
    .map(
      (item): Rule => ({
        priority: item.priority,
        conditions: {
          op: parseConditionOp(item.conditions.op),
          terms: item.conditions.terms.map(parseTerm),
        },
        action: item.action,
        target: item.target ?? null,
        setFlag: item.set_flag ?? null,
        cpuCost: item.cpu_cost,
      }),
    )
    .sort((left, right) => left.priority - right.priority)
  return { rulesetId: raw.ruleset_id, version: raw.version, rules }
}

/**
 * 규칙표 묶음 JSON 을 읽는다.
 *
 * @param raw rulesets 배열을 담은 JSON 의 내용.
 * @returns rulesetId 에서 규칙표로의 대응표. 파일에 적힌 순서를 유지한다.
 */
export function loadRuleSets(raw: RawRuleSetFile): ReadonlyMap<string, RuleSet> {
  const collected = new Map<string, RuleSet>()
  for (const item of raw.rulesets) {
    collected.set(item.ruleset_id, parseRuleSet(item))
  }
  return collected
}
