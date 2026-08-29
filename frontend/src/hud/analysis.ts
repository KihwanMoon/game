/**
 * 사후 분석 집계 — `game/app/services/analyze_battle.py` 의 이식 (GDD §8.3).
 *
 * **계산만 한다.** 문자열 한 줄도 만들지 않는다. 파이썬 쪽도 집계와 서식을 나눠 두었고
 * (`build_rule_stats` / `format_rule_stats`), 그 경계가 여기서도 그대로다 — 표현을 섞으면
 * 웹 화면이 터미널과 다른 수를 적는지 대조할 수 없다. 문구는 `analysisText.ts` 에 있다.
 *
 * 두 가지에 답한다. **규칙별 발동 횟수**는 "어느 규칙이 틀렸는가" 를, **피해 히트맵**은
 * "어디에 서 있었던 것이 틀렸는가" 를 답한다. 그 두 줄이면 로그를 처음부터 읽지 않아도
 * 고칠 곳이 특정된다. P1(실패는 정보다)이 요구하는 것이다.
 *
 * 기준값은 `__golden__/analysis.json` 이며 파이썬이 만든다. 값이 어긋나면 이쪽이 틀린
 * 것이다 — 재생성은 `uv run python -m scripts.export_analysis_golden`.
 */

import { divideFloor } from '../core/combat/damage'
import type { LogEntry } from '../core/eventLog'
import type { Position } from '../core/grid/geometry'
import { sortByKey } from '../core/ordering'
import { PHASE_ACT, PHASE_DECIDE, PHASE_TELEGRAPH, PHASE_UPKEEP } from '../core/sim/phases'

/** 이 말이 결과 문구에 있으면 그 시도는 헛돈 것이다. */
export const WASTE_MARKERS: readonly string[] = ['낭비', '미구현']

/** 규칙 없이 나온 행동(DEFAULT 계획)의 표기. */
export const DEFAULT_RULE_LABEL = 'DEFAULT'

/** 시도의 절반 이상이 헛돌면 우연이 아니라 조건이 상황과 안 맞는 것이다. */
export const SUSPICIOUS_WASTE_PCT = 50

/**
 * 이동(ACT)보다 앞에서 나는 피해다. 그 틱의 **시작** 좌표에서 맞은 것이므로 끝 좌표로
 * 세면 용암 위를 지나친 칸이 아니라 도착한 칸이 붉어진다.
 */
export const PRE_MOVE_PHASES: readonly string[] = [PHASE_UPKEEP, PHASE_TELEGRAPH]

/** 백분율의 밑. 부동소수를 쓰지 않으므로 정수 나눗셈으로 접는다. */
const PERCENT_BASE = 100

/** 규칙 하나의 성적. */
export interface RuleStat {
  /** 화면에 적는 이름. 규칙 번호는 `[3]`, 규칙 없이 나온 행동은 DEFAULT 다. */
  readonly label: string
  /** DECIDE 에 이 규칙으로 결정한 횟수. */
  readonly fired: number
  /** 그 결정이 ACT 에서 실제로 무언가를 한 횟수. */
  readonly acted: number
  /** ACT 까지 갔지만 헛돈 횟수. */
  readonly wasted: number
}

/** 좌표를 아는 대응표. 순회 대상이 아니라 조회용이다. */
export type PositionTable = ReadonlyMap<string, Position>

/** 피해 한 건. 어느 틱에 누가 어느 칸에서 얼마를 맞았는가. */
export interface DamageHit {
  readonly tick: number
  readonly targetId: string
  readonly position: Position
  readonly amount: number
}

/**
 * 시도 중 헛돈 비율. 정수 퍼센트다 — 부동소수를 쓰지 않는다 (R5).
 *
 * @param stat 볼 성적.
 * @returns 0 이상 100 이하의 정수. 시도가 없으면 0.
 */
export function getWastePercent(stat: RuleStat): number {
  const attempts = stat.acted + stat.wasted
  return attempts === 0 ? 0 : divideFloor(stat.wasted * PERCENT_BASE, attempts)
}

/**
 * 결과 문구가 헛돈 시도인가.
 *
 * @param outcome ACT 로그의 결과 문구.
 * @returns 낭비 표식이 하나라도 있으면 true.
 */
export function checkWasted(outcome: string): boolean {
  return WASTE_MARKERS.some((marker) => outcome.includes(marker))
}

/**
 * 한 엔티티의 규칙별 발동·성공·낭비를 센다.
 *
 * @param entries 전투 이벤트 로그 전량.
 * @param entityId 대상 엔티티 id.
 * @returns 우선순위 순으로 정렬된 성적표. DEFAULT 는 맨 뒤에 온다.
 */
