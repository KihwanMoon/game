/**
 * 텍스트 뷰 — 규칙표를 GDD §3.1 의 표기로 쓰고 다시 읽는다 (GDD §8.1, §10 A등급).
 *
 * ```
 * # ruleset g0_pressure v1
 * [1] IF self_hp_percent < 25 AND self_potion_count > 0 THEN USE_POTION
 * [2] IF target_distance[NEAREST] <= 1 THEN ATTACK TARGET NEAREST SET A=true
 * [3] IF self_hp_percent < $hp_max THEN RETREAT TARGET NEAREST
 * ```
 *
 * **왕복이 이 파일의 계약이다.** `parseRuleText(formatRuleText(x))` 는 `x` 와 같아야 한다.
 * 프리셋 공유가 이 형식으로 이뤄지므로(GDD §10 A), 왕복에서 한 필드라도 흘리면 남의 규칙표를
 * 붙여넣었을 때 조용히 다른 규칙표가 만들어진다 — 붙여넣은 사람은 원본이 그랬다고 믿는다.
 *
 * 왕복하지 **않는** 것이 하나 있다. `cpu_cost` 는 텍스트에 적지 않고 항 수에서 다시
 * 계산한다(GDD §3.6 의 1항=1 / 2항=2 / 3항=4). 사람이 손으로 맞출 값이 아니고, 텍스트에
 * 적어 두면 붙여넣은 코드가 비용만 틀린 채로 검증을 통과하지 못하는 일이 생긴다.
 * 자원 JSON 의 규칙표는 전부 이 관계를 지키므로 그것들은 그대로 왕복한다.
 *
 * 우변의 `$이름` 은 자기 스탯 참조다 (F-2). 리터럴과 한 글자로 갈리는 표기를 고른 이유는
 * `사거리` 를 이름으로 쓰면 값 `3` 과 눈으로 구별되지 않기 때문이다.
 */
import {
  COMPARISONS,
  type ConditionOp,
  OP_AND,
  OP_OR,
  OP_SINGLE,
  type Rhs,
  type Rule,
  type RuleSet,
  type StatRef,
  type Term,
  isStatRef,
} from '../core/schemas'
import { calculateCpuCost } from './draft'

/** 스탯 참조 우변의 접두어. */
export const STAT_PREFIX = '$'

/** 주석 줄의 접두어. 붙여넣은 코드에 설명이 섞여 와도 읽히게 한다. */
const COMMENT_PREFIX = '#'

/** `# ruleset <id> v<n>` — 규칙표의 이름과 세대. 없으면 부르는 쪽의 기본값을 쓴다. */
const HEADER_PATTERN = /^#\s*ruleset\s+(\S+)\s+v(\d+)\s*$/
const HEADER_KEYWORD = 'ruleset'

/** `[N] IF <조건> THEN <행동절>`. 번호는 생략할 수 있고 그때는 줄 순서로 매긴다. */
const RULE_PATTERN = /^(?:\[(\d+)\]\s*)?IF\s+(.+?)\s+THEN\s+(.+)$/

/** `lhs[param] cmp rhs`. 인자는 대괄호 안에 온다. */
const TERM_PATTERN = /^([A-Za-z_][A-Za-z0-9_]*)(?:\[([A-Za-z0-9_]+)\])?\s*(<=|>=|==|!=|<|>)\s*(.+)$/

/** `ACTION [TARGET SEL] [SET 플래그]`. */
const ACTION_PATTERN =
  /^([A-Za-z_][A-Za-z0-9_]*)(?:\s+TARGET\s+([A-Za-z_][A-Za-z0-9_]*))?(?:\s+SET\s+(\S+))?\s*$/

/** 조건식을 항과 연산자로 가르는 구분자. 괄호가 없는 문법이라 한 겹으로 끝난다. */
const CONDITION_SPLIT = /\s+(AND|OR)\s+/

/** 정수 리터럴. 부동소수는 코어에 들어오지 않는다. */
const INT_PATTERN = /^-?\d+$/

const DECIMAL_RADIX = 10

/** 파싱 결과. 규칙표와 오류 목록 중 하나만 채워진다. */
export interface RuleTextParse {
  /** 읽어 낸 규칙표. 오류가 하나라도 있으면 undefined 다. */
  readonly ruleset: RuleSet | undefined
  /** 사람이 읽는 오류 줄. `3행: ...` 형태로 줄 번호가 붙는다. */
  readonly errors: readonly string[]
}

/**
 * 우변 하나를 텍스트로 만든다.
 *
 * @param rhs 조건 항의 우변.
 * @returns 리터럴이면 값 그대로, 스탯 참조면 `$이름`.
 */
