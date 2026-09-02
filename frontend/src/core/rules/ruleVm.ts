/**
 * RuleVM — `game/app/rules/rule_vm.py` 의 이식. 규칙표를 읽어 매 틱 행동 하나를 고른다
 * (TDD §5).
 *
 * 평가 순서는 **셀렉터 → 조건 → 행동** 이다 (Phase 0 F-1 결정). 조건의 `대상 HP%` 는 그
 * 규칙의 TARGET 이 가리키는 적을 뜻하며, 셀렉터가 아무도 못 고르면 그 규칙은 발동하지
 * 않는다 — 없는 소환사를 공격하라는 규칙이 틱을 버리는 것을 막는다.
 *
 * 우선순위 오름차순으로 평가해 **최초로 참인 규칙 하나만** 실행한다. 전부 거짓이면
 * DEFAULT 인 '가장 가까운 적에게 접근' 이 나간다 (TDD §5.2).
 *
 * 조건 평가는 순수 함수다. 부작용이 없으므로 같은 스냅샷을 두 번 물으면 같은 답이 나오고,
 * 무한 루프가 원천 차단된다. 플래그 기록 같은 상태 변경은 계획에만 담아 ACT 로 넘긴다.
 *
 * **값이 없는 것과 값이 0 인 것은 다르다.** 아직 만들 수 없는 인지 변수와 읽을 수 없는
 * 스탯은 `undefined` 이고, 그 항은 거짓으로 떨어진다. 0 으로 채워 참이 되게 하면 구현되지
 * 않은 기능이 동작하는 것처럼 보인다.
 */

import { VisionGrid, checkLineOfSight } from '../grid/vision'
import { getManhattanDistance } from '../grid/geometry'
import {
  type BlockCatalog,
  type Comparison,
  type Condition,
  OP_OR,
  type Rule,
  type RuleSet,
  type Term,
  isStatRef,
} from '../schemas'
import { type PerceptionSnapshot, readSnapshot } from '../sim/perception'
import {
  ATTACK_ACTIONS,
  MELEE_REACH,
  USE_ITEM_ACTION,
  USE_SKILL_ACTION,
  type BlockedRule,
  type DecisionPolicy,
  type PlannedAction,
  createPlannedAction,
} from '../sim/plan'
import { resolveTarget } from '../sim/selectors'
import { countItem, type Entity, type WorldState, checkHasSkill, getHpPercent } from '../sim/state'

/** 측정된 값. `undefined` 는 "아직 값을 만들 수 없다" 는 뜻이며 0·false 와 다르다. */
export type MeasuredValue = number | boolean | undefined

/** 대상이 정해져야 값이 나오는 인지 변수. 스냅샷이 아니라 해석된 대상에서 읽는다. */
export const TARGET_BLOCKS: ReadonlySet<string> = new Set([
  'target_hp_percent',
  'target_is_casting',
])

/**
 * 조건 우변에 둘 수 있는 자기 스탯에서 그 값을 읽는 함수로 (F-2).
 *
 * 허용 목록의 정본은 blocks.json 의 rhs_stats 이며, 여기 키와 짝이 맞는지는 테스트가
 * 지킨다. `Record` 가 아니라 `Map` 인 이유는 키 순회 순서다 (R5).
 */
export const RHS_STAT_READERS: ReadonlyMap<string, (actor: Entity) => number> = new Map([
  ['attack_range', (actor: Entity) => actor.attackRange],
  ['attack', (actor: Entity) => actor.attack],
  ['defense', (actor: Entity) => actor.defense],
  ['hp_max', (actor: Entity) => actor.hpMax],
  ['cpu_budget', (actor: Entity) => actor.cpuBudget],
  ['potions', (actor: Entity) => countItem(actor, 'POTION')],
  ['scrolls', (actor: Entity) => countItem(actor, 'SCROLL')],
])

export const DEFAULT_ACTION = 'APPROACH'
export const DEFAULT_SELECTOR = 'NEAREST'

/**
 * 비교 연산자에서 판정 함수로.
 *
 * 양변을 수로 바꿔서 넘긴다. 파이썬의 `bool` 은 `int` 의 하위형이라 `True == 1` 이 참이고
 * `False < True` 가 참인데, 자바스크립트의 `===` 는 그 둘을 거짓으로 만든다. 불리언을
 * 0·1 로 접어 두면 여섯 연산자가 모두 파이썬과 같은 답을 낸다.
 */
