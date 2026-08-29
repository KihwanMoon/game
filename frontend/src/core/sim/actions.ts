/**
 * 행동 실행 — `game/app/simulation/actions.py` 의 이식. ACT 페이즈가 계획을 실제 변경으로
 * 옮긴다 (TDD §4.1).
 *
 * **행동 14개를 전부 다룬다.** 처리하지 않는 행동을 조용히 넘기면 규칙이 발동했는데 아무
 * 일도 일어나지 않고, 플레이어는 자기 논리가 틀렸다고 오해한다 — 그것이 P1(실패는
 * 정보다)을 가장 직접적으로 깨뜨리는 방식이다. 아직 만들 수 없는 행동은 그 사실을 로그에
 * 남긴다.
 */

import { EventLog, createLogEntry } from '../eventLog'
import { calculateDamage } from '../combat/damage'
import {
  type Position,
  formatPosition,
  formatPositionKey,
  getManhattanDistance,
  iterNeighbors,
} from '../grid/geometry'
import { VisionGrid, checkLineOfSight, findCoverPositions } from '../grid/vision'
import { buildDistanceField, findNextStep } from '../pathfinding/distanceField'
import { TILE_DOOR, TILE_SPRING, TILE_STAIRS, WALKABLE_TILES } from '../schemas'
import { registerBlast, resolveHeal, resolvePotion, resolveSummon } from './abilities'
import { PHASE_ACT } from './phases'
import type { EngineConfig, PlannedAction, RawTelegraphSetting } from './plan'
import { type Entity, type WorldState, isAlive } from './state'
import { TelegraphBoard } from './telegraph'

/** 이동 계열 행동. ACT 는 이 다섯을 먼저 처리한다. */
export const MOVE_ACTIONS: ReadonlySet<string> = new Set([
  'APPROACH',
  'RETREAT',
  'MOVE_TO_EXIT',
  'MOVE_TO_HEAL',
  'MOVE_TO_COVER',
])

/** 단일 대상 공격 계열 행동. */
export const ATTACK_ACTIONS: ReadonlySet<string> = new Set(['ATTACK', 'SKILL_1', 'SKILL_2'])

/** 예고를 쓰지 않는 즉발 광역기의 반경. 예고형의 반경은 balance.json 이 정한다. */
export const AREA_ATTACK_RADIUS = 2

/** 이 사거리까지는 시야를 묻지 않는다. 인접한 적은 벽 너머에 있을 수 없다. */
export const MELEE_REACH = 1

/** 포위 가산을 세는 인접 거리. */
const ADJACENT_DISTANCE = 1

/** 기본 스킬 계수. balance.json 에 없는 행동은 1.0배로 친다. */
const DEFAULT_SKILL_COEF_PCT = 100

/**
 * 아직 만들 수 없는 행동과 그 사유. 조용히 무시하지 않고 로그로 알린다.
 *
 * **W6 통합으로 비었다.** MOVE_TO_COVER 는 vision 이, SUMMON 은 abilities 가 받았다.
 * 목록과 `recordDeferred` 를 남겨 두는 것은 다음에 같은 상황이 올 때 — 규칙표가 부를
 * 수는 있으나 아직 실행할 수 없는 행동이 생길 때 — 그것을 조용히 무시하지 않기 위해서다.
 */
export const DEFERRED_ACTIONS: ReadonlyMap<string, string> = new Map()

/** 계획을 실행하고 결과를 로그에 남긴다. */
export class ActionExecutor {
  /**
   * 실행기를 만든다.
   *
   * @param state 세계 상태.
   * @param log 이벤트 로그.
   * @param config 엔진 설정.
   * @param telegraphs 예고를 등록할 판. 없으면 예고형 광역기가 즉발로 떨어진다
   *   (단독 테스트용).
   */
  constructor(
    readonly state: WorldState,
    readonly log: EventLog,
    readonly config: EngineConfig,
    readonly telegraphs: TelegraphBoard = new TelegraphBoard(),
  ) {}

