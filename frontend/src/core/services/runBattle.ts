/**
 * 전투 1회 실행 — `game/app/services/run_battle.py` 의 이식. 방 하나를 끝까지 돌린다.
 *
 * 파일 하나가 시나리오 하나다 (표준 §12). 아래 계층의 모듈들을 엮어 하나의 흐름을 만든다.
 *
 * `assignEnemyPolicies` 가 적에게 각자의 규칙표를 붙인다. 붙이지 않으면 전원이 폴백
 * 정책으로 싸우고, 그러면 도감이 보여줄 규칙표와 실제 행동이 달라져 플레이어가 도감을
 * 읽고 세운 카운터가 통하지 않는다 (GDD §5).
 */

import { buildDamageRules } from '../combat/damage'
import { DeterministicRng } from '../rng'
import { FallbackPolicy } from '../rules/fallbackPolicy'
import { buildRuleVm } from '../rules/ruleVm'
import type { RawBalanceFile } from '../resources'
import type { BlockCatalog, RoomTemplate, RuleSet } from '../schemas'
import { TickEngine } from '../sim/engine'
import {
  OUTCOME_ONGOING,
  type DecisionPolicy,
  type EngineConfig,
  type PolicyFactory,
  type RawEnemyKind,
} from '../sim/plan'
import { PressureTracker, buildPressureRules, initSpringPools } from '../sim/pressure'
import { buildFloorScale, getScaledEnemyStats } from '../sim/scaling'
import type { RawFloorScale } from '../sim/scaling'
import type { RawAntiAbuse } from '../sim/pressure'
import type { RawDamageFormula } from '../combat/damage'
import { FACTION_ENEMY, FACTION_PLAYER, TIER_NORMAL, WorldState, createEntity } from '../sim/state'
import type { Entity } from '../sim/state'
import { buildEntityId, type MonsterSnapshot } from '../schemas/monsterSnapshot'
import { resolveEliteKind, resolveSpawnSpot } from '../sim/variance'
import { BASE_SKILL_POWER_PCT, type PlayerLoadout } from '../schemas/loadout'

/** 이 틱을 넘기면 시간 초과로 끝낸다. */
export const DEFAULT_MAX_TICKS = 400

/** 기본 층. 피해 공식의 방어 감쇠와 층 스케일이 이 값을 본다. */
export const DEFAULT_FLOOR = 1

/** 플레이어 엔티티의 고정 id. 결과 집계가 이 이름으로 찾는다. */
export const PLAYER_ENTITY_ID = 'player'

/** balance.json 의 player 절. */
export interface RawPlayerStats {
  readonly hp_max: number
  readonly attack: number
  readonly defense: number
  readonly attack_range: number
  readonly initiative: number
  readonly regen_base: number
  readonly cpu_budget: number
  readonly potions: number
}

/** balance.json 의 skills 절 한 항목. */
export interface RawSkill {
  readonly guard_pct?: number
  readonly guard_ticks?: number
  readonly id: string
  readonly coef_pct: number
  readonly cooldown: number
  readonly range: number | null
  /** 회복 행동만 갖는다. 대상 최대 HP 의 정수 퍼센트다 (블록 목록 v4). */
  readonly heal_pct?: number
}

/** 엔진 조립에 필요한 balance.json 의 절들만 모은 것. */
export interface BalanceData {
  readonly damageFormula: RawDamageFormula
  readonly player: RawPlayerStats
  readonly skills: readonly RawSkill[]
  readonly enemies: readonly RawEnemyKind[]
  readonly antiAbuse: RawAntiAbuse
  /**
   * 층 깊이 스케일. 절이 없어도 엔진은 돌아야 하므로(파이썬 `balance.get`) 선택 항목이며,
   * 없으면 `buildFloorScale` 의 기본값이 들어간다.
   */
  readonly floorScale: RawFloorScale | undefined
}

/**
 * 밸런스 파일에서 필요한 절을 꺼낸다.
 *
 * `resources.ts` 가 통째로 통과시킨 값이라 여기가 형식을 확인하는 유일한 지점이다.
 * 단언으로 넘기면 절 하나가 빠졌을 때 수백 틱 뒤 엉뚱한 자리에서 터진다.
 *
 * @param raw balance.json 을 읽은 값.
 * @returns 엔진 조립에 쓸 절들.
 * @throws 필요한 절이 없거나 형태가 다른 경우.
 */
