/**
 * LogRow — 이벤트 로그 한 줄.
 *
 * 받는 필드가 `tick·rule·expr·outcome·delta·fired` 인 것은 디자인이 정한 것이 아니라
 * **코어의 출력 계약**이다(design/README.md §5, src/core/eventLog.ts). 그래서 이 props 는
 * `LogEntry` 를 그대로 받을 수 있게 짜여 있다 — 코어의 `engine.log.entries` 원소를
 * 변환 없이 넘길 수 있고, 변환 계층이 없으면 서식을 고쳐도 값이 어긋나지 않는다.
 *
 * 발동/미발동은 글리프(▸ / ·)와 명도 두 채널로 적는다. 증감은 부호를 반드시 붙이므로
 * 색을 못 봐도 방향이 읽힌다.
 */
import { ValueExpr } from './ValueExpr'

/** 틱 번호를 0 으로 채울 자릿수. 코어 `formatLines` 의 `{tick:03d}` 와 같다. */
const TICK_PAD_WIDTH = 3

/** 발동한 줄의 글리프. */
const FIRED_GLYPH = '▸'

/** 발동하지 않은 줄의 글리프. */
const IDLE_GLYPH = '·'

/**
 * LogRow 가 받는 props.
 *
 * `rule` 과 `delta` 가 `number | null` 을 받는 것은 코어가 "없음" 을 null 로 내보내기
 * 때문이다. 0 과 구분해야 하므로 기본값 0 으로 접지 마라.
 */
export interface LogRowProps {
  readonly tick: number
  readonly rule?: number | null
  readonly expr: string
  readonly outcome: string
  readonly delta?: number | null
  readonly fired?: boolean
}

/**
 * 부호를 반드시 붙여 정수를 적는다. 코어 `formatSigned` 와 같은 서식이다.
 *
 * @param value 적을 정수.
 * @returns `+3` 이나 `-3`.
 */
export function formatDelta(value: number): string {
  return value < 0 ? String(value) : `+${String(value)}`
}

/**
 * 로그 한 줄을 그린다.
 *
 * @param props 코어 로그 레코드의 필드들.
 * @returns 렌더 트리.
 */
export function LogRow(props: LogRowProps): React.JSX.Element {
  const fired = props.fired === true
  const rule = props.rule ?? null
  const delta = props.delta ?? null
  const deltaTone = delta !== null && delta < 0 ? 'down' : 'up'

  return (
    <div className={`ds-log-row${fired ? '' : ' ds-log-row--idle'}`}>
      <span className="ds-log-row__tick">T{String(props.tick).padStart(TICK_PAD_WIDTH, '0')}</span>
      <span className="ds-log-row__fired" aria-hidden="true">
        {fired ? FIRED_GLYPH : IDLE_GLYPH}
      </span>
      <span className="ds-sr">{fired ? '발동' : '미발동'}</span>
      <span className="ds-log-row__rule">{rule === null ? '' : `[${String(rule)}]`}</span>
      <span className="ds-log-row__body">
        <ValueExpr text={props.expr} size="sm" dim={!fired} />
        <span className="ds-log-row__outcome"> → {props.outcome}</span>
      </span>
      {delta === null ? (
        <span />
      ) : (
        <span className={`ds-log-row__delta--${deltaTone}`}>{formatDelta(delta)}</span>
      )}
    </div>
  )
}
