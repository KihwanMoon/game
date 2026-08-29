/**
 * 관전 시계 — 배속에 맞춰 엔진을 밀어 준다 (GDD §2.1).
 *
 * **틱 진행은 정수 단위다.** 프레임에 비례해 진행을 나누면 기기의 주사율이 곧 게임 속도가
 * 되고, 7페이즈 한 바퀴 중간에서 멈추면 DECIDE 가 고정한 스냅샷과 ACT 가 보는 세계가
 * 갈린다 (TDD §4.1). 그래서 이 모듈이 하는 일은 "지금 몇 틱을 돌릴지" 를 정하는 것뿐이고,
 * 몇 틱인지는 파이썬과 같은 표(`SPEED_STEP_TICKS`)가 답한다.
 *
 * **시계는 requestAnimationFrame 이 주는 타임스탬프만 본다.** `Date.now` 를 쓰지 않는
 * 것은 코어의 불변 조건과 같은 이유이며, 여기서는 한 가지가 더 있다 — 탭이 뒤로 가면 rAF
 * 가 멈추므로 돌아왔을 때 밀린 시간만큼 몰아서 돌지 않는다.
 */

import { useEffect } from 'react'

import {
  SPEED_PAUSE,
  type TickBatch,
  getStepTicks,
  runTickBatch,
} from '../core/services/runSteppedBattle'
import type { TickEngine } from '../core/sim/engine'
import { OUTCOME_ONGOING } from '../core/sim/phases'

/**
 * ds 의 `SpeedControl` 이 쓰는 숫자 단계에서 파이썬 배속 표기로.
 *
 * 표기가 둘인 것은 계약이 둘이기 때문이다 — 숫자는 디자인 시스템의 것이고 문자열은
 * 파이썬 서비스의 것이다. 한쪽으로 합치면 어느 한쪽 계약을 깬다.
 */
export const SPEED_LABEL_BY_STEP: ReadonlyMap<number, string> = new Map([
  [0, SPEED_PAUSE],
  [1, '1x'],
  [2, '2x'],
  [4, '4x'],
])

/**
 * 한 번에 돌린 뒤 쉬는 간격을 `--dur-tick` 의 몇 배로 둘지.
 *
 * 틱 교체 전환이 140ms 이므로 그 두 배를 두면 전환이 끝나고 한 박자 쉰 뒤 다음 틱이 온다.
 * 간격을 전환보다 짧게 잡으면 명도 전환이 끝나기 전에 값이 또 바뀌어 화면이 떨린다.
 */
export const BATCH_INTERVAL_TICK_UNITS = 2

/** 시간 토큰 이름. 값은 `140ms` 형태다. */
export const TICK_DURATION_TOKEN = '--dur-tick'

/** 토큰을 읽지 못했을 때 쓰는 간격(ms). 토큰이 사라진 화면에서도 시계는 돌아야 한다. */
const FALLBACK_INTERVAL_MS = 280

/** 초를 밀리초로. */
const MS_PER_SECOND = 1000

/**
 * CSS 시간 값을 밀리초로 읽는다.
 *
 * **단위를 봐야 한다.** 토큰 파일에는 `140ms` 라고 적혀 있지만 `getComputedStyle` 은
 * 브라우저에 따라 정규화한 표기 — 크롬은 `.14s` — 를 돌려준다. `parseFloat` 만 쓰면
 * 0.14 를 밀리초로 읽어 간격이 사실상 0 이 되고, 그러면 시계가 매 프레임 한 틱씩 돌아
 * 배속 선택이 아무 일도 하지 않는다. 관전이 성립하지 않는다는 뜻이다 (GDD §2.1).
 * 이 자리는 화면을 실제 브라우저로 띄우기 전에는 드러나지 않는다 — 가짜 토큰을 넣은
 * 단위 테스트는 `140ms` 를 그대로 돌려주기 때문이다.
 *
 * @param text 토큰 값. `140ms` 또는 `.14s` 꼴.
 * @returns 밀리초. 시간 값이 아니면 NaN.
 */
export function parseDurationMs(text: string): number {
  const trimmed = text.trim()
  const value = Number.parseFloat(trimmed)
  if (!Number.isFinite(value)) {
    return Number.NaN
  }
  if (trimmed.endsWith('ms')) {
    return value
  }
  if (trimmed.endsWith('s')) {
    return value * MS_PER_SECOND
  }
  return Number.NaN
}

/**
 * 배치 간격을 토큰에서 읽는다.
 *
 * @param read 토큰 이름을 값으로 바꾸는 함수.
 * @returns 배치 사이의 간격(ms).
 */
export function readBatchIntervalMs(read: (name: string) => string): number {
  const duration = parseDurationMs(read(TICK_DURATION_TOKEN))
  if (!Number.isFinite(duration) || duration <= 0) {
    return FALLBACK_INTERVAL_MS
  }
  return duration * BATCH_INTERVAL_TICK_UNITS
}

/**
 * 숫자 배속 단계를 한 번에 돌릴 틱 수로 바꾼다.
 *
 * @param step ds `SpeedControl` 의 단계 값.
 * @returns 한 번에 돌릴 틱 수. 모르는 단계는 정지로 본다.
 */
export function getStepTicksByStep(step: number): number {
  return getStepTicks(SPEED_LABEL_BY_STEP.get(step) ?? SPEED_PAUSE)
}

/** `useBattleClock` 이 받는 값들. */
export interface BattleClockOptions {
  /** 밀어 줄 엔진. 아직 없으면 undefined. */
  readonly engine: TickEngine | undefined
  /** ds `SpeedControl` 의 단계 값. 0 이면 아무것도 돌리지 않는다. */
  readonly step: number
  /** 배치 사이 간격(ms). */
  readonly intervalMs: number
  /** 승패가 갈렸으면 true. 더 돌리지 않는다. */
  readonly isFinished: boolean
  /** 한 배치가 끝날 때마다 부른다. 화면 갱신은 이 콜백이 맡는다. */
  readonly onBatch: (batch: TickBatch) => void
}

/**
 * 배속에 맞춰 엔진을 돌린다.
 *
 * @param options 엔진·배속·간격·완료 여부·콜백.
 */
export function useBattleClock(options: BattleClockOptions): void {
  const { engine, step, intervalMs, isFinished, onBatch } = options

  useEffect(() => {
    const ticks = getStepTicksByStep(step)
    if (engine === undefined || ticks <= 0 || isFinished) {
      return undefined
    }
    let frame = 0
    let last = Number.NaN
    const advance = (now: number): void => {
      if (Number.isNaN(last)) {
        last = now
      }
      if (now - last >= intervalMs) {
        last = now
        const batch = runTickBatch(engine, ticks)
        onBatch(batch)
        if (batch.outcome !== OUTCOME_ONGOING) {
          return
        }
      }
      frame = requestAnimationFrame(advance)
    }
    frame = requestAnimationFrame(advance)
    return () => {
      cancelAnimationFrame(frame)
    }
  }, [engine, step, intervalMs, isFinished, onBatch])
}
