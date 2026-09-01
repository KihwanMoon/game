/**
 * 방을 비우면 저절로 다음 방으로 (GDD §2.2 의 반대편).
 *
 * **방 사이는 규칙을 고치는 유일한 창이다.** 그래서 곧장 넘기지 않고 몇 초를 두고, 그
 * 몇 초를 화면이 세어 보여 주며, 멈출 수 있게 한다 — 안 그러면 "고치려고 했는데 이미
 * 넘어가 있다" 가 되고, 그것은 자동 진행이 게임의 고리를 끊는 것이다.
 *
 * 넘어가는 것은 **이겼을 때뿐이다.** 진 판에서 저절로 넘어가면 무엇 때문에 졌는지 볼
 * 새가 없다 — 사후 분석이 저절로 뜨는 자리와 같은 이유다.
 *
 * 훅을 안 쓴다. 훅 안에 있으면 검사가 문구를 못 본다 — 이 저장소의 검사는 jsdom 없이
 * 도는 렌더 검사이고, 같은 이유로 이번 세션에서 여러 번 갈랐다.
 */
import { Button } from '../ds/Button'
import { ValueExpr } from '../ds/ValueExpr'
import type { StorageLike } from '../storage'

/** 넘어가기까지 두는 시간. 규칙 한 줄을 고칠 결심을 하기에 충분한 만큼이다. */
export const AUTO_ADVANCE_SECONDS = 3

/** 자동 진행을 켜 두었는지 기기에 남기는 열쇠. */
export const AUTO_ADVANCE_KEY = 'run.autoAdvance.v1'

/** 꺼 두었음을 뜻하는 값. **없으면 켜진 것으로 본다** — 기능을 넣은 쪽이 기본이다. */
const OFF = 'off'

/** `checkShouldAutoAdvance` 가 받는 값들. */
export interface AutoAdvanceInput {
  /** 이 방이 끝났는가. */
  readonly isFinished: boolean
  /** 갈 다음 방이 있는가. 이겼을 때만 생긴다. */
  readonly hasNext: boolean
  /** 자동 진행을 켜 두었는가. */
  readonly isEnabled: boolean
  /** 이번 방에서 사람이 멈췄는가. */
  readonly isStopped: boolean
}

/**
 * 지금 저절로 넘어가야 하는지 정한다.
 *
 * @param input 판단에 드는 값들.
 * @returns 넘어가야 하면 true.
 */
export function checkShouldAutoAdvance(input: AutoAdvanceInput): boolean {
  return input.isFinished && input.hasNext && input.isEnabled && !input.isStopped
}

/**
 * 자동 진행을 켜 두었는지 읽는다.
 *
 * 읽을 수 없으면 켜진 것으로 본다. **여기서 던지면 앱이 안 뜬다** — 자동 진행은 게임을
 * 막을 만한 값이 아니다.
 *
 * @param storage 기기 저장소.
 * @returns 켜져 있으면 true.
 */
export function readAutoAdvance(storage: StorageLike | undefined): boolean {
  try {
    return storage?.getItem(AUTO_ADVANCE_KEY) !== OFF
  } catch {
    return true
  }
}

/**
 * 자동 진행 설정을 기기에 남긴다.
 *
 * @param storage 기기 저장소.
 * @param isEnabled 켤 것인가.
 */
export function writeAutoAdvance(storage: StorageLike | undefined, isEnabled: boolean): void {
  try {
    storage?.setItem(AUTO_ADVANCE_KEY, isEnabled ? 'on' : OFF)
  } catch {
    // 저장이 안 돼도 이번 판은 그대로 돈다. 설정 하나 때문에 판을 멈출 이유가 없다.
  }
}

/**
 * 남은 시간을 한 줄로 적는다.
 *
 * **몇 번째 방으로 가는지 함께 적는다.** 「곧 넘어감」만 적으면 어디로 가는지 모른 채
 * 멈출지를 정해야 한다.
 *
 * @param secondsLeft 남은 초.
 * @param roomNumber 갈 방의 번호(1부터).
 * @param roomTotal 방 총수.
 * @returns 화면에 적을 한 줄.
 */
export function formatAutoAdvanceNote(
  secondsLeft: number,
  roomNumber: number,
  roomTotal: number,
): string {
  return `${String(secondsLeft)}초 뒤 다음 방(${String(roomNumber)}/${String(roomTotal)})으로 간다`
}

/** 자동 진행 안내가 받는 props. */
export interface AutoAdvanceNoticeProps {
  /** 남은 초. undefined 면 안 그린다. */
  readonly secondsLeft: number | undefined
  readonly roomNumber: number
  readonly roomTotal: number
  /** 멈춘다. 이번 방에서만 멈추고 설정은 안 건드린다. */
  readonly onStop: () => void
}

/**
 * 자동 진행이 도는 동안의 안내를 그린다.
 *
 * @param props 남은 초와 갈 방, 멈추기 콜백.
 * @returns 렌더 트리. 도는 중이 아니면 아무것도 안 그린다.
 */
export function AutoAdvanceNotice(props: AutoAdvanceNoticeProps): React.JSX.Element | null {
  if (props.secondsLeft === undefined) {
    return null
  }
  return (
    <div className="launch__auto">
      <ValueExpr
        text={formatAutoAdvanceNote(props.secondsLeft, props.roomNumber, props.roomTotal)}
        size="sm"
      />
      {/* **멈추기가 안내 옆에 붙어 있어야 한다.** 설정 화면에 있으면 지금 멈출 수 없다. */}
      <Button size="sm" variant="ghost" glyph="⏸" title="여기서 멈춘다 — 규칙을 고칠 수 있다" onClick={props.onStop}>
        멈춤
      </Button>
    </div>
  )
}
