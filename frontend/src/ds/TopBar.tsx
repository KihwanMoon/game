/**
 * TopBar — 전투 화면 상단 56px. 층·실 표기와 틱 카운터, 관전 속도.
 *
 * 틱 카운터는 황동을 쓰지 않는다. 화면의 황동 예산 셋은 primary 버튼·armed 규칙·
 * 플레이어 말이 가져가고, 상단 바가 하나를 더 쓰면 전투 화면이 예산을 넘긴다.
 */
import { SpeedControl } from './SpeedControl'

/** TopBar 가 받는 props. */
export interface TopBarProps {
  readonly location: string
  readonly tick: number
  readonly speed: number
  readonly onSpeedChange: (value: number) => void
}

/**
 * 상단 바를 그린다.
 *
 * @param props 위치 표기·현재 틱·속도·속도 변경 콜백.
 * @returns 렌더 트리.
 */
export function TopBar(props: TopBarProps): React.JSX.Element {
  return (
    <header className="ds-topbar">
      <h1 className="ds-topbar__location">{props.location}</h1>
      <span className="ds-topbar__tick">
        <span className="ds-label">tick</span>
        <span className="ds-topbar__tick-value">{props.tick}</span>
      </span>
      <SpeedControl value={props.speed} onChange={props.onSpeedChange} />
    </header>
  )
}
