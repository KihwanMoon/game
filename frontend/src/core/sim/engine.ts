/**
 * 틱 엔진 — `game/app/simulation/engine.py` 의 이식. 7페이즈를 고정 순서로 돈다 (TDD §4.1).
 *
 * UPKEEP → TELEGRAPH → PERCEPTION → DECIDE → ACT → RESOLVE → CLEANUP.
 *
 * PERCEPTION 과 DECIDE 를 나누는 이유는 동시성 공정성이다. 모든 엔티티가 같은 시점의
 * 세계를 보고 판단해야 하며, 순차 갱신하면 처리 순서가 유리/불리를 만든다. 그래서 DECIDE
 * 는 부작용을 내지 않고 계획만 돌려주며, 실제 변경은 ACT 부터다.
 *
 * 행동을 실제로 옮기는 일은 ActionExecutor 가 맡는다. 이 모듈은 순서만 책임진다.
 *
 * 방 하나가 살아 있는 동안 유지되는 것 셋을 함께 든다 — 가시성 캐시, 예고판, 압력
 * 추적기. 앞의 둘은 방 단위이고 압력 추적기만 층 단위라 바깥에서 받는다. 방마다 새로
 * 만들면 GDD §7 의 '층 지연' 압력이 매 방 0 으로 돌아간다.
 *
 * **난수는 두 곳에서만 뽑는다** — UPKEEP 의 추격자 스폰 위치와 ACT 직전의 이니셔티브
 * 동률 가르기다. 그 순서와 횟수가 파이썬과 어긋나면 이후 모든 난수가 밀려 골든 대조가
 * 깨진다 (게이트 G3).
 */

import { EventLog, createLogEntry } from '../eventLog'
import { VisionCache, VisionGrid } from '../grid/vision'
import { compareText, sortByKey } from '../ordering'
import { TILE_LAVA, TILE_SPRING } from '../schemas'
import { ATTACK_ACTIONS, ActionExecutor, MOVE_ACTIONS } from './actions'
import { type PerceptionSnapshot, buildSnapshot } from './perception'
import {
  OUTCOME_ONGOING,
  OUTCOME_PLAYER_LOSS,
  OUTCOME_PLAYER_WIN,
  OUTCOME_TIMEOUT,
  PHASE_DECIDE,
  PHASE_TELEGRAPH,
  PHASE_UPKEEP,
} from './phases'
import type { DecisionPolicy, EngineConfig, PlannedAction, PolicyFactory } from './plan'
import { PressureTracker, applySpringDrain, removeDrainedSprings } from './pressure'
import { FACTION_PLAYER, type Entity, type WorldState, isAlive } from './state'
import { type Telegraph, TelegraphBoard } from './telegraph'

/** 용암 위에 선 엔티티가 매 틱 받는 고정 피해. */
export const LAVA_DAMAGE = 3

/** 생명의 샘이 매 틱 내주는 회복량. 잔여량이 모자라면 남은 만큼만 나온다. */
export const SPRING_REGEN_PER_TICK = 2

/** 전투 중이 아닐 때의 회복 비율. 감쇠가 없다는 뜻이다. */
const FULL_REGEN_PCT = 100

const PERCENT_BASE = 100

/** `TickEngine` 을 조립할 때 넘기는 것들. */
export interface EngineOptions {
  readonly state: WorldState
  /** 규칙표가 배정되지 않은 엔티티가 쓰는 기본 결정기. */
  readonly policy: DecisionPolicy
  readonly config: EngineConfig
  readonly log?: EventLog
  /**
   * 엔티티별 결정기. GDD §5 — 몬스터도 플레이어와 완전히 동일한 DSL 로 기술한다. 하나의
   * 정책을 전 엔티티에 공유하면 적이 플레이어의 규칙표로 싸우게 되고, 그 상태로 잰
   * 승률은 아무 의미가 없다.
   */
  readonly policies?: ReadonlyMap<string, DecisionPolicy>
  /** 진행 중인 예고. 방 단위다 — 방을 나가면 남은 예고도 함께 사라진다. */
  readonly telegraphs?: TelegraphBoard
  /** 어뷰징 차단 (GDD §7). **층 단위 객체라 바깥에서 받는다.** */
  readonly pressure?: PressureTracker
  /** 전투 도중 등장한 엔티티(소환물·추격자)에 규칙표를 붙이는 공장. */
  readonly policyFactory?: PolicyFactory | null
}