export function parseBalance(raw: RawBalanceFile): BalanceData {
  return {
    damageFormula: readObject<RawDamageFormula>(raw, 'damage_formula'),
    player: readObject<RawPlayerStats>(raw, 'player'),
    skills: readArray<RawSkill>(raw, 'skills'),
    enemies: readArray<RawEnemyKind>(raw, 'enemies'),
    antiAbuse: readObject<RawAntiAbuse>(raw, 'anti_abuse'),
    floorScale: raw['floor_scale'] as RawFloorScale | undefined,
  }
}

/**
 * 객체인 절 하나를 꺼낸다.
 *
 * @param raw 읽을 파일.
 * @param key 절 이름.
 * @returns 그 절.
 * @throws 절이 없거나 객체가 아닌 경우.
 */
function readObject<ValueT>(raw: RawBalanceFile, key: string): ValueT {
  const value = raw[key]
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new TypeError(`balance.json 의 ${key} 절이 객체가 아니다`)
  }
  return value as ValueT
}

/**
 * 배열인 절 하나를 꺼낸다.
 *
 * @param raw 읽을 파일.
 * @param key 절 이름.
 * @returns 그 절.
 * @throws 절이 없거나 배열이 아닌 경우.
 */
function readArray<ValueT>(raw: RawBalanceFile, key: string): readonly ValueT[] {
  const value = raw[key]
  if (!Array.isArray(value)) {
    throw new TypeError(`balance.json 의 ${key} 절이 배열이 아니다`)
  }
  return value as readonly ValueT[]
}

/** 전투 한 판의 결과. 리플레이 검증이 이 값을 대조한다. */
export interface BattleResult {
  readonly outcome: string
  readonly ticks: number
  readonly playerHp: number
  readonly logLines: readonly string[]
}

/** `buildEngine` 이 받는 값들. */
export interface EngineSetup {
  readonly template: RoomTemplate
  readonly balance: BalanceData
  readonly seed: number | bigint
  readonly maxTicks?: number
  readonly floor?: number
  /**
   * 배치 흔들기·정예 승격을 켤지. 기본은 켬 — **골든과 튜토리얼이 끈다**.
   * 파이썬의 `is_varied` 와 같은 뜻이다 (G3).
   */
  readonly isVaried?: boolean
  /**
   * 층 단위 압력 추적기. 방마다 새로 만들면 층 체류 스케일이 매 방 0 으로 돌아가므로
   * 연쇄 실행은 하나를 만들어 계속 넘긴다.
   */
  readonly pressure?: PressureTracker
  /**
   * 티켓이 얼려 둔 지속 몬스터 상태. 해당 자리의 층 스케일을 **대체한다**.
   *
   * 얹으면 같은 개체가 층마다 다른 값을 갖게 되어 스냅샷의 뜻이 사라진다.
   */
  readonly snapshots?: readonly MonsterSnapshot[]
  /**
   * 티켓이 얼려 둔 플레이어 전투 입력 (장비·레벨).
   *
   * 없으면 balance.json 기본값으로 선다 — 오프라인 연습이 그 경우다.
   */
  readonly loadout?: PlayerLoadout
}

/**
 * 방 템플릿과 밸런스 값으로 엔진을 조립한다.
 *
 * 순서가 파이썬과 같아야 한다. 특히 샘 잔여량 채우기가 엔티티 배치보다 앞이고, 적 id 는
 * 템플릿의 스폰 순서(index)로 붙는다 — 둘 중 하나만 달라져도 골든 로그가 갈린다.
 *
 * @param setup 템플릿·밸런스·시드와 선택 항목들.
 * @returns 첫 틱을 돌릴 준비가 된 엔진.
 * @throws 템플릿이 부르는 적 종류가 balance.json 에 없는 경우.
 */
/**
 * 이 층에 얹을 스냅샷만 골라 이름으로 건다.
 *
 * **이름이 층을 구분하지 않는다.** 자리 이름은 `{종}_{순번}` 이라 `goblin_rusher_0` 이
 * 1층부터 9층까지 따로 살고, 하강 티켓은 그 전부를 싣는다. 층을 안 보고 이름만으로
 * 겹치면 나중 것이 이기는데 그것이 가장 깊은 층의 개체다 — **1층 방에 9층 레벨 10 짜리가
 * 섰다.** 신규 계정이 첫 방에서 그것을 만났다.
 *
 * **층을 모르는 스냅샷(0)은 그대로 얹는다.** 층을 싣기 전에 발급된 티켓이 그 값이고,
 * 발급 당시와 다르게 재시뮬하면 정상 제출이 반려된다 (R5).
 *
 * @param snapshots 티켓이 얼려 둔 개체들. 하강 전체의 층이 섞여 있다.
 * @param floor 지금 도는 방의 층.
 * @returns entityId → 스냅샷. 이 층 것과 층을 모르는 것만 들어 있다.
 */
