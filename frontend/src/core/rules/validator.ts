/**
 * 규칙표 검증 — `game/app/rules/validator.py` 의 이식 (TDD §5.1).
 *
 * 검증 없이 컴파일하면 규칙이 조용히 무시되고, 플레이어는 자기 논리가 틀렸다고 오해한다.
 * 무엇이 왜 거부됐는지 문자열로 돌려주는 이유가 그것이다 (P1).
 *
 * **규칙 에디터가 타이핑 도중에 이것을 부른다.** 그래서 순수 함수로 두고 세계 상태를
 * 건드리지 않는다 — 같은 규칙표를 두 번 물으면 같은 목록이 나오고, 부르는 쪽이 결과를
 * 캐시할지 말지를 자유롭게 정할 수 있다.
 *
 * **메시지의 순서도 계약이다.** 파이썬과 같은 순서로 쌓지 않으면 에디터가 같은 규칙표에
 * 대해 다른 첫 줄을 띄운다. 기준값은 `golden/rules_golden.json` 의 validator 절이다.
 */

import {
  type ActionBlock,
  type BlockCatalog,
  COMPARISONS,
  CONDITION_OPS,
  MAX_TERMS,
  type PerceptionBlock,
  type Rule,
  type RuleSet,
  type Term,
  isStatRef,
} from '../schemas'

/** 조건 항 수에 따른 CPU 비용 (GDD §3.6). 3항까지만 값을 갖는다. */
export const CPU_COST_BY_TERM_COUNT: ReadonlyMap<number, number> = new Map([
  [1, 1],
  [2, 2],
  [3, 4],
])

/**
 * 스탯 우변은 수치 비교다. bool 인지 변수와 견주면 `내 상태이상 == 사거리` 같은 항이 되어
 * 뜻이 없다 — 값이 나오는데도 영영 거짓인 규칙이 만들어진다.
 */
const NUMERIC_RETURN = 'int'

/** 진영 id 를 사람이 읽는 말로. 메시지에 "ally" 라고 적으면 화면에서만 영어가 튄다. */
const FACTION_LABELS: ReadonlyMap<string, string> = new Map([
  ['enemy', '적대'],
  ['ally', '아군'],
])

/**
 * 빠진 인자를 메시지에 적을 문자열로 만든다.
 *
 * 파이썬은 `None` 을 그대로 문자열로 만들고 자바스크립트는 `null` 로 만든다. 인자를
 * 고르지 않은 규칙은 에디터에서 흔한 중간 상태이므로 이 한 글자가 두 코어의 메시지를
 * 갈라놓는다 — 정본인 파이썬 쪽 표기에 맞춘다.
 *
 * @param param 항의 인자. 고르지 않았으면 null.
 * @returns 메시지에 넣을 표기.
 */
function formatMissingParam(param: string | null): string {
  return param ?? 'None'
}

/**
 * 인자가 허용 목록 안에 있는지 본다.
 *
 * 목록은 문자열만 담지만 인자는 고르지 않은 상태(null)일 수 있다. 그 상태도 "허용되지
 * 않음" 으로 떨어져야 하므로 비교 대상을 넓혀 받는다.
 *
 * @param values 허용된 인자 목록.
 * @param param 항의 인자. 고르지 않았으면 null.
 * @returns 허용 목록에 있으면 true.
 */
function checkParamAllowed(values: readonly string[], param: string | null): boolean {
  return (values as readonly (string | null)[]).includes(param)
}

/**
 * 조건 항의 우변이 성립하는지 본다 (F-2).
 *
 * @param term 검사할 항.
 * @param block 좌변 인지 변수.
 * @param catalog 블록 카탈로그. 허용 스탯의 정본이다.
 * @param label 메시지에 붙일 규칙 표시.
 * @returns 위반 메시지. 성립하면 빈 문자열.
 */
function checkTermRhs(
  term: Term,
  block: PerceptionBlock,
  catalog: BlockCatalog,
  label: string,
): string {
  if (!isStatRef(term.rhs)) {
    return ''
  }
  if (!catalog.rhsStats.has(term.rhs.stat)) {
    return `${label} 목록에 없는 스탯 ${term.rhs.stat}`
  }
  if (block.returns !== NUMERIC_RETURN) {
    return `${label} ${term.lhs} 는 ${block.returns} 라서 스탯과 비교할 수 없다`
  }
  return ''
}

