/**
 * 어뷰징 차단 — `game/app/simulation/pressure.py` 의 이식 (GDD §7, 로드맵 W7).
 *
 * v1 수식의 최적해는 "회복 타일 위 무한 대기 → 풀피로 처치" 였다. 시간이 공짜인 한 그
 * 전략은 언제나 옳으므로 여기서 **시간에 값을 매긴다** — 추격자·층 스케일·샘 잔여량.
 *
 * 수치의 정본은 balance.json 의 anti_abuse 절이다 (TDD §2). 이 모듈의 DEFAULT_* 는 그
 * 절이 통째로 빠졌을 때의 안전망이며, 값을 바꿀 자리가 아니다.
 *
 * 전부 정수 연산이다. 퍼센트는 내림 나눗셈으로 접는다 — 부동소수는 플랫폼마다 결과가
 * 갈려 리플레이를 깨뜨린다 (R5).
 */

import { EventLog, createLogEntry } from '../eventLog'
import { divideFloor } from '../combat/damage'
import { type Position, formatPosition, formatPositionKey, getManhattanDistance } from '../grid/geometry'
import { TILE_DOOR, TILE_FLOOR, TILE_SPRING, WALKABLE_TILES } from '../schemas'
import { PHASE_RESOLVE, PHASE_UPKEEP } from './phases'
import type { RawEnemyKind } from './plan'
import { FACTION_ENEMY, FACTION_PLAYER, type Entity, type WorldState, createEntity } from './state'

export const DEFAULT_HUNTER_SPAWN_TICK = 40
export const DEFAULT_HUNTER_INTERVAL_TICKS = 20
export const DEFAULT_HUNTER_ENTITY = 'goblin_rusher'
export const DEFAULT_FLOOR_ATTACK_PCT = 1
export const DEFAULT_COMBAT_REGEN_PCT = 50
export const DEFAULT_SPRING_POOL = 30

/** "+1%/10틱" 의 10틱. 이 단위 미만의 체류는 내림으로 버린다. */
export const FLOOR_SCALE_TICK_UNIT = 10

const PERCENT_BASE = 100

/** 문이 막혔을 때 물러설 최소 거리. 플레이어 옆에 꽂히면 즉사 장치가 된다. */
export const MIN_SPAWN_DISTANCE = 3

/** 추격자임을 표시하는 플래그. 규칙표가 쓰는 FLAG_A~D 와 겹치지 않는다. */
export const HUNTER_FLAG = 'HUNTER'

/** 특정 개체가 아니라 방 자체가 낸 이벤트의 주체. */
export const WORLD_ENTITY_ID = 'world'

/** balance.json 의 anti_abuse 절을 그대로 담는 값. */
export interface PressureRules {
  readonly hunterSpawnTick: number
  readonly hunterIntervalTicks: number
  readonly hunterEntity: string
  readonly floorAttackPctPer10Ticks: number
  readonly combatRegenPct: number
  readonly springPoolDefault: number
}

/** balance.json 의 anti_abuse 절 원시 형태. 항목은 전부 선택이며 빠지면 기본값을 쓴다. */
export interface RawAntiAbuse {
  readonly hunter_spawn_tick?: number
  readonly hunter_interval_ticks?: number
  readonly hunter_entity?: string
  readonly floor_attack_pct_per_10_ticks?: number
  readonly combat_regen_pct?: number
  readonly spring_pool_default?: number
}

/** 항목이 하나도 없을 때의 규칙. 파이썬 dataclass 의 기본값과 같다. */
export const DEFAULT_PRESSURE_RULES: PressureRules = {
  hunterSpawnTick: DEFAULT_HUNTER_SPAWN_TICK,
  hunterIntervalTicks: DEFAULT_HUNTER_INTERVAL_TICKS,
  hunterEntity: DEFAULT_HUNTER_ENTITY,
  floorAttackPctPer10Ticks: DEFAULT_FLOOR_ATTACK_PCT,
  combatRegenPct: DEFAULT_COMBAT_REGEN_PCT,
  springPoolDefault: DEFAULT_SPRING_POOL,
}

