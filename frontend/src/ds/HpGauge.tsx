/**
 * HpGauge — 연속 막대 하나로 읽는 체력.
 *
 * 체력이 낮을 때 색만 바꾸면 색약 조건에서 사라진다. 그래서 낮은 상태는 색·글리프(▽)·
 * 숫자 세 채널로 적는다. 비율은 정수 나눗셈으로만 계산한다 — 부동소수를 쓰지 않는다.
 */

/** 이 비율 이하를 낮은 체력으로 본다. 퍼센트 정수다. */
export const LOW_HP_PERCENT = 30

/** 낮은 체력을 알리는 글리프. */
const LOW_HP_GLYPH = '▽'

/** 백분율의 상한. */
const FULL_PERCENT = 100

/** HpGauge 가 받는 props. */
export interface HpGaugeProps {
  readonly value: number
  readonly max: number
  /** 막대 폭(px). 생략하면 부모 폭을 채운다. */
  readonly width?: number
}

/**
 * 체력 비율을 정수 퍼센트로 계산한다.
 *
 * @param value 현재 체력.
 * @param max 최대 체력. 0 이하면 0% 로 본다.
 * @returns 0 이상 100 이하의 정수.
 */
export function calculatePercent(value: number, max: number): number {
  if (max <= 0) {
    return 0
  }
  const clamped = Math.max(0, Math.min(Math.trunc(value), Math.trunc(max)))
  return Math.floor((clamped * FULL_PERCENT) / Math.trunc(max))
}

/**
 * 체력 막대를 그린다.
 *
 * @param props 현재 체력·최대 체력·폭.
 * @returns 렌더 트리.
 */
export function HpGauge(props: HpGaugeProps): React.JSX.Element {
  const percent = calculatePercent(props.value, props.max)
  const isLow = percent <= LOW_HP_PERCENT
  const trackWidth = props.width === undefined ? '100%' : `${String(props.width)}px`

  return (
    <span
      className={`ds-hp${isLow ? ' ds-hp--low' : ''}`}
      role="meter"
      aria-valuenow={props.value}
      aria-valuemin={0}
      aria-valuemax={props.max}
      aria-valuetext={`체력 ${String(props.value)} / ${String(props.max)}`}
    >
      {isLow ? (
        <span className="ds-hp__glyph" aria-hidden="true">
          {LOW_HP_GLYPH}
        </span>
      ) : null}
      <span className="ds-hp__track" style={{ width: trackWidth }} aria-hidden="true">
        <span className="ds-hp__fill" style={{ width: `${String(percent)}%` }} />
      </span>
      <span className="ds-readout ds-hp__readout" aria-hidden="true">
        {props.value} / {props.max}
      </span>
    </span>
  )
}
