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
import type { RawAntiAbuse } from '../sim/pressure'
import type { RawDamageFormula } from '../combat/damage'
import { FACTION_ENEMY, FACTION_PLAYER, WorldState, createEntity } from '../sim/state'
import type { Entity } from '../sim/state'

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
  readonly id: string
  readonly coef_pct: number
  readonly cooldown: number
  readonly range: number | null
}

/** 엔진 조립에 필요한 balance.json 의 절들만 모은 것. */
export interface BalanceData {
  readonly damageFormula: RawDamageFormula
  readonly player: RawPlayerStats
  readonly skills: readonly RawSkill[]
  readonly enemies: readonly RawEnemyKind[]
  readonly antiAbuse: RawAntiAbuse
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
   * 층 단위 압력 추적기. 방마다 새로 만들면 층 체류 스케일이 매 방 0 으로 돌아가므로
   * 연쇄 실행은 하나를 만들어 계속 넘긴다.
   */
  readonly pressure?: PressureTracker
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
export function buildEngine(setup: EngineSetup): TickEngine {
  const { template, balance } = setup
  const rng = new DeterministicRng(setup.seed)
  const state = new WorldState(template, rng)
  const rules = buildPressureRules(balance.antiAbuse)
  // 채우지 않으면 생명의 샘이 회복을 한 점도 내지 못한다 (잔여량 0 = 마른 샘).
  initSpringPools(state, rules.springPoolDefault)

  const playerStats = balance.player
  state.entities.set(
    PLAYER_ENTITY_ID,
    createEntity({
      entityId: PLAYER_ENTITY_ID,
      kindId: PLAYER_ENTITY_ID,
      faction: FACTION_PLAYER,
      position: template.playerSpawn,
      hp: playerStats.hp_max,
      hpMax: playerStats.hp_max,
      attack: playerStats.attack,
      defense: playerStats.defense,
      attackRange: playerStats.attack_range,
      initiative: playerStats.initiative,
      regenBase: playerStats.regen_base,
      cpuBudget: playerStats.cpu_budget,
      potions: playerStats.potions,
    }),
  )

  const byId = new Map(balance.enemies.map((kind) => [kind.id, kind]))
  template.enemySpawns.forEach((spawn, index) => {
    const kind = byId.get(spawn.kind)
    if (kind === undefined) {
      throw new Error(`balance.json 에 없는 적 종류다: ${spawn.kind}`)
    }
    const entityId = `${kind.id}_${index}`
    state.entities.set(
      entityId,
      createEntity({
        entityId,
        kindId: kind.id,
        faction: FACTION_ENEMY,
        position: spawn.position,
        hp: kind.hp_max,
        hpMax: kind.hp_max,
        attack: kind.attack,
        defense: kind.defense,
        attackRange: kind.attack_range,
        initiative: kind.initiative,
        regenBase: kind.regen_base ?? 0,
        cpuBudget: kind.cpu_budget ?? 0,
        potions: kind.potions ?? 0,
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
    summonRules: new Map(
      balance.enemies
        .filter((kind) => kind.summon !== undefined)
        .map((kind) => [kind.id, kind.summon as NonNullable<RawEnemyKind['summon']>]),
    ),
    enemyStats,
    floor: setup.floor ?? DEFAULT_FLOOR,
    maxTicks: setup.maxTicks ?? DEFAULT_MAX_TICKS,
    combatRegenPct: rules.combatRegenPct,
  }
  const tracker = setup.pressure ?? new PressureTracker(rules, enemyStats)
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