/**
 * anti_abuse 절을 규칙 값으로 옮긴다.
 *
 * @param antiAbuse balance.json 의 anti_abuse 객체.
 * @returns 읽어들인 규칙. 빠진 항목은 기본값으로 채운다.
 * @throws 추격자 주기가 1틱 미만인 경우. 0 이면 한 틱에 무한히 스폰한다.
 */
export function buildPressureRules(antiAbuse: RawAntiAbuse): PressureRules {
  const interval = antiAbuse.hunter_interval_ticks ?? DEFAULT_HUNTER_INTERVAL_TICKS
  if (interval < 1) {
    throw new RangeError(`hunter_interval_ticks 는 1 이상이어야 한다: ${interval}`)
  }
  return {
    hunterSpawnTick: antiAbuse.hunter_spawn_tick ?? DEFAULT_HUNTER_SPAWN_TICK,
    hunterIntervalTicks: interval,
    hunterEntity: antiAbuse.hunter_entity ?? DEFAULT_HUNTER_ENTITY,
    floorAttackPctPer10Ticks:
      antiAbuse.floor_attack_pct_per_10_ticks ?? DEFAULT_FLOOR_ATTACK_PCT,
    combatRegenPct: antiAbuse.combat_regen_pct ?? DEFAULT_COMBAT_REGEN_PCT,
    springPoolDefault: antiAbuse.spring_pool_default ?? DEFAULT_SPRING_POOL,
  }
}

/**
 * 압력 이벤트 한 줄을 남긴다. expr 에는 실측값을 병기한다 (GDD §8.2).
 *
 * @param log 이벤트 로그.
 * @param tick 틱 번호.
 * @param expr 조건 자리에 남길 문자열.
 * @param outcome 결과 설명.
 * @param phase 발생한 페이즈.
 */
function recordEvent(
  log: EventLog,
  tick: number,
  expr: string,
  outcome: string,
  phase: string,
): void {
  log.record(
    createLogEntry({ tick, entityId: WORLD_ENTITY_ID, phase, expr, outcome, fired: true }),
  )
}

/**
 * 방에서 그 종류의 타일 좌표를 훑는다.
 *
 * @param state 세계 상태.
 * @param tileId 찾을 타일 ID.
 * @returns y, x 순서로 훑은 좌표들. 순서가 고정이라 같은 방이면 같은 결과다 (R5).
 */
export function listTilesOfKind(state: WorldState, tileId: number): readonly Position[] {
  const found: Position[] = []
  for (let y = 0; y < state.room.height; y += 1) {
    for (let x = 0; x < state.room.width; x += 1) {
      if (state.getTile(x, y) === tileId) {
        found.push({ x, y })
      }
    }
  }
  return found
}

/**
 * 방의 생명의 샘마다 총 회복량을 채운다.
 *
 * **엔진 조립 직후 반드시 한 번 불러야 한다.** 채우지 않으면 잔여량이 늘 0 이라 샘은
 * 회복을 한 점도 못 낸 채 첫 RESOLVE 에서 소멸한다 — 차단이 아니라 고장이다. 이미 값이
 * 있는 좌표는 건드리지 않는다.
 *
 * @param state 세계 상태.
 * @param poolSize 샘 하나가 낼 총 회복량.
 * @returns 새로 채운 샘의 수.
 */
export function initSpringPools(state: WorldState, poolSize = DEFAULT_SPRING_POOL): number {
  let filled = 0
  for (const position of listTilesOfKind(state, TILE_SPRING)) {
    const key = formatPositionKey(position)
    if (state.springPools.has(key)) {
      continue
    }
    state.springPools.set(key, poolSize)
    filled += 1
  }
  return filled
}

