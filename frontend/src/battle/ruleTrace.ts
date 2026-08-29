/**
 * 규칙 추적 — 이번 틱에 규칙표의 각 줄이 어떤 상태였는지 화면용으로 남긴다.
 *
 * 규칙 행의 상태가 셋이라는 것이 이 게임의 핵심 정보다 (design/README.md §2).
 * 참·발동 / 참·미발동 / 거짓을 UI 가 구분해 보여주지 못하면 플레이어는 자기 규칙표의
 * 우선순위를 영영 못 읽는다 (P1).
 *
 * **RuleVM 을 다시 구현하지 않는다.** 실제 계획은 안쪽 VM 이 내고, 여기서는 그 계획의
 * `ruleIndex` 를 경계로 줄들을 가른다 —
 *
 *   우선순위 < 발동한 규칙   VM 이 평가했고 거짓이었다 → `false`, 실측값을 병기한다
 *   우선순위 = 발동한 규칙   → `true` + armed, 조건문은 **코어가 만든 expr 을 그대로** 쓴다
 *   우선순위 > 발동한 규칙   VM 이 단축 평가로 보지 않았다 → `pending`
 *
 * 경계를 계획에서 얻으므로 화면과 코어가 어긋날 수 없다. 여기서 루프를 다시 짜면 언젠가
 * 두 판정이 갈리고, 그때 플레이어는 로그와 규칙표 중 어느 쪽을 믿어야 할지 알 수 없다.
 *
 * 조건 평가는 순수 함수이며 난수를 쓰지 않는다(`evaluateCondition`·`resolveTarget`).
 * 그래서 이 정책을 끼워도 난수 소비 순서가 바뀌지 않는다 (R5).
 */

import {
  type BlockCatalog,
  type Rhs,
  type Rule,
  type RuleSet,
  OP_OR,
  isStatRef,
} from '../core/schemas'
import { evaluateCondition, type RuleVm } from '../core/rules/ruleVm'
import type { PerceptionSnapshot } from '../core/sim/perception'
import type { DecisionPolicy, PlannedAction } from '../core/sim/plan'
import { resolveTarget } from '../core/sim/selectors'
import type { Entity, WorldState } from '../core/sim/state'
import type { RuleRowState } from '../ds'

/** 셀렉터가 아무도 고르지 못해 평가조차 되지 않은 줄에 붙이는 꼬리말. */
export const NO_TARGET_NOTE = '대상 없음'

/** 조건절을 잇는 표기. 코어의 `evaluateCondition` 과 같은 문자열을 쓴다. */
const JOIN_AND = ' AND '
const JOIN_OR = ' OR '

/** 규칙표 한 줄의 이번 틱 상태. RuleRow 가 그대로 받는다. */
export interface RuleTraceRow {
  /** 우선순위. RuleRow 의 index 다. */
  readonly priority: number
  readonly state: RuleRowState
  readonly armed: boolean
  /** 실측값이 병기된 조건문. pending 인 줄은 값 없이 이름만 적는다. */
  readonly condition: string
  /** 행동절. `SKILL_1 → 가장 가까운 적` 형태다. */
  readonly action: string
  /** 이 줄까지의 누적 CPU. */
  readonly cpuUsed: number
}

/** 한 틱의 추적 결과. */
export interface RuleTrace {
  readonly tick: number
  readonly entityId: string
  readonly rows: readonly RuleTraceRow[]
}

/**
 * 우변 하나를 사람이 읽는 문자열로 만든다.
 *
 * @param rhs 조건 항의 우변.
 * @param catalog 라벨을 얻을 블록 카탈로그.
 * @returns 리터럴이면 값 그대로, 스탯 참조면 그 스탯의 한국어 이름.
 */
function formatRhsLabel(rhs: Rhs, catalog: BlockCatalog): string {
  if (!isStatRef(rhs)) {
    return String(rhs)
  }
  return catalog.rhsStats.get(rhs.stat)?.labelKo ?? rhs.stat
}

/**
 * 아직 평가되지 않은 줄의 조건문을 만든다.
 *
 * 실측값을 `(없음)` 으로 적지 않는다. 그것은 "값을 만들 수 없었다" 는 뜻이고, 여기는
 * **아직 보지 않았다** 는 뜻이라 둘을 같은 표기로 적으면 진단이 틀어진다.
 *
 * @param rule 규칙 한 줄.
 * @param catalog 라벨을 얻을 블록 카탈로그.
 * @returns 값 없이 이름만 적힌 조건문.
 */
export function formatPendingCondition(rule: Rule, catalog: BlockCatalog): string {
  const joiner = rule.conditions.op === OP_OR ? JOIN_OR : JOIN_AND
  return rule.conditions.terms
    .map((term) => {
      const base = catalog.perceptions.get(term.lhs)?.labelKo ?? term.lhs
      const label = term.lhsParam === null ? base : `${base}[${term.lhsParam}]`
      return `${label} ${term.comparison} ${formatRhsLabel(term.rhs, catalog)}`
    })
    .join(joiner)
}

/**
 * 행동절을 만든다.
 *
 * @param rule 규칙 한 줄.
 * @param catalog 라벨을 얻을 블록 카탈로그.
 * @returns `사격 → 가장 가까운 적` 형태의 한 줄.
 */