export const COMPARATORS: ReadonlyMap<Comparison, (left: number, right: number) => boolean> =
  new Map([
    ['<', (left: number, right: number) => left < right],
    ['<=', (left: number, right: number) => left <= right],
    ['>', (left: number, right: number) => left > right],
    ['>=', (left: number, right: number) => left >= right],
    ['==', (left: number, right: number) => left === right],
    ['!=', (left: number, right: number) => left !== right],
  ])

/** 조건식 평가의 결과. 참거짓과 사람이 읽는 문자열을 함께 낸다. */
export interface ConditionResult {
  readonly fired: boolean
  readonly expr: string
}

/** `evaluateCondition` 이 스냅샷 밖에서 받아야 하는 것들. */
export interface ConditionContext {
  /** PERCEPTION 이 고정한 값들. */
  readonly snapshot: PerceptionSnapshot
  /** 라벨을 얻을 블록 카탈로그. */
  readonly catalog: BlockCatalog
  /** 셀렉터가 고른 대상. 대상 계열 인지 변수가 여기서 값을 얻는다. */
  readonly target?: Entity | undefined
  /** 남은 CPU 예산. `self_cpu_headroom` 항이 이것을 읽는다. */
  readonly cpuHeadroom?: number | undefined
  /** 규칙표의 주인. 스탯 우변이 이 엔티티에서 값을 얻는다 (F-2). */
  readonly actor?: Entity | undefined
  /** 예고를 걸어 둔 엔티티 id 들 (WorldState.castingIds). */
  readonly castingIds?: readonly string[]
}

/**
 * 조건 항의 좌변 값을 읽는다.
 *
 * 대상 계열과 CPU 여유는 스냅샷에 없다. 전자는 규칙마다 셀렉터가 다르고, 후자는 규칙표를
 * 알아야 계산되기 때문이다 — 둘 다 VM 만 답할 수 있다.
 *
 * @param term 읽을 항.
 * @param snapshot PERCEPTION 이 고정한 값들.
 * @param target 이 규칙의 셀렉터가 고른 대상. 없으면 undefined.
 * @param cpuHeadroom 남은 CPU 예산.
 * @param castingIds 예고를 걸어 둔 엔티티 id 들.
 * @returns 측정된 값. 아직 만들 수 없는 값이면 undefined.
 */
export function readTermValue(
  term: Term,
  snapshot: PerceptionSnapshot,
  target: Entity | undefined,
  cpuHeadroom: number | undefined = undefined,
  castingIds: readonly string[] = [],
): MeasuredValue {
  if (term.lhs === 'target_hp_percent') {
    return target === undefined ? undefined : getHpPercent(target)
  }
  if (term.lhs === 'target_is_casting') {
    return target === undefined ? undefined : castingIds.includes(target.entityId)
  }
  if (term.lhs === 'self_cpu_headroom') {
    return cpuHeadroom
  }
  if (TARGET_BLOCKS.has(term.lhs)) {
    return undefined
  }
  return readSnapshot(snapshot, term.lhs, term.lhsParam)
}

/**
 * 엔티티의 스탯 값을 읽는다 (F-2).
 *
 * @param actor 규칙표의 주인. 없으면 값을 만들 수 없다.
 * @param stat blocks.json 의 rhsStats 에 있는 스탯 id.
 * @returns 측정된 값. 주인이 없거나 모르는 스탯이면 undefined.
 */
export function readStatValue(actor: Entity | undefined, stat: string): number | undefined {
  const reader = RHS_STAT_READERS.get(stat)
  if (actor === undefined || reader === undefined) {
    return undefined
  }
  return reader(actor)
}

/**
 * 조건 항의 우변 값을 읽는다. 리터럴이면 그대로다.
 *
 * @param term 읽을 항.
 * @param actor 규칙표의 주인. 스탯 우변이 이 엔티티에서 값을 얻는다.
 * @returns 비교에 쓸 값. 읽을 수 없는 스탯이면 undefined.
 */