/**
 * 샘에서 회복량을 꺼내고 잔여량을 그만큼 깎는다.
 *
 * @param state 세계 상태.
 * @param position 샘 좌표.
 * @param amount 꺼내려는 양.
 * @returns 실제로 꺼낸 양. 잔여량이 모자라면 남은 만큼만, 다 썼으면 0 이다.
 */
export function applySpringDrain(state: WorldState, position: Position, amount: number): number {
  const key = formatPositionKey(position)
  const pool = state.springPools.get(key) ?? 0
  const drawn = Math.max(0, Math.min(amount, pool))
  if (drawn > 0) {
    state.springPools.set(key, pool - drawn)
  }
  return drawn
}

/**
 * 잔여량이 바닥난 샘을 바닥 타일로 지운다 (페이즈 6 RESOLVE).
 *
 * @param state 세계 상태.
 * @param log 이벤트 로그. 없으면 남기지 않는다.
 * @returns 이번에 소멸한 샘의 좌표들. 방 좌표 순서를 지킨다.
 */
export function removeDrainedSprings(
  state: WorldState,
  log: EventLog | null = null,
): readonly Position[] {
  const drained = listTilesOfKind(state, TILE_SPRING).filter(
    (position) => (state.springPools.get(formatPositionKey(position)) ?? 0) <= 0,
  )
  for (const position of drained) {
    state.tileOverrides.set(formatPositionKey(position), TILE_FLOOR)
    if (log !== null) {
      recordEvent(
        log,
        state.tick,
        `샘 잔여량(0) ${formatPosition(position)}`,
        '샘 소멸',
        PHASE_RESOLVE,
      )
    }
  }
  return drained
}

/**
 * 층 체류 틱이 만드는 적 공격력 보너스 퍼센트.
 *
 * @param floorTicks 이 층에서 보낸 틱 수.
 * @param pctPerUnit FLOOR_SCALE_TICK_UNIT 틱마다 얹을 퍼센트.
 * @returns 보너스 퍼센트. 단위 미만은 내림으로 버린다.
 */
export function calculateFloorBonusPct(floorTicks: number, pctPerUnit: number): number {
  return divideFloor(Math.max(0, floorTicks), FLOOR_SCALE_TICK_UNIT) * pctPerUnit
}

/**
 * 보너스 퍼센트를 얹은 공격력.
 *
 * @param baseAttack 스케일 전 공격력.
 * @param bonusPct 얹을 퍼센트.
 * @returns 내림 정수로 접은 공격력.
 */
export function calculateScaledAttack(baseAttack: number, bonusPct: number): number {
  return divideFloor(baseAttack * (PERCENT_BASE + bonusPct), PERCENT_BASE)
}

/**
 * 추격자가 들어설 수 있는 칸을 우선순위대로 모은다.
 *
 * 문이 1순위다. 방 밖에서 쫓아온 것이 벽 안쪽에 솟으면 대비할 방법이 없다. 문이 막혔을
 * 때만 플레이어에게서 떨어진 빈 칸으로 물러난다.
 *
 * @param state 세계 상태.
 * @returns 후보 좌표들. 방 좌표 순서라 같은 상황이면 같은 순서다 (R5). 없으면 빈 배열.
 */
export function listHunterSpawns(state: WorldState): readonly Position[] {
  const occupied = new Set(state.listActors().map((actor) => formatPositionKey(actor.position)))
  const doors = listTilesOfKind(state, TILE_DOOR).filter(
    (pos) => !occupied.has(formatPositionKey(pos)),
  )
  if (doors.length > 0) {
    return doors
  }

  const free: Position[] = []
  for (let y = 0; y < state.room.height; y += 1) {
    for (let x = 0; x < state.room.width; x += 1) {
      const cell: Position = { x, y }
      if (WALKABLE_TILES.has(state.getTile(x, y)) && !occupied.has(formatPositionKey(cell))) {
        free.push(cell)
      }
    }
  }
  const players = state.listActors().filter((actor) => actor.faction === FACTION_PLAYER)
  const far = free.filter((pos) =>
    players.every((player) => getManhattanDistance(pos, player.position) >= MIN_SPAWN_DISTANCE),
  )
  return far.length > 0 ? far : free
}

