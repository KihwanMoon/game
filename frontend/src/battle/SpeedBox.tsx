/**
 * SpeedBox — 모바일의 배속 박스. `‖ ×1 ×2 ×4 ≫` 다섯 칸. **세로와 가로가 함께 쓴다.**
 *
 * 데스크톱 `TopBar` 는 배속 넷을 낱개 버튼으로 두고 즉시 실행(`≫`)을 그 옆 별도 버튼으로
 * 둔다. 모바일에는 버튼을 흩뿌릴 자리가 없고, 즉시 실행은 사실상 "가장 빠른 배속" 이라
 * 같은 눈금 안의 마지막 칸으로 들어온다. 테두리 하나를 1px 괘선으로 나눈 계기이지
 * 낱개 버튼들이 아니다.
 *
 * 활성은 배경 명도와 `aria-pressed` 로만 말한다. **황동을 쓰지 않는다** — 모바일 전투
 * 화면의 황동 예산 셋은 발동한 규칙 번호·그 줄의 좌측 세로바·도면의 플레이어 말이
 * 가져간다.
 *
 * 라벨은 ds `SPEED_LABELS` 를 그대로 쓴다. 배속 이름을 화면마다 다시 적으면 같은 단계가
 * 데스크톱에서는 `×2`, 모바일에서는 `2x` 가 되고, 그것은 같은 조작을 두 이름으로
 * 부르는 것이다.
 *
 * 칸의 폭은 배치가 정한다 — 세로는 화면 폭을 다섯으로 나누고(flex 1), 가로는 44px 고정
 * (`--speed-cell-w`)이다. 그래서 이 파일에는 치수가 없다.
 */
import { Button, SPEED_LABELS, SPEED_STEPS } from '../ds'

/** 즉시 실행 칸의 도형. 데스크톱 상단의 `즉시` 버튼과 같은 글리프다. */
export const INSTANT_GLYPH = '≫'

/** 즉시 실행 칸의 이름. 글리프만으로는 소리 내어 읽히지 않는다. */
const INSTANT_TITLE = '끝까지 돌린다'

/** SpeedBox 가 받는 props. */
export interface SpeedBoxProps {
  /** ds `SpeedControl` 과 같은 숫자 단계. 0 이 정지다. */
  readonly value: number
  readonly onChange: (value: number) => void
  /** `≫` 를 눌렀을 때. 남은 판을 끝까지 돌린다. */
  readonly onInstant: () => void
}

/**
 * 배속 박스를 그린다.
 *
 * @param props 현재 배속·변경 콜백·즉시 실행 콜백.
 * @returns 렌더 트리.
 */
export function SpeedBox(props: SpeedBoxProps): React.JSX.Element {
  return (
    <div className="battle__speed" role="group" aria-label="관전 속도">
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
      <Button size="sm" variant="ghost" title={INSTANT_TITLE} onClick={props.onInstant}>
        {INSTANT_GLYPH}
      </Button>
    </div>
  )
}
