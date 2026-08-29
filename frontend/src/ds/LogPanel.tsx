/**
 * LogPanel — 로그 줄들을 쌓는 오른쪽 300px 열.
 *
 * `entries` 는 코어의 `engine.log.entries` 를 그대로 받는다. LogEntry 가 LogRowProps 의
 * 상위집합이라 변환 계층이 없다 — 변환을 두면 코어가 필드를 늘릴 때마다 UI 가 조용히
 * 옛 값을 그린다.
 */
import type { LogRowProps } from './LogRow'
import { LogRow } from './LogRow'

/** LogPanel 이 받는 props. */
export interface LogPanelProps {
  readonly entries: readonly LogRowProps[]
}

/**
 * 로그 목록을 그린다.
 *
 * @param props 로그 레코드 목록. 코어가 남긴 순서를 유지한다.
 * @returns 렌더 트리.
 */
export function LogPanel(props: LogPanelProps): React.JSX.Element {
  if (props.entries.length === 0) {
    return (
      <div className="ds-log">
        <span className="ds-log__empty ds-label">기록 없음</span>
      </div>
    )
  }

  return (
    <div className="ds-log" role="log">
      {props.entries.map((entry, index) => (
        <LogRow
          key={`${String(entry.tick)}-${String(index)}`}
          tick={entry.tick}
          rule={entry.rule ?? null}
          expr={entry.expr}
          outcome={entry.outcome}
          delta={entry.delta ?? null}
          fired={entry.fired === true}
        />
      ))}
    </div>
  )
}