/**
 * 방·층 체류 틱을 세고 그만큼의 압력을 되돌린다.
 *
 * 엔진이 아니라 이쪽이 체류 틱을 센다. 방을 옮겨도 층 체류는 이어져야 하는데 (GDD §7
 * 층 지연) 엔진은 방 하나의 수명만 살기 때문이다.
 */
export class PressureTracker {
  roomTicks = 0

  /** 방을 옮겨도 이어진다 (GDD §7 층 지연). */
  floorTicks = 0

  hunterCount = 0

  /** 스케일 전 공격력. 매 틱 현재값에 곱하면 복리가 되어 수십 틱 만에 발산한다. */
  readonly baseAttacks = new Map<string, number>()

  /** 로그를 값이 바뀐 틱에만 남기려고 든다. */
  appliedPct = 0

  /**
   * 추적기를 만든다.
   *
   * @param rules anti_abuse 절에서 읽은 규칙.
   * @param enemyStats kindId -> balance.json 의 적 스탯. 추격자를 만들 때만 읽는다.
   */
  constructor(
    readonly rules: PressureRules = DEFAULT_PRESSURE_RULES,
    readonly enemyStats: ReadonlyMap<string, RawEnemyKind> = new Map(),
  ) {}

  /** 방·층 체류 틱을 1 올린다. */
  addTick(): void {
    this.roomTicks += 1
    this.floorTicks += 1
  }

  /**
   * 새 방에 들어설 때의 초기화. 층 체류 틱은 남는다.
   *
   * 기준 공격력을 함께 지운다. 어느 방에나 goblin_rusher_0 이 있으므로 남겨 두면 다른
   * 개체의 값을 그 id 로 읽는다.
   */
  resetRoom(): void {
    this.roomTicks = 0
    this.hunterCount = 0
    this.appliedPct = 0
    this.baseAttacks.clear()
  }

  /** 새 층에 내려설 때의 초기화. 층 체류 틱까지 지운다. */
  resetFloor(): void {
    this.floorTicks = 0
    this.resetRoom()
  }

  /**
   * 이번 틱이 추격자를 낼 틱인가.
   *
   * @returns 체류가 hunterSpawnTick 을 넘긴 첫 틱과, 그 뒤 주기마다 true.
   */
  isHunterDue(): boolean {
    const elapsed = this.roomTicks - this.rules.hunterSpawnTick
    if (elapsed <= 0) {
      return false
    }
    return (elapsed - 1) % this.rules.hunterIntervalTicks === 0
  }

  /**
   * 지금 적 공격력에 얹히는 보너스 퍼센트.
   *
   * @returns 층 체류 틱에서 계산한 퍼센트.
   */
  getBonusPct(): number {
    return calculateFloorBonusPct(this.floorTicks, this.rules.floorAttackPctPer10Ticks)
  }

  /**
   * 층 체류 시간만큼 적 공격력을 올린다.
   *
   * 플레이어는 대상이 아니다. 양쪽이 함께 오르면 상대 압력이 0 이 된다.
   *
   * @param state 세계 상태.
   * @param log 이벤트 로그. 없으면 남기지 않는다.
   * @returns 이번에 적용한 보너스 퍼센트.
   */
  applyScale(state: WorldState, log: EventLog | null = null): number {
    const bonusPct = this.getBonusPct()
    for (const actor of state.listActors()) {
      if (actor.faction === FACTION_PLAYER) {
        continue
      }
      let base = this.baseAttacks.get(actor.entityId)
      if (base === undefined) {
        base = actor.attack
        this.baseAttacks.set(actor.entityId, base)
      }
      actor.attack = calculateScaledAttack(base, bonusPct)
    }
    if (log !== null && bonusPct !== this.appliedPct) {
      recordEvent(
        log,
        state.tick,
        `층 체류(${this.floorTicks}) / 단위(${FLOOR_SCALE_TICK_UNIT})`,
        `적 공격력 +${bonusPct}%`,
        PHASE_UPKEEP,
      )
    }
    this.appliedPct = bonusPct
    return bonusPct
  }

