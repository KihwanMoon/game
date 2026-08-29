/**
 * 규칙 에디터 (W11~W12, GDD §8.1).
 *
 * 골격은 전투 화면과 같은 치수를 쓴다 — 상단 56px / 좌 320px 팔레트 / 가운데 가변 규칙표 /
 * 우 300px 검증 / 하단 48px. 두 화면을 오가며 같은 규칙표를 보게 되므로, 열 폭이 달라지면
 * 눈이 매번 다시 자리를 잡아야 한다.
 *
 * **검증은 타이핑마다 부른다.** `validateRuleSet` 은 순수 함수라 세계 상태를 건드리지
 * 않는다(validator.ts). 메시지는 `[N]` 라벨로 규칙에 되돌려 붙여 **그 줄 아래**에 적는다 —
 * 위반 목록만 따로 있으면 어느 줄이 문제인지 사람이 다시 찾아야 한다 (P1).
 *
 * **CPU 예산 초과는 편집을 막지 않는다** (GDD §3.6). 넘긴 상태로도 계속 고칠 수 있고,
 * 누적 비용이 예산을 넘는 지점부터 규칙 행의 좌측 세로바가 rust 로 바뀐다. 어느 줄에서
 * 넘겼는지가 "얼마나 넘겼는지" 보다 실제로 쓸모 있는 정보다.
 *
 * 황동은 세 곳까지다 — 상단의 적용 버튼(primary), 선택된 규칙의 좌측 세로바, 포커스 링.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'

import { Button, GlyphState, Panel, SegmentedGauge, ValueExpr, useViewportMode } from '../ds'
import { validateRuleSet } from '../core/rules/validator'
import type { BlockCatalog, Rule, RuleSet, Term } from '../core/schemas'
import { writeClipboard } from './clipboard'
import { PalettePanel } from './PalettePanel'
import { RuleEditMobile } from './RuleEditMobile'
import { RuleRowEditor, type RuleRowActions } from './RuleRowEditor'
import { TextView } from './TextView'
import {
  addRule,
  addTerm,
  applyActionChoice,
  applyLhsChoice,
  calculateTotalCpu,
  duplicateRule,
  moveRule,
  removeRule,
  removeTerm,
  updateRule,
  updateTerm,
} from './draft'
import { formatRuleText, parseRuleText } from './ruleText'
import type { TermReadings } from './termMeasure'

/** `[3] 목록에 없는 ...` 에서 규칙 번호를 떼어 낸다. */
const PROBLEM_LABEL_PATTERN = /^\[(\d+)\]\s*(.*)$/

const DECIMAL_RADIX = 10

/** 규칙 행 하나를 가리키는 선택자. 새로 만든 규칙으로 포커스를 옮길 때 쓴다. */
const ROW_SELECTOR = '.rule-row'

/** 측정값이 하나도 없는 표. 새 Map 을 렌더마다 만들지 않으려고 상수로 둔다. */
const EMPTY_READINGS: TermReadings = new Map()

/** 모바일 편집 화면에서 돌아갈 곳의 이름. 이 앱에서 편집 화면의 뒤는 규칙표 목록이다. */
const BACK_LABEL = '규칙표'

/** RuleEditor 의 props. */
export interface RuleEditorProps {
  readonly ruleset: RuleSet
  readonly catalog: BlockCatalog
  readonly cpuBudget: number
  readonly ruleSlots: number
  readonly onChange: (ruleset: RuleSet) => void
  /**
   * 상단 바 오른쪽에 덧붙일 조작부. 앱이 출격 버튼과 방·시드 선택을 여기에 끼운다.
   *
   * 에디터가 출격을 직접 알지 않는 이유는, 규칙표를 어디로 내보내는지가 에디터의 일이
   * 아니기 때문이다 — 던전일 수도 있고 프리셋 저장일 수도 있다. `BattleView`·`HudScreen`
   * 과 같은 이름의 슬롯이라 세 화면의 상단 바가 같은 규약을 쓴다.
   */
  readonly controls?: ReactNode
  /**
   * 팔레트 아래에 세울 패널. 앱이 코드 라이브러리(프리셋 8슬롯·공유 코드)를 여기 끼운다.
   *
   * `controls` 와 같은 이유로 슬롯이다 — 규칙표를 **어디에 두는지**는 에디터의 일이 아니다.
   * 저장 위치가 브라우저인지 서버인지 파일인지는 바깥이 정하고, 에디터는 규칙표 하나를
   * 고치는 일만 안다.
   */
  readonly library?: ReactNode
  /**
   * 직전 틱의 조건 항 측정값. 모바일 편집 화면의 실측 줄이 이것을 읽는다.
   *
   * 없으면 실측 줄이 `–` 와 pending 으로 선다 — 「아직 평가되지 않았다」이며 「값을 만들
   * 수 없었다」가 아니다 (`termMeasure.ts`).
   */
  readonly readings?: TermReadings
}

