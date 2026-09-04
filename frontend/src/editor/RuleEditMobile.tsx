/**
 * 모바일 규칙 편집 화면 (명세 C).
 *
 * **세로에서 규칙 편집은 전용 전체 화면이다.** 데스크톱의 세 열(팔레트 320 · 우선순위
 * 리스트 · 검증 300)을 390px 안에 밀어 넣지 않는다 — 실측에서 팔레트 하나가 블록 41개를
 * 320px 열에 쌓아 40%만 보였고, 그것을 더 좁은 화면에 그대로 옮기면 고를 수 없는 목록이
 * 된다. 대신 화면을 둘로 나눈다.
 *
 *   규칙표 목록  ──[규칙 줄을 누른다]──▶  규칙 하나의 전용 편집 화면
 *        ▲                                          │
 *        └──────────────[취소 · 저장]───────────────┘
 *
 * 명세 C 가 그린 것은 뒤쪽 화면이다. 앞쪽 목록을 함께 두는 이유는 **어디로도 나갈 수 없는
 * 화면을 만들지 않기 위해서다** — 규칙을 고르고, 더하고, 저장한 규칙표를 불러오고,
 * 출격시키는 길이 전부 목록에 있다. 명세의 `← 전투로` 는 전투 화면에서 곧장 들어오는
 * 흐름을 적은 것이고, 앱에서 편집 화면의 뒤는 그 목록이라 라벨만 `backLabel` 로 받는다.
 *
 * **저장과 취소가 무엇을 하는가.** 편집은 데스크톱과 똑같이 즉시 반영된다(규칙표 한 벌이
 * 두 화면을 잇는다). 그래서 `저장` 은 확정하고 목록으로 돌아가는 일이고, `취소` 는 이
 * 화면을 **열었을 때의 규칙표로 되돌리고** 나가는 일이다. 되돌릴 지점은 화면을 여는
 * 쪽(`RuleEditor`)이 들고 있다.
 *
 * 황동 예산은 이 화면에서 둘이다 — 상단바의 규칙 번호와 저장 버튼(모바일 원본). 그래서
 * 카드 안에도, 목록에도 황동이 없다.
 *
 * **훅이 없다.** 상태는 전부 `RuleEditor` 가 들고 여기로는 값과 콜백만 내려온다. 그래서
 * 테스트가 이 함수를 직접 불러 반환된 트리에서 칸을 고르고 버튼을 눌러 볼 수 있다.
 */
import type { ReactNode } from 'react'

import { GlyphState, SegmentedGauge, ValueExpr } from '../ds'
import type { BlockCatalog, RuleSet } from '../core/schemas'
import { formatActionLabel } from './blockOptions'
import { calculateTotalCpu } from './draft'
import { COMBAT_TAB_ID, type EditorTab } from './editorTabs'
import { ActionCard, ConditionCard, CpuCard, PriorityCard } from './RuleEditCards'
import type { RuleRowActions } from './RuleRowEditor'
import { formatMeasuredCondition, type TermReadings } from './termMeasure'

/** 화면 글자. 한 곳에 모아 두어 두 배치가 같은 말을 쓰게 한다. */
const LIST_TITLE = '규칙표'
const ADD_RULE_TEXT = '＋ 규칙 추가'
const CANCEL_TEXT = '되돌리기'
const SAVE_TEXT = '저장'
const CPU_LABEL = 'cpu'
const PASS_TEXT = '검증 통과'

/** 이 화면이 설 수 있는 배치. 데스크톱은 세 열 에디터가 그대로 선다. */
export type EditLayout = 'portrait' | 'landscape'