export function buildFloorOverrides(
  snapshots: readonly MonsterSnapshot[],
  floor: number,
): ReadonlyMap<string, MonsterSnapshot> {
  const picked = new Map<string, MonsterSnapshot>()
  for (const item of snapshots) {
    if (item.zoneFloor === 0 || item.zoneFloor === floor) {
      picked.set(item.entityId, item)
    }
  }
  return picked
}

export function buildEngine(setup: EngineSetup): TickEngine {
  const { template, balance } = setup
  const rng = new DeterministicRng(setup.seed)
  const state = new WorldState(template, rng)
  const rules = buildPressureRules(balance.antiAbuse)
  // 채우지 않으면 생명의 샘이 회복을 한 점도 내지 못한다 (잔여량 0 = 마른 샘).
  initSpringPools(state, rules.springPoolDefault)

  const playerStats = balance.player
  // 로드아웃이 있으면 장비·레벨이 확정한 값이 기본값을 **대체한다** (결정 #13).
  // 얹으면 같은 장비가 밸런스 패치마다 다른 값을 낸다.
  const loadout = setup.loadout
  const playerHp = loadout?.hpMax ?? playerStats.hp_max
  state.entities.set(
    PLAYER_ENTITY_ID,
    createEntity({
      entityId: PLAYER_ENTITY_ID,
      kindId: PLAYER_ENTITY_ID,
      faction: FACTION_PLAYER,
      position: template.playerSpawn,
      hp: playerHp,
      hpMax: playerHp,
      attack: loadout?.attack ?? playerStats.attack,
      defense: loadout?.defense ?? playerStats.defense,
      attackRange: loadout?.attackRange ?? playerStats.attack_range,
      initiative: loadout?.initiative ?? playerStats.initiative,
      regenBase: playerStats.regen_base,
      cpuBudget: loadout?.cpuBudget ?? playerStats.cpu_budget,
      // 지능이 올린 스킬위력. 로드아웃이 없으면 기준값이라 기존 판이 그대로다.
      skillPowerPct: loadout?.skillPowerPct ?? BASE_SKILL_POWER_PCT,
      // 로드아웃이 있으면 인벤토리가 정한 것을 쓴다 (#54). 없으면 기본값이다.
      consumables:
        loadout === undefined
          ? new Map([['POTION', playerStats.potions]])
          : new Map(loadout.consumables),
      // null 은 "장착 개념이 배선되지 않음" 이라 전부 허용한다 — 오프라인 연습이
      // 그 경우다. 로드아웃이 있으면 그 목록만 쓴다.
      skills: loadout === undefined ? null : [...loadout.skills],
    }),
  )

  const byId = new Map(balance.enemies.map((kind) => [kind.id, kind]))
  const floor = setup.floor ?? DEFAULT_FLOOR
  const scale = buildFloorScale(balance.floorScale)
  // 스냅샷은 entityId 로 겹친다. 방 배치가 `{kind}_{index}` 로 붙이므로 그 이름을
  // 겨냥하며, 이름이 갈리면 스냅샷이 아무에게도 적용되지 않고 조용히 넘어간다.
  const overrides = buildFloorOverrides(setup.snapshots ?? [], floor)
  // **변수 축을 따로 판다** (R5) — 파이썬과 같은 라벨·같은 순서다 (G3).
  // **끌 수 있어야 한다** — 파이썬의 `is_varied` 와 같은 뜻이다 (G3). 골든·튜토리얼이 끈다.
  const isVaried = setup.isVaried ?? true
  const variance = rng.createStream('variance')
  const taken = new Set<string>([
    `${String(template.playerSpawn.x)},${String(template.playerSpawn.y)}`,
  ])
  template.enemySpawns.forEach((spawn, index) => {
    // 지속 몬스터가 앉은 자리는 안 흔들고 안 바꾼다 — 스냅샷이 그 개체를 덮어야 하는데
    // 종이나 자리가 갈리면 얼려 둔 상태가 아무에게도 안 붙는다.
    const entityId = buildEntityId(spawn.kind, index)
    const found = overrides.get(entityId)
    const kindId =
      found === undefined && isVaried
        ? resolveEliteKind(spawn.kind, floor, variance)
        : spawn.kind
    const spot =
      found === undefined && isVaried
        ? resolveSpawnSpot(template, spawn.position, taken, variance)
        : spawn.position
    taken.add(`${String(spot.x)},${String(spot.y)}`)
    // **스냅샷이 종도 정한다.** 얼려 둔 것은 그 개체의 상태 전부이고 종은 그 일부다.
    // 이것이 없으면 도플갱어가 방에 설 자리가 없다 (G3 — 파이썬과 같은 규칙).
    const namedKind =
      found !== undefined && byId.has(found.kindId) ? found.kindId : kindId
    const kind = byId.get(namedKind)
    if (kind === undefined) {
      throw new Error(`balance.json 에 없는 적 종류다: ${kindId}`)
    }
    const scaled = getScaledEnemyStats(kind, scale, floor)
    state.entities.set(
      entityId,
      createEntity({
        entityId,
        kindId: kind.id,
        faction: FACTION_ENEMY,
        position: spot,
        hp: found?.hpMax ?? scaled.hpMax,
        hpMax: found?.hpMax ?? scaled.hpMax,
        attack: found?.attack ?? scaled.attack,
        defense: found?.defense ?? kind.defense,
        // **키트도 얼려 둔 것을 쓴다** (G3 — 파이썬 `run_battle` 과 같은 규칙).
        // 스탯만 대체하던 때는 장궁 든 봇의 그림자가 사거리 1 근접으로 싸웠다. 안 실린
        // 값은 종의 것을 그대로 쓰므로, 옛 티켓은 예전과 똑같이 재시뮬된다 (R5).
        attackRange: found?.attackRange || kind.attack_range,
        initiative: kind.initiative,
        regenBase: kind.regen_base ?? 0,
        cpuBudget: found?.cpuBudget ?? kind.cpu_budget ?? 0,
        consumables: new Map([
          ['POTION', found !== undefined && found.potions >= 0 ? found.potions : (kind.potions ?? 0)],
        ]),
        // undefined 는 「장착 개념이 안 배선됨 = 전부 허용」이다. 빈 것(아무것도 없음)과
        // 뜻이 반대라, 스냅샷의 빈 것은 **모른다**로 읽어 undefined 로 둔다.
        ...(found === undefined || found.skills.length === 0 ? {} : { skills: found.skills }),
        // 등급은 이름표로만 나른다. 전투 수식은 안 본다 — 화면이 색으로 가른다.
        tier: kind.tier ?? TIER_NORMAL,
      }),
    )
  })

  const enemyStats = new Map(balance.enemies.map((kind) => [kind.id, kind]))
  const config: EngineConfig = {
    damageRules: buildDamageRules(balance.damageFormula),
    kindTypes: new Map(balance.enemies.map((kind) => [kind.id, kind.type])),
    skillCoefPct: new Map(balance.skills.map((skill) => [skill.id, skill.coef_pct])),
    skillRange: new Map(balance.skills.map((skill) => [skill.id, skill.range ?? null])),
    skillCooldowns: new Map(balance.skills.map((skill) => [skill.id, skill.cooldown])),
    skillGuardPct: new Map(
      balance.skills.filter((s) => s.guard_pct !== undefined).map((s) => [s.id, s.guard_pct ?? 0]),
    ),
    skillGuardTicks: new Map(
      balance.skills
        .filter((s) => s.guard_ticks !== undefined)
        .map((s) => [s.id, s.guard_ticks ?? 0]),
    ),
    skillHealPct: new Map(
      balance.skills
        .filter((skill) => skill.heal_pct !== undefined)
        .map((skill) => [skill.id, skill.heal_pct ?? 0]),
    ),
    summonRules: new Map(
      balance.enemies
        .filter((kind) => kind.summon !== undefined)
        .map((kind) => [kind.id, kind.summon as NonNullable<RawEnemyKind['summon']>]),
    ),
    enemyStats,
    floorScale: scale,
    floor,
    maxTicks: setup.maxTicks ?? DEFAULT_MAX_TICKS,
    combatRegenPct: rules.combatRegenPct,
  }
  const tracker = setup.pressure ?? new PressureTracker(rules, enemyStats)
  // 층은 엔진이 정본이다. 넘겨받은 추적기에도 덮어써야 층 3 에서 뒤늦게 나온 추격자만
  // 층 1 스탯으로 서는 일이 없다 — 추적기는 층 단위 객체라 방마다 재사용된다.
  tracker.floor = floor
  tracker.floorScale = scale
  return new TickEngine({ state, policy: new FallbackPolicy(), config, pressure: tracker })
}