export function readRhsValue(term: Term, actor: Entity | undefined): MeasuredValue {
  if (isStatRef(term.rhs)) {
    return readStatValue(actor, term.rhs.stat)
  }
  return term.rhs
}

/**
 * 측정값을 로그에 넣을 문자열로 만든다.
 *
 * @param value 측정된 값. 아직 만들 수 없는 값이면 undefined.
 * @returns 사람이 읽는 표기. 값이 없으면 "없음".
 */
export function formatValue(value: MeasuredValue): string {
  if (value === undefined) {
    return '없음'
  }
  if (typeof value === 'boolean') {
    return value ? '참' : '거짓'
  }
  return String(value)
}

/**
 * 항을 실측값이 붙은 문자열로 편다.
 *
 * GDD §8.2 가 요구하는 것은 참/거짓이 아니라 **평가된 조건의 실제 값**이다.
 * `적거리(2) <= 사거리(3)` 처럼 양변에 괄호로 병기해야 죽고 나서 고칠 곳이 특정된다.
 * 우변이 리터럴이면 값이 곧 표기이므로 괄호를 붙이지 않는다.
 *
 * @param term 대상 항.
 * @param value 측정된 좌변 값.
 * @param catalog 라벨을 얻을 블록 카탈로그.
 * @param rhsValue 측정된 우변 값. 스탯 우변일 때만 쓰인다.
 * @returns 사람이 읽는 조건 문자열.
 */
export function renderTerm(
  term: Term,
  value: MeasuredValue,
  catalog: BlockCatalog,
  rhsValue: MeasuredValue = undefined,
): string {
  const block = catalog.perceptions.get(term.lhs)
  const base = block === undefined ? term.lhs : block.labelKo
  const label = term.lhsParam === null ? base : `${base}[${term.lhsParam}]`
  let right: string
  if (isStatRef(term.rhs)) {
    const stat = catalog.rhsStats.get(term.rhs.stat)
    const statLabel = stat === undefined ? term.rhs.stat : stat.labelKo
    right = `${statLabel}(${formatValue(rhsValue)})`
  } else {
    right = formatValue(term.rhs)
  }
  return `${label}(${formatValue(value)}) ${term.comparison} ${right}`
}

/**
 * 측정값을 비교에 쓸 수로 접는다. 불리언은 0·1 이다.
 *
 * @param value 측정된 값.
 * @returns 비교에 쓸 수.
 */
function convertToNumber(value: number | boolean): number {
  return typeof value === 'boolean' ? Number(value) : value
}

/**
 * 조건식을 평가하고 사람이 읽는 문자열을 함께 만든다.
 *
 * 값을 아직 만들 수 없는 블록(LOS 등)이 섞이면 그 항은 거짓으로 본다. 0 으로 채워 참이
 * 되게 하면 구현되지 않은 기능이 동작하는 것처럼 보인다. 읽을 수 없는 스탯 우변도 같은
 * 이유로 거짓이다.
 *
 * @param condition 평가할 조건식.
 * @param context 스냅샷·카탈로그와 VM 만 답할 수 있는 값들.
 * @returns 참거짓과 렌더링된 조건 문자열.
 */
export function evaluateCondition(
  condition: Condition,
  context: ConditionContext,
): ConditionResult {
  const castingIds = context.castingIds ?? []
  const results: boolean[] = []
  const rendered: string[] = []
  for (const term of condition.terms) {
    const value = readTermValue(
      term,
      context.snapshot,
      context.target,
      context.cpuHeadroom,
      castingIds,
    )
    const right = readRhsValue(term, context.actor)
    rendered.push(renderTerm(term, value, context.catalog, right))
    if (value === undefined || right === undefined) {
      results.push(false)
      continue
    }
    const compare = COMPARATORS.get(term.comparison)
    if (compare === undefined) {
      // 파이썬은 여기서 KeyError 로 멎는다. false 로 흘려보내면 그 규칙이 영영 발동하지
      // 않고, 플레이어는 자기 논리를 의심하게 된다 (P1). 파서와 검증기가 먼저 막지만
      // 마지막 방어선도 조용해서는 안 된다.
      throw new Error(`알 수 없는 비교 연산자다: ${term.comparison}`)
    }
    results.push(compare(convertToNumber(value), convertToNumber(right)))
  }

  const isOr = condition.op === OP_OR
  const joiner = isOr ? ' OR ' : ' AND '
  const fired = isOr ? results.some(Boolean) : results.every(Boolean)
  return { fired, expr: rendered.join(joiner) }
}

