/**
 * 되감기용 규칙표 상태 — **지나간 틱**의 규칙표를 로그 한 줄로 되짚는다.
 *
 * `battle/ruleTrace.ts` 와 목적이 다르다. 그쪽은 정책을 감싸 **지금 도는 틱**을 다시
 * 평가해 모든 줄의 실측값을 얻는다(TracingRuleVm). 그것은 살아 있는 엔진이 있어야만
 * 되는 방식이라 되감기에는 쓸 수 없다 — 5틱 전의 세계는 이미 없다.
 *
 * 여기서는 그 틱의 DECIDE 로그 한 줄만 본다. RuleVM 은 위에서부터 훑다가 처음 참이 된
 * 규칙에서 멈추므로, 발동한 줄의 자리만 알면 표 전체가 복원된다 — 그 위는 전부 거짓,
 * 아래는 아예 평가되지 않음(pending). 실측값이 병기된 조건문은 발동한 줄에만 있고,
 * 나머지 줄의 표기는 `battle/ruleTrace.ts` 의 서식 함수를 그대로 쓴다. 두 화면의 규칙표
 * 문구가 갈리지 않게 하려는 것이다.
 */

import { formatActionText, formatPendingCondition } from '../battle'
import type { LogEntry } from '../core/eventLog'
import type { BlockCatalog, RuleSet } from '../core/schemas'
import { PHASE_DECIDE } from '../core/sim/phases'
import type { RuleRowState } from '../ds'

/** 되감아 본 규칙표 한 줄. RuleRow 가 그대로 받는다. */
export interface ReplayTraceRow {
  readonly priority: number
  readonly state: RuleRowState
  readonly armed: boolean
  /** 발동한 줄은 실측값이 병기된 코어의 expr, 나머지는 값 없는 이름뿐이다. */
  readonly condition: string
  readonly action: string
  /** 이 줄까지의 누적 CPU. 예산 초과는 오류가 아니라 수치다. */
  readonly cpuUsed: number
}

/**
 * 그 틱에 그 엔티티가 내린 결정 한 줄을 찾는다.
 *
 * @param entries 로그 전량.
 * @param tick 볼 틱.
 * @param entityId 볼 엔티티.
 * @returns DECIDE 로그 한 줄. 그 틱에 결정이 없었으면 undefined.
 */
export function findDecision(
  entries: readonly LogEntry[],
  tick: number,
  entityId: string,
): LogEntry | undefined {
  return entries.find(
    (entry) => entry.tick === tick && entry.entityId === entityId && entry.phase === PHASE_DECIDE,
  )
}

/**
 * 한 줄의 판정 상태를 정한다.
 *
 * @param index 그 줄의 첨자.
 * @param firedIndex 발동한 줄의 첨자. 전부 거짓이었으면 undefined.
 * @param hasDecision 그 틱에 결정 자체가 있었는가.
 * @returns RuleRow 가 받는 세 상태 중 하나.
 */
function resolveTraceState(
  index: number,
  firedIndex: number | undefined,
  hasDecision: boolean,
): RuleRowState {
  if (!hasDecision) {
    return 'pending'
  }
  if (firedIndex === undefined || index < firedIndex) {
    // firedIndex 가 없으면 전부 거짓이라 DEFAULT 로 떨어진 틱이다 — 모든 줄이 평가됐다.
    return 'false'
  }
  if (index === firedIndex) {
    return 'true'
  }
  // 위에서 이미 발동했으므로 여기까지 오지 않았다. 거짓과 구분해야 할 상태다.
  return 'pending'
}

/**
 * 규칙표를 그 틱의 상태로 편다.
 *
 * @param ruleset 플레이어 규칙표.
 * @param catalog 라벨을 얻을 블록 카탈로그.
 * @param decision 그 틱의 DECIDE 로그. 없으면 전 줄이 평가 대기다.
 * @returns 규칙표 순서 그대로의 줄들.
 */
export function buildReplayTrace(
  ruleset: RuleSet,
  catalog: BlockCatalog,
  decision: LogEntry | undefined,
): readonly ReplayTraceRow[] {
  // 규칙 번호가 아니라 **첨자**로 가른다. priority 가 1부터 촘촘하다는 보장이 없고,
  // RuleVM 이 도는 순서는 배열 순서이기 때문이다.
  const found =
    decision === undefined || decision.rule === null
      ? -1
      : ruleset.rules.findIndex((rule) => rule.priority === decision.rule)
  const firedIndex = found < 0 ? undefined : found

  let cpuUsed = 0
  return ruleset.rules.map((rule, index) => {
    cpuUsed += rule.cpuCost
    const armed = firedIndex !== undefined && index === firedIndex
    return {
      priority: rule.priority,
      state: resolveTraceState(index, firedIndex, decision !== undefined),
      armed,
      condition:
        armed && decision !== undefined ? decision.expr : formatPendingCondition(rule, catalog),
      action: formatActionText(rule, catalog),
      cpuUsed,
    }
  })
}
