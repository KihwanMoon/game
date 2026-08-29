/**
 * 스텝 실행 — `game/app/services/run_stepped_battle.py` 의 이식 (GDD §2.1 의 배속).
 *
 * 오토배틀은 플레이어 입력이 없는 시간이 길다. 그 시간을 관찰과 진단으로 채우려면
 * 화면이 진행을 붙잡을 수 있어야 하고, 그 단위가 여기 있는 '구간'이다. 일시정지 /
 * 1x / 2x / 4x / 즉시 실행이 전부 "한 번에 몇 틱을 돌리는가" 하나로 환산된다.
 *
 * **틱 자체는 나누지 않는다.** 7페이즈 한 바퀴가 원자 단위이며, 그 중간에서 멈추면
 * DECIDE 가 고정한 스냅샷과 ACT 가 보는 세계가 갈려 동시성 공정성이 깨진다 (TDD §4.1).
 * 그래서 가장 느린 배속도 1틱이고, 일시정지는 0틱 — 즉 아무것도 돌리지 않는 것이다.
 *
 * 화면이 이 모듈을 거치는 이유가 하나 더 있다. 브라우저의 프레임 간격은 기기마다
 * 다른데, 프레임에 비례해 틱을 돌리면 같은 시드가 같은 지점에서 멈추지 않는다. 배속을
 * **틱 수**로 환산해 두면 프레임이 몇 번 왔는지와 무관하게 진행이 정수 단위로만 는다.
 */

import type { LogEntry } from '../eventLog'
import { OUTCOME_ONGOING } from '../sim/phases'
import type { TickEngine } from '../sim/engine'
import { DEFAULT_MAX_TICKS } from './runBattle'

/** 일시정지. 한 번에 0틱을 돌린다 — 아무것도 돌리지 않는 것이다. */
export const SPEED_PAUSE = 'pause'

/** 즉시 실행. 한 번에 상한까지 돌려 승패를 낸다. */
export const SPEED_INSTANT = 'instant'

/** 배속 표기에서 한 번에 돌릴 틱 수로. 즉시 실행은 상한이 필요해 여기 없다. */
export const SPEED_STEP_TICKS: ReadonlyMap<string, number> = new Map([
  [SPEED_PAUSE, 0],
  ['1x', 1],
  ['2x', 2],
  ['4x', 4],
])

/** 고를 수 있는 배속 표기. 배열 순서가 곧 화면 순서다. */
export const SPEED_LABELS: readonly string[] = [SPEED_PAUSE, '1x', '2x', '4x', SPEED_INSTANT]

/** 한 번에 돌린 구간과 그 사이에 쌓인 로그. */
export interface TickBatch {
  readonly startTick: number
  readonly endTick: number
  readonly outcome: string
  readonly entries: readonly LogEntry[]
}

/**
 * 배속 표기를 한 번에 돌릴 틱 수로 바꾼다 (GDD §2.1).
 *
 * @param speedLabel pause·1x·2x·4x·instant 중 하나.
 * @param maxTicks 즉시 실행이 한 번에 돌릴 상한.
 * @returns 한 번에 돌릴 틱 수. 일시정지는 0 이다.
 * @throws 모르는 배속 표기인 경우.
 */
export function getStepTicks(speedLabel: string, maxTicks: number = DEFAULT_MAX_TICKS): number {
  if (speedLabel === SPEED_INSTANT) {
    return maxTicks
  }
  const ticks = SPEED_STEP_TICKS.get(speedLabel)
  if (ticks === undefined) {
    throw new Error(`모르는 배속이다: ${speedLabel} (가능: ${SPEED_LABELS.join(', ')})`)
  }
  return ticks
}

/**
 * 틱을 정해진 수만큼만 돌리고 멈춘다. 스텝 실행의 기본 단위다.
 *
 * 승패가 먼저 갈리면 남은 틱을 돌리지 않는다.
 *
 * @param engine 조립된 엔진.
 * @param ticks 이번에 돌릴 틱 수. 0 이하면 아무것도 돌리지 않는다.
 * @returns 돌린 구간과 그 사이에 쌓인 로그. 한 틱도 돌리지 않았으면 startTick 이
 *   endTick 보다 크고 entries 는 비어 있다.
 */
export function runTickBatch(engine: TickEngine, ticks: number): TickBatch {
  const firstTick = engine.state.tick + 1
  const seen = engine.log.count()
  let outcome = OUTCOME_ONGOING
  for (let step = 0; step < Math.max(0, ticks); step += 1) {
    outcome = engine.runTick()
    if (outcome !== OUTCOME_ONGOING) {
      break
    }
  }
  return {
    startTick: firstTick,
    endTick: engine.state.tick,
    outcome,
    entries: engine.log.entries.slice(seen),
  }
}
