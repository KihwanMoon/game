/**
 * LogStream — 오른쪽 300px 로그 열. 관전 중에 **읽히는** 로그를 만드는 것이 목적이다.
 *
 * 코어의 `LogPanel` 은 줄을 그대로 쌓는다. 그것으로 충분하지 않은 이유가 셋이다.
 *
 *   1. 한 틱에 여러 개체가 줄을 남긴다. 누구의 판단인지 없으면 로그가 뒤섞여 읽힌다.
 *      `LogRow` 계약에 엔티티 칸이 없으므로(tick·rule·expr·outcome·delta·fired) 구간
 *      머리에 한 번 적는다.
 *   2. 400틱이면 수천 줄이다. 전부 DOM 에 올리면 틱마다 그 전부가 다시 그려진다.
 *      `selectLogWindow` 로 그리는 줄 수를 묶고, 잘라 낸 수를 화면에 적는다.
 *   3. 관전은 꼬리를 따라가지만 진단은 한 곳을 붙잡는다. 그래서 추적/고정 토글이 있다.
 *
 * 황동에 대하여 — "발동한 줄을 황동으로 강조" 를 **이번 틱**으로 한정했다. 규칙이
 * 발동한 줄은 판마다 수백 개라 전부 황동으로 칠하면 화면당 3곳이라는 예산이 무의미해지고
 * 광원이 여러 개인 화면이 된다. 지난 틱의 발동은 명도 한 단(--line-strong 세로바)으로
 * 남기고, 지금 보고 있는 틱만 황동 세로바를 받는다 — RuleRow 의 armed 와 같은 뜻이다.
 */
import { useEffect, useRef } from 'react'

import type { LogEntry } from '../core/eventLog'
import { Button, LogRow } from '../ds'

import { formatTickLabel } from './analysisText'
import { groupLogRows, selectLogWindow } from './logWindow'

/** 추적 상태의 버튼 표기. */
const FOLLOW_GLYPH = '▼'

/** 고정 상태의 버튼 표기. */
const FROZEN_GLYPH = '‖'

/** LogStream 이 받는 props. */
export interface LogStreamProps {
  readonly entries: readonly LogEntry[]
  /** 꼬리를 따라갈 것인가. 거짓이면 anchorIndex 자리에 멈춘다. */
  readonly follow: boolean
  readonly onFollowChange: (value: boolean) => void
  /** 고정 상태에서 창의 첫 줄로 삼을 첨자. */
  readonly anchorIndex?: number
  /** 황동 세로바를 받을 틱. 지금 보고 있는 틱이다. */
  readonly currentTick?: number
  readonly maxRows?: number
}

/**
 * 로그 열을 그린다.
 *
 * @param props 로그·추적 여부·기준 첨자·현재 틱.
 * @returns 렌더 트리.
 */
export function LogStream(props: LogStreamProps): React.JSX.Element {
  const scrollRef = useRef<HTMLDivElement>(null)
  const view = selectLogWindow(props.entries, {
    ...(props.maxRows === undefined ? {} : { maxRows: props.maxRows }),
    ...(props.follow || props.anchorIndex === undefined ? {} : { anchorIndex: props.anchorIndex }),
  })
  const groups = groupLogRows(view.rows)
  const lastIndex = view.startIndex + view.rows.length

  // 추적 중일 때만 꼬리로 붙인다. 고정 중에 스크롤을 옮기면 붙잡아 둔 자리가 사라진다.
  useEffect(() => {
    const node = scrollRef.current
    if (node !== null && props.follow) {
      node.scrollTop = node.scrollHeight
    }
  }, [props.follow, lastIndex])

  return (
    <div className="hud-log">
      <div className="hud-log__bar">
        <span className="ds-label">{props.entries.length}줄</span>
        <Button
          size="sm"
          variant="ghost"
          active={props.follow}
          glyph={props.follow ? FOLLOW_GLYPH : FROZEN_GLYPH}
          onClick={() => {
            props.onFollowChange(!props.follow)
          }}
        >
          {props.follow ? '추적' : '고정'}
        </Button>
      </div>
      <div className="hud-log__scroll" ref={scrollRef} role="log">
        {view.hiddenBefore > 0 ? (
          <p className="hud-log__cut">앞의 {view.hiddenBefore}줄 접힘</p>
        ) : null}
        {groups.length === 0 ? <p className="hud-log__cut">기록 없음</p> : null}
        {groups.map((group) => (
          <section className="hud-log__group" key={`${String(group.tick)}-${String(group.count)}`}>
            <header className="hud-log__tick">
              <span className="hud-log__tick-label">{formatTickLabel(group.tick)}</span>
              <span className="hud-log__tick-count">{group.count}</span>
            </header>
            {group.runs.map((run, runIndex) => (
              // 한 틱 안에서 같은 개체가 두 번 이상 등장한다 — 결정 페이즈와 행동 페이즈가
              // 따로 찍히기 때문이다(T006 에 player 가 DECIDE 로 한 번, ACT 로 한 번).
              // `틱-개체` 로는 그 둘이 같은 키가 되어 React 가 줄을 겹쳐 버린다. 실제
              // 브라우저에서 잡힌 결함이고, jsdom 테스트는 콘솔을 보지 않아 놓쳤다.
              <div
                className="hud-log__run"
                key={`${String(group.tick)}-${String(runIndex)}-${run.entityId}`}
              >
                <p className="hud-log__actor">{run.entityId}</p>
                {run.entries.map((entry, index) => (
                  <div
                    className={buildRowClass(entry, group.tick === props.currentTick)}
                    key={`${run.entityId}-${String(index)}`}
                  >
                    <LogRow
                      tick={entry.tick}
                      rule={entry.rule}
                      expr={entry.expr}
                      outcome={entry.outcome}
                      delta={entry.delta}
                      fired={entry.fired}
                    />
                  </div>
                ))}
              </div>
            ))}
          </section>
        ))}
        {view.hiddenAfter > 0 ? (
          <p className="hud-log__cut">뒤의 {view.hiddenAfter}줄 접힘</p>
        ) : null}
      </div>
    </div>
  )
}

/**
 * 한 줄이 받을 수식자를 정한다.
 *
 * @param entry 그 줄.
 * @param isCurrent 지금 보고 있는 틱인가.
 * @returns 클래스 이름들.
 */
function buildRowClass(entry: LogEntry, isCurrent: boolean): string {
  const firedRule = entry.fired && entry.rule !== null
  const names = ['hud-log__row']
  if (firedRule) {
    names.push(isCurrent ? 'hud-log__row--armed' : 'hud-log__row--fired')
  }
  return names.join(' ')
}
