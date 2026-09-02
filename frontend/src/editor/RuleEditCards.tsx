/**
 * 모바일 규칙 편집의 카드 넷 — 조건 · 행동 · 우선순위 · CPU (명세 C).
 *
 * 데스크톱 에디터는 팔레트(320) · 우선순위 리스트 · 검증(300) 세 열이고, 규칙 한 줄이
 * 리스트 안에서 통째로 편집된다. 390px 에는 그 세 열이 들어가지 않는다 — 실측에서 팔레트
 * 하나가 41개 블록을 320px 열에 쌓아 40%만 보였다. 그래서 **세로에서는 규칙 하나가 화면
 * 하나**가 되고, 고를 것들이 팔레트가 아니라 카드 안의 선택 칸으로 들어온다.
 *
 * **판정과 편집 조작은 새로 짜지 않는다.** 규칙표를 고치는 것은 전부 `draft.ts` 의 순수
 * 함수이고(데스크톱 행이 부르는 것과 같은 `RuleRowActions`), 목록은 `blockOptions.ts`,
 * 실측 줄은 `termMeasure.ts` 가 만든다. 여기 있는 것은 배열과 표현뿐이다.
 *
 * 황동은 편집 화면에서 둘까지다 — 상단바의 규칙 번호와 저장 버튼. 그래서 카드 안에는
 * 황동이 하나도 없다. 우선순위 세그먼트의 활성도 명도와 굵기로만 적는다.
 *
 * 훅이 없다. 상태는 `RuleEditor` 가 들고 여기로는 값과 콜백만 내려온다.
 */
import { GlyphState, SegmentedGauge, ValueExpr } from '../ds'
import {
  COMPARISONS,
  MAX_TERMS,
  OP_AND,
  OP_OR,
  isStatRef,
  type BlockCatalog,
  type Comparison,
  type ConditionOp,
  type Rule,
  type Term,
} from '../core/schemas'
import {
  listActionGroups,
  listComparisons,
  listFlagNames,
  listPerceptionGroups,
  listRhsStats,
  formatParamLabel,
  listSelectorsForAction,
} from './blockOptions'
import { buildDefaultRhs } from './draft'
import { EditCard, EditField, EditNumber, EditSegments, type EditOptionGroup } from './EditParts'
import { FLAG_FALSE, FLAG_NONE, FLAG_TRUE, buildSetFlag, getFlagName, getFlagValue } from './flagClause'
import type { RuleRowActions } from './RuleRowEditor'
import { MEASURE_SOURCE, formatMeasuredTerm, resolveMeasureState, type TermReadings } from './termMeasure'

/** 항이 둘 이상일 때 고를 수 있는 연산자. 괄호가 없는 문법이라 한 줄에 한 종류만 온다. */
const EDIT_OPS: readonly ConditionOp[] = [OP_AND, OP_OR]

/** 우변이 리터럴인지 자기 스탯 참조인지 (F-2). 데스크톱 `TermEditor` 와 같은 두 갈래다. */
const RHS_LITERAL = 'literal'
const RHS_STAT = 'stat'

/** 카드 제목. */
const CONDITION_TITLE = '조건'
const ACTION_TITLE = '행동'
const PRIORITY_TITLE = '우선순위'
const CPU_TITLE = 'cpu'

/** 우선순위 카드의 설명문. 이 게임에서 순서가 곧 논리라는 사실이 여기 한 줄로 적힌다. */
export const PRIORITY_NOTE =
  '위에서부터 먼저 평가한다. 같은 틱에 참인 규칙이 여러 개면 위쪽 하나만 발동한다.'

/** 조건 항 추가 버튼의 글자. 점선 테두리라 「아직 없는 자리」로 읽힌다. */
const ADD_TERM_TEXT = '＋ 조건 추가'

/** ConditionCard 가 받는 props. */
export interface ConditionCardProps {
  readonly rule: Rule
  /** 규칙표 안에서의 자리. `actions` 가 이 첨자로 규칙을 찾는다. */
  readonly index: number
  readonly catalog: BlockCatalog
  /** 직전 틱의 측정값. 비어 있으면 모든 항이 pending 이다. */
  readonly readings: TermReadings
  readonly actions: RuleRowActions
}