  /**
   * 아직 실행할 수 없는 행동이라는 사실을 로그에 남긴다.
   *
   * @param entity 행위자.
   * @param plan 실행하려던 계획.
   */
  recordDeferred(entity: Entity, plan: PlannedAction): void {
    const reason = DEFERRED_ACTIONS.get(plan.actionId) ?? '사유 미상'
    this.recordResult(entity.entityId, plan, `미구현 — ${reason}`, null)
  }

  /**
   * 이동 계열 행동을 실행한다.
   *
   * @param entity 이동할 엔티티.
   * @param plan 실행할 계획.
   */
  applyMove(entity: Entity, plan: PlannedAction): void {
    if (DEFERRED_ACTIONS.has(plan.actionId)) {
      this.recordDeferred(entity, plan)
      return
    }
    if (plan.actionId === 'MOVE_TO_EXIT') {
      this.applyStep(entity, this.findTiles(new Set([TILE_DOOR, TILE_STAIRS])), plan)
      return
    }
    if (plan.actionId === 'MOVE_TO_HEAL') {
      this.applyStep(entity, this.findTiles(new Set([TILE_SPRING])), plan)
      return
    }
    if (plan.actionId === 'MOVE_TO_COVER') {
      this.applyCoverMove(entity, plan)
      return
    }

    const target = this.state.entities.get(plan.targetId ?? '')
    if (target === undefined || !isAlive(target)) {
      this.recordResult(entity.entityId, plan, '대상 없음 — 틱 낭비', null)
      return
    }
    if (plan.actionId === 'APPROACH') {
      this.applyStep(entity, [target.position], plan)
      return
    }
    const occupied = this.listOccupied(entity)
    const here = getManhattanDistance(entity.position, target.position)
    const away = iterNeighbors(entity.position).filter(
      (pos) =>
        WALKABLE_TILES.has(this.state.getTile(pos.x, pos.y)) &&
        !occupied.has(formatPositionKey(pos)) &&
        getManhattanDistance(pos, target.position) > here,
    )
    this.applyStep(entity, away, plan)
  }

  /**
   * 단일 대상 공격을 실행한다.
   *
   * @param entity 공격자.
   * @param plan 실행할 계획.
   */
  applyAttack(entity: Entity, plan: PlannedAction): void {
    const target = this.state.entities.get(plan.targetId ?? '')
    if (target === undefined || !isAlive(target)) {
      this.recordResult(entity.entityId, plan, '대상 없음 — 틱 낭비', null)
      return
    }
    // 파이썬은 `skill_range.get(id) or entity.attack_range` 다. null 뿐 아니라 0 도
    // 엔티티 사거리로 넘어가므로 `??` 로 바꾸면 사거리 0 스킬의 동작이 달라진다.
    const declared = this.config.skillRange.get(plan.actionId)
    const reach = declared === undefined || declared === null || declared === 0
      ? entity.attackRange
      : declared
    const distance = getManhattanDistance(entity.position, target.position)
    if (distance > reach) {
      this.recordResult(entity.entityId, plan, `사거리 밖(${distance} > ${reach}) — 틱 낭비`, null)
      return
    }
    // GDD §4.1 — 원거리 공격은 직선 시야가 통할 때만 닿는다. 이것이 없으면 엄폐가
    // 아무것도 막지 못해 MOVE_TO_COVER 가 순손실이 된다.
    if (
      reach > MELEE_REACH &&
      !checkLineOfSight(this.buildGrid(), entity.position, target.position)
    ) {
      this.recordResult(entity.entityId, plan, '시야 없음 — 틱 낭비', null)
      return
    }
    this.applyStrike(entity, target, plan)
    this.applyCooldown(entity, plan.actionId)
  }

