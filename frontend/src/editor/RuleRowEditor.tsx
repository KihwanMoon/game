/**
 * 우선순위 리스트의 한 줄 — 규칙 하나를 통째로 편집한다.
 *
 * 리스트에서 **위에 있는 줄이 먼저 평가된다**(TDD §5.2). 순서가 곧 논리이므로 순서를 바꾸는
 * 길이 두 개다. 마우스로는 좌측 손잡이를 끌고, 키보드로는 Alt+↑/↓ 를 누른다. 드래그만 두면
 * 키보드로는 규칙표를 완성할 수 없고, 그것은 과업이 못박은 요구를 어기는 것이다.
 *
 * 좌측 세로바는 세 가지를 동시에 적는다 — 선택(황동), CPU 예산 초과(rust), 그 밖(괘선).
 * 초과는 오류가 아니라 수치이므로 편집을 막지 않는다 (GDD §3.6).
 */
import type { KeyboardEvent } from 'react'

import { GlyphState } from '../ds'
import { MAX_TERMS, type BlockCatalog, type Rule, type Term } from '../core/schemas'
import { listActionGroups, listFlagNames, listSelectorsForAction } from './blockOptions'
import { TermEditor } from './TermEditor'

/** SET 절이 없음을 고르는 값. 빈 문자열은 select 의 기본값과 섞이므로 따로 둔다. */
const FLAG_NONE = 'NONE'
const FLAG_SEPARATOR = '='
const FLAG_TRUE = 'true'
const FLAG_FALSE = 'false'

/** 부모가 규칙표를 고치는 통로. 한 조작이 한 함수다. */
export interface RuleRowActions {
  readonly select: (index: number) => void
  readonly update: (index: number, patch: Partial<Rule>) => void
  readonly changeLhs: (ruleIndex: number, termIndex: number, blockId: string) => void
  readonly changeTerm: (ruleIndex: number, termIndex: number, patch: Partial<Term>) => void
  readonly changeAction: (ruleIndex: number, actionId: string) => void
  readonly addTerm: (ruleIndex: number) => void
  readonly removeTerm: (ruleIndex: number, termIndex: number) => void
  readonly addRule: (index: number) => void
  readonly duplicate: (index: number) => void
  readonly remove: (index: number) => void
  readonly move: (from: number, to: number) => void
}

/** RuleRowEditor 의 props. */
export interface RuleRowEditorProps {
  readonly rule: Rule
  readonly index: number
  readonly total: number
  readonly catalog: BlockCatalog
  readonly selected: boolean
  readonly overBudget: boolean
  readonly problems: readonly string[]
  /** 지금 끌고 있는 규칙이 여기 놓일 자리인지. 놓을 곳을 선으로 미리 보여 준다. */
  readonly dropTarget: boolean
  readonly actions: RuleRowActions
  readonly onDragBegin: (index: number) => void
  readonly onDragOverRow: (index: number) => void
  readonly onDrop: (index: number) => void
}

/**
 * SET 절 문자열에서 플래그 이름을 읽는다.
 *
 * @param setFlag `A=true` 형태의 SET 절. 없으면 null.
 * @returns 플래그 이름, 또는 없음 표시.
 */
function getFlagName(setFlag: string | null): string {
  if (setFlag === null) {
    return FLAG_NONE
  }
  const separator = setFlag.indexOf(FLAG_SEPARATOR)
  return separator < 0 ? setFlag : setFlag.slice(0, separator)
}

/**
 * SET 절 문자열에서 넣을 값을 읽는다.
 *
 * 코어는 `=` 뒤가 `false` 가 아니면 전부 참으로 읽는다(actions.ts). 여기서도 같은 판정을
 * 쓴다 — 화면이 참이라 적은 것을 엔진이 거짓으로 읽으면 규칙표가 조용히 다르게 돈다.
 *
 * @param setFlag `A=true` 형태의 SET 절. 없으면 null.
 * @returns 'true' 또는 'false'.
 */