/** RuleEditMobile 이 받는 props. */
export interface RuleEditMobileProps {
  readonly mode: EditLayout
  readonly ruleset: RuleSet
  readonly catalog: BlockCatalog
  readonly cpuBudget: number
  readonly ruleSlots: number
  /** 규칙 번호별 검증 메시지. 규칙 줄 **아래**에 붙는다 — 목록만 따로 있으면 못 따라간다. */
  readonly problems: ReadonlyMap<number, readonly string[]>
  /** 규칙표 전체에 걸리는 메시지. 목록 화면의 아래에 적는다. */
  readonly globalProblems: readonly string[]
  /** 편집 중인 규칙의 자리. 음수면 목록 화면이다. */
  readonly editIndex: number
  /** 직전 틱의 측정값. 비어 있으면 실측 줄이 `–` 와 pending 으로 선다. */
  readonly readings: TermReadings
  readonly actions: RuleRowActions
  readonly onOpen: (index: number) => void
  readonly onAdd: () => void
  /** 편집 중인 규칙의 자리를 옮긴다. 화면이 그 규칙을 따라가야 한다. */
  readonly onReorder: (to: number) => void
  readonly onCancel: () => void
  readonly onSave: () => void
  /** 편집 화면 왼쪽 위에 적을 돌아갈 곳의 이름. */
  readonly backLabel: string
  /** 앱이 끼워 넣는 조작부(방·시드·출격·되돌리기). 없으면 목록에서 나갈 길이 사라진다. */
  readonly controls?: ReactNode
  /** 앱이 끼워 넣는 코드 라이브러리(프리셋 8슬롯·공유 코드). */
  readonly library?: ReactNode
  /**
   * 전투 말고 더 있는 규칙표 탭들. 정비 규칙이 여기 온다.
   *
   * **모바일은 세 열을 못 편다.** 그래서 데스크톱처럼 팔레트·본문·검증을 나란히 두지 않고
   * 세로로 쌓는다 — 좁은 화면의 규약이다 (명세 C).
   */
  readonly tabs?: readonly EditorTab[]
  /** 지금 열린 탭. 전투면 `COMBAT_TAB_ID`. */
  readonly tabId?: string
  readonly onTab?: (id: string) => void
}

/** RuleListScreen 이 받는 props. */
interface RuleListScreenProps extends RuleEditMobileProps {
  readonly totalCpu: number
}

/**
 * 규칙표 목록 화면을 그린다. 규칙 줄을 누르면 그 규칙의 편집 화면이 열린다.
 *
 * 조건문은 **잘리지 않는다.** 실측값 병기가 규칙 줄의 존재 이유이므로(GDD §8.2, P1)
 * 끝이 사라지면 줄이 있는 뜻이 없다 — 좁으면 자르지 않고 접는다.
 *
 * @param props 규칙표와 콜백들.
 * @returns 렌더 트리.
 */