  /**
   * 반경 안의 적 전체를 친다.
   *
   * @param entity 공격자.
   * @param plan 실행할 계획.
   */
  applyAreaAttack(entity: Entity, plan: PlannedAction): void {
    const telegraph = this.config.enemyStats.get(entity.kindId)?.telegraph
    if (telegraph !== undefined) {
      this.registerTelegraph(entity, plan, telegraph)
      return
    }
    const victims = this.state
      .listHostiles(entity)
      .filter(
        (other) => getManhattanDistance(entity.position, other.position) <= AREA_ATTACK_RADIUS,
      )
    if (victims.length === 0) {
      this.recordResult(entity.entityId, plan, '반경 안에 적 없음 — 틱 낭비', null)
      return
    }
    for (const victim of victims) {
      this.applyStrike(entity, victim, plan)
    }
    this.applyCooldown(entity, plan.actionId)
  }

  /**
   * 잡몹을 부른다 (GDD §5). 주기는 쿨타임[SUMMON] 이 맡는다.
   *
   * @param entity 소환사.
   * @param plan 실행할 계획.
   */
  applySummon(entity: Entity, plan: PlannedAction): void {
    const { outcome } = resolveSummon(this.state, this.config, entity)
    this.recordResult(entity.entityId, plan, outcome, null)
  }

  /**
   * 포션을 쓴다.
   *
   * @param entity 사용자.
   * @param plan 실행할 계획.
   */
  applyPotion(entity: Entity, plan: PlannedAction): void {
    const { healed, outcome } = resolvePotion(entity)
    this.recordResult(entity.entityId, plan, outcome, healed)
  }

  /**
   * 아군 하나를 회복한다 (GDD §5). 대상은 셀렉터가 이미 골랐다.
   *
   * @param entity 시전자.
   * @param plan 실행할 계획.
   */
  applyHeal(entity: Entity, plan: PlannedAction): void {
    const { healed, outcome } = resolveHeal(this.state, this.config, entity, plan)
    if (healed > 0) {
      this.applyCooldown(entity, plan.actionId)
    }
    this.recordResult(entity.entityId, plan, outcome, healed === 0 ? null : healed)
  }

  /**
   * 의도적으로 아무것도 하지 않는다. 무시와 구분하기 위해 로그는 남긴다.
   *
   * @param entity 대상.
   * @param plan 실행할 계획.
   */
  applyHold(entity: Entity, plan: PlannedAction): void {
    this.recordResult(entity.entityId, plan, '대기', null)
  }

  /**
   * 규칙이 지정한 플래그를 세우거나 내린다 (GDD §3.5).
   *
   * @param entity 대상 엔티티.
   * @param plan 실행 중인 계획.
   */
  applyFlag(entity: Entity, plan: PlannedAction): void {
    if (plan.setFlag === null) {
      return
    }
    const separator = plan.setFlag.indexOf('=')
    const name = separator < 0 ? plan.setFlag : plan.setFlag.slice(0, separator)
    const raw = separator < 0 ? '' : plan.setFlag.slice(separator + 1)
    entity.flags.set(name.trim(), raw.trim().toLowerCase() !== 'false')
  }

  /**
   * 피해를 입히고 로그를 남긴다.
   *
   * @param target 피격자.
   * @param amount 피해량.
   * @param phase 발생한 페이즈.
   * @param expr 로그에 남길 문자열.
   * @param actorId 피해를 일으킨 주체. 지형 피해면 피격자 자신이다.
   * @param rule 이 피해를 일으킨 규칙의 우선순위. 지형 피해처럼 규칙이 없으면 null.
   *   이것을 빠뜨리면 규칙이 죽인 적이 DEFAULT 의 공으로 집계되어, 사후 분석이 "어느
   *   규칙이 통했는가" 를 거짓으로 말한다 (P1).
   */
  applyDamage(
    target: Entity,
    amount: number,
    phase: string,
    expr: string,
    actorId: string,
    rule: number | null = null,
  ): void {
    target.hp = Math.max(0, target.hp - amount)
    const suffix = isAlive(target) ? '' : ' 사망'
    this.log.record(
      createLogEntry({
        tick: this.state.tick,
        entityId: actorId,
        phase,
        expr,
        outcome: `${target.entityId} HP ${target.hp}/${target.hpMax}${suffix}`,
        delta: -amount,
        fired: true,
        targetId: target.entityId,
        rule,
      }),
    )
  }