/**
 * 인지 변수 목록을 선택 칸의 묶음으로 바꾼다.
 *
 * @param catalog 블록 카탈로그.
 * @returns 카테고리별 묶음.
 */
function buildPerceptionGroups(catalog: BlockCatalog): readonly EditOptionGroup[] {
  return listPerceptionGroups(catalog).map((group) => ({
    label: group.labelKo,
    options: group.blocks.map((block) => ({ value: block.blockId, label: block.labelKo })),
  }))
}

/**
 * 행동 목록을 선택 칸의 묶음으로 바꾼다.
 *
 * @param catalog 블록 카탈로그.
 * @returns 카테고리별 묶음.
 */
function buildActionGroups(catalog: BlockCatalog): readonly EditOptionGroup[] {
  return listActionGroups(catalog).map((group) => ({
    label: group.labelKo,
    options: group.blocks.map((block) => ({ value: block.blockId, label: block.labelKo })),
  }))
}

/**
 * 조건 항 하나의 우변 칸을 그린다 — 리터럴과 자기 스탯 참조 중 하나다 (F-2).
 *
 * 값 칸과 종류 칸을 한 칸 안에 둔 이유는 읽는 순서다. `적거리 <= 3` 은 왼쪽에서
 * 오른쪽으로 읽히는 한 문장이고, 종류를 값 앞에 두면 그 문장이 끊긴다.
 *
 * @param props 항·자리·카탈로그·콜백.
 * @returns 렌더 트리.
 */
function TermRhs(props: {
  readonly term: Term
  readonly index: number
  readonly termIndex: number
  readonly catalog: BlockCatalog
  readonly actions: RuleRowActions
}): React.JSX.Element {
  const { term, termIndex } = props
  const block = props.catalog.perceptions.get(term.lhs)
  const stats = listRhsStats(props.catalog)
  const name = `조건 ${String(termIndex + 1)}`

  if (block?.returns === 'bool') {
    return (
      <EditField
        label={`${name} 우변`}
        value={term.rhs === true ? FLAG_TRUE : FLAG_FALSE}
        options={[
          { value: FLAG_TRUE, label: '참' },
          { value: FLAG_FALSE, label: '거짓' },
        ]}
        onChange={(value) => {
          props.actions.changeTerm(props.index, termIndex, { rhs: value === FLAG_TRUE })
        }}
      />
    )
  }

  return (
    <span className="edit-cond__rhs">
      {isStatRef(term.rhs) ? (
        <EditField
          label={`${name} 우변 스탯`}
          value={term.rhs.stat}
          options={stats.map((stat) => ({ value: stat.blockId, label: stat.labelKo }))}
          onChange={(value) => {
            props.actions.changeTerm(props.index, termIndex, { rhs: { stat: value } })
          }}
        />
      ) : (
        <EditNumber
          label={`${name} 우변 값`}
          value={typeof term.rhs === 'number' ? term.rhs : 0}
          onChange={(value) => {
            props.actions.changeTerm(props.index, termIndex, { rhs: value })
          }}
        />
      )}
      <EditField
        label={`${name} 우변 종류`}
        value={isStatRef(term.rhs) ? RHS_STAT : RHS_LITERAL}
        options={[
          { value: RHS_LITERAL, label: '값' },
          { value: RHS_STAT, label: '스탯' },
        ]}
        onChange={(kind) => {
          const first = stats[0]
          if (kind === RHS_STAT && first !== undefined) {
            props.actions.changeTerm(props.index, termIndex, { rhs: { stat: first.blockId } })
            return
          }
          props.actions.changeTerm(props.index, termIndex, {
            rhs: block === undefined ? 0 : buildDefaultRhs(block),
          })
        }}
      />
    </span>
  )
}

/**
 * 조건 카드를 그린다 — 항마다 세 조각(좌변·비교·우변)과 그 아래 실측 줄.
 *
 * @param props 규칙·자리·카탈로그·측정값·콜백.
 * @returns 렌더 트리.
 */
