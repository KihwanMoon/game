/**
 * 편집 조작 — 규칙표 하나를 받아 고친 규칙표 하나를 낸다. 전부 순수 함수다.
 *
 * 상태를 제자리에서 고치지 않는 이유가 둘이다. 되돌리기를 나중에 붙일 때 이전 값을
 * 그대로 들고 있으면 되고, 검증기가 순수 함수라 **편집 결과를 그 자리에서 다시 검증**해도
 * 세계 상태에 아무 일도 일어나지 않기 때문이다 (validator.ts 주석).
 *
 * **우선순위는 언제나 1..n 으로 다시 매긴다.** 드래그로 순서를 바꾸는 것이 곧 우선순위를
 * 바꾸는 것이고(GDD §8.1), 번호에 구멍이 나면 검증기의 `[N]` 라벨과 화면의 행 번호가
 * 어긋나 "몇 번 규칙이 틀렸다" 는 메시지를 따라갈 수 없다.
 *
 * CPU 비용도 항 수에서 다시 계산한다. 사람이 손으로 맞출 값이 아니며, 어긋나면 검증기가
 * `CPU 비용 N 가 항 수 기준 M 와 다르다` 로 잡아 편집 중 내내 붉은 줄이 남는다.
 */
import { CPU_COST_BY_TERM_COUNT } from '../core/rules/validator'
import {
  type ActionBlock,
  type BlockCatalog,
  type Comparison,
  type Condition,
  MAX_TERMS,
  OP_AND,
  OP_SINGLE,
  type PerceptionBlock,
  type Rhs,
  type Rule,
  type RuleSet,
  type Term,
} from '../core/schemas'
import { BOOL_COMPARISONS, listSelectorsForAction } from './blockOptions'

/** 항이 없거나 3개를 넘으면 비용표에 값이 없다. 검증기가 항 수 쪽을 위반으로 잡는다. */
const NO_CPU_COST = 0

/** 범위가 없는 정수 인지 변수의 기본 우변. 0 은 `>= 0` 처럼 늘 참인 항을 만들기 쉽다. */
const DEFAULT_INT_RHS = 1

/** 범위의 가운데를 기본값으로 삼을 때 쓰는 제수. */
const RANGE_HALF = 2

/** 새 규칙의 기본 행동과 셀렉터. 만들자마자 검증을 통과하는 조합이어야 한다. */
const DEFAULT_ACTION_ID = 'ATTACK'
const DEFAULT_SELECTOR_ID = 'NEAREST'
const DEFAULT_COMPARISON: Comparison = '<'

/**
 * 항 수에서 CPU 비용을 계산한다 (GDD §3.6).
 *
 * @param termCount 조건 항의 개수.
 * @returns 비용. 1~3항 밖이면 0.
 */
export function calculateCpuCost(termCount: number): number {
  return CPU_COST_BY_TERM_COUNT.get(termCount) ?? NO_CPU_COST
}

/**
 * 규칙표 전체의 CPU 합계를 낸다.
 *
 * @param ruleset 합계를 낼 규칙표.
 * @returns 규칙별 비용의 합.
 */
export function calculateTotalCpu(ruleset: RuleSet): number {
  return ruleset.rules.reduce((sum, rule) => sum + rule.cpuCost, NO_CPU_COST)
}

/**
 * 인지 변수에 어울리는 기본 우변을 만든다.
 *
 * @param block 좌변 인지 변수.
 * @returns bool 이면 true, 범위가 있으면 가운데 값, 그 밖에는 1.
 */
export function buildDefaultRhs(block: PerceptionBlock): Rhs {
  if (block.returns === 'bool') {
    return true
  }
  if (block.valueRange !== null) {
    const [low, high] = block.valueRange
    return Math.floor((low + high) / RANGE_HALF)
  }
  return DEFAULT_INT_RHS
}