  // ── 내부 ──────────────────────────────────────────────────────────────────

  /**
   * 실행 결과를 남긴다.
   *
   * @param actorId 행위자 id.
   * @param plan 실행한 계획.
   * @param outcome 결과 설명.
   * @param delta 수치 변화. 없으면 null.
   */
  private recordResult(
    actorId: string,
    plan: PlannedAction,
    outcome: string,
    delta: number | null,
  ): void {
    const target = plan.targetId ? ` @${plan.targetId}` : ''
    this.log.record(
      createLogEntry({
        tick: this.state.tick,
        entityId: actorId,
        phase: PHASE_ACT,
        expr: `${plan.actionId}${target}`,
        outcome,
        rule: plan.ruleIndex,
        delta,
        fired: true,
      }),
    )
  }

  /**
   * 자기 자신을 뺀 다른 엔티티들이 서 있는 칸.
   *
   * @param entity 기준 엔티티.
   * @returns 점유된 좌표의 열쇠 집합.
   */
  private listOccupied(entity: Entity): ReadonlySet<string> {
    return new Set(
      this.state
        .listActors()
        .filter((other) => other !== entity)
        .map((other) => formatPositionKey(other.position)),
    )
  }

  /**
   * 시야 판정용 격자를 만든다.
   *
   * WorldState 를 감싸는 이유는 파괴된 벽(tileOverrides)을 반영하기 위해서다.
   * RoomTemplate 을 넘기면 부수기 전 지형으로 판정한다.
   *
   * @returns 이번 순간의 지형을 읽는 격자.
   */
  private buildGrid(): VisionGrid {
    return new VisionGrid(this.state, this.state.room.width, this.state.room.height)
  }

  /**
   * 성공한 행동에 쿨타임을 건다.
   *
   * 실패한 틱(사거리 밖·대상 없음)에는 걸지 않는다. 헛친 것까지 세면 규칙표를 고쳐도
   * 발동 간격이 그대로여서 원인을 특정할 수 없다 (P1).
   *
   * @param entity 행위자.
   * @param actionId 사용한 행동 id.
   */
  private applyCooldown(entity: Entity, actionId: string): void {
    const ticks = this.config.skillCooldowns.get(actionId) ?? 0
    if (ticks > 0) {
      entity.cooldowns.set(actionId, ticks)
    }
  }

  /**
   * 방에서 해당 종류의 타일 좌표를 모은다.
   *
   * @param kinds 찾을 타일 ID 집합.
   * @returns 행 우선 순서의 좌표들. 없으면 빈 배열.
   */
  private findTiles(kinds: ReadonlySet<number>): readonly Position[] {
    const found: Position[] = []
    for (let y = 0; y < this.state.room.height; y += 1) {
      for (let x = 0; x < this.state.room.width; x += 1) {
        if (kinds.has(this.state.getTile(x, y))) {
          found.push({ x, y })
        }
      }
    }
    return found
  }