/** 한 방의 전투를 틱 단위로 진행한다. */
export class TickEngine {
  readonly state: WorldState

  /**
   * 규칙표가 배정되지 않은 엔티티가 쓰는 기본 결정기. 파이썬 dataclass 의 필드가
   * 그렇듯 조립 뒤에도 바꿀 수 있다 — 골든 대조가 정책만 갈아 끼우고 같은 방을 돌린다.
   */
  policy: DecisionPolicy

  readonly config: EngineConfig

  readonly log: EventLog

  readonly policies: Map<string, DecisionPolicy>

  readonly telegraphs: TelegraphBoard

  readonly pressure: PressureTracker

  policyFactory: PolicyFactory | null

  readonly vision: VisionCache

  readonly actions: ActionExecutor

  /**
   * 엔진을 조립한다. 방 진입 시 한 번 하는 준비 — 가시성 맵 사전 계산 — 도 여기서 한다.
   *
   * @param options 세계 상태·기본 결정기·설정과 선택 항목들.
   */
  constructor(options: EngineOptions) {
    this.state = options.state
    this.policy = options.policy
    this.config = options.config
    this.log = options.log ?? new EventLog()
    this.policies = new Map(options.policies ?? [])
    this.telegraphs = options.telegraphs ?? new TelegraphBoard()
    this.pressure = options.pressure ?? new PressureTracker()
    this.policyFactory = options.policyFactory ?? null

    const grid = new VisionGrid(this.state, this.state.room.width, this.state.room.height)
    this.vision = new VisionCache(grid)
    this.actions = new ActionExecutor(this.state, this.log, this.config, this.telegraphs)
    this.registerNewcomers()
  }

  /**
   * 아직 준비되지 않은 엔티티에 가시성 맵과 규칙표를 붙인다.
   *
   * 소환물과 추격자는 방을 세운 뒤에 생기므로 조립 시점의 일괄 배정이 닿지 않는다.
   * 붙이지 않으면 그들만 폴백 정책으로 싸워 아무 압력도 되지 못한다.
   */
  registerNewcomers(): void {
    for (const actor of this.state.listActors()) {
      if (this.vision.read(actor.entityId) === undefined) {
        this.vision.register(actor.entityId, actor.position)
      }
      if (this.policies.has(actor.entityId) || this.policyFactory === null) {
        continue
      }
      const policy = this.policyFactory.buildPolicy(actor)
      if (policy !== undefined) {
        this.policies.set(actor.entityId, policy)
      }
    }
  }

  /**
   * 그 엔티티의 결정기를 돌려준다.
   *
   * @param entityId 대상 엔티티 id.
   * @returns 지정된 결정기, 없으면 기본 결정기.
   */
  getPolicy(entityId: string): DecisionPolicy {
    return this.policies.get(entityId) ?? this.policy
  }

  /**
   * 압력·쿨타임·상태이상·회복·타일 피해를 처리한다 (페이즈 1).
   *
   * 압력을 엔티티 순회보다 **먼저** 건다. 그래야 그 틱에 등장한 추격자가 전투 중
   * 판정(회복 감쇠)에 들어가고, 자신도 같은 틱의 층 보너스를 받는다.
   */
  runUpkeep(): void {
    this.pressure.runUpkeep(this.state, this.log)
    this.registerNewcomers()
    const executor = this.actions
    const inCombat = this.state.listActors().some((e) => e.faction !== FACTION_PLAYER)
    for (const entity of this.state.listActors()) {
      for (const [skill, remaining] of entity.cooldowns) {
        entity.cooldowns.set(skill, Math.max(0, remaining - 1))
      }
      for (const [status, remaining] of entity.statuses) {
        entity.statuses.set(status, Math.max(0, remaining - 1))
      }
      if (this.state.getTile(entity.position.x, entity.position.y) === TILE_LAVA) {
        executor.applyDamage(entity, LAVA_DAMAGE, PHASE_UPKEEP, '용암 위', entity.entityId)
      }
      this.applyRegen(entity, inCombat)
    }
  }

