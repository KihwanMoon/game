/**
 * 모바일 시트 — 규칙표와 로그가 탭 하나로 합쳐진 면. **세로와 가로가 함께 쓴다.**
 *
 * 데스크톱은 규칙표(좌 320)와 로그(우 300)가 도면 양옆에 동시에 서 있다. 모바일에는 그
 * 자리가 없어 둘을 한 면에 겹치고 탭으로 가른다. 겹치는 것은 두 열뿐이고 **도면은 겹치지
 * 않는다** — 규칙을 읽는 동안에도 유닛 위치가 계속 보여야 하기 때문이다.
 *
 * 탭 활성은 **명도와 굵기로만** 말한다. 황동을 쓰지 않는다 — 모바일 전투 화면의 황동
 * 예산 셋은 발동한 규칙 번호·그 줄의 좌측 세로바·도면의 플레이어 말이 가져간다.
 *
 * **이 파일에 배치 분기가 없다.** 배치별로 다른 것은 치수뿐이고 그 치수는 토큰이 정한다
 * (`--sheet-tab-h` 44/36 · `--row-h` 54/50 · `--btn-h` 44/30). 토큰으로 표현되지 않는
 * 하나 — 하단을 두 단으로 쌓느냐 한 줄로 눕히느냐 — 도 마크업이 아니라 격자 설정이라
 * `battle.css` 의 `.battle--landscape` 절이 정한다. 가로는 높이가 390px 뿐이라 두 단을
 * 쌓을 자리가 없다.
 *
 * 상태 계산(탭 카운트·꺼진 규칙·판에 실을 규칙표)은 `portraitSheet.ts` 가, 규칙 줄
 * 만들기는 `ruleRows.ts` 가 맡는다. 여기서 다시 계산하지 않는다.
 */
import type { ReactNode, Ref } from 'react'

import { Button, LogPanel, RuleRow, RuleTable, SegmentedGauge } from '../ds'
import type { LogRowProps } from '../ds'
import { SHEET_TABS, SHEET_TAB_LABELS, formatRuleCondition, type SheetTab } from './portraitSheet'
import type { RuleRowView } from './ruleRows'

/** CPU 게이지의 라벨. */
const CPU_LABEL = 'cpu'

/** 시트 하단 두 버튼의 글자. */
const STEP_TEXT = '한 틱'
const RESTART_TEXT = '처음부터'

/** SheetTabs 가 받는 props. */
export interface SheetTabsProps {
  readonly active: SheetTab
  /** 탭마다 함께 적는 카운트. `4/5`·`T027`. */
  readonly counts: ReadonlyMap<SheetTab, string>
  readonly onChange: (tab: SheetTab) => void
}

/**
 * 시트 탭 줄을 그린다.
 *
 * @param props 활성 탭·카운트·변경 콜백.
 * @returns 렌더 트리.
 */
export function SheetTabs(props: SheetTabsProps): React.JSX.Element {
  return (
    <div className="battle__tabs" role="tablist" aria-label="시트">
      {SHEET_TABS.map((id) => (
        <button
          key={id}
          type="button"
          role="tab"
          aria-selected={props.active === id}
          className={`battle__tab${props.active === id ? ' battle__tab--on' : ''}`}
          onClick={() => {
            props.onChange(id)
          }}
        >
          <span className="battle__tab-name">{SHEET_TAB_LABELS.get(id) ?? id}</span>
          <span className="battle__tab-count">{props.counts.get(id) ?? ''}</span>
        </button>
      ))}
    </div>
  )
}

/** RuleSheet 이 받는 props. */
export interface RuleSheetProps {
  /** 규칙표 전량. **꺼진 줄도 들어 있다** — 다시 켜려면 보여야 한다. */
  readonly rules: readonly RuleRowView[]
  /** 규칙 줄을 누르면 그 규칙을 켜고 끈다 (모바일 원본 D). */
  readonly onToggle: (priority: number) => void
}

/**
 * 시트의 규칙표를 그린다.
 *
 * @param props 규칙 줄들과 토글 콜백.
 * @returns 렌더 트리.
 */