/**
 * kind_id 로 규칙표를 찾아 결정기를 만든다 (`plan.PolicyFactory`).
 *
 * 전투 도중 등장하는 소환물·추격자에 규칙표를 붙이는 자리다. 조립 시점의 일괄 배정은
 * 그때 없던 개체에 닿지 못한다.
 */
export class EnemyPolicyFactory implements PolicyFactory {
  /**
   * 종류별 규칙표를 미리 풀어 둔 공장을 만든다.
   *
   * @param catalog 동결된 블록 카탈로그.
   * @param kindTypes 엔티티 종류에서 적 유형으로의 대응표.
   * @param rulesetByKind 엔티티 종류에서 규칙표로의 대응표.
   */
  constructor(
    readonly catalog: BlockCatalog,
    readonly kindTypes: ReadonlyMap<string, string>,
    readonly rulesetByKind: ReadonlyMap<string, RuleSet>,
  ) {}

  /**
   * 그 엔티티의 결정기를 만든다.
   *
   * @param entity 대상 엔티티.
   * @returns 규칙표가 있으면 RuleVM, 없으면 undefined.
   */
  buildPolicy(entity: Entity): DecisionPolicy | undefined {
    const ruleset = this.rulesetByKind.get(entity.kindId)
    if (ruleset === undefined) {
      return undefined
    }
    return buildRuleVm(ruleset, this.catalog, this.kindTypes)
  }
}