  /**
   * 추격자 하나를 방에 들인다.
   *
   * 스폰 위치는 후보 목록에서 WorldState.rng 로 고른다. 방 좌표 순서로 모은 목록이라
   * 같은 시드가 같은 자리를 낸다 (R5). **여기가 UPKEEP 의 유일한 난수 소비 지점이므로
   * 호출 조건이 달라지면 그 뒤의 모든 난수가 밀린다.**
   *
   * @param state 세계 상태.
   * @param log 이벤트 로그. 없으면 남기지 않는다.
   * @returns 등장한 추격자. 스탯이 없거나 설 자리가 없으면 undefined.
   */
  createHunter(state: WorldState, log: EventLog | null = null): Entity | undefined {
    const stats = this.enemyStats.get(this.rules.hunterEntity)
    const expr = `방 체류(${this.roomTicks}) > 한계(${this.rules.hunterSpawnTick})`
    if (stats === undefined) {
      if (log !== null) {
        recordEvent(log, state.tick, expr, '추격자 스탯 없음', PHASE_UPKEEP)
      }
      return undefined
    }
    const spawns = listHunterSpawns(state)
    if (spawns.length === 0) {
      if (log !== null) {
        recordEvent(log, state.tick, expr, '빈 칸 없음 — 등장 실패', PHASE_UPKEEP)
      }
      return undefined
    }

    const position = state.rng.getChoice(spawns)
    // 소환물과 같은 일련번호를 쓴다. id 가 겹치면 한쪽이 조용히 덮인다.
    state.spawnCounter += 1
    this.hunterCount += 1
    const hunter = createEntity({
      entityId: `${this.rules.hunterEntity}_h${state.spawnCounter}`,
      kindId: this.rules.hunterEntity,
      faction: FACTION_ENEMY,
      position,
      hp: stats.hp_max,
      hpMax: stats.hp_max,
      attack: stats.attack,
      defense: stats.defense,
      attackRange: stats.attack_range,
      initiative: stats.initiative,
      regenBase: stats.regen_base ?? 0,
      cpuBudget: stats.cpu_budget ?? 0,
      flags: new Map([[HUNTER_FLAG, true]]),
    })
    state.entities.set(hunter.entityId, hunter)
    if (log !== null) {
      recordEvent(
        log,
        state.tick,
        expr,
        `추격자 ${hunter.entityId} 등장 ${formatPosition(position)}`,
        PHASE_UPKEEP,
      )
    }
    return hunter
  }

  /**
   * 체류 틱을 올리고 이번 틱의 압력을 적용한다 (페이즈 1 UPKEEP).
   *
   * 추격자를 먼저 들이고 스케일을 나중에 건다. 반대로 하면 갓 등장한 추격자만 그 틱의
   * 보너스를 놓친다.
   *
   * @param state 세계 상태.
   * @param log 이벤트 로그. 없으면 남기지 않는다.
   * @returns 이번 틱에 등장한 추격자들. 없으면 빈 배열.
   */
  runUpkeep(state: WorldState, log: EventLog | null = null): readonly Entity[] {
    this.addTick()
    const hunters: Entity[] = []
    if (this.isHunterDue()) {
      const hunter = this.createHunter(state, log)
      if (hunter !== undefined) {
        hunters.push(hunter)
      }
    }
    this.applyScale(state, log)
    return hunters
  }
}