function RuleListScreen(props: RuleListScreenProps): React.JSX.Element {
  const { ruleset, catalog } = props
  const problemCount =
    props.globalProblems.length + [...props.problems.values()].reduce((sum, one) => sum + one.length, 0)
  const over = props.totalCpu > props.cpuBudget
  const tabs = props.tabs ?? []
  const openTab = tabs.find((tab) => tab.id === props.tabId)
  const tabStrip =
    tabs.length === 0 || props.onTab === undefined ? null : (
      <div className="edit-m__tabs" role="tablist">
        <button
          type="button"
          className={`edit-m__tab${openTab === undefined ? ' edit-m__tab--on' : ''}`}
          aria-pressed={openTab === undefined}
          onClick={() => {
            props.onTab?.(COMBAT_TAB_ID)
          }}
        >
          전투 규칙
        </button>
        {tabs.map((tab) => (
          <button
            type="button"
            key={tab.id}
            className={`edit-m__tab${tab.id === props.tabId ? ' edit-m__tab--on' : ''}`}
            aria-pressed={tab.id === props.tabId}
            onClick={() => {
              props.onTab?.(tab.id)
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>
    )

  // 전투가 아닌 규칙표를 고르고 있다. **팔레트·본문·검증을 세로로 쌓는다** — 좁은
  // 화면에는 열이 하나뿐이라, 세 열을 나란히 두려 하면 전부 못 읽을 폭이 된다.
  if (openTab !== undefined) {
    return (
      <div className={`edit-m edit-m--${props.mode} edit-m--list`}>
        <header className="edit-m__bar edit-m__bar--top">
          <h1 className="edit-m__title">{openTab.label}</h1>
          <span className="edit-m__meta">{openTab.gauge}</span>
        </header>
        <div className="edit-m__body">
          {tabStrip}
          {props.controls === undefined ? null : (
            <div className="edit-m__controls">{props.controls}</div>
          )}
          {openTab.main}
          {openTab.palette}
          {openTab.check}
          {props.library}
        </div>
      </div>
    )
  }

  return (
    <div className={`edit-m edit-m--${props.mode} edit-m--list`}>
      <header className="edit-m__bar edit-m__bar--top">
        <h1 className="edit-m__title">{LIST_TITLE}</h1>
        <span className="edit-m__meta">
          <ValueExpr
            text={`규칙 ${String(ruleset.rules.length)} / ${String(props.ruleSlots)}`}
            size="sm"
            dim
          />
          <GlyphState
            state={problemCount === 0 ? 'true' : 'danger'}
            size="sm"
            label={problemCount === 0 ? PASS_TEXT : `위반 ${String(problemCount)}`}
          />
        </span>
      </header>

      <div className="edit-m__body">
        {tabStrip}
        {props.controls === undefined ? null : (
          <div className="edit-m__controls">{props.controls}</div>
        )}

        <ul className="edit-m__rules">
          {ruleset.rules.map((rule, at) => {
            const found = props.problems.get(rule.priority) ?? []
            return (
              <li className="edit-m__rule" key={`rule-${String(at)}`}>
                <button
                  type="button"
                  className="edit-m__hit"
                  aria-label={`규칙 ${String(rule.priority)} 편집`}
                  onClick={() => {
                    props.onOpen(at)
                  }}
                >
                  <span className="edit-m__index">[{rule.priority}]</span>
                  <span className="edit-m__lines">
                    <ValueExpr
                      text={formatMeasuredCondition(rule, catalog, props.readings)}
                      size="sm"
                    />
                    <span className="edit-m__act">{formatActionLabel(rule, catalog)}</span>
                  </span>
                  <GlyphState
                    state={found.length > 0 ? 'danger' : 'pending'}
                    size="sm"
                    label={`cpu ${String(rule.cpuCost)}`}
                  />
                </button>
                <span className="edit-m__ops">
                  <button
                    type="button"
                    className="edit-m__op"
                    aria-label={`규칙 ${String(rule.priority)} 복제`}
                    onClick={() => {
                      props.actions.duplicate(at)
                    }}
                  >
                    ⧉
                  </button>
                  <button
                    type="button"
                    className="edit-m__op"
                    aria-label={`규칙 ${String(rule.priority)} 삭제`}
                    onClick={() => {
                      props.actions.remove(at)
                    }}
                  >
                    ×
                  </button>
                </span>
                {found.length === 0 ? null : (
                  <ul className="edit-m__problems">
                    {found.map((text) => (
                      <li key={text}>
                        <GlyphState state="danger" size="sm" label={text} />
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            )
          })}
        </ul>

        <div className="edit-m__add">
          <button type="button" className="edit-op edit-op--add" onClick={props.onAdd}>
            {ADD_RULE_TEXT}
          </button>
        </div>

        {props.globalProblems.length === 0 ? null : (
          <ul className="edit-m__problems edit-m__problems--global">
            {props.globalProblems.map((text) => (
              <li key={text}>
                <GlyphState state="danger" size="sm" label={text} />
              </li>
            ))}
          </ul>
        )}

        {props.library}
      </div>

      <footer className="edit-m__foot">
        <SegmentedGauge
          label={CPU_LABEL}
          value={props.totalCpu}
          max={props.cpuBudget}
          tone={over ? 'danger' : 'cpu'}
          readout={`${String(props.totalCpu)} / ${String(props.cpuBudget)}`}
        />
      </footer>
    </div>
  )
}

/** RuleEditScreen 이 받는 props. */
interface RuleEditScreenProps extends RuleEditMobileProps {
  readonly totalCpu: number
  readonly at: number
}

/**
 * 규칙 하나의 전용 편집 화면을 그린다 — 명세 C 의 카드 넷.
 *
 * 세로는 카드를 쌓고 하단바에 취소·저장을 둔다. 가로는 `1fr 300px` 두 열이고 취소·저장이
 * 우열 안으로 들어간다 — 높이가 390px 뿐이라 하단바를 하나 더 쌓을 자리가 없다.
 *
 * @param props 규칙표·자리·콜백들.
 * @returns 렌더 트리.
 */
function RuleEditScreen(props: RuleEditScreenProps): React.JSX.Element {
  const rule = props.ruleset.rules[props.at]
  if (rule === undefined) {
    return <RuleListScreen {...props} />
  }
  const found = props.problems.get(rule.priority) ?? []

  const buttons = (
    <div className="edit-m__actions">
      <button type="button" className="edit-m__btn" onClick={props.onCancel}>
        {CANCEL_TEXT}
      </button>
      <button type="button" className="edit-m__btn edit-m__btn--save" onClick={props.onSave}>
        {SAVE_TEXT}
      </button>
    </div>
  )

  const problemList =
    found.length === 0 ? null : (
      <ul className="edit-m__problems">
        {found.map((text) => (
          <li key={text}>
            <GlyphState state="danger" size="sm" label={text} />
          </li>
        ))}
      </ul>
    )

  const condition = (
    <ConditionCard
      rule={rule}
      index={props.at}
      catalog={props.catalog}
      readings={props.readings}
      actions={props.actions}
    />
  )
  const action = (
    <ActionCard rule={rule} index={props.at} catalog={props.catalog} actions={props.actions} />
  )
  const priority = (
    <PriorityCard rule={rule} total={props.ruleset.rules.length} onReorder={props.onReorder} />
  )
  const cpu = <CpuCard rule={rule} totalCpu={props.totalCpu} cpuBudget={props.cpuBudget} />

  const head = (
    <header className="edit-m__bar edit-m__bar--top">
      {/* **뒤로는 되돌리기가 아니다.** 예전에는 이 화살표가 `onCancel` 을 불러, 규칙을
          고치고 목록으로 돌아가면 고친 것이 조용히 사라졌다 — 그것이 "수정해도 저장이
          안 된다" 로 보고됐다. 되돌리는 것은 아래의 「취소」 하나뿐이다. */}
      <button type="button" className="edit-m__back" onClick={props.onSave}>
        <span className="edit-m__back-arrow" aria-hidden="true">
          ←
        </span>
        {props.backLabel}
      </button>
      <h1 className="edit-m__heading">
        <span className="edit-m__heading-num">{rule.priority}</span>번 규칙 편집
      </h1>
    </header>
  )

  if (props.mode === 'landscape') {
    return (
      <div className="edit-m edit-m--landscape edit-m--edit">
        {head}
        <div className="edit-ls__body">
          <div className="edit-ls__col edit-ls__col--main">
            {condition}
            {action}
            {problemList}
          </div>
          <div className="edit-ls__col edit-ls__col--side">
            {priority}
            {cpu}
            {buttons}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="edit-m edit-m--portrait edit-m--edit">
      {head}
      <div className="edit-m__body edit-m__cards">
        {condition}
        {action}
        {priority}
        {cpu}
        {problemList}
      </div>
      <footer className="edit-m__bar edit-m__bar--edit">{buttons}</footer>
    </div>
  )
}

/**
 * 모바일 규칙 편집 화면을 그린다. 목록과 전용 편집 화면 중 하나가 선다.
 *
 * @param props 규칙표·검증·콜백 전부.
 * @returns 렌더 트리.
 */
export function RuleEditMobile(props: RuleEditMobileProps): React.JSX.Element {
  const totalCpu = calculateTotalCpu(props.ruleset)
  if (props.editIndex < 0) {
    return <RuleListScreen {...props} totalCpu={totalCpu} />
  }
  return <RuleEditScreen {...props} totalCpu={totalCpu} at={props.editIndex} />
}