/**
 * 인지 변수 하나로 조건 항을 만든다. 인자를 받는 블록이면 첫 인자를 미리 골라 둔다.
 *
 * 인자를 비워 두면 `쿨타임[None] 는 허용되지 않는다` 가 즉시 뜬다. 방금 만든 항이 곧바로
 * 위반으로 표시되면 사람은 자기가 뭘 잘못했는지부터 찾는다 — 고를 것을 미리 골라 둔다.
 *
 * @param block 좌변 인지 변수.
 * @returns 만들어진 항.
 */
export function createTerm(block: PerceptionBlock): Term {
  const comparison = block.returns === 'bool' ? (BOOL_COMPARISONS[0] ?? '==') : DEFAULT_COMPARISON
  return {
    lhs: block.blockId,
    comparison,
    rhs: buildDefaultRhs(block),
    lhsParam: block.param === null ? null : (block.param.values[0] ?? null),
  }
}

/**
 * 카탈로그의 첫 인지 변수를 집는다.
 *
 * @param catalog 블록 카탈로그.
 * @returns 첫 인지 변수.
 * @throws 인지 변수가 하나도 없는 경우.
 */
function findFirstPerception(catalog: BlockCatalog): PerceptionBlock {
  const first = catalog.perceptions.values().next()
  if (first.done === true) {
    throw new Error('카탈로그에 인지 변수가 없다')
  }
  return first.value
}

/**
 * 빈 규칙 하나를 만든다.
 *
 * @param catalog 블록 카탈로그.
 * @param priority 새 규칙의 우선순위.
 * @param blockId 좌변으로 쓸 인지 변수 id. 없으면 카탈로그의 첫 변수.
 * @returns 만들어진 규칙. 만든 즉시 검증을 통과한다.
 */
export function createRule(catalog: BlockCatalog, priority: number, blockId?: string): Rule {
  const block =
    blockId === undefined
      ? findFirstPerception(catalog)
      : (catalog.perceptions.get(blockId) ?? findFirstPerception(catalog))
  const terms = [createTerm(block)]
  const targeted = catalog.actions.get(DEFAULT_ACTION_ID)?.targeted ?? false
  return {
    priority,
    conditions: { op: OP_SINGLE, terms },
    action: DEFAULT_ACTION_ID,
    target: targeted ? DEFAULT_SELECTOR_ID : null,
    actionParam: null,
    setFlag: null,
    cpuCost: calculateCpuCost(terms.length),
  }
}

/**
 * 규칙 목록을 우선순위 1..n 으로 다시 매긴다.
 *
 * @param rules 화면에 보이는 순서 그대로의 규칙 목록.
 * @param ruleset 원래 규칙표. id 와 version 을 물려받는다.
 * @returns 번호가 다시 매겨진 규칙표.
 */
export function renumberRules(rules: readonly Rule[], ruleset: RuleSet): RuleSet {
  return {
    rulesetId: ruleset.rulesetId,
    version: ruleset.version,
    rules: rules.map((rule, index) => ({ ...rule, priority: index + 1 })),
  }
}

/**
 * 규칙 하나를 고친다. 조건이 바뀌었으면 CPU 비용을 다시 계산한다.
 *
 * @param ruleset 원래 규칙표.
 * @param index 고칠 규칙의 자리.
 * @param patch 덮어쓸 필드들.
 * @returns 고쳐진 규칙표.
 */
export function updateRule(ruleset: RuleSet, index: number, patch: Partial<Rule>): RuleSet {
  const rules = ruleset.rules.map((rule, at) => {
    if (at !== index) {
      return rule
    }
    const merged = { ...rule, ...patch }
    return { ...merged, cpuCost: calculateCpuCost(merged.conditions.terms.length) }
  })
  return renumberRules(rules, ruleset)
}