export function formatActionText(rule: Rule, catalog: BlockCatalog): string {
  const action = catalog.actions.get(rule.action)?.labelKo ?? rule.action
  if (rule.target === null) {
    return action
  }
  const selector = catalog.selectors.get(rule.target)?.labelKo ?? rule.target
  return `${action} → ${selector}`
}

/** `buildRuleTrace` 가 받는 값들. */
export interface RuleTraceInput {
  readonly ruleset: RuleSet
  readonly catalog: BlockCatalog
  readonly kindTypes: ReadonlyMap<string, string>
  readonly entity: Entity
  readonly snapshot: PerceptionSnapshot
  readonly state: WorldState
  /** VM 이 실제로 고른 계획. 경계를 여기서 얻는다. */
  readonly plan: PlannedAction
  /** 남은 CPU 예산. `self_cpu_headroom` 항이 이것을 읽는다. */
  readonly cpuHeadroom: number
}

/**
 * 이번 틱의 규칙표 상태를 만든다.
 *
 * @param input 규칙표·카탈로그·엔티티·스냅샷·계획.
 * @returns 규칙 줄마다의 상태.
 */
export function buildRuleTrace(input: RuleTraceInput): RuleTrace {
  const armedPriority = input.plan.ruleIndex
  const rows: RuleTraceRow[] = []
  let cpuUsed = 0

  for (const rule of input.ruleset.rules) {
    cpuUsed += rule.cpuCost
    if (armedPriority !== null && rule.priority === armedPriority) {
      rows.push({
        priority: rule.priority,
        state: 'true',
        armed: true,
        condition: input.plan.expr,
        action: formatActionText(rule, input.catalog),
        cpuUsed,
      })
      continue
    }
    if (armedPriority !== null && rule.priority > armedPriority) {
      rows.push({
        priority: rule.priority,
        state: 'pending',
        armed: false,
        condition: formatPendingCondition(rule, input.catalog),
        action: formatActionText(rule, input.catalog),
        cpuUsed,
      })
      continue
    }
    rows.push({
      priority: rule.priority,
      state: 'false',
      armed: false,
      condition: describeRejectedRule(rule, input),
      action: formatActionText(rule, input.catalog),
      cpuUsed,
    })
  }

  return { tick: input.state.tick, entityId: input.entity.entityId, rows }
}

/**
 * 거짓으로 떨어진 줄의 조건문을 실측값과 함께 만든다.
 *
 * 셀렉터가 아무도 고르지 못한 규칙은 VM 이 조건을 보지도 않고 건너뛴다 (F-1). 그 사실을
 * 적어 두지 않으면 플레이어는 조건식을 의심하며 시간을 버린다.
 *
 * @param rule 규칙 한 줄.
 * @param input 추적 입력.
 * @returns 실측값이 병기된 조건문.
 */
function describeRejectedRule(rule: Rule, input: RuleTraceInput): string {
  const target =
    rule.target === null
      ? undefined
      : resolveTarget(rule.target, input.entity, input.state, input.kindTypes)
  if (rule.target !== null && target === undefined) {
    return `${formatPendingCondition(rule, input.catalog)} — ${NO_TARGET_NOTE}`
  }
  return evaluateCondition(rule.conditions, {
    snapshot: input.snapshot,
    catalog: input.catalog,
    target,
    cpuHeadroom: input.cpuHeadroom,
    actor: input.entity,
    castingIds: input.state.castingIds,
  }).expr
}

/**
 * RuleVM 을 감싸 이번 틱의 규칙표 상태를 남기는 결정기.
 *
 * 계획은 안쪽 VM 이 낸 것을 **그대로** 돌려준다. 여기서 행동을 바꾸면 화면을 켰을 때와
 * 껐을 때의 전투 결과가 달라져 게이트 G3 의 전제가 무너진다.
 */
export class TracingRuleVm implements DecisionPolicy {
  /** 마지막 틱의 추적 결과. 아직 한 틱도 돌지 않았으면 undefined 다. */
  trace: RuleTrace | undefined = undefined

  /**
   * 추적기를 만든다.
   *
   * @param inner 감쌀 VM.
   * @param catalog 라벨을 얻을 블록 카탈로그.
   */
  constructor(
    readonly inner: RuleVm,
    readonly catalog: BlockCatalog,
  ) {}

  /**
   * 안쪽 VM 에 결정을 맡기고 그 결과로 규칙표 상태를 만든다.
   *
   * @param entity 결정 주체.
   * @param snapshot PERCEPTION 이 고정한 값들.
   * @param state 세계 상태. 읽기만 한다.
   * @returns 안쪽 VM 이 낸 계획 그대로.
   */
  planAction(entity: Entity, snapshot: PerceptionSnapshot, state: WorldState): PlannedAction {
    const plan = this.inner.planAction(entity, snapshot, state)
    this.trace = buildRuleTrace({
      ruleset: this.inner.ruleset,
      catalog: this.catalog,
      kindTypes: this.inner.kindTypes,
      entity,
      snapshot,
      state,
      plan,
      cpuHeadroom: this.inner.getHeadroom(entity),
    })
    return plan
  }
}