export function formatRhsText(rhs: Rhs): string {
  if (isStatRef(rhs)) {
    return `${STAT_PREFIX}${rhs.stat}`
  }
  return String(rhs)
}

/**
 * 조건 항 하나를 텍스트로 만든다.
 *
 * @param term 조건 항.
 * @returns `lhs[param] cmp rhs` 형태의 한 조각.
 */
export function formatTermText(term: Term): string {
  const lhs = term.lhsParam === null ? term.lhs : `${term.lhs}[${term.lhsParam}]`
  return `${lhs} ${term.comparison} ${formatRhsText(term.rhs)}`
}

/**
 * 규칙 한 줄을 텍스트로 만든다.
 *
 * @param rule 규칙.
 * @returns `[N] IF ... THEN ...` 한 줄.
 */
export function formatRuleLine(rule: Rule): string {
  const joiner = rule.conditions.op === OP_SINGLE ? ` ${OP_AND} ` : ` ${rule.conditions.op} `
  const condition = rule.conditions.terms.map(formatTermText).join(joiner)
  const parts = [`[${String(rule.priority)}]`, 'IF', condition, 'THEN', rule.action]
  if (rule.target !== null) {
    parts.push('TARGET', rule.target)
  }
  if (rule.setFlag !== null) {
    parts.push('SET', rule.setFlag)
  }
  return parts.join(' ')
}

/**
 * 규칙표 전체를 텍스트로 만든다. 이 문자열이 프리셋 공유의 단위다.
 *
 * @param ruleset 내보낼 규칙표.
 * @returns 머리글 한 줄과 규칙 한 줄씩.
 */
export function formatRuleText(ruleset: RuleSet): string {
  const header = `${COMMENT_PREFIX} ${HEADER_KEYWORD} ${ruleset.rulesetId} v${String(ruleset.version)}`
  return [header, ...ruleset.rules.map(formatRuleLine)].join('\n')
}

/**
 * 우변 텍스트를 읽는다.
 *
 * @param text 우변 조각.
 * @returns 리터럴 또는 스탯 참조. 형식을 알 수 없으면 undefined.
 */
function parseRhsText(text: string): Rhs | undefined {
  const body = text.trim()
  if (body === 'true') {
    return true
  }
  if (body === 'false') {
    return false
  }
  if (body.startsWith(STAT_PREFIX)) {
    const stat = body.slice(STAT_PREFIX.length)
    const ref: StatRef = { stat }
    return stat === '' ? undefined : ref
  }
  if (INT_PATTERN.test(body)) {
    return Number.parseInt(body, DECIMAL_RADIX)
  }
  return undefined
}

/**
 * 조건 항 하나를 읽는다.
 *
 * @param text 항 조각.
 * @param problems 오류를 쌓을 목록.
 * @param label 오류에 붙일 줄 표시.
 * @returns 읽어 낸 항. 실패하면 undefined.
 */
function parseTermText(text: string, problems: string[], label: string): Term | undefined {
  const matched = TERM_PATTERN.exec(text.trim())
  if (matched === null) {
    problems.push(`${label} 조건 항을 읽을 수 없다: ${text.trim()}`)
    return undefined
  }
  const [, lhs, param, cmp, rhsText] = matched
  if (lhs === undefined || cmp === undefined || rhsText === undefined) {
    problems.push(`${label} 조건 항을 읽을 수 없다: ${text.trim()}`)
    return undefined
  }
  const comparison = COMPARISONS.find((candidate) => candidate === cmp)
  if (comparison === undefined) {
    problems.push(`${label} 알 수 없는 비교 연산자다: ${cmp}`)
    return undefined
  }
  const rhs = parseRhsText(rhsText)
  if (rhs === undefined) {
    problems.push(`${label} 우변은 정수·true·false 이거나 ${STAT_PREFIX}스탯 이어야 한다: ${rhsText}`)
    return undefined
  }
  return { lhs, comparison, rhs, lhsParam: param ?? null }
}

/**
 * 조건식을 항 목록과 연산자로 가른다.
 *
 * AND 와 OR 를 한 줄에 섞는 것은 막는다. 괄호가 없는 문법에서 섞으면 결합 순서가 표기에
 * 나타나지 않아, 쓴 사람과 읽는 코어가 다른 뜻으로 읽게 된다.
 *
 * @param text 조건식 전체.
 * @param problems 오류를 쌓을 목록.
 * @param label 오류에 붙일 줄 표시.
 * @returns 연산자와 항 목록. 실패하면 undefined.
 */