function getFlagValue(setFlag: string | null): string {
  if (setFlag === null) {
    return FLAG_TRUE
  }
  const separator = setFlag.indexOf(FLAG_SEPARATOR)
  const raw = separator < 0 ? '' : setFlag.slice(separator + 1)
  return raw.trim().toLowerCase() === FLAG_FALSE ? FLAG_FALSE : FLAG_TRUE
}

/**
 * 규칙 한 줄을 그린다.
 *
 * @param props 규칙과 콜백들.
 * @returns 렌더 트리.
 */
export function RuleRowEditor(props: RuleRowEditorProps): React.JSX.Element {
  const { rule, index, catalog, actions } = props
  const action = catalog.actions.get(rule.action)
  const flagName = getFlagName(rule.setFlag)
  const flagValue = getFlagValue(rule.setFlag)
  const flagNames = listFlagNames(catalog)
  const invalid = props.problems.length > 0

  /**
   * 플래그 선택을 SET 절 문자열로 되돌린다.
   *
   * @param name 플래그 이름. 없음이면 SET 절을 지운다.
   * @param value 넣을 값.
   */
  function applyFlag(name: string, value: string): void {
    actions.update(index, {
      setFlag: name === FLAG_NONE ? null : `${name}${FLAG_SEPARATOR}${value}`,
    })
  }

  /**
   * 한 동작 단축키를 처리한다. 전부 Alt 조합이라 입력칸의 타이핑과 겹치지 않는다.
   *
   * @param event 키 이벤트.
   */
  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>): void {
    if (!event.altKey) {
      return
    }
    const handlers: ReadonlyMap<string, () => void> = new Map([
      ['ArrowUp', () => { actions.move(index, index - 1) }],
      ['ArrowDown', () => { actions.move(index, index + 1) }],
      ['Enter', () => { actions.addRule(index) }],
      ['d', () => { actions.duplicate(index) }],
      ['Backspace', () => { actions.remove(index) }],
      ['Delete', () => { actions.remove(index) }],
      ['t', () => { actions.addTerm(index) }],
    ])
    const handler = handlers.get(event.key)
    if (handler !== undefined) {
      event.preventDefault()
      handler()
    }
  }

  const barKind = props.overBudget ? 'over' : props.selected ? 'selected' : 'plain'

  return (
    <div
      className={`rule-row${props.selected ? ' is-selected' : ''}${invalid ? ' is-invalid' : ''}${props.dropTarget ? ' is-drop-target' : ''}`}
      role="group"
      aria-label={`규칙 ${String(rule.priority)}`}
      tabIndex={0}
      onFocus={() => { actions.select(index) }}
      onMouseDown={() => { actions.select(index) }}
      onKeyDown={handleKeyDown}
      onDragOver={(event) => { event.preventDefault(); props.onDragOverRow(index) }}
      onDrop={(event) => { event.preventDefault(); props.onDrop(index) }}
    >
      <span className={`rule-row__bar rule-row__bar--${barKind}`} aria-hidden="true" />

      <div className="rule-row__head">
        <span
          className="rule-row__handle"
          draggable
          role="button"
          tabIndex={-1}
          aria-label={`규칙 ${String(rule.priority)} 순서 손잡이`}
          title="끌어서 순서 변경 · Alt+↑/↓"
          onDragStart={() => { props.onDragBegin(index) }}
        >
          ≡
        </span>
        <span className="rule-row__index">[{rule.priority}]</span>
        <GlyphState state={invalid ? 'danger' : 'pending'} size="sm" label={`cpu ${String(rule.cpuCost)}`} />
        <span className="rule-row__spacer" />
        <button type="button" className="rule-row__op" title="위로 (Alt+↑)" onClick={() => { actions.move(index, index - 1) }} disabled={index === 0}>▲</button>
        <button type="button" className="rule-row__op" title="아래로 (Alt+↓)" onClick={() => { actions.move(index, index + 1) }} disabled={index === props.total - 1}>▼</button>
        <button type="button" className="rule-row__op" title="복제 (Alt+D)" onClick={() => { actions.duplicate(index) }}>⧉</button>
        <button type="button" className="rule-row__op" title="아래에 규칙 추가 (Alt+Enter)" onClick={() => { actions.addRule(index) }}>＋</button>
        <button type="button" className="rule-row__op" title="삭제 (Alt+Backspace)" onClick={() => { actions.remove(index) }}>×</button>
      </div>

      <div className="rule-row__terms">
        {rule.conditions.terms.map((term, termIndex) => (
          <div className="rule-row__term" key={`term-${String(termIndex)}`}>
            <span className="rule-row__joiner">
              {termIndex === 0 ? 'IF' : rule.conditions.op}
            </span>
            <TermEditor
              term={term}
              termIndex={termIndex}
              catalog={catalog}
              removable={rule.conditions.terms.length > 1}
              onLhsChange={(at, blockId) => { actions.changeLhs(index, at, blockId) }}
              onTermChange={(at, patch) => { actions.changeTerm(index, at, patch) }}
              onRemove={(at) => { actions.removeTerm(index, at) }}
            />
          </div>
        ))}
        <div className="rule-row__term rule-row__term--tools">
          <span className="rule-row__joiner" />
          <button
            type="button"
            className="rule-row__add-term"
            disabled={rule.conditions.terms.length >= MAX_TERMS}
            title="조건 항 추가 (Alt+T)"
            onClick={() => { actions.addTerm(index) }}
          >
            ＋ 조건
          </button>
          {rule.conditions.terms.length > 1 ? (
            <select
              className="term__field term__field--op"
              value={rule.conditions.op}
              aria-label={`규칙 ${String(rule.priority)} 조건 연산자`}
              onChange={(event) => {
                actions.update(index, {
                  conditions: { op: event.target.value as Rule['conditions']['op'], terms: rule.conditions.terms },
                })
              }}
            >
              <option value="AND">AND — 전부 참</option>
              <option value="OR">OR — 하나라도 참</option>
            </select>
          ) : null}
        </div>
      </div>

      <div className="rule-row__act">
        <span className="rule-row__joiner">THEN</span>
        <select
          className="term__field term__field--action"
          value={rule.action}
          aria-label={`규칙 ${String(rule.priority)} 행동`}
          onChange={(event) => { actions.changeAction(index, event.target.value) }}
        >
          {listActionGroups(catalog).map((group) => (
            <optgroup label={group.labelKo} key={group.category}>
              {group.blocks.map((item) => (
                <option value={item.blockId} key={item.blockId}>
                  {item.labelKo}
                </option>
              ))}
            </optgroup>
          ))}
        </select>

        {action?.targeted === true ? (
          <>
            <span className="rule-row__joiner">TARGET</span>
            <select
              className="term__field term__field--target"
              value={rule.target ?? ''}
              aria-label={`규칙 ${String(rule.priority)} 대상`}
              onChange={(event) => { actions.update(index, { target: event.target.value }) }}
            >
              {listSelectorsForAction(catalog, action).map((item) => (
                <option value={item.blockId} key={item.blockId}>
                  {item.labelKo}
                </option>
              ))}
            </select>
          </>
        ) : null}

        <span className="rule-row__joiner">SET</span>
        <select
          className="term__field term__field--flag"
          value={flagName}
          aria-label={`규칙 ${String(rule.priority)} 플래그`}
          onChange={(event) => { applyFlag(event.target.value, flagValue) }}
        >
          <option value={FLAG_NONE}>없음</option>
          {flagNames.map((name) => (
            <option value={name} key={name}>
              {name}
            </option>
          ))}
        </select>
        {flagName === FLAG_NONE ? null : (
          <select
            className="term__field term__field--flagval"
            value={flagValue}
            aria-label={`규칙 ${String(rule.priority)} 플래그 값`}
            onChange={(event) => { applyFlag(flagName, event.target.value) }}
          >
            <option value={FLAG_TRUE}>참</option>
            <option value={FLAG_FALSE}>거짓</option>
          </select>
        )}
      </div>

      {invalid ? (
        <ul className="rule-row__problems">
          {props.problems.map((text) => (
            <li key={text}>
              <GlyphState state="danger" size="sm" label={text} />
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