/**
 * 규칙표가 쓰는 CPU 총량을 센다 (GDD §3.6).
 *
 * @param ruleset 대상 규칙표.
 * @returns cpuCost 의 합.
 */
export function countCpuUsage(ruleset: RuleSet): number {
  return ruleset.rules.reduce((total, rule) => total + rule.cpuCost, 0)
}

/** 컴파일된 규칙표. 방 진입 시 한 번 만들고 틱마다 재사용한다 (TDD §5.1). */
/**
 * 원거리 공격인데 직선 시야가 막혔는가 (GDD §4.1).
 *
 * 근접은 안 본다 — 인접한 칸에 시야를 묻는 것은 뜻이 없고, 물으면 벽 모서리에서 근접
 * 공격이 안 나가는 일이 생긴다.
 *
 * @param action 규칙이 고른 행동.
 * @param entity 행위자.
 * @param target 셀렉터가 고른 대상.
 * @param state 지금 세계. 부순 벽을 반영해야 하므로 템플릿이 아니라 상태를 본다.
 * @returns 막혔으면 true.
 */
export function checkSightBlocked(
  action: string,
  entity: Entity,
  target: Entity | undefined,
  state: WorldState,
): boolean {
  if (!ATTACK_ACTIONS.has(action) || target === undefined) {
    return false
  }
  if (entity.attackRange <= MELEE_REACH) {
    return false
  }
  const grid = new VisionGrid(state, state.room.width, state.room.height)
  return !checkLineOfSight(grid, entity.position, target.position)
}

export class RuleVm implements DecisionPolicy {
  /**
   * VM 을 만든다.
   *
   * @param ruleset 우선순위 순으로 정렬된 규칙표.
   * @param catalog 동결된 블록 카탈로그.
   * @param kindTypes 엔티티 종류에서 적 유형으로의 대응표.
   */
  constructor(
    readonly ruleset: RuleSet,
    readonly catalog: BlockCatalog,
    readonly kindTypes: ReadonlyMap<string, string>,
  ) {}

  /**
   * 규칙의 대상을 먼저 정한다 (F-1 결정).
   *
   * @param rule 평가 중인 규칙.
   * @param entity 결정 주체.
   * @param state 세계 상태.
   * @returns 고른 대상과, 이 규칙을 계속 볼 수 있는가.
   */
  private resolveRuleTarget(
    rule: Rule,
    entity: Entity,
    state: WorldState,
  ): { target: Entity | undefined; isUsable: boolean } {
    if (rule.target === null) {
      return { target: undefined, isUsable: true }
    }
    const target = resolveTarget(rule.target, entity, state, this.kindTypes)
    return { target, isUsable: target !== undefined }
  }

  /**
   * 남은 CPU 예산 (GDD §3.6).
   *
   * @param entity 규칙표를 쓰는 엔티티.
   * @returns 예산에서 규칙표가 쓰는 양을 뺀 값. 음수면 초과 상태다.
   */
  getHeadroom(entity: Entity): number {
    return entity.cpuBudget - countCpuUsage(this.ruleset)
  }