/**
 * 규칙을 하나 더한다.
 *
 * @param ruleset 원래 규칙표.
 * @param catalog 블록 카탈로그.
 * @param index 이 자리 **뒤에** 넣는다. 음수면 맨 앞.
 * @param blockId 새 규칙의 조건으로 쓸 인지 변수 id. 없으면 카탈로그의 첫 변수.
 * @returns 규칙이 더해진 규칙표.
 */
export function addRule(
  ruleset: RuleSet,
  catalog: BlockCatalog,
  index: number,
  blockId?: string,
): RuleSet {
  const at = Math.min(Math.max(index + 1, 0), ruleset.rules.length)
  const rules = [...ruleset.rules]
  rules.splice(at, 0, createRule(catalog, at + 1, blockId))
  return renumberRules(rules, ruleset)
}

/**
 * 규칙을 지운다.
 *
 * @param ruleset 원래 규칙표.
 * @param index 지울 규칙의 자리.
 * @returns 규칙이 빠진 규칙표.
 */
export function removeRule(ruleset: RuleSet, index: number): RuleSet {
  return renumberRules(
    ruleset.rules.filter((_unused, at) => at !== index),
    ruleset,
  )
}

/**
 * 규칙을 복제해 바로 아래에 넣는다.
 *
 * 규칙표 편집의 대부분은 "비슷한데 대상만 다른 줄" 을 만드는 일이다. 복제가 없으면
 * 조건 세 조각과 행동·셀렉터를 매번 다시 고르게 된다.
 *
 * @param ruleset 원래 규칙표.
 * @param index 복제할 규칙의 자리.
 * @returns 복제본이 더해진 규칙표.
 */
export function duplicateRule(ruleset: RuleSet, index: number): RuleSet {
  const source = ruleset.rules[index]
  if (source === undefined) {
    return ruleset
  }
  const rules = [...ruleset.rules]
  rules.splice(index + 1, 0, { ...source })
  return renumberRules(rules, ruleset)
}

/**
 * 규칙의 자리를 옮긴다. 드래그와 키보드 이동이 모두 이 함수를 부른다.
 *
 * @param ruleset 원래 규칙표.
 * @param from 집은 자리.
 * @param to 놓을 자리.
 * @returns 순서가 바뀐 규칙표.
 */
export function moveRule(ruleset: RuleSet, from: number, to: number): RuleSet {
  const rules = [...ruleset.rules]
  const moved = rules[from]
  if (moved === undefined || to < 0 || to >= rules.length || from === to) {
    return ruleset
  }
  rules.splice(from, 1)
  rules.splice(to, 0, moved)
  return renumberRules(rules, ruleset)
}

/**
 * 조건 항을 하나 더한다. 항이 하나뿐이던 규칙은 연산자가 AND 로 바뀐다.
 *
 * @param ruleset 원래 규칙표.
 * @param catalog 블록 카탈로그.
 * @param ruleIndex 규칙의 자리.
 * @param blockId 새 항의 좌변. 없으면 카탈로그의 첫 변수.
 * @returns 항이 더해진 규칙표. 이미 3항이면 원래 규칙표 그대로.
 */
export function addTerm(
  ruleset: RuleSet,
  catalog: BlockCatalog,
  ruleIndex: number,
  blockId?: string,
): RuleSet {
  const rule = ruleset.rules[ruleIndex]
  if (rule === undefined || rule.conditions.terms.length >= MAX_TERMS) {
    return ruleset
  }
  const block =
    blockId === undefined
      ? findFirstPerception(catalog)
      : (catalog.perceptions.get(blockId) ?? findFirstPerception(catalog))
  const terms = [...rule.conditions.terms, createTerm(block)]
  const op = rule.conditions.op === OP_SINGLE ? OP_AND : rule.conditions.op
  return updateRule(ruleset, ruleIndex, { conditions: { op, terms } })
}

