/**
 * 행동 실행 — `game/app/simulation/actions.py` 의 이식. ACT 페이즈가 계획을 실제 변경으로
 * 옮긴다 (TDD §4.1).
 *
 * **행동 14개를 전부 다룬다.** 처리하지 않는 행동을 조용히 넘기면 규칙이 발동했는데 아무
 * 일도 일어나지 않고, 플레이어는 자기 논리가 틀렸다고 오해한다 — 그것이 P1(실패는
 * 정보다)을 가장 직접적으로 깨뜨리는 방식이다. 아직 만들 수 없는 행동은 그 사실을 로그에
 * 남긴다.
 */

import { CANCEL_BY_HIT, MIN_LEAD_TICKS } from './telegraph'
import { findSkill } from '../skills/catalog'
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
import {
  GUARD_STATUS,
  ITEM_POTION,
  ITEM_SCROLL,
  registerBlast,
  resolveHeal,
  resolvePotion,
  resolveScroll,
  resolveSummon,
} from './abilities'
import { PHASE_ACT } from './phases'
import {
  GUARD_SKILL_ID,
  MELEE_REACH,
  SLOW_EVERY,
  STATUS_SLOW,
} from './plan'
import type { EngineConfig, PlannedAction, RawTelegraphSetting } from './plan'
import { divideFloor } from '../combat/damage'
import { PERCENT_BASE, type Entity, type WorldState, isAlive } from './state'
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

/** 예고를 쓰지 않는 즉발 광역기의 반경. 예고형의 반경은 balance.json 이 정한다. */

/** 이 사거리까지는 시야를 묻지 않는다. 인접한 적은 벽 너머에 있을 수 없다. */

/** 포위 가산을 세는 인접 거리. */
const ADJACENT_DISTANCE = 1

/** 기본 스킬 계수. balance.json 에 없는 행동은 1.0배로 친다. */

/**
 * 아직 만들 수 없는 행동과 그 사유. 조용히 무시하지 않고 로그로 알린다.
 *
 * **W6 통합으로 비었다.** MOVE_TO_COVER 는 vision 이, SUMMON 은 abilities 가 받았다.
 * 목록과 `recordDeferred` 를 남겨 두는 것은 다음에 같은 상황이 올 때 — 규칙표가 부를
 * 수는 있으나 아직 실행할 수 없는 행동이 생길 때 — 그것을 조용히 무시하지 않기 위해서다.
 */
export const DEFERRED_ACTIONS: ReadonlyMap<string, string> = new Map()

/** 계획을 실행하고 결과를 로그에 남긴다. */
/**
 * 둔화 때문에 이번 틱에 못 움직이는가 — 파이썬 `check_slowed_this_tick` 과 같다.
 *
 * **둔화는 두 틱에 한 칸이다** (GDD §211 의 「이동 2틱 소모」). 없으면 `SLOW` 는 인지
 * 변수에만 있고 걸어도 아무 일이 없다. 틱의 홀짝으로 가르는 이유는 걸린 시점을 따로
 * 들면 그것이 세계 상태가 되어 두 코어가 함께 얼려야 하기 때문이다 (R5).
 *
 * @param entity 움직이려는 엔티티.
 * @param tick 지금 틱.
 * @returns 못 움직이면 true.
 */
