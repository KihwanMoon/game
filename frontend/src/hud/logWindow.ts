/**
 * 로그 창 고르기와 틱 묶기 — 그리는 줄 수를 상한으로 묶는다.
 *
 * 한 판이 400틱이면 로그는 수천 줄이 된다. 전부 DOM 에 올리면 틱마다 그 전부가 다시
 * 그려져 관전이 끊기고, 관전이 끊기면 "관찰과 진단" 이 성립하지 않는다 (GDD §8).
 *
 * 픽셀을 재는 가상 스크롤 대신 **줄 수로 자르는 윈도잉**을 골랐다. 화면 높이를 재려면
 * 행 높이를 자바스크립트가 알아야 하는데, 그 값은 토큰(`--log-row-h`)에 있고 토큰을
 * 스크립트로 다시 적는 순간 디자인 시스템의 정본이 둘이 된다. 줄 수로 자르면 잘린
 * 쪽의 수를 그대로 화면에 적을 수 있어 사라진 줄이 있다는 사실도 숨겨지지 않는다.
 *
 * 순수 함수다. 화면 상태를 건드리지 않으므로 테스트가 쉽고, 스크롤 위치와 무관하다.
 */

import type { LogEntry } from '../core/eventLog'

/** 한 번에 그릴 로그 줄의 상한. */
export const DEFAULT_WINDOW_ROWS = 240

/**
 * 사망 리플레이가 되돌아보는 틱 수 (GDD §8.3).
 *
 * 파이썬 `replay_battle.DEATH_REPLAY_TICKS` 와 같은 값이어야 한다. 두 쪽이 다른 구간을
 * 보여 주면 터미널에서 짚은 원인과 화면에서 짚은 원인이 어긋난다.
 */
export const DEATH_REPLAY_TICKS = 15

/** 잘라 낸 로그 창 하나. */
export interface LogWindow {
  readonly rows: readonly LogEntry[]
  /** 원본에서 rows 가 시작되는 첨자. */
  readonly startIndex: number
  /** 앞쪽에서 숨긴 줄 수. */
  readonly hiddenBefore: number
  /** 뒤쪽에서 숨긴 줄 수. */
  readonly hiddenAfter: number
}

/** `selectLogWindow` 가 받는 값들. */
export interface WindowRequest {
  readonly maxRows?: number
  /**
   * 창의 첫 줄로 삼을 첨자. 생략하면 꼬리를 보여 준다 — 추적 중인 화면의 기본이다.
   * 되감기 슬라이더가 어떤 틱을 고르면 그 틱의 첫 줄 첨자가 여기로 온다.
   */
  readonly anchorIndex?: number
}

/** 한 틱 안에서 같은 엔티티가 연속으로 남긴 줄들. */
export interface LogRun {
  readonly entityId: string
  readonly entries: readonly LogEntry[]
}

/** 틱 하나의 로그 묶음. */
export interface LogGroup {
  readonly tick: number
  readonly runs: readonly LogRun[]
  readonly count: number
}

/**
 * 값을 범위 안으로 접는다.
 *
 * @param value 접을 값.
 * @param low 하한.
 * @param high 상한. 하한보다 작으면 하한을 쓴다.
 * @returns 범위 안의 값.
 */
function clampIndex(value: number, low: number, high: number): number {
  return Math.max(low, Math.min(Math.max(low, high), value))
}

/**
 * 그릴 로그 구간을 고른다.
 *
 * @param entries 로그 전량.
 * @param request 상한 줄 수와 기준 첨자.
 * @returns 자른 구간과 앞뒤로 숨긴 줄 수.
 */
export function selectLogWindow(
  entries: readonly LogEntry[],
  request: WindowRequest = {},
): LogWindow {
  const maxRows = Math.max(1, request.maxRows ?? DEFAULT_WINDOW_ROWS)
  const tailStart = Math.max(0, entries.length - maxRows)
  const start =
    request.anchorIndex === undefined
      ? tailStart
      : clampIndex(request.anchorIndex, 0, tailStart)
  const rows = entries.slice(start, start + maxRows)
  return {
    rows,
    startIndex: start,
    hiddenBefore: start,
    hiddenAfter: entries.length - (start + rows.length),
  }
}

/**
 * 로그를 틱 단위로 묶고, 틱 안에서는 같은 엔티티의 연속 구간으로 다시 묶는다.
 *
 * 엔티티 이름을 줄마다 적지 않는 이유는 폭이다. 로그 열은 300px 이고 `LogRow` 의 계약에
 * 엔티티 칸이 없다(tick·rule·expr·outcome·delta·fired). 대신 구간 머리에 한 번 적으면
 * 모노 컬럼이 흐트러지지 않으면서 누구의 판단인지가 남는다.
 *
 * @param rows 그릴 로그 줄들. 코어가 남긴 순서여야 한다.
 * @returns 앞에서부터의 틱 묶음들.
 */
export function groupLogRows(rows: readonly LogEntry[]): readonly LogGroup[] {
  const groups: LogGroup[] = []
  let tick: number | undefined
  let runs: LogRun[] = []
  let run: LogEntry[] = []
  let entityId: string | undefined

  const closeRun = (): void => {
    if (entityId !== undefined && run.length > 0) {
      runs.push({ entityId, entries: run })
    }
    run = []
  }
  const closeGroup = (): void => {
    closeRun()
    if (tick !== undefined && runs.length > 0) {
      groups.push({
        tick,
        runs,
        count: runs.reduce((total, item) => total + item.entries.length, 0),
      })
    }
    runs = []
  }

  for (const entry of rows) {
    if (entry.tick !== tick) {
      closeGroup()
      tick = entry.tick
      entityId = undefined
    }
    if (entry.entityId !== entityId) {
      closeRun()
      entityId = entry.entityId
    }
    run.push(entry)
  }
  closeGroup()
  return groups
}

/**
 * 그 틱의 첫 줄 첨자를 찾는다. 되감기 슬라이더가 창을 옮길 때 쓴다.
 *
 * @param entries 로그 전량.
 * @param tick 찾을 틱.
 * @returns 첫 줄의 첨자. 그 틱에 남은 줄이 없으면 undefined.
 */
export function findTickIndex(entries: readonly LogEntry[], tick: number): number | undefined {
  const index = entries.findIndex((entry) => entry.tick === tick)
  return index < 0 ? undefined : index
}

/**
 * 마지막 몇 틱의 로그만 남긴다 (파이썬 `filter_recent_entries`).
 *
 * 기준은 마지막 **줄**의 틱이 아니라 로그에 있는 최대 틱이다. 정리(CLEANUP) 단계가 앞
 * 틱의 줄을 뒤에 남기는 경우가 있어 둘이 갈릴 수 있다.
 *
 * @param entries 방 하나의 전체 로그.
 * @param ticks 남길 틱 수. 0 이하면 아무것도 남기지 않는다.
 * @returns 마지막 틱에서 ticks 만큼 거슬러 올라간 구간. 순서는 원본 그대로다.
 */
export function filterRecentEntries(
  entries: readonly LogEntry[],
  ticks: number = DEATH_REPLAY_TICKS,
): readonly LogEntry[] {
  if (entries.length === 0 || ticks <= 0) {
    return []
  }
  const lastTick = entries.reduce((peak, entry) => Math.max(peak, entry.tick), 0)
  const firstTick = lastTick - ticks + 1
  return entries.filter((entry) => entry.tick >= firstTick)
}