/**
 * 조건 항을 지운다. 항이 하나만 남으면 연산자가 SINGLE 로 돌아간다.
 *
 * @param ruleset 원래 규칙표.
 * @param ruleIndex 규칙의 자리.
 * @param termIndex 지울 항의 자리.
 * @returns 항이 빠진 규칙표. 마지막 한 항은 지우지 않는다.
 */
export function removeTerm(ruleset: RuleSet, ruleIndex: number, termIndex: number): RuleSet {
  const rule = ruleset.rules[ruleIndex]
  if (rule === undefined || rule.conditions.terms.length <= 1) {
    return ruleset
  }
  const terms = rule.conditions.terms.filter((_unused, at) => at !== termIndex)
  const op = terms.length === 1 ? OP_SINGLE : rule.conditions.op
  return updateRule(ruleset, ruleIndex, { conditions: { op, terms } })
}

/**
 * 조건 항 하나를 고친다.
 *
 * @param ruleset 원래 규칙표.
 * @param ruleIndex 규칙의 자리.
 * @param termIndex 항의 자리.
 * @param patch 덮어쓸 필드들.
 * @returns 고쳐진 규칙표.
 */
export function updateTerm(
  ruleset: RuleSet,
  ruleIndex: number,
  termIndex: number,
  patch: Partial<Term>,
): RuleSet {
  const rule = ruleset.rules[ruleIndex]
  if (rule === undefined) {
    return ruleset
  }
  const terms = rule.conditions.terms.map((term, at) =>
    at === termIndex ? { ...term, ...patch } : term,
  )
  const conditions: Condition = { op: rule.conditions.op, terms }
  return updateRule(ruleset, ruleIndex, { conditions })
}

/**
 * 항의 좌변을 바꾸고 딸린 값들을 함께 맞춘다.
 *
 * 좌변만 갈면 인자와 우변이 이전 블록의 것으로 남는다 — `내 HP% == true` 나
 * `주변8칸[SKILL_1]` 같은 항이 만들어지고, 사람은 자기가 고르지도 않은 값 때문에 뜬
 * 위반 메시지를 읽게 된다. 그래서 좌변 변경은 한 조작으로 셋을 함께 옮긴다.
 *
 * @param ruleset 원래 규칙표.
 * @param catalog 블록 카탈로그.
 * @param ruleIndex 규칙의 자리.
 * @param termIndex 항의 자리.
 * @param blockId 새 좌변 인지 변수 id.
 * @returns 고쳐진 규칙표.
 */
export function applyLhsChoice(
  ruleset: RuleSet,
  catalog: BlockCatalog,
  ruleIndex: number,
  termIndex: number,
  blockId: string,
): RuleSet {
  const block = catalog.perceptions.get(blockId)
  if (block === undefined) {
    return ruleset
  }
  return updateTerm(ruleset, ruleIndex, termIndex, createTerm(block))
}

/**
 * 규칙의 행동을 바꾸고 TARGET 절을 함께 맞춘다.
 *
 * targeted 행동인데 셀렉터가 없으면 `TARGET 셀렉터가 필요하다`, 아닌데 있으면
 * `TARGET 을 받지 않는다` 가 뜬다. 둘 다 사람이 알 필요 없는 규칙이므로 여기서 채운다.
 *
 * 진영도 여기서 맞춘다 (v4). `ATTACK @NEAREST` 를 `HEAL` 로 바꾸면 셀렉터가 적대로 남아
 * 곧바로 위반이 되므로, 새 행동이 요구하는 진영의 첫 셀렉터로 갈아 끼운다.
 *
 * @param ruleset 원래 규칙표.
 * @param catalog 블록 카탈로그.
 * @param ruleIndex 규칙의 자리.
 * @param actionId 새 행동 id.
 * @returns 고쳐진 규칙표.
 */
/**
 * 그 행동에 쓸 수 있는 셀렉터를 고른다. 쓰던 것이 여전히 쓸 수 있으면 그대로 둔다.
 *
 * @param catalog 블록 카탈로그.
 * @param action 새로 고른 행동.
 * @param current 지금 걸려 있는 셀렉터. 없으면 null.
 * @returns 셀렉터 id.
 */