/**
 * 조건 항 하나가 목록 안에 있고 인자·우변이 맞는지 본다.
 *
 * @param term 검사할 항.
 * @param catalog 동결된 블록 카탈로그.
 * @param unlocked 해금된 블록 id 집합.
 * @param label 메시지에 붙일 규칙 표시.
 * @returns 위반 메시지 목록.
 */
function checkTerm(
  term: Term,
  catalog: BlockCatalog,
  unlocked: ReadonlySet<string>,
  label: string,
): string[] {
  const problems: string[] = []
  // 파서가 이미 연산자를 거르지만 에디터는 타이핑 도중의 값을 그대로 넘긴다. 타입이
  // 좁아 늘 참인 검사로 보이는 것을 피하려고 문자열 목록으로 대조한다.
  if (!(COMPARISONS as readonly string[]).includes(term.comparison)) {
    problems.push(`${label} 알 수 없는 비교 연산자 ${term.comparison}`)
  }
  const block = catalog.perceptions.get(term.lhs)
  if (block === undefined) {
    problems.push(`${label} 목록에 없는 인지 변수 ${term.lhs}`)
    return problems
  }
  if (!unlocked.has(term.lhs)) {
    problems.push(`${label} 아직 해금되지 않은 인지 변수 ${term.lhs}`)
  }
  if (block.param === null && term.lhsParam !== null) {
    problems.push(`${label} ${term.lhs} 는 인자를 받지 않는다`)
  } else if (block.param !== null && !checkParamAllowed(block.param.values, term.lhsParam)) {
    const shown = formatMissingParam(term.lhsParam)
    problems.push(`${label} ${term.lhs} 의 인자 ${shown} 는 허용되지 않는다`)
  }
  const rhsProblem = checkTermRhs(term, block, catalog, label)
  if (rhsProblem !== '') {
    problems.push(rhsProblem)
  }
  return problems
}

/**
 * 조건식 전체가 동결 목록 안에 있는지 본다.
 *
 * @param rule 검사할 규칙.
 * @param catalog 동결된 블록 카탈로그.
 * @param unlocked 해금된 블록 id 집합.
 * @returns 위반 메시지 목록.
 */
function checkTerms(rule: Rule, catalog: BlockCatalog, unlocked: ReadonlySet<string>): string[] {
  const problems: string[] = []
  const label = `[${rule.priority}]`
  if (!(CONDITION_OPS as readonly string[]).includes(rule.conditions.op)) {
    problems.push(`${label} 알 수 없는 조건 연산자 ${rule.conditions.op}`)
  }
  const count = rule.conditions.terms.length
  if (count < 1 || count > MAX_TERMS) {
    problems.push(`${label} 조건 항이 1~${MAX_TERMS}개를 벗어났다`)
  }
  for (const term of rule.conditions.terms) {
    problems.push(...checkTerm(term, catalog, unlocked, label))
  }
  return problems
}

/**
 * 행동이 요구하는 진영과 셀렉터가 고르는 진영이 맞는지 본다 (블록 목록 v4).
 *
 * `HEAL @NEAREST` 는 적을 회복하고 `ATTACK @ALLY_WOUNDED` 는 아군을 때린다. 둘 다 문법으로는
 * 만들 수 있으므로 여기서 막지 않으면 규칙표가 조용히 반대로 돈다.
 *
 * @param rule 검사할 규칙.
 * @param action 그 규칙의 행동 블록.
 * @param catalog 동결된 블록 카탈로그.
 * @param label 메시지에 붙일 규칙 표시.
 * @returns 위반 메시지 목록.
 */
function checkTargetFaction(
  rule: Rule,
  action: ActionBlock,
  catalog: BlockCatalog,
  label: string,
): string[] {
  const selector = catalog.selectors.get(rule.target ?? '')
  if (selector === undefined || action.targetFaction === null) {
    return []
  }
  if (selector.faction === action.targetFaction) {
    return []
  }
  const want = FACTION_LABELS.get(action.targetFaction) ?? action.targetFaction
  const got = FACTION_LABELS.get(selector.faction) ?? selector.faction
  return [`${label} ${rule.action} 는 ${want} 셀렉터가 필요하다 — ${rule.target} 는 ${got} 셀렉터다`]
}