/**
 * 적 종류에서 규칙표로 가는 표를 미리 풀어 공장을 만든다.
 *
 * @param balance 밸런스 값들.
 * @param catalog 동결된 블록 카탈로그.
 * @param enemyRulesets ruleset_id 에서 규칙표로의 대응표.
 * @returns 엔티티마다 결정기를 만들어 주는 공장.
 */
export function buildEnemyPolicyFactory(
  balance: BalanceData,
  catalog: BlockCatalog,
  enemyRulesets: ReadonlyMap<string, RuleSet>,
): EnemyPolicyFactory {
  const byKind = new Map<string, RuleSet>()
  for (const kind of balance.enemies) {
    const rulesetId = kind.ruleset_id
    if (rulesetId === undefined) {
      continue
    }
    const ruleset = enemyRulesets.get(rulesetId)
    if (ruleset !== undefined) {
      byKind.set(kind.id, ruleset)
    }
  }
  return new EnemyPolicyFactory(
    catalog,
    new Map(balance.enemies.map((kind) => [kind.id, kind.type])),
    byKind,
  )
}

/**
 * 적 엔티티에 각자의 규칙표를 붙인다 (GDD §5).
 *
 * 공장을 함께 걸어 둔다. 소환물·추격자는 조립 시점에 없는 개체이므로 이것이 없으면
 * 그들만 폴백 정책으로 싸운다.
 *
 * @param engine 대상 엔진.
 * @param balance 밸런스 값들.
 * @param catalog 동결된 블록 카탈로그.
 * @param enemyRulesets ruleset_id 에서 규칙표로의 대응표.
 */
export function assignEnemyPolicies(
  engine: TickEngine,
  balance: BalanceData,
  catalog: BlockCatalog,
  enemyRulesets: ReadonlyMap<string, RuleSet>,
): void {
  engine.policyFactory = buildEnemyPolicyFactory(balance, catalog, enemyRulesets)
  engine.registerNewcomers()
}

/**
 * 승패가 갈릴 때까지 틱을 돌린다.
 *
 * @param engine 조립된 엔진.
 * @returns 결과와 로그.
 * @throws 플레이어 엔티티가 없는 경우. 조립이 잘못된 것이다.
 */
export function runBattle(engine: TickEngine): BattleResult {
  let outcome = OUTCOME_ONGOING
  while (outcome === OUTCOME_ONGOING) {
    outcome = engine.runTick()
  }
  const player = engine.state.entities.get(PLAYER_ENTITY_ID)
  if (player === undefined) {
    throw new Error(`플레이어 엔티티가 없다: ${PLAYER_ENTITY_ID}`)
  }
  return {
    outcome,
    ticks: engine.state.tick,
    playerHp: player.hp,
    logLines: engine.log.formatLines(),
  }
}
