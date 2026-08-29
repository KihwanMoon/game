/**
 * TickScrubber — 틱을 앞뒤로 미는 슬라이더. 되감기가 이것 하나로 끝난다 (GDD §8.3).
 *
 * 세계를 되돌리는 것이 아니라 이미 다 돌려 둔 프레임 배열의 첨자를 옮기는 것이다
 * (`battleSession.ts`). 그래서 뒤로 미는 데 비용이 없고, 같은 자리로 돌아오면 늘 같은
 * 화면이 나온다 — 결정론이 UI 에서 값을 하는 지점이다 (R5).
 *
 * 슬라이더 옆의 수치는 모노다. 손잡이 위치만으로는 몇 틱인지 읽히지 않고, 사후 분석에서
 * 필요한 것은 "몇 틱" 그 자체이기 때문이다.
 */

import { formatTickLabel } from './analysisText'

/** TickScrubber 가 받는 props. */
export interface TickScrubberProps {
  readonly min: number
  readonly max: number
  readonly value: number
  readonly onChange: (value: number) => void
  readonly label: string
}

/** 슬라이더 값의 진법. */
const DECIMAL_RADIX = 10

/**
 * 틱 슬라이더를 그린다.
 *
 * @param props 범위·현재 값·변경 콜백·라벨.
 * @returns 렌더 트리.
 */
export function TickScrubber(props: TickScrubberProps): React.JSX.Element {
  return (
    <div className="hud-scrub">
      <span className="ds-label">{props.label}</span>
      <input
        className="hud-scrub__range"
        type="range"
        min={props.min}
        max={props.max}
        value={props.value}
        aria-label={props.label}
        onChange={(event) => {
          props.onChange(Number.parseInt(event.target.value, DECIMAL_RADIX))
        }}
      />
      <span className="hud-scrub__readout">
        {formatTickLabel(props.value)} / {formatTickLabel(props.max)}
      </span>
    </div>
  )
}
