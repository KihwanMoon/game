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
export interface PlannedAction {
  readonly entityId: string
  readonly actionId: string
  readonly targetId: string | null
  readonly ruleIndex: number | null
  readonly expr: string
  /** 플래그 기록은 상태 변경이므로 DECIDE 가 아니라 ACT 에서 적용한다 (TDD §5.2). */
  readonly setFlag: string | null
}

/** `createPlannedAction` 이 받는 값들. 생략한 항목은 파이썬 dataclass 의 기본값과 같다. */
export interface PlannedActionInput {
  readonly entityId: string
  readonly actionId: string
  readonly targetId?: string | null
  readonly ruleIndex?: number | null
  readonly expr?: string
  readonly setFlag?: string | null
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
