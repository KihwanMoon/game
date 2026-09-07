/**
 * 규칙 한 줄을 고치는 조작들 — **화면과 상태 사이의 계약**.
 *
 * `RuleEditor` 가 상태를 들고 이 묶음을 내려보내면, 편집 화면은 그것을 부르기만 한다.
 * 그래서 화면이 규칙표를 직접 고치지 않고, 되돌리기(`취소`)가 한 곳에서만 일어난다.
 *
 * **제 모듈에 산다.** 예전에는 데스크톱 줄 편집기(`RuleRowEditor`) 안에 있었는데,
 * 데스크톱 배치를 지울 때 계약까지 함께 사라질 뻔했다 — 계약은 배치가 아니다.
 */
import type { Rule, Term } from '../core/schemas'

/** 규칙 줄에 걸 수 있는 조작 전부. */
export interface RuleRowActions {
  readonly update: (index: number, patch: Partial<Rule>) => void
  readonly changeLhs: (ruleIndex: number, termIndex: number, blockId: string) => void
  readonly changeTerm: (ruleIndex: number, termIndex: number, patch: Partial<Term>) => void
  readonly changeAction: (ruleIndex: number, actionId: string) => void
  readonly changeParam: (ruleIndex: number, actionParam: string) => void
  readonly addTerm: (ruleIndex: number) => void
  readonly removeTerm: (ruleIndex: number, termIndex: number) => void
  readonly addRule: (index: number) => void
  readonly duplicate: (index: number) => void
  readonly remove: (index: number) => void
  readonly move: (from: number, to: number) => void
}
