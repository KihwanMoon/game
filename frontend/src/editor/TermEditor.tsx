/**
 * 조건 항 하나의 편집기 — **{인지변수} {비교} {값}** 세 조각을 고른다.
 *
 * 자유 입력이 아니라 선택인 이유는 속도다. 블록 id 를 타이핑하게 하면 오타가 곧 위반
 * 메시지가 되고, 사람은 자기 논리가 아니라 철자를 의심하며 시간을 쓴다 (P1). 고를 수 있는
 * 것만 화면에 있으면 틀린 규칙표는 만들 수 있어도 **읽을 수 없는 규칙표는 만들 수 없다.**
 *
 * 인자를 받는 인지 변수(쿨타임[스킬]·플래그[A~D]·대상거리[셀렉터]·가장가까운목표거리[타일])는
 * 인자 선택칸이 좌변 바로 옆에 함께 뜬다. 인자는 좌변의 일부이지 따로 붙는 옵션이 아니다.
 *
 * 전부 네이티브 `select`·`input` 이다. 키보드만으로 규칙 하나를 완성해야 하는데(과업 요구),
 * 직접 만든 드롭다운은 그 보장을 처음부터 다시 짜야 한다.
 */
import type { ChangeEvent } from 'react'

import { COMPARISONS, type BlockCatalog, type Comparison, type Term } from '../core/schemas'
import { listComparisons, listPerceptionGroups, listRhsStats } from './blockOptions'
import { buildDefaultRhs } from './draft'

/** 우변이 리터럴인지 자기 스탯 참조인지 (F-2). */
type RhsKind = 'literal' | 'stat'

const RHS_KIND_LITERAL: RhsKind = 'literal'
const RHS_KIND_STAT: RhsKind = 'stat'

const DECIMAL_RADIX = 10

/** TermEditor 가 부모에게 알리는 것들. */
export interface TermEditorProps {
  readonly term: Term
  readonly termIndex: number
  readonly catalog: BlockCatalog
  readonly removable: boolean
  readonly onLhsChange: (termIndex: number, blockId: string) => void
  readonly onTermChange: (termIndex: number, patch: Partial<Term>) => void
  readonly onRemove: (termIndex: number) => void
}

/**
 * 조건 항 한 줄을 그린다.
 *
 * @param props 항과 콜백들.
 * @returns 렌더 트리.
 */
export function TermEditor(props: TermEditorProps): React.JSX.Element {
  const { term, termIndex, catalog } = props
  const block = catalog.perceptions.get(term.lhs)
  const isBool = block?.returns === 'bool'
  const statRhs = typeof term.rhs === 'object'
  const rhsKind: RhsKind = statRhs ? RHS_KIND_STAT : RHS_KIND_LITERAL
  const stats = listRhsStats(catalog)

  /**
   * 좌변을 바꾼다. 인자와 우변은 부모가 새 블록 기준으로 다시 맞춘다.
   *
   * @param event 선택 변경 이벤트.
   */
  function handleLhs(event: ChangeEvent<HTMLSelectElement>): void {
    props.onLhsChange(termIndex, event.target.value)
  }

  /**
   * 우변의 종류를 리터럴과 스탯 참조 사이에서 바꾼다.
   *
   * @param event 선택 변경 이벤트.
   */
  function handleRhsKind(event: ChangeEvent<HTMLSelectElement>): void {
    if (event.target.value === RHS_KIND_STAT) {
      const first = stats[0]
      if (first !== undefined) {
        props.onTermChange(termIndex, { rhs: { stat: first.blockId } })
      }
      return
    }
    props.onTermChange(termIndex, { rhs: block === undefined ? 0 : buildDefaultRhs(block) })
  }

  return (
    <div className="term">
      <select
        className="term__field term__field--lhs"
        value={term.lhs}
        aria-label={`조건 ${String(termIndex + 1)} 인지 변수`}
        onChange={handleLhs}
      >
        {listPerceptionGroups(catalog).map((group) => (
          <optgroup label={group.labelKo} key={group.category}>
            {group.blocks.map((item) => (
              <option value={item.blockId} key={item.blockId}>
                {item.labelKo}
              </option>
            ))}
          </optgroup>
        ))}
      </select>

      {block?.param == null ? null : (
        <select
          className="term__field term__field--param"
          value={term.lhsParam ?? ''}
          aria-label={`조건 ${String(termIndex + 1)} ${block.param.name} 인자`}
          onChange={(event) => {
            props.onTermChange(termIndex, { lhsParam: event.target.value })
          }}
        >
          {block.param.values.map((value) => (
            <option value={value} key={value}>
              {value}
            </option>
          ))}
        </select>
      )}

      <select
        className="term__field term__field--cmp"
        value={term.comparison}
        aria-label={`조건 ${String(termIndex + 1)} 비교`}
        onChange={(event) => {
          props.onTermChange(termIndex, { comparison: event.target.value as Comparison })
        }}
      >
        {listComparisons(block, COMPARISONS).map((item) => (
          <option value={item} key={item}>
            {item}
          </option>
        ))}
      </select>

      {isBool ? null : (
        <select
          className="term__field term__field--kind"
          value={rhsKind}
          aria-label={`조건 ${String(termIndex + 1)} 우변 종류`}
          onChange={handleRhsKind}
        >
          <option value={RHS_KIND_LITERAL}>값</option>
          <option value={RHS_KIND_STAT}>내 스탯</option>
        </select>
      )}

      {isBool ? (
        <select
          className="term__field term__field--rhs"
          value={term.rhs === true ? 'true' : 'false'}
          aria-label={`조건 ${String(termIndex + 1)} 우변`}
          onChange={(event) => {
            props.onTermChange(termIndex, { rhs: event.target.value === 'true' })
          }}
        >
          <option value="true">참</option>
          <option value="false">거짓</option>
        </select>
      ) : null}

      {!isBool && rhsKind === RHS_KIND_STAT ? (
        <select
          className="term__field term__field--rhs"
          value={typeof term.rhs === 'object' ? term.rhs.stat : ''}
          aria-label={`조건 ${String(termIndex + 1)} 우변 스탯`}
          onChange={(event) => {
            props.onTermChange(termIndex, { rhs: { stat: event.target.value } })
          }}
        >
          {stats.map((item) => (
            <option value={item.blockId} key={item.blockId}>
              {item.labelKo}
            </option>
          ))}
        </select>
      ) : null}

      {!isBool && rhsKind === RHS_KIND_LITERAL ? (
        <input
          className="term__field term__field--number"
          type="number"
          inputMode="numeric"
          step={1}
          value={typeof term.rhs === 'number' ? term.rhs : 0}
          aria-label={`조건 ${String(termIndex + 1)} 우변 값`}
          onFocus={(event) => { event.target.select() }}
          onChange={(event) => {
            const parsed = Number.parseInt(event.target.value, DECIMAL_RADIX)
            props.onTermChange(termIndex, { rhs: Number.isNaN(parsed) ? 0 : parsed })
          }}
        />
      ) : null}

      <button
        type="button"
        className="term__drop"
        disabled={!props.removable}
        title="이 항을 지운다 (Alt+Backspace)"
        aria-label={`조건 ${String(termIndex + 1)} 삭제`}
        onClick={() => {
          props.onRemove(termIndex)
        }}
      >
        ×
      </button>
    </div>
  )
}
