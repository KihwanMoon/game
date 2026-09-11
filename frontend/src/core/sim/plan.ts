/**
 * 틱 진행의 공용 타입 — `game/app/simulation/plan.py` 의 이식. 계획·설정·페이즈 이름.
 *
 * 엔진과 행동 실행기가 함께 쓰는 것만 둔다. 한쪽에 두면 다른 쪽이 그것을 import 하면서
 * 순환 참조가 생긴다.
 */

import type { SkillDef, SkillEffect } from '../skills/catalog'
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

/**
 * 공격으로 치는 행동들. **규칙 평가와 실행이 같은 목록을 봐야 한다** — 갈리면 규칙은
 * 「불가」로 막았는데 실행은 때리거나, 그 반대가 된다.
 */
export const ATTACK_ACTIONS: ReadonlySet<string> = new Set(['ATTACK', 'SKILL_1', 'SKILL_2'])

/**
 * 근접 사거리. 이보다 멀리 닿는 공격만 직선 시야를 묻는다 — 인접한 칸에 시야를 묻는 것은
 * 뜻이 없고, 물으면 벽 모서리에서 근접 공격이 안 나간다.
 */
export const MELEE_REACH = 1

/** 방어 감소율과 유지 틱을 읽을 스킬 id. GUARD 계열이 하나뿐이라 상수로 둔다. */
export const GUARD_SKILL_ID = 'GUARD_BRACE'

/**
 * 틱을 안 쓰는 스킬들. 파이썬 `FREE_SKILLS` 와 같다.
 *
 * **규칙표에서는 한 줄을 차지하지만 그 틱의 행동은 아니다.** 데이터가 아니라 상수인
 * 이유: 「자리를 안 먹는다」는 밸런스 값이 아니라 규칙이다 — 데이터로 두면 공격 스킬에
 * 켜 볼 수 있고, 그러면 한 틱에 둘을 때린다.
 */
export const FREE_SKILLS: ReadonlySet<string> = new Set([GUARD_SKILL_ID])

/**
 * 틱을 안 쓰는 소모품들. 파이썬 `FREE_ITEMS` 와 같다 (2026-09-11 실측).
 *
 * **같은 기제면 같은 규칙이다** — 보호 주문서는 방벽과 똑같은 `GUARD` 상태를 똑같은
 * 값으로 거는데, 한쪽만 틱을 내면 세계에 규칙이 둘이 된다. 실측도 같은 말을 했다: 층
 * 배치 80런에서 보호 주문서를 쓰는 규칙표가 기준(57%)보다 **낮은** 47% 였다.
 *
 * **즉발 주문서는 여기 없다.** 순간이동·화염은 그 자체가 행동이라 틱을 낸다.
 */
export const FREE_ITEMS: ReadonlySet<string> = new Set(['SCROLL'])

/** 둔화. **이동이 두 틱에 한 칸이 된다** (GDD §211). */
export const STATUS_SLOW = 'SLOW'

/** 둔화 중 몇 틱마다 한 칸 움직이는가. 2 면 절반 속도다. */
export const SLOW_EVERY = 2 

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
  /**
   * **자리를 안 먹는 행동들** (2026-09-10 결정). 규칙표는 켜고 끄는 것만 정하고 틱을
   * 안 쓴다 — 방벽이 그 첫 자리다. 파이썬 `free_skills` 와 같다.
   */
  readonly freeSkills: readonly string[]
  /** 자리를 안 먹는 소모품들 (`FREE_ITEMS`). 충전은 그대로 탄다. */
  readonly freeItems: readonly string[]
  /**
   * **규칙표가 직접 다루는 소모품 태그들** (2026-09-11). 조건 발동이 이 목록을 비껴
   * 간다 — 내가 적은 줄이 기본보다 세다.
   */
  readonly managedItems: readonly string[]
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
  readonly freeSkills?: readonly string[]
  readonly freeItems?: readonly string[]
  readonly managedItems?: readonly string[]
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
    freeSkills: input.freeSkills ?? [],
    freeItems: input.freeItems ?? [],
    managedItems: input.managedItems ?? [],
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
  /** 스킬이 켜는 취소 스위치. 몬스터 절에는 없다 (설계/5_스킬 §10.3). */
  readonly cancel_on_act?: boolean
  readonly cancel_on_hit?: boolean
  /** 형태. 없으면 반경으로 읽는다 (몬스터 절에는 없다). */
  readonly shape?: string
  readonly length?: number
  readonly toward?: { readonly x: number; readonly y: number }
  readonly effects?: readonly SkillEffect[]
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
  /**
   * 스킬 id -> 정의. **예전에는 속성마다 맵이 따로였다** — 계수·사거리·쿨타임·회복률·
   * 감쇠율·감쇠틱 여섯이다. 속성을 하나 더할 때마다 맵이 늘었고, 무엇보다 맵끼리
   * 어긋날 수 있었다: 계수 맵에만 있고 쿨타임 맵에 없는 스킬은 「쿨타임 0」으로 조용히
   * 돈다. 레코드 하나면 그 어긋남이 성립하지 않는다 (파이썬 `EngineConfig.skills`).
   */
  readonly skills: ReadonlyMap<string, SkillDef>
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