  /**
   * 예고를 1틱 진행하고 만기된 것을 터뜨린다 (페이즈 2).
   *
   * PERCEPTION 보다 앞이어야 한다. 카운트다운이 끝난 남은 틱을 그 틱의 인지 변수가 읽고
   * 규칙표가 회피를 결정한다 — 뒤집으면 항상 1틱 늦게 인지한다.
   */
  runTelegraph(): void {
    for (const telegraph of this.telegraphs.runCountdown(this.state, this.log)) {
      this.applySelfDestruct(telegraph)
    }
    // 셀렉터 CASTING 과 `대상이 시전 중인가` 가 읽는다. 정렬해 내려야 같은 시드가 같은
    // 대상을 고른다 (R5).
    const casters = new Set(this.telegraphs.listActive().map((pending) => pending.casterId))
    this.state.castingIds = [...casters].sort(compareText)
  }

  /**
   * 전 엔티티의 인지 변수를 이 시점에 고정한다 (페이즈 3).
   *
   * 가시성 맵을 먼저 갱신한다. refresh 는 좌표가 그대로면 이전 맵을 그대로 돌려주므로
   * 실제 재계산은 이번 틱에 움직인 엔티티분만 일어난다 (TDD §5.4).
   *
   * @returns entityId 에서 스냅샷으로의 대응표.
   */
  buildPerceptions(): ReadonlyMap<string, PerceptionSnapshot> {
    this.registerNewcomers()
    for (const actor of this.state.listActors()) {
      this.vision.refresh(actor.entityId, actor.position)
    }
    const snapshots = new Map<string, PerceptionSnapshot>()
    for (const entity of this.state.listActors()) {
      snapshots.set(
        entity.entityId,
        buildSnapshot({
          state: this.state,
          entity,
          kindTypes: this.config.kindTypes,
          grid: this.vision.grid,
          board: this.telegraphs,
        }),
      )
    }
    return snapshots
  }

  /**
   * 각 엔티티의 행동을 결정한다 (페이즈 4). 세계를 바꾸지 않는다.
   *
   * @param snapshots PERCEPTION 이 고정한 스냅샷들.
   * @returns 엔티티별 계획.
   * @throws 스냅샷이 없는 엔티티가 섞인 경우. PERCEPTION 을 건너뛴 것이므로 버그다.
   */
  planActions(snapshots: ReadonlyMap<string, PerceptionSnapshot>): readonly PlannedAction[] {
    const plans = this.state.listActors().map((entity) => {
      const snapshot = snapshots.get(entity.entityId)
      if (snapshot === undefined) {
        throw new Error(`인지 스냅샷이 없는 엔티티다: ${entity.entityId}`)
      }
      return this.getPolicy(entity.entityId).planAction(entity, snapshot, this.state)
    })
    // 결정을 매 틱 남긴다. 피해가 난 틱만 기록하면 "왜 그 규칙이 안 떴는지" 를 되짚을
    // 수 없고, 그것이 P1(실패는 정보다)의 실현을 막는다.
    for (const plan of plans) {
      const target = plan.targetId ? ` @${plan.targetId}` : ''
      this.log.record(
        createLogEntry({
          tick: this.state.tick,
          entityId: plan.entityId,
          phase: PHASE_DECIDE,
          expr: plan.expr,
          outcome: `${plan.actionId}${target}`,
          rule: plan.ruleIndex,
          fired: true,
        }),
      )
    }
    return plans
  }

