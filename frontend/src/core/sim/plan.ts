/**
 * 틱 진행의 공용 타입 — `game/app/simulation/plan.py` 의 이식. 계획·설정·페이즈 이름.
 *
 * 엔진과 행동 실행기가 함께 쓰는 것만 둔다. 한쪽에 두면 다른 쪽이 그것을 import 하면서
 * 순환 참조가 생긴다.
 */

import type { DamageRules } from '../combat/damage'
import type { PerceptionSnapshot } from './perception'
import type { FloorScale } from './scaling'
import type { Entity, WorldState } from './state'

// 페이즈·판정 이름은 phases.ts 가 정본이다. 여기서 다시 내보내는 것은 엔진 쪽 호출자가
// 계획 타입과 페이즈 이름을 한 곳에서 받게 하기 위한 것이다.
export {
  OUTCOME_ONGOING,
  OUTCOME_PLAYER_LOSS,
  OUTCOME_PLAYER_WIN,
  OUTCOME_TIMEOUT,
  PHASE_ACT,
  PHASE_CLEANUP,
  PHASE_DECIDE,
  PHASE_ORDER,
  PHASE_PERCEPTION,
  PHASE_RESOLVE,
  PHASE_TELEGRAPH,
  PHASE_UPKEEP,
} from './phases'

/** DECIDE 가 내놓는 계획. 아직 세계를 바꾸지 않았다. */
/**
 * 규칙 상태 네 번째 (블록 v5, 결정 #04). 참·발동 / 참·미발동 / 거짓 / **불가**.
 *
 * 거짓과 다르다 — 조건은 참인데 실행할 수단이 없다. 파이썬 `OUTCOME_BLOCKED` 와 같은
 * 글자여야 한다: 로그 문자열이 골든 대조 대상이다.
 */
export const OUTCOME_BLOCKED = '불가'

/** 스킬을 정체로 가리키는 행동 (블록 v5, 결정 #04). 파이썬과 같은 값이어야 한다. */
export const USE_SKILL_ACTION = 'USE_SKILL'

/** 소모품 사용 (v6, #54). 파라미터는 카탈로그 id 가 아니라 태그다 — 물약을 여러 등급으로
 * 늘려도 규칙표가 가리키는 것이 그대로여야 한다. */
export const USE_ITEM_ACTION = 'USE_ITEM'

/** 방어 감소율과 유지 틱을 읽을 스킬 id. GUARD 계열이 하나뿐이라 상수로 둔다. */
export const GUARD_SKILL_ID = 'GUARD_BRACE' 

/** 조건은 참이었으나 실행할 수단이 없어 건너뛴 규칙 하나. */
export interface BlockedRule {
  readonly ruleIndex: number
  readonly expr: string
  readonly reason: string
}

export interface PlannedAction {
  readonly entityId: string
  readonly actionId: string
  readonly targetId: string | null
  readonly ruleIndex: number | null
  readonly expr: string
  /** 플래그 기록은 상태 변경이므로 DECIDE 가 아니라 ACT 에서 적용한다 (TDD §5.2). */
  readonly setFlag: string | null
  /** 실행할 스킬 (블록 v5). `USE_SKILL` 이 아니면 null 이다. */
  readonly skillId: string | null
  /** `USE_ITEM[kind]` 가 가리키는 소모품 태그 (v6, #54). 스킬과 같은 한 겹의 지시다. */
  readonly itemKind: string | null
  /**
   * 조건은 참인데 수단이 없어 건너뛴 규칙들 (블록 v5, 결정 #04).
   *
   * 조용히 다음 규칙으로 가면 플레이어는 왜 안 떴는지 알 수 없다 (P1).
   */
  readonly blocked: readonly BlockedRule[]
}

/** `createPlannedAction` 이 받는 값들. 생략한 항목은 파이썬 dataclass 의 기본값과 같다. */
export interface PlannedActionInput {
  readonly entityId: string
  readonly actionId: string
  readonly targetId?: string | null
  readonly ruleIndex?: number | null
  readonly expr?: string
  readonly setFlag?: string | null
  readonly skillId?: string | null
  readonly itemKind?: string | null
  readonly blocked?: readonly BlockedRule[]
}

/**
 * 기본값을 채워 계획을 만든다.
 *
 * @param input 채워 넣을 값들.
 * @returns 만들어진 계획.
 */
export function createPlannedAction(input: PlannedActionInput): PlannedAction {
  return {
    entityId: input.entityId,
    actionId: input.actionId,
    targetId: input.targetId ?? null,
    ruleIndex: input.ruleIndex ?? null,
    expr: input.expr ?? '',
    setFlag: input.setFlag ?? null,
    skillId: input.skillId ?? null,
    itemKind: input.itemKind ?? null,
    blocked: input.blocked ?? [],
  }
}

/** 행동 결정기. RuleVM 과 폴백 정책이 이 모양을 만족한다. */
export interface DecisionPolicy {
  /**
   * 이번 틱의 행동을 정한다. 부작용을 내지 않는다.
   *
   * @param entity 결정 대상.
   * @param snapshot PERCEPTION 이 고정한 값들.
   * @param state 세계 상태. 읽기만 한다.
   * @returns 실행할 계획.
   */
  planAction(entity: Entity, snapshot: PerceptionSnapshot, state: WorldState): PlannedAction
}

/**
 * 전투 도중 등장한 엔티티에 규칙표를 붙이는 것.
 *
 * 소환물과 추격자는 방을 세운 뒤에 생기므로 조립 시점의 일괄 배정이 닿지 않는다. 붙이지
 * 않으면 그들만 폴백 정책(접근만 하고 공격하지 않음)으로 싸워, 도감이 보여주는 규칙표와
 * 실제 행동이 갈린다 (GDD §5).
 */
