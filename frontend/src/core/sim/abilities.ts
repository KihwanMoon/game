/**
 * 데이터가 정하는 능력 — `game/app/simulation/abilities.py` 의 이식 (GDD §4.2·§5).
 *
 * 규칙표는 `SUMMON` · `AREA_ATTACK` · `HEAL` 을 부를 뿐이고, 무엇을 몇 마리까지
 * 부르는지·예고를 몇 틱 앞세우는지·얼마나 회복하는지는 balance.json 이 정한다. 그 둘을
 * 잇는 자리다. 여기 있는 것은 결과와 로그 문자열만 돌려주고 기록은 실행기가 한다.
 *
 * 소환 위치는 인접 4칸을 고정 순서로 훑어 첫 빈 칸을 쓴다. 난수를 쓰지 않는 이유는 R5 다
 * — 같은 시드가 같은 자리를 내야 리플레이가 성립한다.
 *
 * 회복(v4)은 사거리를 공격과 같은 규칙으로 잰다 — 스킬 자체 사거리가 없으면 시전자의
 * attackRange 다. **직선 시야는 묻지 않는다.** 대상별 시야를 묻는 인지 변수가 DSL 에 없어
 * 요구하면 조건이 참인데 영영 실패하는 규칙을 플레이어가 고칠 방법이 없어진다 (P1).
 */

import {
  type Position,
  formatPosition,
  formatPositionKey,
  getManhattanDistance,
  iterSteps,
} from '../grid/geometry'
import { WALKABLE_TILES } from '../schemas'
import { divideFloor } from '../combat/damage'
import type { EngineConfig, PlannedAction, RawEnemyKind, RawTelegraphSetting } from './plan'
import { getScaledEnemyStats } from './scaling'
import { type Entity, type WorldState, createEntity, isAlive } from './state'
import { type TelegraphBoard, buildBlastTiles } from './telegraph'

/** 소환 쿨타임을 다는 키. 인지 변수 self_cooldown_ready[SUMMON] 가 이것을 읽는다. */
export const SUMMON_ACTION = 'SUMMON'

/** 회복 쿨타임을 다는 키. 인지 변수 self_cooldown_ready[HEAL] 가 이것을 읽는다. */
export const HEAL_ACTION = 'HEAL'

/** 정수 퍼센트의 분모. 부동소수를 쓰지 않으므로 비율은 전부 이 값으로 나눈다 (R5). */
const PERCENT_BASE = 100

/** 포션이 채우는 몫. 최대 HP 의 절반이다. */
const POTION_HEAL_DIVISOR = 2

/** 회복 한 번의 결과. 파이썬의 `(int, str)` 튜플에 대응한다. */
export interface HealResult {
  readonly healed: number
  readonly outcome: string
}

/** 포션 한 번의 결과. 회복량이 null 이면 포션이 없어 아무 일도 없었다는 뜻이다. */
export interface PotionResult {
  readonly healed: number | null
  readonly outcome: string
}

/** 소환 시도 한 번의 결과. 파이썬의 `(Entity | None, str)` 튜플에 대응한다. */
export interface SummonResult {
  readonly minion: Entity | undefined
  readonly outcome: string
}

/**
 * 그 소환사가 부른 개체 중 살아 있는 수 (GDD §7 무한 증식 차단).
 *
 * @param state 세계 상태.
 * @param summonerId 소환사 엔티티 id.
 * @returns 살아 있는 소환물 수.
 */
export function countAliveMinions(state: WorldState, summonerId: string): number {
  return state.listActors().filter((other) => other.summonerId === summonerId).length
}

/**
 * 소환사 옆의 첫 빈 칸을 찾는다.
 *
 * @param state 세계 상태.
 * @param summoner 부른 쪽.
 * @returns 놓을 좌표. 인접 4칸이 모두 막혔으면 undefined.
 */