  /**
   * 계획을 실행한다 (페이즈 5). 이동을 먼저, 공격을 나중에 한다.
   *
   * @param plans DECIDE 가 내놓은 계획들.
   */
  applyActions(plans: readonly PlannedAction[]): void {
    const executor = this.actions
    const order = this.sortByInitiative(plans)
    for (const plan of order) {
      const entity = this.getLiveEntity(plan)
      if (entity !== undefined && MOVE_ACTIONS.has(plan.actionId)) {
        executor.applyMove(entity, plan)
      }
    }
    for (const plan of order) {
      const entity = this.getLiveEntity(plan)
      if (entity === undefined) {
        continue
      }
      this.applySettled(executor, entity, plan)
      executor.applyFlag(entity, plan)
    }
  }

  /**
   * 사망 정리와 타일 상태 갱신 (페이즈 6).
   *
   * 여기서 바뀌는 타일은 샘 → 바닥뿐이고 둘 다 시야를 막지 않으므로 가시성 맵을 다시
   * 만들지 않는다. **파괴 가능 벽을 부수는 기능이 붙으면 그렇지 않다** — refresh 는
   * 좌표만 보므로, 그 틱에는 전원 register 를 다시 불러야 한다.
   */
  resolveEffects(): void {
    removeDrainedSprings(this.state, this.log)
    const alive = new Set(this.state.listActors().map((actor) => actor.entityId))
    // 죽은 관측자의 낡은 맵이 남으면 노출 판정에 섞여 원인 추적이 어려워진다.
    const stale = [...this.vision.maps.keys()].filter((entityId) => !alive.has(entityId))
    for (const entityId of stale.sort(compareText)) {
      this.vision.drop(entityId)
    }
  }

  /**
   * 승패를 판정한다 (페이즈 7).
   *
   * @returns OUTCOME_* 중 하나.
   */
  runCleanup(): string {
    const actors = this.state.listActors()
    if (!actors.some((e) => e.faction === FACTION_PLAYER)) {
      return OUTCOME_PLAYER_LOSS
    }
    if (!actors.some((e) => e.faction !== FACTION_PLAYER)) {
      return OUTCOME_PLAYER_WIN
    }
    if (this.state.tick >= this.config.maxTicks) {
      return OUTCOME_TIMEOUT
    }
    return OUTCOME_ONGOING
  }

  /**
   * 7페이즈를 한 바퀴 돈다.
   *
   * @returns 이번 틱 종료 시점의 승패 판정.
   */
  runTick(): string {
    this.state.tick += 1
    this.runUpkeep()
    this.runTelegraph()
    const snapshots = this.buildPerceptions()
    const plans = this.planActions(snapshots)
    this.applyActions(plans)
    this.resolveEffects()
    return this.runCleanup()
  }

  // ── 내부 ──────────────────────────────────────────────────────────────────

  /**
   * 자폭형 예고가 터졌으면 시전자도 함께 죽인다 (GDD §5).
   *
   * 예고판은 (WorldState, EventLog) 만 계약으로 갖고 종류 데이터를 모른다. 그래서 '누가
   * 자폭형인가' 는 여기서 본다.
   *
   * @param telegraph 이번 틱에 발동한 예고.
   */
  private applySelfDestruct(telegraph: Telegraph): void {
    const caster = this.state.entities.get(telegraph.casterId)
    if (caster === undefined || !isAlive(caster)) {
      return
    }
    const setting = this.config.enemyStats.get(caster.kindId)?.telegraph
    if (setting?.self_destruct !== true) {
      return
    }
    this.actions.applyDamage(
      caster,
      caster.hp,
      PHASE_TELEGRAPH,
      `${telegraph.skillId} 자폭`,
      caster.entityId,
    )
  }