/** 검증 메시지를 규칙별로 나눈 것. */
interface ProblemIndex {
  readonly byPriority: ReadonlyMap<number, readonly string[]>
  readonly global: readonly string[]
  readonly total: number
}

/**
 * 검증 메시지를 규칙 번호별로 가른다.
 *
 * @param problems `validateRuleSet` 이 낸 목록. 순서는 그대로 유지한다.
 * @returns 규칙별 메시지와 규칙표 전체에 걸리는 메시지.
 */
function buildProblemIndex(problems: readonly string[]): ProblemIndex {
  const byPriority = new Map<number, string[]>()
  const global: string[] = []
  for (const problem of problems) {
    const matched = PROBLEM_LABEL_PATTERN.exec(problem)
    const [, priorityText, body] = matched ?? []
    if (priorityText === undefined || body === undefined) {
      global.push(problem)
      continue
    }
    const priority = Number.parseInt(priorityText, DECIMAL_RADIX)
    const bucket = byPriority.get(priority)
    if (bucket === undefined) {
      byPriority.set(priority, [body])
    } else {
      bucket.push(body)
    }
  }
  return { byPriority, global, total: problems.length }
}

/**
 * 누적 CPU 가 예산을 넘는 규칙의 자리를 표시한다.
 *
 * @param ruleset 규칙표.
 * @param cpuBudget 예산.
 * @returns 규칙 자리마다 초과 여부.
 */
function buildOverBudgetFlags(ruleset: RuleSet, cpuBudget: number): readonly boolean[] {
  let running = 0
  return ruleset.rules.map((rule) => {
    running += rule.cpuCost
    return running > cpuBudget
  })
}

/**
 * 규칙 에디터 화면.
 *
 * @param props 규칙표와 제약, 변경 콜백.
 * @returns 렌더 트리.
 */