  /**
   * 규칙표를 위에서부터 평가해 이번 틱의 행동을 고른다.
   *
   * @param entity 결정 주체.
   * @param snapshot PERCEPTION 이 고정한 값들.
   * @param state 세계 상태. 읽기만 한다.
   * @returns 최초로 참이 된 규칙의 계획. 전부 거짓이면 DEFAULT 계획.
   */
  planAction(entity: Entity, snapshot: PerceptionSnapshot, state: WorldState): PlannedAction {
    const blocked: BlockedRule[] = []
    for (const rule of this.ruleset.rules) {
      const { target, isUsable } = this.resolveRuleTarget(rule, entity, state)
      if (!isUsable) {
        continue
      }
      const { fired, expr } = evaluateCondition(rule.conditions, {
        snapshot,
        catalog: this.catalog,
        target,
        cpuHeadroom: this.getHeadroom(entity),
        actor: entity,
        castingIds: state.castingIds,
      })
      if (!fired) {
        continue
      }
      // 조건이 참이어도 수단이 없으면 넘어간다. 그리고 **그 사실을 들고 나온다** —
      // 조용히 다음 규칙으로 가면 플레이어는 왜 안 떴는지 알 수 없다 (P1).
      if (rule.action === USE_SKILL_ACTION && !checkHasSkill(entity, rule.actionParam ?? '')) {
        blocked.push({
          ruleIndex: rule.priority,
          expr,
          reason: `${String(rule.actionParam)} 미장착`,
        })
        continue
      }
      // 소모품도 같다 — 조건은 참인데 수단이 없다. 이것이 「거짓」과 다르다는 것이
      // 이 게임의 규칙 상태 4종 중 하나다 (결정 #04).
      // **인자가 없으면 물약이다.** USE_POTION 별칭과 같은 규약이고 실행부도 그렇게
      // 떨어진다 — 예전에는 문지기만 빈 문자열을 세서(늘 0) 인자 없는 소모품 규칙이
      // 영원히 「불가」였다 (e2).
      const itemKind = rule.action === USE_ITEM_ACTION ? (rule.actionParam ?? 'POTION') : null
      if (rule.action === USE_ITEM_ACTION && countItem(entity, itemKind ?? '') <= 0) {
        blocked.push({
          ruleIndex: rule.priority,
          expr,
          reason: `${String(itemKind)} 없음`,
        })
        continue
      }
      // **시야가 막힌 원거리 공격도 「불가」다** — 조건은 참인데 수단이 없다.
      //
      // 예전에는 그대로 발동시켜 틱만 버렸다. 사거리 안에 있는 한 조건은 매 틱 참이라
      // 같은 규칙이 영원히 다시 뽑히고, 캐릭터가 엄폐물 뒤의 적을 향해 가만히 선 채로
      // 판이 끝났다. 파이썬 `check_sight_blocked` 와 같은 자리다 (G3).
      if (checkSightBlocked(rule.action, entity, target, state)) {
        blocked.push({ ruleIndex: rule.priority, expr, reason: '시야 없음' })
        continue
      }
      return createPlannedAction({
        entityId: entity.entityId,
        actionId: rule.action,
        targetId: target === undefined ? null : target.entityId,
        ruleIndex: rule.priority,
        expr,
        setFlag: rule.setFlag,
        skillId: rule.action === USE_SKILL_ACTION ? rule.actionParam : null,
        itemKind,
        blocked,
      })
    }
    return { ...this.buildDefaultAction(entity, state), blocked }
  }

  /**
   * 전부 거짓일 때의 기본 행동 (TDD §5.2).
   *
   * @param entity 결정 주체.
   * @param state 세계 상태.
   * @returns 가장 가까운 적에게 접근하는 계획. 적이 없으면 대기.
   */
  private buildDefaultAction(entity: Entity, state: WorldState): PlannedAction {
    const target = resolveTarget(DEFAULT_SELECTOR, entity, state, this.kindTypes)
    if (target === undefined) {
      return createPlannedAction({ entityId: entity.entityId, actionId: 'HOLD', expr: '적 없음' })
    }
    const distance = getManhattanDistance(entity.position, target.position)
    return createPlannedAction({
      entityId: entity.entityId,
      actionId: DEFAULT_ACTION,
      targetId: target.entityId,
      expr: `모든 규칙 거짓 → DEFAULT (적거리 ${distance})`,
    })
  }
}

/**
 * 규칙표를 실행 가능한 형태로 만든다.
 *
 * @param ruleset 검증을 통과한 규칙표.
 * @param catalog 동결된 블록 카탈로그.
 * @param kindTypes 엔티티 종류에서 적 유형으로의 대응표.
 * @returns DecisionPolicy 로 쓸 수 있는 VM.
 */
export function buildRuleVm(
  ruleset: RuleSet,
  catalog: BlockCatalog,
  kindTypes: ReadonlyMap<string, string>,
): RuleVm {
  return new RuleVm(ruleset, catalog, kindTypes)
}