function parseConditionText(
  text: string,
  problems: string[],
  label: string,
): { readonly op: ConditionOp; readonly terms: readonly Term[] } | undefined {
  const pieces = text.split(CONDITION_SPLIT)
  const operators = pieces.filter((_unused, index) => index % 2 === 1)
  const unique = [...new Set(operators)]
  if (unique.length > 1) {
    problems.push(`${label} 한 줄에 AND 와 OR 를 섞을 수 없다`)
    return undefined
  }
  const first = unique[0]
  let op: ConditionOp = OP_SINGLE
  if (first === OP_AND) {
    op = OP_AND
  } else if (first === OP_OR) {
    op = OP_OR
  }
  const terms: Term[] = []
  for (const piece of pieces.filter((_unused, index) => index % 2 === 0)) {
    const term = parseTermText(piece, problems, label)
    if (term === undefined) {
      return undefined
    }
    terms.push(term)
  }
  return { op, terms }
}

/**
 * 규칙 한 줄을 읽는다.
 *
 * @param line 줄 내용.
 * @param fallbackPriority 번호가 없을 때 쓸 우선순위.
 * @param problems 오류를 쌓을 목록.
 * @param label 오류에 붙일 줄 표시.
 * @returns 읽어 낸 규칙. 실패하면 undefined.
 */
function parseRuleLine(
  line: string,
  fallbackPriority: number,
  problems: string[],
  label: string,
): Rule | undefined {
  const matched = RULE_PATTERN.exec(line)
  if (matched === null) {
    problems.push(`${label} [번호] IF 조건 THEN 행동 형태가 아니다`)
    return undefined
  }
  const [, priorityText, conditionText, actionText] = matched
  if (conditionText === undefined || actionText === undefined) {
    problems.push(`${label} [번호] IF 조건 THEN 행동 형태가 아니다`)
    return undefined
  }
  const condition = parseConditionText(conditionText, problems, label)
  if (condition === undefined) {
    return undefined
  }
  const actionMatched = ACTION_PATTERN.exec(actionText.trim())
  if (actionMatched === null) {
    problems.push(`${label} THEN 뒤를 읽을 수 없다: ${actionText.trim()}`)
    return undefined
  }
  const [, action, target, setFlag] = actionMatched
  if (action === undefined) {
    problems.push(`${label} THEN 뒤를 읽을 수 없다: ${actionText.trim()}`)
    return undefined
  }
  return {
    priority:
      priorityText === undefined ? fallbackPriority : Number.parseInt(priorityText, DECIMAL_RADIX),
    conditions: condition,
    action,
    target: target ?? null,
    setFlag: setFlag ?? null,
    cpuCost: calculateCpuCost(condition.terms.length),
  }
}

/**
 * 텍스트를 규칙표로 읽는다. `formatRuleText` 의 역방향이다.
 *
 * 블록 id 가 목록에 있는지, 행동이 셀렉터를 받는지는 **여기서 보지 않는다**. 그것은
 * `validateRuleSet` 의 몫이고, 둘을 합치면 오타 하나에 두 종류의 메시지가 겹쳐 뜬다.
 * 이 함수가 답하는 것은 "이 문자열이 규칙표 모양인가" 하나다.
 *
 * @param text 텍스트 뷰의 내용.
 * @param rulesetId 머리글이 없을 때 쓸 규칙표 id.
 * @param version 머리글이 없을 때 쓸 세대.
 * @returns 규칙표 또는 오류 목록.
 */
export function parseRuleText(text: string, rulesetId: string, version: number): RuleTextParse {
  const problems: string[] = []
  const rules: Rule[] = []
  let foundId = rulesetId
  let foundVersion = version

  const lines = text.split('\n')
  for (const [index, raw] of lines.entries()) {
    const line = raw.trim()
    const label = `${String(index + 1)}행:`
    if (line === '') {
      continue
    }
    if (line.startsWith(COMMENT_PREFIX)) {
      const header = HEADER_PATTERN.exec(line)
      const [, id, versionText] = header ?? []
      if (id !== undefined && versionText !== undefined) {
        foundId = id
        foundVersion = Number.parseInt(versionText, DECIMAL_RADIX)
      }
      continue
    }
    const rule = parseRuleLine(line, rules.length + 1, problems, label)
    if (rule !== undefined) {
      rules.push(rule)
    }
  }

  if (problems.length > 0) {
    return { ruleset: undefined, errors: problems }
  }
  return {
    ruleset: { rulesetId: foundId, version: foundVersion, rules },
    errors: [],
  }
}