export interface PolicyFactory {
  /**
   * 그 엔티티에 맞는 결정기를 만든다.
   *
   * @param entity 대상 엔티티.
   * @returns 만들어진 결정기. 규칙표가 없으면 undefined.
   */
  buildPolicy(entity: Entity): DecisionPolicy | undefined
}

/** balance.json 의 종류별 summon 절. '무엇을 몇 마리까지' 만 정한다. */
export interface RawSummonRule {
  readonly every_ticks: number
  readonly spawns: string
  readonly max_alive: number
}

/** balance.json 의 종류별 telegraph 절. */
export interface RawTelegraphSetting {
  readonly skill: string
  readonly lead_ticks: number
  readonly visible_ticks: number
  readonly radius: number
  readonly damage: number
  readonly cancel_on_death: boolean
  readonly self_destruct?: boolean
}

/** balance.json 의 적 종류 한 항목. 소환물·추격자를 만들 때 그대로 읽는다. */
export interface RawEnemyKind {
  /** 일반·엘리트·보스. 화면이 등급을 가르는 이름표이며 전투 수식은 안 본다. */
  readonly tier?: string
  readonly id: string
  readonly type: string
  readonly hp_max: number
  readonly attack: number
  readonly defense: number
  readonly attack_range: number
  readonly initiative: number
  readonly regen_base?: number
  readonly cpu_budget?: number
  readonly potions?: number
  readonly ruleset_id?: string
  readonly summon?: RawSummonRule
  readonly telegraph?: RawTelegraphSetting
}

/**
 * 엔진이 balance.json 에서 받아 쓰는 값들.
 *
 * 목록을 객체가 아니라 `ReadonlyMap` 으로 받는다. 조회만 하는 값이라도 객체로 두면
 * 다음 사람이 `Object.keys` 로 순회하고, 그 순간 순서가 결정론에서 빠져나간다 (R5).
 */
export interface EngineConfig {
  readonly damageRules: DamageRules
  readonly kindTypes: ReadonlyMap<string, string>
  readonly skillCoefPct: ReadonlyMap<string, number>
  /**
   * 스킬이 자체 사거리를 가지면 그것을 쓴다. null 이면 엔티티의 attackRange 다. 이것이
   * 없으면 balance.json 이 선언한 사거리가 조용히 무시되어, 원거리 스킬을 전제한
   * 규칙표(GDD §3.5 카이팅)가 매 틱 '사거리 밖' 으로 헛돈다.
   */
  readonly skillRange: ReadonlyMap<string, number | null>
  /**
   * 스킬 id -> 사용 후 걸리는 쿨타임(틱). ACT 가 성공한 행동에만 걸고 UPKEEP 이 매 틱
   * 1씩 깎는다. 이것이 비어 있으면 `내 쿨타임[스킬] 완료` 가 영구히 참이 되어 그 항을
   * 쓴 규칙이 사실상 한 항 짧아진다 — 조용히 틀리는 조건이 된다.
   */
  readonly skillCooldowns: ReadonlyMap<string, number>
  /**
   * 행동 id -> 회복량. 대상 최대 HP 의 정수 퍼센트다 (블록 목록 v4 의 HEAL). 고정값이
   * 아니라 비율인 이유는 회복이 대상의 덩치에 비례해야 하기 때문이고, 퍼센트 정수인
   * 이유는 R5 다 — 부동소수를 쓰면 플랫폼마다 결과가 갈린다.
   */
  readonly skillHealPct: ReadonlyMap<string, number>
  /**
   * 방어 태세의 피해 감소율과 유지 틱 (결정 #16).
   *
   * **파이썬에는 있는데 여기 없었다.** 방패를 껴도 브라우저는 아무 일도 안 하고 서버만
   * 적용해, 같은 판이 두 코어에서 갈렸다 (게이트 G3). 보호 주문서(v6)도 같은 값을 쓴다.
   */
  readonly skillGuardPct: ReadonlyMap<string, number>
  readonly skillGuardTicks: ReadonlyMap<string, number>
  /**
   * kindId -> 소환 규칙. '언제 소환하는가' 는 규칙표가 정하고, 여기 남는 것은 '무엇을
   * 몇 마리까지' 와 쿨타임[SUMMON] 의 초기값이 되는 주기(every_ticks)다.
   */
  readonly summonRules: ReadonlyMap<string, RawSummonRule>
  readonly enemyStats: ReadonlyMap<string, RawEnemyKind>
  /**
   * 층 깊이 스케일. 개체를 만드는 자리(방 배치·소환·추격자)가 전부 이것을 거쳐야 같은
   * 층에 다른 기준의 적이 섞이지 않는다 (`scaling.getScaledEnemyStats`).
   */
  readonly floorScale: FloorScale
  readonly floor: number
  readonly maxTicks: number
  readonly combatRegenPct: number
}

/**
 * `USE_SKILL` 계획을 그 스킬의 계획으로 바꾼다.
 *
 * v5 의 `USE_SKILL[id]` 는 한 겹의 지시다. 실행 직전에 풀어 주면 실행기는 예전 행동
 * 이름만 알면 되고, 스킬이 늘어도 실행기가 늘지 않는다 — 블록을 파라미터화한 이유와
 * 같은 방향이다.
 *
 * @param plan 실행할 계획.
 * @returns `USE_SKILL` 이면 skillId 로 바꾼 계획, 아니면 그대로.
 */
export function resolveSkillPlan(plan: PlannedAction): PlannedAction {
  if (plan.actionId !== USE_SKILL_ACTION || plan.skillId === null) {
    return plan
  }
  return { ...plan, actionId: plan.skillId }
}