function pickSelectorForAction(
  catalog: BlockCatalog,
  action: ActionBlock,
  current: string | null,
  actionParam: string | null = null,
): string {
  const allowed = listSelectorsForAction(catalog, action, actionParam)
  const kept = allowed.find((item) => item.blockId === current)
  return kept?.blockId ?? allowed[0]?.blockId ?? DEFAULT_SELECTOR_ID
}

/**
 * 규칙의 행동을 바꾸고 TARGET 절을 함께 맞춘다.
 *
 * @param ruleset 원래 규칙표.
 * @param catalog 블록 카탈로그.
 * @param ruleIndex 규칙의 자리.
 * @param actionId 새 행동 id.
 * @returns 고쳐진 규칙표.
 */
export function applyActionChoice(
  ruleset: RuleSet,
  catalog: BlockCatalog,
  ruleIndex: number,
  actionId: string,
): RuleSet {
  const rule = ruleset.rules[ruleIndex]
  const action = catalog.actions.get(actionId)
  if (rule === undefined || action === undefined) {
    return ruleset
  }
  const actionParam = pickActionParam(action, rule.actionParam)
  return updateRule(ruleset, ruleIndex, {
    action: actionId,
    target: action.targeted
      ? pickSelectorForAction(catalog, action, rule.target, actionParam)
      : null,
    actionParam,
  })
}

/**
 * 행동 인자를 바꾸고, 그 인자에서 못 쓰는 대상이면 함께 바꾼다.
 *
 * **진영은 스킬이 정한다.** 치유(아군)에서 스킬 1(적)로 바꾸면 SELF 대상이 그대로
 * 남아 검증에서 반려된다 — 인자를 바꾼 사람은 대상을 안 바꿨으므로, 조용한 반려 대신
 * 유효한 첫 후보로 갈아 끼운다.
 *
 * @param ruleset 지금 규칙표.
 * @param catalog 블록 카탈로그.
 * @param ruleIndex 바꿀 규칙 자리.
 * @param actionParam 새 인자.
 * @returns 새 규칙표.
 */
export function applyParamChoice(
  ruleset: RuleSet,
  catalog: BlockCatalog,
  ruleIndex: number,
  actionParam: string,
): RuleSet {
  const rule = ruleset.rules[ruleIndex]
  const action = rule === undefined ? undefined : catalog.actions.get(rule.action)
  if (rule === undefined || action === undefined) {
    return ruleset
  }
  return updateRule(ruleset, ruleIndex, {
    actionParam,
    target: action.targeted
      ? pickSelectorForAction(catalog, action, rule.target, actionParam)
      : null,
  })
}

/**
 * 이 행동이 받는 인자의 값을 고른다.
 *
 * **인자를 안 정하면 조용히 기본값으로 떨어진다.** `USE_ITEM` 은 인자가 없으면 물약을
 * 쓰고, 그래서 주문서를 쓰는 규칙을 지을 방법이 없었다 — 블록 데이터에는 `POTION`·
 * `SCROLL` 이 처음부터 적혀 있었는데 편집기가 그것을 한 번도 안 물었다.
 *
 * 쓰던 값이 이 행동에서도 유효하면 지킨다. 행동을 바꿨다고 고른 소모품이 바뀌면
 * 「내가 안 고친 것이 달라진다」가 된다.
 *
 * @param action 고른 행동.
 * @param current 지금 값.
 * @returns 쓸 인자 값. 인자를 안 받는 행동이면 null.
 */
export function pickActionParam(action: ActionBlock, current: string | null): string | null {
  const values = action.param?.values
  if (values === undefined || values.length === 0) {
    return null
  }
  return current !== null && values.includes(current) ? current : (values[0] ?? null)
}
