/**
 * SegmentedGauge — 눈금이 끊어진 게이지. CPU 예산과 소수 자원용이다.
 *
 * **`value` 가 `max` 를 넘는 것은 오류가 아니라 수치다.** CPU 예산 초과는 편집을 막지 않고
 * `cpu 10 / 8` 처럼 그대로 보고된다(design/README.md §3). 초과분 눈금은 tone 과 무관하게
 * 위험색으로 넘어가고, 읽는 값도 함께 색이 바뀐다 — 색·위치·숫자 세 채널이다.
 */

/** 게이지 색 계열. */
export type GaugeTone = 'cpu' | 'hp' | 'danger' | 'dim'

/**
 * 그릴 눈금 수의 상한. 이 게이지는 CPU 예산처럼 한 자릿수 눈금을 위한 것이고, 상한을
 * 넘는 값은 눈금이 아니라 `readout` 숫자로 읽는다. 상한이 없으면 큰 max 하나가 DOM 을
 * 수천 개로 부풀린다.
 */
export const SEGMENT_LIMIT = 32

/** SegmentedGauge 가 받는 props. */
export interface SegmentedGaugeProps {
  readonly value: number
  readonly max: number
  readonly tone?: GaugeTone
  /** 게이지 위에 붙는 라벨. */
  readonly label?: string
  /**
   * 숫자를 함께 적는다. 색을 못 보는 경로의 채널이다.
   *
   * `true` 면 `값 / 최대` 를 이 컴포넌트가 만들고, 문자열을 주면 그 문자열을 그대로
   * 쓴다. 문자열을 받는 이유는 규칙 에디터처럼 **누적** CPU 를 적는 자리가 있어서다 —
   * 그때 게이트가 그리는 눈금과 읽는 숫자의 출처가 다르다.
   */
  readonly readout?: boolean | string
}

/** 눈금 한 칸의 상태. */
export type SegmentFill = 'off' | 'on' | 'over'

/**
 * 눈금 칸들의 상태를 계산한다. 부동소수를 쓰지 않는 정수 비교뿐이다.
 *
 * @param value 현재 값. max 를 넘을 수 있다.
 * @param max 예산.
 * @returns 왼쪽부터의 칸 상태 목록.
 */
export function buildSegments(value: number, max: number): readonly SegmentFill[] {
  const budget = Math.max(0, Math.trunc(max))
  const used = Math.max(0, Math.trunc(value))
  const total = Math.min(Math.max(budget, used), SEGMENT_LIMIT)
  return Array.from({ length: total }, (_unused, index) => {
    if (index < Math.min(used, budget)) {
      return 'on'
    }
    return index < used ? 'over' : 'off'
  })
}

/**
 * 눈금 게이지를 그린다.
 *
 * @param props 값·예산·색 계열·라벨·숫자 표시 여부.
 * @returns 렌더 트리.
 */
export function SegmentedGauge(props: SegmentedGaugeProps): React.JSX.Element {
  const tone = props.tone ?? 'cpu'
  const segments = buildSegments(props.value, props.max)
  const isOver = props.value > props.max
  const readout =
    typeof props.readout === 'string'
      ? props.readout
      : `${String(props.value)} / ${String(props.max)}`
  const hasReadout = props.readout !== undefined && props.readout !== false
  const hasHead = props.label !== undefined || hasReadout

  return (
    <div
      className={`ds-gauge ds-gauge--${tone}`}
      role="meter"
      aria-valuenow={props.value}
      aria-valuemin={0}
      aria-valuemax={props.max}
      aria-valuetext={readout}
      aria-label={props.label}
    >
      {hasHead ? (
        <div className="ds-gauge__head">
          {props.label === undefined ? null : <span className="ds-label">{props.label}</span>}
          {hasReadout ? (
            <span className={`ds-readout${isOver ? ' ds-gauge__readout--over' : ''}`}>
              {readout}
            </span>
          ) : null}
        </div>
      ) : null}
      <div className="ds-gauge__track" aria-hidden="true">
        {segments.map((fill, index) => (
          <span
            className={`ds-gauge__seg ds-gauge__seg--${fill}`}
            key={`${String(index)}-${fill}`}
          />
        ))}
      </div>
    </div>
  )
}
