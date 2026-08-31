/**
 * 규칙 한 줄을 한국어 문장으로 읽는다.
 *
 * **DSL 표기와 나란히 두는 것이지 대신하는 것이 아니다.** `ruleText.ts` 의 표기
 * (`적거리(2) <= 사거리(3) -> ATTACK @NEAREST`)는 값을 병기하고 그대로 옮겨 적을 수
 * 있어야 해서 그 모양이며, 그것이 이 게임의 문법이다. 다만 처음 보는 사람은 그 문법을
 * 모르고, **모르는 문법으로 적힌 목록에서는 무엇을 고를지 정할 수 없다.**
 *
 * 그래서 여기서 만드는 문장에는 실측값이 없다. 값은 판이 돌 때 로그가 말하고, 이 문장은
 * "이 규칙이 무엇을 하려는 것인가" 만 말한다.
 *
 * 라벨은 전부 `blocks.json` 의 `label_ko` 에서 온다 — 화면이 따로 이름을 지으면 카탈로그가
 * 바뀔 때 둘이 갈린다.
 */
import type { BlockCatalog, Comparison, Rhs, Rule, Term } from '../core/schemas'
import { OP_OR } from '../core/schemas'

/** 비교 연산자를 사람 말로. 문장 끝에 붙는 서술어라 「이면」 앞에 그대로 놓인다. */
export const COMPARISON_WORDS: ReadonlyMap<Comparison, string> = new Map([
  ['<', '미만'],
  ['<=', '이하'],
  ['>', '초과'],
  ['>=', '이상'],
  ['==', '이고'],
  ['!=', '이 아니고'],
])

/** 조건이 하나도 없을 때. 「언제나」가 참을 뜻한다는 것은 설명이 필요 없다. */
export const ALWAYS_TEXT = '언제나'

/**
 * 우변을 사람 말로 만든다.
 *
 * @param rhs 우변. 숫자·참거짓·스탯 참조 중 하나다.
 * @param catalog 블록 카탈로그. 스탯 이름을 여기서 찾는다.
 * @returns 우변 문구.
 */
export function formatRhsWord(rhs: Rhs, catalog: BlockCatalog): string {
  if (typeof rhs === 'boolean') {
    return rhs ? '참' : '거짓'
  }
  if (typeof rhs === 'number') {
    return String(rhs)
  }
  return catalog.rhsStats.get(rhs.stat)?.labelKo ?? rhs.stat
}

/**
 * 조건 항 하나를 사람 말로 만든다.
 *
 * @param term 항.
 * @param catalog 블록 카탈로그.
 * @returns 「내 HP% 가 40 이하」 꼴의 문구.
 */
export function formatTermWord(term: Term, catalog: BlockCatalog): string {
  const block = catalog.perceptions.get(term.lhs)
  const name = block?.labelKo ?? term.lhs
  // 인자가 붙는 인지(`enemy_type_present[SUMMONER]`)는 인자가 곧 뜻의 절반이다.
  const full = term.lhsParam === null ? name : `${name}(${term.lhsParam})`
  const word = COMPARISON_WORDS.get(term.comparison) ?? term.comparison
  return `${full} 가 ${formatRhsWord(term.rhs, catalog)} ${word}`
}

/**
 * 규칙 한 줄을 한국어 문장으로 만든다.
 *
 * @param rule 규칙.
 * @param catalog 블록 카탈로그.
 * @returns 「적 거리 가 3 이하이면 → 가장 가까운 적을 공격」 꼴의 문장.
 */
export function formatRuleSentence(rule: Rule, catalog: BlockCatalog): string {
  const terms = rule.conditions.terms
  const joiner = rule.conditions.op === OP_OR ? ' 또는 ' : ' 그리고 '
  const when =
    terms.length === 0
      ? ALWAYS_TEXT
      : `${terms.map((term) => formatTermWord(term, catalog)).join(joiner)}이면`
  const action = catalog.actions.get(rule.action)?.labelKo ?? rule.action
  const param = rule.actionParam === null ? '' : `[${rule.actionParam}]`
  const selector =
    rule.target === null
      ? ''
      : `${catalog.selectors.get(rule.target)?.labelKo ?? rule.target}을(를) `
  const flag = rule.setFlag === null ? '' : ` (깃발 ${rule.setFlag})`
  return `${when} → ${selector}${action}${param}${flag}`
}