  /**
   * 목표들 쪽으로 한 칸 간다. 막히면 제자리이며 그 틱은 낭비된다 (TDD §4.2).
   *
   * @param entity 이동할 엔티티.
   * @param goals 목표 좌표들.
   * @param plan 실행 중인 계획.
   */
  private applyStep(entity: Entity, goals: readonly Position[], plan: PlannedAction): void {
    if (goals.length === 0) {
      this.recordResult(entity.entityId, plan, '목표 없음 — 틱 낭비', null)
      return
    }
    const occupied = this.listOccupied(entity)
    const field = buildDistanceField(this.state, goals, occupied)
    const step = findNextStep(field, entity.position)
    if (step === undefined) {
      this.recordResult(entity.entityId, plan, '길 막힘 — 틱 낭비', null)
      return
    }
    if (occupied.has(formatPositionKey(step))) {
      // 거리장은 목표 칸을 점유 여부와 무관하게 0 으로 깐다(APPROACH 의 목표가 곧 적이
      // 선 칸이므로 그래야 길이 이어진다). 그 마지막 한 걸음까지 허용하면 두 개체가 한
      // 칸에 겹쳐 적거리 0 이 나오고 RETREAT 이 영영 막힌다.
      this.recordResult(
        entity.entityId,
        plan,
        `다음 칸 점유 ${formatPosition(step)} — 제자리`,
        null,
      )
      return
    }
    entity.position = step
    this.recordResult(entity.entityId, plan, `이동 ${formatPosition(step)}`, null)
  }

  /**
   * 모든 적의 시야에서 벗어나는 칸으로 한 칸 간다 (GDD §4.4).
   *
   * 목표는 벽 자체가 아니라 **그 뒤에 서면 시야가 끊기는 칸**이다. 벽으로 가면 등을
   * 붙인 채 그대로 노출된다.
   *
   * @param entity 이동할 엔티티.
   * @param plan 실행 중인 계획.
   */
  private applyCoverMove(entity: Entity, plan: PlannedAction): void {
    // listHostiles 는 listActors 순서라 이미 결정론적이다. 집합으로 만들지 않는다 (R5).
    const threats = this.state.listHostiles(entity).map((other) => other.position)
    const goals = findCoverPositions(this.buildGrid(), threats, this.listOccupied(entity))
    const here = formatPositionKey(entity.position)
    if (goals.some((goal) => formatPositionKey(goal) === here)) {
      // 목표 거리가 0 이면 findNextStep 이 undefined 를 돌려줘 "길 막힘" 으로 찍힌다.
      // 이미 숨어 있는 것과 갈 수 없는 것은 다른 사실이다 (P1).
      this.recordResult(entity.entityId, plan, '이미 엄폐 중', null)
      return
    }
    this.applyStep(entity, goals, plan)
  }

  /**
   * 즉발 대신 예고를 건다 (GDD §4.2).
   *
   * @param entity 시전자.
   * @param plan 실행 중인 계획.
   * @param telegraph balance.json 의 그 종류 telegraph 절.
   */
  private registerTelegraph(
    entity: Entity,
    plan: PlannedAction,
    telegraph: RawTelegraphSetting,
  ): void {
    const outcome = registerBlast(this.state, this.telegraphs, entity, telegraph)
    this.applyCooldown(entity, plan.actionId)
    this.recordResult(entity.entityId, plan, outcome, null)
  }

  /**
   * 한 대상에게 피해를 계산해 넣는다.
   *
   * @param entity 공격자.
   * @param target 피격자.
   * @param plan 실행 중인 계획.
   */
  private applyStrike(entity: Entity, target: Entity, plan: PlannedAction): void {
    const adjacent = this.state
      .listHostiles(target)
      .filter(
        (other) => getManhattanDistance(other.position, target.position) <= ADJACENT_DISTANCE,
      ).length
    const amount = calculateDamage({
      attack: entity.attack,
      skillCoefPct: this.config.skillCoefPct.get(plan.actionId) ?? DEFAULT_SKILL_COEF_PCT,
      defense: target.defense,
      floor: this.config.floor,
      adjacentEnemies: adjacent,
      rules: this.config.damageRules,
    })
    this.applyDamage(
      target,
      amount,
      PHASE_ACT,
      `${plan.actionId} @${target.entityId}`,
      entity.entityId,
      plan.ruleIndex,
    )
  }
}