export function RuleSheet(props: RuleSheetProps): React.JSX.Element {
  return (
    <RuleTable>
      {props.rules.map((rule) => (
        <RuleRow
          key={rule.priority}
          index={rule.priority}
          state={rule.state}
          condition={formatRuleCondition(rule.condition, rule.enabled)}
          action={rule.action}
          cpu={rule.cpu}
          armed={rule.armed}
          enabled={rule.enabled}
          onClick={() => {
            props.onToggle(rule.priority)
          }}
        />
      ))}
    </RuleTable>
  )
}

/** SheetFoot 이 받는 props. */
export interface SheetFootProps {
  /** 켜진 규칙들의 누적 CPU. */
  readonly cpuUsed: number
  readonly cpuBudget: number
  readonly onStep: () => void
  readonly onRestart: () => void
}

/**
 * 시트 하단(CPU 게이지 + `한 틱` / `처음부터`)을 그린다.
 *
 * 예산 초과는 오류가 아니라 수치다. 게이지 색만 위험색으로 넘어가고 조작은 그대로
 * 계속된다 (design/README.md §3).
 *
 * 게이지와 버튼의 **배열**은 여기서 정하지 않는다. 세로는 두 단으로 쌓고 가로는 한 줄로
 * 눕히는데, 그것은 마크업이 아니라 격자 설정이라 CSS 가 배치별로 정한다.
 *
 * @param props 누적 CPU·예산·두 콜백.
 * @returns 렌더 트리.
 */
export function SheetFoot(props: SheetFootProps): React.JSX.Element {
  const isOver = props.cpuUsed > props.cpuBudget
  return (
    <div className="battle__sheet-foot">
      <SegmentedGauge
        label={CPU_LABEL}
        value={props.cpuUsed}
        max={props.cpuBudget}
        tone={isOver ? 'danger' : 'cpu'}
        readout
      />
      <div className="battle__sheet-actions">
        <Button size="sm" variant="ghost" block onClick={props.onStep}>
          {STEP_TEXT}
        </Button>
        <Button size="sm" variant="ghost" block onClick={props.onRestart}>
          {RESTART_TEXT}
        </Button>
      </div>
    </div>
  )
}

/** BattleSheet 이 받는 props. */
export interface BattleSheetProps {
  readonly tab: SheetTab
  readonly counts: ReadonlyMap<SheetTab, string>
  readonly onTabChange: (tab: SheetTab) => void
  readonly rules: readonly RuleRowView[]
  readonly onToggleRule: (priority: number) => void
  readonly entries: readonly LogRowProps[]
  /** 탭 본문 아래 고정되는 하단. 배치마다 배열이 달라 슬롯으로 받는다. */
  readonly foot?: ReactNode
  /**
   * 시트 본문. 로그를 마지막 줄에 붙여 두려고 밖에서 잡는다.
   *
   * 스크롤을 여기서 걸지 않는 이유는 붙일 시점이 **틱**이기 때문이다. 이 컴포넌트는
   * 틱을 모르고 로그 배열만 받으므로, 배열 참조가 바뀔 때마다 내리면 아무것도 바뀌지
   * 않은 재렌더에서도 읽던 자리가 밀린다.
   */
  readonly bodyRef?: Ref<HTMLDivElement> | undefined
}

/**
 * 시트 한 장(탭 줄 + 본문 + 하단)을 그린다.
 *
 * @param props 탭 상태·규칙 줄·로그 줄·하단 슬롯.
 * @returns 렌더 트리.
 */
export function BattleSheet(props: BattleSheetProps): React.JSX.Element {
  return (
    <div className="battle__sheet">
      <SheetTabs active={props.tab} counts={props.counts} onChange={props.onTabChange} />
      <div className="battle__sheet-body" ref={props.bodyRef}>
        {props.tab === 'log' ? (
          <LogPanel entries={props.entries} />
        ) : (
          <RuleSheet rules={props.rules} onToggle={props.onToggleRule} />
        )}
      </div>
      {props.foot}
    </div>
  )
}
