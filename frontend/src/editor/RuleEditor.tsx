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
import { useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'

import { useViewportMode } from '../ds'
import { validateRuleSet } from '../core/rules/validator'
import type { BlockCatalog, Rule, RuleSet, Term } from '../core/schemas'
import { writeClipboard } from './clipboard'
import { RuleEditMobile } from './RuleEditMobile'
import type { RuleRowActions } from './ruleRowActions'
import { TextView } from './TextView'
import {
  addRule,
  addTerm,
  applyActionChoice,
  applyParamChoice,
  applyLhsChoice,
  duplicateRule,
  moveRule,
  removeRule,
  removeTerm,
  updateRule,
  updateTerm,
} from './draft'
import { COMBAT_TAB_ID, type EditorTab } from './editorTabs'
import { formatRuleText, parseRuleText } from './ruleText'
import type { TermReadings } from './termMeasure'

export { COMBAT_TAB_ID }
export type { EditorTab }

/** `[3] 목록에 없는 ...` 에서 규칙 번호를 떼어 낸다. */
const PROBLEM_LABEL_PATTERN = /^\[(\d+)\]\s*(.*)$/

const DECIMAL_RADIX = 10

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
  /**
   * 전투 규칙 말고 더 붙일 규칙표 탭들. 앱이 정비 규칙을 여기 끼운다.
   *
   * 슬롯인 이유는 `controls`·`library` 와 같다 — **정비가 무엇을 하는지는 에디터의 일이
   * 아니다.** 에디터가 아는 것은 「규칙표가 여럿이고 한 번에 하나를 고친다」까지다.
   */
  readonly tabs?: readonly EditorTab[]
  /**
   * 탭 줄 오른쪽 끝에 늘 서 있는 상태. 앱이 연결 상태를 여기 끼운다.
   *
   * **탭 줄이 자리인 이유**는 모든 탭에서 보여야 하기 때문이다. 예전에는 서랍의 첫 칸이
   * 열려 있을 때만 연결 상태가 보였는데, 그것은 설계가 아니라 우연이었다 — 서랍을 다른
   * 탭으로 옮겨 두면 서버가 죽어도 화면에 아무 말이 없었다.
   *
   * 슬롯인 이유는 `controls`·`library` 와 같다 — 에디터는 서버를 모른다.
   */
  readonly status?: ReactNode
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
 * 규칙 에디터 화면.
 *
 * @param props 규칙표와 제약, 변경 콜백.
 * @returns 렌더 트리.
 */
export function RuleEditor(props: RuleEditorProps): React.JSX.Element {
  const { ruleset, catalog, cpuBudget, ruleSlots, onChange } = props
  const [textMode, setTextMode] = useState(false)
  const [textDraft, setTextDraft] = useState('')
  // 모바일에서 편집 중인 규칙의 자리. 음수면 규칙표 목록이다.
  const [editIndex, setEditIndex] = useState(-1)
  // 편집 화면을 열었을 때의 규칙표. `취소` 가 이 지점으로 되돌린다. 상태가 아니라 ref 인
  // 이유는 이 값이 화면을 다시 그리지 않기 때문이다 — 되돌릴 때 한 번 읽히고 만다.
  const restoreRef = useRef<RuleSet | undefined>(undefined)
  // 지금 고치고 있는 규칙표. 전투가 기본이다 — 이 게임의 규칙표는 여전히 전투가 중심이다.
  const [tabId, setTabId] = useState(COMBAT_TAB_ID)
  const mode = useViewportMode()

  const problems = useMemo(
    () => validateRuleSet(ruleset, catalog, cpuBudget, ruleSlots),
    [ruleset, catalog, cpuBudget, ruleSlots],
  )
  const index = useMemo(() => buildProblemIndex(problems), [problems])
  const textParse = useMemo(
    () => parseRuleText(textDraft, ruleset.rulesetId, ruleset.version),
    [textDraft, ruleset.rulesetId, ruleset.version],
  )

  /**
   * 새 규칙표를 부모로 올린다.
   *
   * @param next 새 규칙표.
   */
  function commit(next: RuleSet): void {
    onChange(next)
  }

  const actions: RuleRowActions = {
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
    changeParam: (ruleIndex: number, actionParam: string) => {
      commit(applyParamChoice(ruleset, catalog, ruleIndex, actionParam))
    },
    addTerm: (ruleIndex: number) => { commit(addTerm(ruleset, catalog, ruleIndex)) },
    removeTerm: (ruleIndex: number, termIndex: number) => {
      commit(removeTerm(ruleset, ruleIndex, termIndex))
    },
    addRule: (at: number) => { commit(addRule(ruleset, catalog, at)) },
    duplicate: (at: number) => { commit(duplicateRule(ruleset, at)) },
    remove: (at: number) => { commit(removeRule(ruleset, at)) },
    move: (from: number, to: number) => { commit(moveRule(ruleset, from, to)) },
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

  // **화면은 하나다** (2026-09-07). 데스크톱 세 열을 지웠고, 남은 것이 명세 C 가 그린
  // 이 화면이다 — 줄인 것이 아니라 따로 그린 것이라 검증이 규칙 줄 바로 아래에 붙고
  // 팔레트가 규칙 하나의 전용 화면이 된다. 여기 남은 상태(고치는 조작·검증·텍스트)는
  // 배치와 무관해서 기기를 돌려도 고치던 규칙이 그대로 이어진다.
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
      tabs={props.tabs ?? []}
      tabId={tabId}
      onTab={setTabId}
      {...(props.status === undefined ? {} : { status: props.status })}
      isTextMode={textMode}
      onToggleText={toggleTextMode}
      textView={
        <TextView
          text={textDraft}
          errors={textParse.errors}
          ruleCount={textParse.ruleset?.rules.length ?? 0}
          onTextChange={handleTextChange}
          onCopy={() => {
            writeClipboard(textDraft)
          }}
        />
      }
    />
  )
}