export function ConditionCard(props: ConditionCardProps): React.JSX.Element {
  const { rule, index, catalog, actions } = props
  const terms = rule.conditions.terms
  const single = terms.length <= 1

  return (
    <EditCard title={CONDITION_TITLE} meta={MEASURE_SOURCE}>
      {terms.map((term, termIndex) => {
        const block = catalog.perceptions.get(term.lhs)
        const name = `조건 ${String(termIndex + 1)}`
        return (
          <div className="edit-cond__term" key={`term-${String(termIndex)}`}>
            <div className="edit-cond__row">
              <EditField
                label={`${name} 인지 변수`}
                value={term.lhs}
                groups={buildPerceptionGroups(catalog)}
                onChange={(blockId) => {
                  actions.changeLhs(index, termIndex, blockId)
                }}
              />
              <EditField
                label={`${name} 비교`}
                value={term.comparison}
                options={listComparisons(block, COMPARISONS).map((item) => ({
                  value: item,
                  label: item,
                }))}
                onChange={(value) => {
                  actions.changeTerm(index, termIndex, { comparison: value as Comparison })
                }}
              />
              <TermRhs
                term={term}
                index={index}
                termIndex={termIndex}
                catalog={catalog}
                actions={actions}
              />
              {block?.param == null ? null : (
                <EditField
                  wide
                  label={`${name} ${block.param.name} 인자`}
                  value={term.lhsParam ?? ''}
                  options={block.param.values.map((value) => ({ value, label: value }))}
                  onChange={(value) => {
                    actions.changeTerm(index, termIndex, { lhsParam: value })
                  }}
                />
              )}
            </div>

            <div className="edit-measure">
              <GlyphState state={resolveMeasureState(term, props.readings)} size="sm" />
              <ValueExpr text={formatMeasuredTerm(term, catalog, props.readings)} size="sm" />
              <button
                type="button"
                className="edit-measure__drop"
                disabled={single}
                aria-label={`${name} 삭제`}
                title="이 항을 지운다"
                onClick={() => {
                  actions.removeTerm(index, termIndex)
                }}
              >
                ×
              </button>
            </div>
          </div>
        )
      })}

      <div className="edit-cond__ops">
        {EDIT_OPS.map((op) => (
          <button
            key={op}
            type="button"
            className={`edit-op${rule.conditions.op === op ? ' edit-op--on' : ''}`}
            disabled={single}
            aria-pressed={rule.conditions.op === op}
            onClick={() => {
              actions.update(index, { conditions: { op, terms } })
            }}
          >
            {op}
          </button>
        ))}
        <button
          type="button"
          className="edit-op edit-op--add"
          disabled={terms.length >= MAX_TERMS}
          onClick={() => {
            actions.addTerm(index)
          }}
        >
          {ADD_TERM_TEXT}
        </button>
      </div>
    </EditCard>
  )
}

/** ActionCard 가 받는 props. */
export interface ActionCardProps {
  readonly rule: Rule
  readonly index: number
  readonly catalog: BlockCatalog
  readonly actions: RuleRowActions
}

/**
 * 행동 카드를 그린다 — 행동과 셀렉터, 그리고 SET 절.
 *
 * SET 절은 명세 C 의 표에 없지만 규칙의 일부다. 빼면 모바일에서 만든 규칙표가 플래그를
 * 쓰지 못하고, 그러면 같은 규칙표를 두 화면이 다르게 편집하는 상태가 된다 — 조건 칸과
 * 같은 모양의 줄 하나를 더하는 쪽을 골랐다.
 *
 * @param props 규칙·자리·카탈로그·콜백.
 * @returns 렌더 트리.
 */