export function RuleEditor(props: RuleEditorProps): React.JSX.Element {
  const { ruleset, catalog, cpuBudget, ruleSlots, onChange } = props
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [textMode, setTextMode] = useState(false)
  const [textDraft, setTextDraft] = useState('')
  const [dragIndex, setDragIndex] = useState(-1)
  const [dropIndex, setDropIndex] = useState(-1)
  const [focusIndex, setFocusIndex] = useState(-1)
  const listRef = useRef<HTMLDivElement>(null)
  // 모바일에서 편집 중인 규칙의 자리. 음수면 규칙표 목록이다.
  const [editIndex, setEditIndex] = useState(-1)
  // 편집 화면을 열었을 때의 규칙표. `취소` 가 이 지점으로 되돌린다. 상태가 아니라 ref 인
  // 이유는 이 값이 화면을 다시 그리지 않기 때문이다 — 되돌릴 때 한 번 읽히고 만다.
  const restoreRef = useRef<RuleSet | undefined>(undefined)
  const mode = useViewportMode()

  const problems = useMemo(
    () => validateRuleSet(ruleset, catalog, cpuBudget, ruleSlots),
    [ruleset, catalog, cpuBudget, ruleSlots],
  )
  const index = useMemo(() => buildProblemIndex(problems), [problems])
  const totalCpu = calculateTotalCpu(ruleset)
  const overFlags = buildOverBudgetFlags(ruleset, cpuBudget)
  const textParse = useMemo(
    () => parseRuleText(textDraft, ruleset.rulesetId, ruleset.version),
    [textDraft, ruleset.rulesetId, ruleset.version],
  )

  useEffect(() => {
    if (focusIndex < 0) {
      return
    }
    const rows = listRef.current?.querySelectorAll<HTMLElement>(ROW_SELECTOR)
    rows?.item(focusIndex)?.focus()
    setFocusIndex(-1)
  }, [focusIndex])

  /**
   * 새 규칙표를 부모로 올리고 선택을 그 자리에 맞춘다.
   *
   * @param next 새 규칙표.
   * @param select 선택할 자리. 없으면 그대로 둔다.
   * @param focus 포커스까지 옮길지.
   */
  function commit(next: RuleSet, select?: number, focus = false): void {
    onChange(next)
    if (select !== undefined) {
      const clamped = Math.min(Math.max(select, 0), Math.max(next.rules.length - 1, 0))
      setSelectedIndex(clamped)
      if (focus) {
        setFocusIndex(clamped)
      }
    }
  }

  const actions: RuleRowActions = {
    select: (at: number) => { setSelectedIndex(at) },
    update: (at: number, patch: Partial<Rule>) => { commit(updateRule(ruleset, at, patch)) },
    changeLhs: (ruleIndex: number, termIndex: number, blockId: string) => {
      commit(applyLhsChoice(ruleset, catalog, ruleIndex, termIndex, blockId))
    },
    changeTerm: (ruleIndex: number, termIndex: number, patch: Partial<Term>) => {
      commit(updateTerm(ruleset, ruleIndex, termIndex, patch))
    },
    changeAction: (ruleIndex: number, actionId: string) => {
      commit(applyActionChoice(ruleset, catalog, ruleIndex, actionId))
    },
    addTerm: (ruleIndex: number) => { commit(addTerm(ruleset, catalog, ruleIndex)) },
    removeTerm: (ruleIndex: number, termIndex: number) => {
      commit(removeTerm(ruleset, ruleIndex, termIndex))
    },
    addRule: (at: number) => { commit(addRule(ruleset, catalog, at), at + 1, true) },
    duplicate: (at: number) => { commit(duplicateRule(ruleset, at), at + 1, true) },
    remove: (at: number) => { commit(removeRule(ruleset, at), Math.max(at - 1, 0), true) },
    move: (from: number, to: number) => { commit(moveRule(ruleset, from, to), to, true) },
  }

  // 모바일은 데스크톱 세 열을 줄인 것이 아니라 **다른 화면**이다 (명세 C). 규칙표를 고치는
  // 조작(`actions`)과 검증은 위에서 이미 다 나왔고, 여기서 갈리는 것은 트리뿐이라 기기를
  // 돌려도 고치던 규칙이 그대로 이어진다.
  if (mode !== 'desktop') {
    return (
      <RuleEditMobile
        mode={mode}
        ruleset={ruleset}
        catalog={catalog}
        cpuBudget={cpuBudget}
        ruleSlots={ruleSlots}
        problems={index.byPriority}
        globalProblems={index.global}
        editIndex={editIndex}
        readings={props.readings ?? EMPTY_READINGS}
        actions={actions}
        backLabel={BACK_LABEL}
        onOpen={(at) => {
          restoreRef.current = ruleset
          setSelectedIndex(at)
          setEditIndex(at)
        }}
        onAdd={() => {
          restoreRef.current = ruleset
          actions.addRule(ruleset.rules.length - 1)
          setEditIndex(ruleset.rules.length)
        }}
        onReorder={(to) => {
          actions.move(editIndex, to)
          setEditIndex(to)
        }}
        onCancel={() => {
          const restore = restoreRef.current
          if (restore !== undefined) {
            onChange(restore)
          }
          restoreRef.current = undefined
          setEditIndex(-1)
        }}
        onSave={() => {
          restoreRef.current = undefined
          setEditIndex(-1)
        }}
        {...(props.controls === undefined ? {} : { controls: props.controls })}
        {...(props.library === undefined ? {} : { library: props.library })}
      />
    )
  }

  /**
   * 텍스트 뷰를 켜고 끈다. 켤 때 현재 규칙표를 텍스트로 굽는다.
   */
  function toggleTextMode(): void {
    if (!textMode) {
      setTextDraft(formatRuleText(ruleset))
    }
    setTextMode(!textMode)
  }

  /**
   * 텍스트 편집을 반영한다. 읽히는 동안에만 규칙표를 갱신한다.
   *
   * @param text 텍스트 뷰의 새 내용.
   */
  function handleTextChange(text: string): void {
    setTextDraft(text)
    const parsed = parseRuleText(text, ruleset.rulesetId, ruleset.version)
    if (parsed.ruleset !== undefined) {
      onChange(parsed.ruleset)
    }
  }

  const hasSelection = ruleset.rules.length > 0
  const validGlyph = index.total === 0 ? 'true' : 'danger'
  const cpuReadout = `${String(totalCpu)} / ${String(cpuBudget)}`

  return (
    <div className="editor">
      <header className="editor__top">
        <h1 className="editor__title">규칙 에디터</h1>
        <ValueExpr text={ruleset.rulesetId} size="sm" dim />
        <span className="editor__spacer" />
        <SegmentedGauge value={totalCpu} max={cpuBudget} tone="cpu" label="cpu" readout={cpuReadout} />
        <ValueExpr text={`규칙 ${String(ruleset.rules.length)} / ${String(ruleSlots)}`} size="sm" />
        <GlyphState
          state={validGlyph}
          size="sm"
          label={index.total === 0 ? '검증 통과' : `위반 ${String(index.total)}`}
        />
        <Button
          variant={textMode ? 'primary' : 'secondary'}
          size="sm"
          glyph="≡"
          active={textMode}
          title="텍스트 뷰 토글"
          onClick={toggleTextMode}
        >
          텍스트 뷰
        </Button>
        {props.controls}
      </header>

      <div className="editor__body">
        <div className="editor__col editor__col--palette">
          <PalettePanel
            catalog={catalog}
            hasSelection={hasSelection}
            selectedPriority={ruleset.rules[selectedIndex]?.priority}
            onPickPerception={(blockId) => {
              commit(addRule(ruleset, catalog, ruleset.rules.length - 1, blockId), ruleset.rules.length, true)
            }}
            onPickAction={(actionId) => {
              commit(applyActionChoice(ruleset, catalog, selectedIndex, actionId))
            }}
            onPickSelector={(selectorId) => {
              commit(updateRule(ruleset, selectedIndex, { target: selectorId }))
            }}
          />
          {props.library}
        </div>

        <span className="editor__rule-line" aria-hidden="true" />

        <div className="editor__col editor__col--main">
          {textMode ? (
            <TextView
              text={textDraft}
              errors={textParse.errors}
              ruleCount={textParse.ruleset?.rules.length ?? 0}
              onTextChange={handleTextChange}
              onCopy={() => { writeClipboard(textDraft) }}
            />
          ) : (
            <Panel
              title="우선순위 리스트"
              meta="위에서부터 평가 · 최초로 참인 규칙 하나만 실행"
              padded={false}
              scroll
            >
              <div className="rule-list" ref={listRef}>
                {ruleset.rules.map((rule, at) => (
                  <RuleRowEditor
                    key={`rule-${String(at)}`}
                    rule={rule}
                    index={at}
                    total={ruleset.rules.length}
                    catalog={catalog}
                    selected={at === selectedIndex}
                    overBudget={overFlags[at] ?? false}
                    problems={index.byPriority.get(rule.priority) ?? []}
                    dropTarget={dragIndex >= 0 && at === dropIndex && at !== dragIndex}
                    actions={actions}
                    onDragBegin={(from) => { setDragIndex(from); setDropIndex(from) }}
                    onDragOverRow={setDropIndex}
                    onDrop={(to) => {
                      if (dragIndex >= 0) {
                        commit(moveRule(ruleset, dragIndex, to), to, true)
                      }
                      setDragIndex(-1)
                      setDropIndex(-1)
                    }}
                  />
                ))}
                <div className="rule-list__foot">
                  <Button
                    variant="secondary"
                    size="sm"
                    glyph="＋"
                    onClick={() => { actions.addRule(ruleset.rules.length - 1) }}
                  >
                    규칙 추가
                  </Button>
                  <ValueExpr
                    text="전부 거짓이면 기본 행동(가장 가까운 적에게 접근)이 나간다"
                    size="sm"
                    dim
                  />
                </div>
              </div>
            </Panel>
          )}
        </div>

        <span className="editor__rule-line" aria-hidden="true" />

        <div className="editor__col editor__col--check">
          <Panel title="검증" meta={index.total === 0 ? '통과' : String(index.total)} scroll>
            {index.total === 0 ? (
              <GlyphState state="true" label="실행 가능한 규칙표다" size="sm" />
            ) : (
              <ul className="check-list">
                {index.global.map((text) => (
                  <li key={text}>
                    <GlyphState state="danger" size="sm" label={text} />
                  </li>
                ))}
                {[...index.byPriority].map(([priority, items]) =>
                  items.map((text) => (
                    <li key={`${String(priority)}-${text}`}>
                      <GlyphState state="danger" size="sm" label={`[${String(priority)}] ${text}`} />
                    </li>
                  )),
                )}
              </ul>
            )}
          </Panel>
        </div>
      </div>

      <footer className="editor__bottom">
        <ValueExpr
          text="Alt+↑/↓ 순서 · Alt+Enter 추가 · Alt+D 복제 · Alt+T 조건 추가 · Alt+Backspace 삭제 · Ctrl+Z 되돌리기"
          size="sm"
          dim
        />
        <span className="editor__spacer" />
        <ValueExpr text={`cpu ${cpuReadout}`} size="sm" dim={totalCpu <= cpuBudget} />
      </footer>
    </div>
  )
}