/**
 * 행동과 셀렉터의 조합이 성립하는지 본다.
 *
 * @param rule 검사할 규칙.
 * @param catalog 동결된 블록 카탈로그.
 * @param unlocked 해금된 블록 id 집합.
 * @returns 위반 메시지 목록.
 */
function checkAction(rule: Rule, catalog: BlockCatalog, unlocked: ReadonlySet<string>): string[] {
  const problems: string[] = []
  const label = `[${rule.priority}]`
  const action = catalog.actions.get(rule.action)
  if (action === undefined) {
    return [`${label} 목록에 없는 행동 ${rule.action}`]
  }
  if (!unlocked.has(rule.action)) {
    problems.push(`${label} 아직 해금되지 않은 행동 ${rule.action}`)
  }
  if (action.targeted && rule.target === null) {
    problems.push(`${label} ${rule.action} 는 TARGET 셀렉터가 필요하다`)
  }
  if (!action.targeted && rule.target !== null) {
    problems.push(`${label} ${rule.action} 는 TARGET 을 받지 않는다`)
  }
  if (rule.target !== null && !catalog.selectors.has(rule.target)) {
    problems.push(`${label} 목록에 없는 셀렉터 ${rule.target}`)
  }
  problems.push(...checkTargetFaction(rule, action, catalog, label))
  return problems
}

/**
 * 전부 해금된 상태의 블록 id 집합을 만든다.
 *
 * @param catalog 동결된 블록 카탈로그.
 * @returns 인지 변수와 행동 id 를 합친 집합.
 */
function buildFullUnlockSet(catalog: BlockCatalog): ReadonlySet<string> {
  return new Set([...catalog.perceptions.keys(), ...catalog.actions.keys()])
}

/**
 * 규칙표가 실행 가능한지 검사한다.
 *
 * CPU 예산 초과는 오류가 아니라 수치다. 목록에 한 줄로 담아 돌려주며, 부르는 쪽은 그
 * 상태에서도 편집을 계속하게 둔다 (GDD §3.6).
 *
 * @param ruleset 검사할 규칙표.
 * @param catalog 동결된 블록 카탈로그.
 * @param cpuBudget 이 엔티티의 CPU 예산.
 * @param ruleSlots 이 엔티티의 규칙 슬롯 수.
 * @param unlocked 해금된 블록 id 집합. null 이면 전부 해금된 것으로 본다.
 * @returns 위반 메시지 목록. 비어 있으면 실행 가능하다. 순서도 기준이다.
 */
export function validateRuleSet(
  ruleset: RuleSet,
  catalog: BlockCatalog,
  cpuBudget: number,
  ruleSlots: number,
  unlocked: ReadonlySet<string> | null = null,
): string[] {
  const allowed = unlocked ?? buildFullUnlockSet(catalog)

  const problems: string[] = []
  if (ruleset.rules.length > ruleSlots) {
    problems.push(`규칙 ${ruleset.rules.length}개가 슬롯 ${ruleSlots}개를 넘는다`)
  }

  const priorities = ruleset.rules.map((rule) => rule.priority)
  if (priorities.length !== new Set(priorities).size) {
    problems.push('우선순위가 중복된다 — 평가 순서가 정해지지 않는다')
  }

  let totalCpu = 0
  for (const rule of ruleset.rules) {
    const expected = CPU_COST_BY_TERM_COUNT.get(rule.conditions.terms.length)
    if (expected !== undefined && rule.cpuCost !== expected) {
      problems.push(
        `[${rule.priority}] CPU 비용 ${rule.cpuCost} 가 항 수 기준 ${expected} 와 다르다`,
      )
    }
    totalCpu += rule.cpuCost
    problems.push(...checkTerms(rule, catalog, allowed))
    problems.push(...checkAction(rule, catalog, allowed))
  }

  if (totalCpu > cpuBudget) {
    problems.push(`CPU ${totalCpu} 가 예산 ${cpuBudget} 을 넘는다`)
  }
  return problems
}
