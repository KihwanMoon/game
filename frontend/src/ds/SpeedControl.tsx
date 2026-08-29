/**
 * SpeedControl — 관전 속도. 0 은 정지다.
 *
 * 플레이어는 캐릭터를 조종하지 않고 규칙이 도는 것을 본다. 그래서 속도는 재생기의
 * 조작부에 가깝고, 눌린 단계는 색이 아니라 `aria-pressed` 와 배경 명도로 함께 말한다.
 */
import { Button } from './Button'

/** 고를 수 있는 속도 단계. 배열 순서가 화면 순서다. */
export const SPEED_STEPS: readonly number[] = [0, 1, 2, 4]

/** 단계별 라벨. 정지는 유니코드 도형이고 이모지가 아니다. */
export const SPEED_LABELS: ReadonlyMap<number, string> = new Map([
  [0, '‖'],
  [1, '×1'],
  [2, '×2'],
  [4, '×4'],
])

/** SpeedControl 이 받는 props. */
export interface SpeedControlProps {
  readonly value: number
  readonly onChange: (value: number) => void
}

/**
 * 속도 선택기를 그린다.
 *
 * @param props 현재 속도와 변경 콜백.
 * @returns 렌더 트리.
 */
export function SpeedControl(props: SpeedControlProps): React.JSX.Element {
  return (
    <div className="ds-speed" role="group" aria-label="관전 속도">
      {SPEED_STEPS.map((step) => (
        <Button
          key={step}
          size="sm"
          variant="ghost"
          active={props.value === step}
          onClick={() => {
            props.onChange(step)
          }}
        >
          {SPEED_LABELS.get(step) ?? String(step)}
        </Button>
      ))}
    </div>
  )
}