  /**
   * 이동이 끝난 뒤 하는 행동을 실행기에 넘긴다.
   *
   * @param executor 행동 실행기.
   * @param entity 행위자.
   * @param plan 실행할 계획.
   */
  private applySettled(
    executor: ActionExecutor,
    entity: Entity,
    plan: PlannedAction,
  ): void {
    if (ATTACK_ACTIONS.has(plan.actionId)) {
      executor.applyAttack(entity, plan)
    } else if (plan.actionId === 'AREA_ATTACK') {
      executor.applyAreaAttack(entity, plan)
    } else if (plan.actionId === 'USE_POTION') {
      executor.applyPotion(entity, plan)
    } else if (plan.actionId === 'HEAL') {
      executor.applyHeal(entity, plan)
    } else if (plan.actionId === 'HOLD' || plan.actionId === 'SET_FLAG') {
      executor.applyHold(entity, plan)
    } else if (plan.actionId === 'SUMMON') {
      // 이동 루프보다 뒤여야 소환 위치가 이번 틱의 이동 결과를 반영한다.
      executor.applySummon(entity, plan)
    }
  }

  /**
   * 계획의 주체가 아직 살아 있으면 돌려준다.
   *
   * @param plan 확인할 계획.
   * @returns 살아 있는 엔티티, 아니면 undefined.
   */
  private getLiveEntity(plan: PlannedAction): Entity | undefined {
    const entity = this.state.entities.get(plan.entityId)
    return entity !== undefined && isAlive(entity) ? entity : undefined
  }

  /**
   * 이동 충돌을 가를 순서를 정한다 (TDD §4.2).
   *
   * entityId 사전순으로 가르면 이름이 앞선 엔티티가 영구히 유리해진다. 그래서
   * 이니셔티브를 먼저 보고, 동률은 시드 PRNG 로 가른다 — 시드가 같으면 같은 순서다.
   *
   * **계획 하나마다 난수를 정확히 하나 뽑는다.** 조건부로 건너뛰면 파이썬과 소비
   * 횟수가 어긋나 그 뒤의 모든 난수가 밀린다.
   *
   * @param plans 정렬할 계획들.
   * @returns 실행 순서대로 정렬된 계획들.
   * @throws 세계에 없는 엔티티의 계획이 섞인 경우.
   */
  private sortByInitiative(plans: readonly PlannedAction[]): readonly PlannedAction[] {
    const keyed = plans.map((plan) => {
      const entity = this.state.entities.get(plan.entityId)
      if (entity === undefined) {
        throw new Error(`세계에 없는 엔티티의 계획이다: ${plan.entityId}`)
      }
      return { initiative: -entity.initiative, tiebreak: this.state.rng.getUint64(), plan }
    })
    return sortByKey(keyed, (item) => [item.initiative, item.tiebreak]).map((item) => item.plan)
  }

  /**
   * 회복을 적용한다. 전투 중에는 감쇠하고 샘은 잔여량을 깎는다 (GDD §7).
   *
   * @param entity 대상.
   * @param inCombat 전투 중인가.
   */
  private applyRegen(entity: Entity, inCombat: boolean): void {
    let tileRegen = 0
    const position = entity.position
    if (this.state.getTile(position.x, position.y) === TILE_SPRING) {
      // 잔여량 항목이 없는 좌표에 0 을 써 넣지 않는다 — 써 넣으면 그 샘이 초기화되기도
      // 전에 RESOLVE 의 소멸 대상이 된다.
      tileRegen = applySpringDrain(this.state, position, SPRING_REGEN_PER_TICK)
    }
    // 전투 중 감쇠는 GDD §7 의 어뷰징 차단이다. 정수 연산이라 regenBase 1 은 전투 중
    // 0 이 된다 — 문서의 0.5 를 내림한 값이며 의도된 결과다.
    const regenPct = inCombat ? this.config.combatRegenPct : FULL_REGEN_PCT
    const base = Math.floor((entity.regenBase * regenPct) / PERCENT_BASE)
    const healed = Math.min(entity.hpMax - entity.hp, base + tileRegen)
    if (healed > 0) {
      entity.hp += healed
    }
  }
}