export function ActionCard(props: ActionCardProps): React.JSX.Element {
  const { rule, index, catalog, actions } = props
  const action = catalog.actions.get(rule.action)
  const targeted = action?.targeted === true
  const flagName = getFlagName(rule.setFlag)
  const flagValue = getFlagValue(rule.setFlag)
  const label = `규칙 ${String(rule.priority)}`

  return (
    <EditCard title={ACTION_TITLE}>
      <div className="edit-act">
        <EditField
          label={`${label} 행동`}
          value={rule.action}
          groups={buildActionGroups(catalog)}
          wide={!targeted}
          onChange={(actionId) => {
            actions.changeAction(index, actionId)
          }}
        />
        {action?.param == null ? null : (
          <EditField
            label={`${label} ${action.param.name === 'item' ? '소모품' : '스킬'}`}
            value={rule.actionParam ?? action.param.values[0] ?? ''}
            options={action.param.values.map((value) => ({
              value,
              label: formatParamLabel(value),
            }))}
            onChange={(actionParam) => {
              actions.update(index, { actionParam })
            }}
          />
        )}
        {targeted ? (
          <EditField
            label={`${label} 대상`}
            value={rule.target ?? ''}
            options={listSelectorsForAction(catalog, action).map((item) => ({
              value: item.blockId,
              label: item.labelKo,
            }))}
            onChange={(target) => {
              actions.update(index, { target })
            }}
          />
        ) : null}
        <EditField
          label={`${label} 플래그`}
          value={flagName}
          wide={flagName === FLAG_NONE}
          options={[
            { value: FLAG_NONE, label: 'SET 없음' },
            ...listFlagNames(catalog).map((name) => ({ value: name, label: `SET ${name}` })),
          ]}
          onChange={(name) => {
            actions.update(index, { setFlag: buildSetFlag(name, flagValue) })
          }}
        />
        {flagName === FLAG_NONE ? null : (
          <EditField
            label={`${label} 플래그 값`}
            value={flagValue}
            options={[
              { value: FLAG_TRUE, label: '참' },
              { value: FLAG_FALSE, label: '거짓' },
            ]}
            onChange={(value) => {
              actions.update(index, { setFlag: buildSetFlag(flagName, value) })
            }}
          />
        )}
      </div>
    </EditCard>
  )
}

/** PriorityCard 가 받는 props. */
export interface PriorityCardProps {
  readonly rule: Rule
  readonly total: number
  /** 자리를 옮긴다. 편집 중인 규칙을 따라가야 하므로 `actions.move` 를 직접 부르지 않는다. */
  readonly onReorder: (to: number) => void
}

/**
 * 우선순위 카드를 그린다. 세그먼트 한 칸이 규칙표에서의 자리 하나다.
 *
 * @param props 규칙·규칙 수·자리 이동 콜백.
 * @returns 렌더 트리.
 */
export function PriorityCard(props: PriorityCardProps): React.JSX.Element {
  const slots = Array.from({ length: props.total }, (_unused, at) => String(at + 1))
  return (
    <EditCard title={PRIORITY_TITLE}>
      <EditSegments
        label="우선순위"
        value={String(props.rule.priority)}
        options={slots.map((slot) => ({ value: slot, label: slot }))}
        onPick={(value) => {
          props.onReorder(Number(value) - 1)
        }}
      />
      <p className="edit-note">{PRIORITY_NOTE}</p>
    </EditCard>
  )
}

/** CpuCard 가 받는 props. */
export interface CpuCardProps {
  readonly rule: Rule
  /** 이 편집을 저장한 뒤의 규칙표 합계. */
  readonly totalCpu: number
  readonly cpuBudget: number
}

/**
 * CPU 카드를 그린다.
 *
 * **예산 초과는 오류가 아니라 수치다** (GDD §3.6). 게이지 색만 위험색으로 넘어가고
 * 편집은 그대로 계속된다 — 막으면 "얼마나 넘겼는지" 를 볼 수 없다.
 *
 * @param props 규칙과 합계·예산.
 * @returns 렌더 트리.
 */
export function CpuCard(props: CpuCardProps): React.JSX.Element {
  const over = props.totalCpu > props.cpuBudget
  const readout = `${String(props.totalCpu)} / ${String(props.cpuBudget)}`
  return (
    <EditCard title={CPU_TITLE}>
      <SegmentedGauge
        label={CPU_TITLE}
        value={props.totalCpu}
        max={props.cpuBudget}
        tone={over ? 'danger' : 'cpu'}
        readout={readout}
      />
      <div className="edit-cpu">
        <span className="edit-cpu__item">{`이 규칙 cpu ${String(props.rule.cpuCost)}`}</span>
        <span className="edit-cpu__item">{`저장 후 ${readout}`}</span>
      </div>
    </EditCard>
  )
}