export function findSummonPosition(state: WorldState, summoner: Entity): Position | undefined {
  const occupied = new Set(state.listActors().map((other) => formatPositionKey(other.position)))
  for (const position of iterSteps(summoner.position)) {
    if (
      WALKABLE_TILES.has(state.getTile(position.x, position.y)) &&
      !occupied.has(formatPositionKey(position))
    ) {
      return position
    }
  }
  return undefined
}

/**
 * 소환물을 만들어 세계에 넣는다.
 *
 * @param state 세계 상태.
 * @param summoner 부른 쪽. 진영과 소환 상한 계산의 기준이 된다.
 * @param config 엔진 설정. 층 스케일을 여기서 읽는다.
 * @param kindId 불러낼 종류 id.
 * @param stats balance.json 의 그 종류 항목.
 * @param position 놓을 좌표.
 * @returns 등장한 개체.
 */
export function createMinion(
  state: WorldState,
  config: EngineConfig,
  summoner: Entity,
  kindId: string,
  stats: RawEnemyKind,
  position: Position,
): Entity {
  const scaled = getScaledEnemyStats(stats, config.floorScale, config.floor)
  // 일련번호는 단조 증가여야 같은 시드가 같은 id 를 만든다 (R5).
  state.spawnCounter += 1
  const minion = createEntity({
    entityId: `${kindId}_s${state.spawnCounter}`,
    kindId,
    faction: summoner.faction,
    position,
    hp: scaled.hpMax,
    hpMax: scaled.hpMax,
    attack: scaled.attack,
    defense: stats.defense,
    attackRange: stats.attack_range,
    initiative: stats.initiative,
    regenBase: stats.regen_base ?? 0,
    cpuBudget: stats.cpu_budget ?? 0,
    potions: stats.potions ?? 0,
    summonerId: summoner.entityId,
  })
  state.entities.set(minion.entityId, minion)
  return minion
}

/**
 * 소환을 한 번 시도하고 결과를 말한다.
 *
 * 상한에 걸린 틱에도 쿨타임을 다시 건다. 걸지 않으면 소환사가 매 틱 이 규칙에 걸려 아래
 * 규칙과 DEFAULT 가 영영 평가되지 않는다.
 *
 * @param state 세계 상태.
 * @param config 소환 규칙과 종류 스탯을 담은 설정.
 * @param summoner 부른 쪽.
 * @returns 등장한 개체(없으면 undefined)와 로그에 남길 결과 문자열.
 */
export function resolveSummon(
  state: WorldState,
  config: EngineConfig,
  summoner: Entity,
): SummonResult {
  const rule = config.summonRules.get(summoner.kindId)
  if (rule === undefined) {
    return { minion: undefined, outcome: '소환 능력 없음 — 틱 낭비' }
  }
  summoner.cooldowns.set(SUMMON_ACTION, rule.every_ticks)
  const alive = countAliveMinions(state, summoner.entityId)
  if (alive >= rule.max_alive) {
    return { minion: undefined, outcome: `동시 상한(${alive}/${rule.max_alive})` }
  }
  const stats = config.enemyStats.get(rule.spawns)
  const position = findSummonPosition(state, summoner)
  if (stats === undefined || position === undefined) {
    return { minion: undefined, outcome: '놓을 자리 없음 — 틱 낭비' }
  }
  const minion = createMinion(state, config, summoner, rule.spawns, stats, position)
  return { minion, outcome: `${minion.entityId} 등장 ${formatPosition(position)}` }
}

/**
 * 즉발 광역기 대신 예고를 건다 (GDD §4.2).
 *
 * 반경의 정본은 이 예고 설정이다 — actions 의 AREA_ATTACK_RADIUS 는 예고를 쓰지 않는
 * 즉발 광역기의 값이며 둘은 다른 능력이다.
 *
 * 벽과 방 밖은 걸러 낸다. 거르지 않으면 닿지도 않는 칸이 붉게 칠해져, 플레이어가 피할
 * 필요가 없는 곳을 피하려 든다.
 *
 * @param state 세계 상태.
 * @param board 예고를 담을 판.
 * @param caster 시전자.
 * @param telegraph balance.json 의 그 종류 telegraph 절.
 * @returns 로그에 남길 결과 문자열.
 */