export function checkSlowedThisTick(entity: Entity, tick: number): boolean {
  return (entity.statuses.get(STATUS_SLOW) ?? 0) > 0 && tick % SLOW_EVERY !== 0
}

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
  /**
   * 둔화로 이번 틱을 쉬는가 — 쉬면 적고 true 를 돌려준다.
   *
   * **이동만이 아니라 행동 전체다** (2026-09-10 결정). 예전에는 이동 경로에서만 봤고,
   * 그래서 `SLOW` 는 **안 움직여도 때리는 사격형에게 아무 효과가 없었다** — 이미 붙은
   * 돌진형에게도 없었다.
   *
   * **시전은 안 끊긴다.** 쉬는 틱은 아무 행동도 안 한 틱이고, 예고를 끊는 것은
   * 「다른 행동을 했다」는 사실이다.
   *
   * @param entity 행위자.
   * @param plan 이번 틱의 계획. 로그에 무엇을 하려 했는지 남긴다.
   * @returns 쉬면 true. 그때 부르는 쪽은 그 계획을 실행하지 않는다.
   */
  recordRest(entity: Entity, plan: PlannedAction): boolean {
    if (!checkSlowedThisTick(entity, this.state.tick)) {
      return false
    }
    this.recordResult(entity.entityId, plan, '둔화 — 이번 틱은 쉰다', null)
    return true
  }

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
    const declared = findSkill(this.config.skills, plan.actionId).reach
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
  /**
   * 스킬이 예고를 정하면 그것을 걸고 true 를 돌려준다 — 파이썬 `apply_cast` 와 같다.
   *
   * **디스패치를 데이터로 가르는 자리다.** 실행기는 `actionId` 로 갈리므로 새 스킬 id 는
   * 어느 갈래에도 안 닿는다 — 예고는 그 행동의 성질이지 이름의 성질이 아니다.
   *
   * **피해를 시전 시점에 얼린다.** 예고 피해는 방어 감쇠를 안 거치는 고정값이라,
   * 발동 때 다시 계산하면 그 사이의 버프가 회피 판정에 섞인다.
   *
   * @param entity 시전자.
   * @param plan 실행할 계획.
   * @returns 예고를 걸었으면 true. 이 스킬이 예고를 안 쓰면 false.
   */
  applyCast(entity: Entity, plan: PlannedAction): boolean {
    const skill = findSkill(this.config.skills, plan.actionId)
    if (skill.telegraph <= 0) {
      return false
    }
    const target = this.state.entities.get(plan.targetId ?? '')
    // **유물이 제약을 바꾼다** (설계/5_스킬 §10.7). 스킬을 열어 주지 않는 이유는 그러면
    // 그 스킬이 유물 드롭률 뒤에 갇히기 때문이고, 더 센 것을 주지 않는 이유는 그러면
    // 규칙표가 안 바뀌기 때문이다 — 바뀌는 것은 **대가**다.
    const lead = Math.max(MIN_LEAD_TICKS, skill.telegraph - entity.castLeadCut)
    this.registerTelegraph(entity, plan, {
      skill: plan.actionId,
      shape: skill.shape.kind,
      radius: skill.shape.radius + entity.blastRadius,
      length: skill.shape.length,
      // `LINE` 은 방향이 필요하다. 대상이 없으면 같은 칸을 가리켜 칸이 0 개가 되고,
      // 그때는 예고가 빈 칸으로 서서 아무도 안 맞는다 — 그 사실은 로그에 남는다.
      toward: target?.position ?? entity.position,
      effects: skill.effects,
      damage: divideFloor(entity.attack * skill.coefPct, PERCENT_BASE),
      lead_ticks: lead,
      visible_ticks: lead,
      cancel_on_death: true,
      // 흔들림 없는 시전은 **행동 취소만** 끈다. 피격 취소는 그대로다 — 둘 다 끄면
      // 「안전한 자리에서 쏘는가」가 사라져 상위 호환이 된다 (§10.7).
      cancel_on_act: skill.cancelOnAct && entity.steadyCast <= 0,
      cancel_on_hit: skill.cancelOnHit,
    })
    return true
  }

  applyAreaAttack(entity: Entity, plan: PlannedAction): void {
    const telegraph = this.config.enemyStats.get(entity.kindId)?.telegraph
    if (telegraph !== undefined) {
      this.registerTelegraph(entity, plan, telegraph)
      return
    }
    // **반경의 정본은 데이터다** (파이썬 `shape.radius` 와 같다). 상수였을 때는 JSON 을
    // 고쳐도 브라우저가 안 달라져 두 코어가 조용히 갈릴 수 있었다.
    const radius = findSkill(this.config.skills, plan.actionId).shape.radius
    const victims = this.state
      .listHostiles(entity)
      .filter(
        (other) => getManhattanDistance(entity.position, other.position) <= radius,
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
   * 소모품을 쓴다 (v6, #54).
   *
   * **종류로 갈린다.** `USE_POTION` 은 `USE_ITEM[POTION]` 의 별칭이므로 태그가 없으면
   * 포션으로 본다 — 저장된 규칙표와 골든이 그 id 를 쓰기 때문이다.
   *
   * **모르는 종류는 아무것도 안 쓴다.** 예전에는 포션으로 떨어졌는데, 규칙이 가리킨 것은
   * 그 태그이고 실제로 빠지는 것은 포션이라 엉뚱한 소모품이 사라졌다.
   *
   * @param entity 사용자.
   * @param plan 실행할 계획.
   */
  applyItem(entity: Entity, plan: PlannedAction): void {
    const kind = plan.itemKind ?? ITEM_POTION
    if (kind === ITEM_SCROLL) {
      const ticks = findSkill(this.config.skills, GUARD_SKILL_ID).guardTicks
      const held = resolveScroll(entity, ticks)
      this.recordResult(entity.entityId, plan, held.outcome, held.healed)
      return
    }
    if (kind !== ITEM_POTION) {
      this.recordResult(entity.entityId, plan, `${kind} 쓸 줄 모른다 — 틱 낭비`, null)
      return
    }
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
   * 방어 태세를 세운다 (블록 v5, 결정 #16). 파이썬 `apply_guard` 의 이식이다.
   *
   * **이 갈래가 통째로 없었다 (2026-09-09).** `USE_SKILL[GUARD_BRACE]` 가 파이썬에서는
   * 태세를 세우는데 브라우저에서는 `applySettled` 의 어느 갈래에도 안 걸려 그냥 끝났다 —
   * 방패를 든 규칙표가 두 코어에서 다르게 돌았고, 골든이 이 스킬을 하나도 안 덮어
   * 게이트 G3 가 침묵했다. 주문서 경로(`resolveScroll`)만 같은 상태를 세우고 있었다.
   *
   * 상태에 남은 틱으로 들어가고 UPKEEP 이 줄인다. 피해 감소는 `applyDamage` 가 본다.
   *
   * @param entity 시전자.
   * @param plan 실행할 계획.
   */
  applyGuard(entity: Entity, plan: PlannedAction, skillId = ''): void {
    // **이 틱을 안 쓴다** (2026-09-10 결정). 엔진이 행동 고리보다 앞에서 부르고, 그 뒤
    // 개체는 제 할 일을 그대로 한다 — 켜는 데 한 틱을 내던 것이 방벽이 어느 구간에서도
    // 값을 못 하던 이유였다 (설계/5_스킬 §2.1).
    //
    // `skillId` 를 따로 받는 이유: 자리를 안 먹는 호출은 계획의 행동이 다른 것이다.
    const used = skillId === '' ? plan.actionId : skillId
    const ticks = findSkill(this.config.skills, used).guardTicks
    entity.statuses.set(GUARD_STATUS, ticks)
    const percent = findSkill(this.config.skills, used).guardPct
    this.recordResult(
      entity.entityId,
      plan,
      `${used} 방어 ${String(percent)}% / ${String(ticks)}틱`,
      null,
    )
    this.applyCooldown(entity, used)
  }

  /**
   * 부를 줄 모르는 스킬을 로그에 남긴다. 파이썬 `record_missing_executor` 와 같다.
   *
   * **조용히 사라지는 것이 제일 나쁜 실패다.** `USE_SKILL[X]` 가 어느 갈래에도 안 걸리면
   * 오류도 로그도 안 남는다 — 스킬을 데이터로 더해도 아무 일이 안 일어나는데 아무도
   * 모른다. `skillId` 로 가리는 이유는 이 경로가 이동 계획에도 불리기 때문이다.
   *
   * @param entity 행위자.
   * @param plan 실행할 수 없던 계획.
   */
  recordMissingExecutor(entity: Entity, plan: PlannedAction): void {
    this.recordResult(entity.entityId, plan, '쓸 줄 모른다 — 실행기가 없다', null)
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
    // 방어 태세는 여기서 본다. 정수 나눗셈이며 내림이다 (R5) — 부동소수를 쓰면
    // 두 코어가 같은 피해에서 갈린다.
    let dealt = amount
    if ((target.statuses.get(GUARD_STATUS) ?? 0) > 0) {
      const reduction = findSkill(this.config.skills, GUARD_SKILL_ID).guardPct
      dealt = divideFloor(dealt * (PERCENT_BASE - reduction), PERCENT_BASE)
    }
    target.hp = Math.max(0, target.hp - dealt)
    // **맞으면 시전이 끊긴다** — 켜 둔 예고만. 0 이 아니라 실제로 깎였을 때만 본다:
    // 방어 태세가 전부 막아 낸 피해로 끊기면 방어가 벌이 된다 (파이썬과 같은 규칙).
    if (dealt > 0) {
      this.telegraphs.applyCancel(this.state, this.log, target.entityId, CANCEL_BY_HIT)
    }
    const suffix = isAlive(target) ? '' : ' 사망'
    this.log.record(
      createLogEntry({
        tick: this.state.tick,
        entityId: actorId,
        phase,
        expr,
        outcome: `${target.entityId} HP ${target.hp}/${target.hpMax}${suffix}`,
        delta: -dealt,
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
    const skill = findSkill(this.config.skills, actionId)
    // **예고를 쓰는 스킬에만 유물의 대가가 붙는다** (설계/5_스킬 §10.7). 반경을 넓히는
    // 유물이 평타 간격까지 늘리면 마법의 대가가 아니라 캐릭터의 벌이 되고, 쿨타임 0 인
    // 행동에 8 이 붙으면 평타가 8틱에 한 번이 된다.
    const ticks = skill.cooldown + (skill.telegraph > 0 ? entity.castCooldownAdd : 0)
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
      // 스킬 계수(스킬이 정한다)와 스킬위력(개체가 정한다)은 다른 것이다. 곱해서
      // 넘기는 이유는 수식이 계수 하나만 받기 때문이며, 정수 곱 뒤 내림 나눗셈이라
      // 기본값 100 에서는 결과가 한 톨도 바뀌지 않는다 (결정 #51).
      skillCoefPct: Math.floor(
        (findSkill(this.config.skills, plan.actionId).coefPct *
          entity.skillPowerPct) /
          PERCENT_BASE,
      ),
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