export function buildRuleStats(
  entries: readonly LogEntry[],
  entityId: string,
): readonly RuleStat[] {
  const fired = new Map<number | null, number>()
  const acted = new Map<number | null, number>()
  const wasted = new Map<number | null, number>()

  for (const entry of entries) {
    if (entry.entityId !== entityId) {
      continue
    }
    if (entry.phase === PHASE_DECIDE) {
      addCount(fired, entry.rule)
    } else if (entry.phase === PHASE_ACT) {
      addCount(checkWasted(entry.outcome) ? wasted : acted, entry.rule)
    }
  }

  const keys = [...new Set([...fired.keys(), ...acted.keys(), ...wasted.keys()])]
  // 파이썬 `key=lambda k: (k is None, k or 0)` 와 같은 순서다. None 은 맨 뒤로 간다.
  const ordered = sortByKey(keys, (key) => [key === null ? 1 : 0, key ?? 0])
  return ordered.map((key) => ({
    label: key === null ? DEFAULT_RULE_LABEL : `[${String(key)}]`,
    fired: fired.get(key) ?? 0,
    acted: acted.get(key) ?? 0,
    wasted: wasted.get(key) ?? 0,
  }))
}

/**
 * 한 칸 세기. 없던 열쇠는 0 에서 시작한다.
 *
 * @param counts 세는 표.
 * @param key 규칙 번호. 규칙 없이 나온 행동은 null 이다.
 */
function addCount(counts: Map<number | null, number>, key: number | null): void {
  counts.set(key, (counts.get(key) ?? 0) + 1)
}

/**
 * 한 틱의 로그에서 피격 좌표를 뽑는다.
 *
 * 좌표는 로그에 없다. 로그가 남기는 것은 "누가 얼마를 맞았는가" 이고 "어디에서" 는 그
 * 틱의 세계 상태에만 있으므로, 호출자가 틱 전후의 좌표표를 함께 넘긴다.
 *
 * @param entries 그 한 틱에 쌓인 로그.
 * @param startPositions 틱 시작 시점의 entityId → 좌표.
 * @param endPositions 틱 종료 시점의 entityId → 좌표. 그 틱에 등장한 개체는 시작 시점
 *   표에 없으므로 이쪽으로 대신한다.
 * @returns 로그에 남은 순서대로의 피격 기록. 피해가 아닌 줄은 빠진다.
 */
export function extractDamageHits(
  entries: readonly LogEntry[],
  startPositions: PositionTable,
  endPositions: PositionTable,
): readonly DamageHit[] {
  const hits: DamageHit[] = []
  for (const entry of entries) {
    if (entry.targetId === null || entry.delta === null || entry.delta >= 0) {
      continue
    }
    const source = PRE_MOVE_PHASES.includes(entry.phase) ? startPositions : endPositions
    const position = source.get(entry.targetId) ?? endPositions.get(entry.targetId)
    if (position === undefined) {
      continue
    }
    hits.push({
      tick: entry.tick,
      targetId: entry.targetId,
      position,
      amount: -entry.delta,
    })
  }
  return hits
}

/**
 * 피격 기록을 격자 합계로 접는다 (GDD §8.3).
 *
 * @param hits 피격 기록들.
 * @param width 방의 가로 칸 수.
 * @param height 방의 세로 칸 수.
 * @param targetId 이 엔티티가 맞은 것만 센다. 생략하면 전원을 센다.
 * @returns `[y][x]` 순서의 피해 합계 격자. 방 밖 좌표는 버린다.
 */
export function buildDamageHeatmap(
  hits: readonly DamageHit[],
  width: number,
  height: number,
  targetId?: string,
): readonly (readonly number[])[] {
  const grid = Array.from({ length: height }, () => new Array<number>(width).fill(0))
  for (const hit of hits) {
    if (targetId !== undefined && hit.targetId !== targetId) {
      continue
    }
    const { x, y } = hit.position
    const row = grid[y]
    if (row === undefined || x < 0 || x >= width) {
      continue
    }
    row[x] = (row[x] ?? 0) + hit.amount
  }
  return grid
}

/** 히트맵에서 가장 많이 맞은 칸. */
export interface HeatPeak {
  readonly position: Position
  readonly amount: number
}

/**
 * 히트맵에서 가장 많이 맞은 칸을 찾는다.
 *
 * 같은 값이 여럿이면 행 우선(위쪽, 그다음 왼쪽)으로 먼저 나온 칸을 준다. 순서를 정해
 * 두지 않으면 같은 판을 두 번 열었을 때 다른 칸을 짚는다.
 *
 * @param grid buildDamageHeatmap 결과.
 * @returns 최댓값과 그 좌표. 피해가 한 건도 없으면 undefined.
 */
export function findHeatmapPeakCell(grid: readonly (readonly number[])[]): HeatPeak | undefined {
  let peak: HeatPeak | undefined
  grid.forEach((row, y) => {
    row.forEach((value, x) => {
      if (value > 0 && (peak === undefined || value > peak.amount)) {
        peak = { position: { x, y }, amount: value }
      }
    })
  })
  return peak
}

/**
 * 히트맵에서 가장 많이 맞은 칸의 값. 강도 단계를 정하는 기준이다.
 *
 * @param grid buildDamageHeatmap 결과.
 * @returns 최댓값. 피해가 없으면 0.
 */
export function findHeatmapPeak(grid: readonly (readonly number[])[]): number {
  return findHeatmapPeakCell(grid)?.amount ?? 0
}