export function registerBlast(
  state: WorldState,
  board: TelegraphBoard,
  caster: Entity,
  telegraph: RawTelegraphSetting,
): string {
  const tiles = buildBlastTiles(caster.position, telegraph.radius).filter((position) =>
    WALKABLE_TILES.has(state.getTile(position.x, position.y)),
  )
  board.register({
    casterId: caster.entityId,
    skillId: telegraph.skill,
    tiles,
    damage: telegraph.damage,
    leadTicks: telegraph.lead_ticks,
    visibleTicks: telegraph.visible_ticks,
    cancelOnDeath: telegraph.cancel_on_death,
  })
  return `예고 ${tiles.length}칸 — ${telegraph.lead_ticks}틱 뒤 발동`
}

/**
 * 셀렉터가 고른 아군을 회복한다 (GDD §5 치유형).
 *
 * 회복량은 대상 최대 HP 의 정수 퍼센트다. 사거리 밖이거나 채울 여지가 없으면 회복하지
 * 않고 그 사유를 문자열로 돌려준다 — 쿨타임을 걸지 않아야 실행기가 그 틱을 낭비로 적고,
 * 플레이어가 규칙표의 어디를 고쳐야 하는지 알 수 있다 (P1).
 *
 * @param state 세계 상태.
 * @param config 엔진 설정. 회복 비율과 스킬 사거리를 여기서 읽는다.
 * @param actor 시전자.
 * @param plan 실행 중인 계획. 회복 행동 id 와 셀렉터가 고른 아군 id 를 담고 있다.
 * @returns 회복량과 로그에 남길 결과 문자열. 회복하지 못했으면 회복량이 0 이다.
 */
export function resolveHeal(
  state: WorldState,
  config: EngineConfig,
  actor: Entity,
  plan: PlannedAction,
): HealResult {
  const target = state.entities.get(plan.targetId ?? '')
  if (target === undefined || !isAlive(target)) {
    return { healed: 0, outcome: '대상 없음 — 틱 낭비' }
  }
  // 파이썬은 `skill_range.get(id) or actor.attack_range` 다. null 뿐 아니라 0 도 엔티티
  // 사거리로 넘어가므로 `??` 로 바꾸면 사거리 0 스킬의 동작이 달라진다.
  const declared = config.skillRange.get(plan.actionId)
  const reach =
    declared === undefined || declared === null || declared === 0 ? actor.attackRange : declared
  const distance = getManhattanDistance(actor.position, target.position)
  if (distance > reach) {
    return { healed: 0, outcome: `사거리 밖(${distance} > ${reach}) — 틱 낭비` }
  }
  const percent = config.skillHealPct.get(plan.actionId) ?? 0
  const amount = Math.min(
    target.hpMax - target.hp,
    divideFloor(target.hpMax * percent, PERCENT_BASE),
  )
  if (amount <= 0) {
    return { healed: 0, outcome: `${target.entityId} 회복 여지 없음 — 틱 낭비` }
  }
  target.hp += amount
  return { healed: amount, outcome: `${target.entityId} HP ${target.hp}/${target.hpMax}` }
}

/**
 * 포션 하나를 써서 자기 HP 를 채운다.
 *
 * @param entity 사용자.
 * @returns 회복량과 로그에 남길 결과 문자열. 포션이 없으면 회복량이 null 이다 — 0 과
 *   구분해야 "만피라서 0" 과 "포션이 없어 아무 일도 없었다" 가 갈린다.
 */
export function resolvePotion(entity: Entity): PotionResult {
  if (entity.potions <= 0) {
    return { healed: null, outcome: '포션 없음 — 틱 낭비' }
  }
  entity.potions -= 1
  const healed = Math.min(entity.hpMax - entity.hp, divideFloor(entity.hpMax, POTION_HEAL_DIVISOR))
  entity.hp += healed
  return { healed, outcome: `HP ${entity.hp}/${entity.hpMax}` }
}
