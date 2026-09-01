/**
 * 전투 한 판의 조립 — 화면이 붙잡고 돌릴 엔진을 만든다.
 *
 * **조립 순서가 계약이다** (frontend/README.md). 플레이어 규칙표를 먼저 꽂고 그다음에
 * `assignEnemyPolicies` 를 부른다. 순서를 바꾸면 그 안의 `registerNewcomers` 가 플레이어
 * 자리를 적 공장으로 먼저 채워 플레이어 규칙표가 조용히 덮인다. 파이썬 run_chain.py ·
 * run_room_loop.py 도 같은 순서다.
 *
 * 플레이어 정책만 `TracingRuleVm` 으로 감싼다. 규칙표 화면을 보는 대상이 플레이어 하나라
 * 적까지 감싸면 매 틱 여덟 번의 재평가가 화면에 쓰이지도 않고 돈다.
 */

import { BALANCE, BLOCK_CATALOG, ENEMY_RULESETS, ROOM_TEMPLATES } from '../core/resources'
import {
  assignEnemyPolicies,
  buildEngine,
  parseBalance,
  PLAYER_ENTITY_ID,
  runBattle,
  type BalanceData,
} from '../core/services/runBattle'
import { ChainCursor } from '../core/services/runChain'
import { buildRuleVm } from '../core/rules/ruleVm'
import type { MonsterSnapshot, PlayerLoadout, RoomTemplate, RuleSet } from '../core/schemas'
import type { TickEngine } from '../core/sim/engine'
import { OUTCOME_ONGOING } from '../core/sim/phases'
import { FACTION_ENEMY, createEntity } from '../core/sim/state'
import { TracingRuleVm } from './ruleTrace'

/** 템플릿에 없는 적을 한 마리 덧붙이는 지시. */
export interface ExtraEnemy {
  readonly kind: string
  readonly x: number
  readonly y: number
}

/** 전투 한 판을 특정하는 값들. 같은 값이면 같은 판이 나온다 (R5). */
export interface BattleSetup {
  readonly roomId: string
  readonly rulesetId: string
  readonly seed: number
  /**
   * 덧붙일 적. 방 다섯 개의 스폰이 전부 고블린 3종이라, 이것이 없으면 폭탄 슬라임의
   * 예고(TELEGRAPH 페이즈)나 대소환사의 소환이 한 번도 돌지 않는다 — 예고 타일을 눈으로
   * 확인할 수 없다는 뜻이다.
   */
  readonly extraEnemies?: readonly ExtraEnemy[]
  /**
   * 티켓이 얼려 둔 지속 몬스터 상태 (docs/설계/6_몬스터 §5).
   *
   * **이것이 없으면 브라우저와 서버가 다른 판을 돈다.** 서버는 티켓의 스냅샷으로
   * 재시뮬하므로, 화면이 기본 적을 그리는 동안 서버는 엘리트를 상대한다.
   */
  readonly snapshots?: readonly MonsterSnapshot[]
  /**
   * 티켓이 얼려 둔 플레이어 전투 입력 (장비·레벨).
   *
   * **이것이 없으면 화면은 맨몸으로 싸우고 서버는 장비를 낀 채로 재시뮬한다.**
   */
  readonly loadout?: PlayerLoadout
  /**
   * 티켓이 얼려 둔 층 (설계/6_몬스터 §3).
   *
   * **이것이 없으면 화면은 1층으로 싸우고 서버는 깊은 층으로 재시뮬한다.** 층 스케일이
   * 적의 HP·공격력에 얹히므로 두 판이 갈리고, 이긴 판이 진 것으로 확정된다 (G3).
   */
  readonly floor?: number
  /**
   * 이 판이 연쇄의 몇 번째 방인가.
   *
   * **앞 방들을 여기서 다시 돌린다.** 그래야 "같은 setup 이면 같은 판" (R5) 이 유지되고,
   * 사후 분석이 관전한 것과 같은 판을 본다 — 인계된 HP 를 setup 에 적어 두면 그 값을
   * 손으로 고쳐 강한 판을 만들 수 있다.
   */
  readonly chain?: ChainPosition
}

/** 연쇄에서의 위치. */
export interface ChainPosition {
  readonly roomIds: readonly string[]
  /** 0부터. 이 방을 관전한다. */
  readonly index: number
}

/** 조립된 판. 화면은 이 묶음만 들고 돈다. */
export interface BattleSession {
  readonly engine: TickEngine
  readonly template: RoomTemplate
  readonly ruleset: RuleSet
  readonly balance: BalanceData
  /** 플레이어 규칙표의 이번 틱 상태를 들고 있는 정책. */
  readonly tracer: TracingRuleVm
}

/** 덧붙인 적의 id 접미사. 템플릿 스폰의 `{종류}_{index}` 와 겹치면 한 쪽이 조용히 덮인다. */
const EXTRA_ID_INFIX = '_x'

/**
 * 방 id 로 템플릿을 찾는다.
 *
 * @param roomId 찾을 방 id.
 * @returns 룸 템플릿.
 * @throws 없는 방 id 인 경우.
 */
export function findRoomTemplate(roomId: string): RoomTemplate {
  const template = ROOM_TEMPLATES.find((one) => one.templateId === roomId)
  if (template === undefined) {
    throw new Error(`없는 방 id 다: ${roomId}`)
  }
  return template
}

/**
 * 템플릿에 없는 적을 방에 덧붙인다.
 *
 * @param engine 조립된 엔진.
 * @param balance 밸런스 값들.
 * @param extras 덧붙일 적들.
 * @throws balance.json 에 없는 적 종류인 경우.
 */
export function addExtraEnemies(
  engine: TickEngine,
  balance: BalanceData,
  extras: readonly ExtraEnemy[],
): void {
  const byId = new Map(balance.enemies.map((one) => [one.id, one]))
  extras.forEach((extra, index) => {
    const kind = byId.get(extra.kind)
    if (kind === undefined) {
      throw new Error(`balance.json 에 없는 적 종류다: ${extra.kind}`)
    }
    const entityId = `${extra.kind}${EXTRA_ID_INFIX}${String(index)}`
    engine.state.entities.set(
      entityId,
      createEntity({
        entityId,
        kindId: extra.kind,
        faction: FACTION_ENEMY,
        position: { x: extra.x, y: extra.y },
        hp: kind.hp_max,
        hpMax: kind.hp_max,
        attack: kind.attack,
        defense: kind.defense,
        attackRange: kind.attack_range,
        initiative: kind.initiative,
        regenBase: kind.regen_base ?? 0,
        cpuBudget: kind.cpu_budget ?? 0,
        consumables: new Map([['POTION', kind.potions ?? 0]]),
      }),
    )
  })
  engine.registerNewcomers()
}


/**
 * 방 하나짜리 판을 조립한다.
 *
 * @param setup 판을 특정하는 값들.
 * @param template 룸 템플릿.
 * @param ruleset 플레이어 규칙표.
 * @param balance 밸런스.
 * @param buildTracer 플레이어 정책을 만드는 것.
 * @returns 조립된 엔진.
 */
function buildSingleRoom(
  setup: BattleSetup,
  template: RoomTemplate,
  ruleset: RuleSet,
  balance: BalanceData,
  buildTracer: (engine: TickEngine, rules: RuleSet) => TracingRuleVm,
): TickEngine {
  const engine = buildEngine({
    template,
    balance,
    seed: setup.seed,
    snapshots: setup.snapshots ?? [],
    floor: setup.floor ?? 1,
    ...(setup.loadout === undefined ? {} : { loadout: setup.loadout }),
  })
  engine.policies.set(PLAYER_ENTITY_ID, buildTracer(engine, ruleset))
  assignEnemyPolicies(engine, balance, BLOCK_CATALOG, ENEMY_RULESETS)
  return engine
}

/**
 * 연쇄의 한 방을 조립한다. **앞 방들을 여기서 다시 돌린다.**
 *
 * 연쇄 규칙(시드 분기·HP 인계·층 압력)은 `ChainCursor` 하나에만 있다. 화면이 그것을 다시
 * 구현하면 헤드리스 경로와 갈려 "재현" 이 재현이 아니게 된다.
 *
 * @param setup 판을 특정하는 값들.
 * @param position 연쇄에서의 위치.
 * @param ruleset 플레이어 규칙표.
 * @param balance 밸런스.
 * @param buildTracer 관전할 방의 플레이어 정책을 만드는 것.
 * @returns 관전할 방의 엔진.
 * @throws 앞 방에서 이미 졌는데 뒷 방을 요구한 경우. 그 판은 존재하지 않는다.
 */
function buildChainRoom(
  setup: BattleSetup,
  position: ChainPosition,
  ruleset: RuleSet,
  balance: BalanceData,
  buildTracer: (engine: TickEngine, rules: RuleSet) => TracingRuleVm,
): TickEngine {
  const cursor = new ChainCursor({
    templates: position.roomIds.map(findRoomTemplate),
    balance,
    catalog: BLOCK_CATALOG,
    playerRuleset: ruleset,
    enemyRulesets: ENEMY_RULESETS,
    seed: setup.seed,
    snapshots: setup.snapshots ?? [],
    floor: setup.floor ?? 1,
    ...(setup.loadout === undefined ? {} : { loadout: setup.loadout }),
  })
  for (let index = 0; index < position.index; index += 1) {
    const past = cursor.buildNext()
    if (past === undefined) {
      throw new Error(`연쇄 ${String(position.index)}번 방에 닿을 수 없다 — 앞 방에서 졌다`)
    }
    cursor.recordRoom(runBattle(past))
  }
  const engine = cursor.buildNext(buildTracer)
  if (engine === undefined) {
    throw new Error(`연쇄 ${String(position.index)}번 방에 닿을 수 없다 — 앞 방에서 졌다`)
  }
  return engine
}

/**
 * 전투 한 판을 조립한다. 첫 틱은 아직 돌지 않았다.
 *
 * @param setup 방·규칙표·시드와 덧붙일 적.
 * @param rulesets 규칙표 id 대응표.
 * @returns 돌릴 준비가 된 판.
 * @throws 없는 방이거나 없는 규칙표인 경우.
 */
export function buildBattleSession(
  setup: BattleSetup,
  rulesets: ReadonlyMap<string, RuleSet>,
): BattleSession {
  const template = findRoomTemplate(setup.roomId)
  const ruleset = rulesets.get(setup.rulesetId)
  if (ruleset === undefined) {
    throw new Error(`없는 규칙표 id 다: ${setup.rulesetId}`)
  }
  const balance = parseBalance(BALANCE)
  let tracer: TracingRuleVm | undefined
  /**
   * 플레이어 정책에 추적기를 씌운다. 화면이 규칙 상태를 그리려면 필요하다.
   *
   * @param target 조립된 엔진.
   * @param rules 플레이어 규칙표.
   * @returns 추적기.
   */
  function buildTracer(target: TickEngine, rules: RuleSet): TracingRuleVm {
    tracer = new TracingRuleVm(buildRuleVm(rules, BLOCK_CATALOG, target.config.kindTypes), BLOCK_CATALOG)
    return tracer
  }

  const engine =
    setup.chain === undefined
      ? buildSingleRoom(setup, template, ruleset, balance, buildTracer)
      : buildChainRoom(setup, setup.chain, ruleset, balance, buildTracer)
  if (tracer === undefined) {
    throw new Error('플레이어 정책이 만들어지지 않았다')
  }
  addExtraEnemies(engine, balance, setup.extraEnemies ?? [])

  return { engine, template, ruleset, balance, tracer }
}

/**
 * 아직 승패가 갈리지 않았는가.
 *
 * @param outcome 마지막 판정.
 * @returns 진행 중이면 true.
 */
export function checkOngoing(outcome: string): boolean {
  return outcome === OUTCOME_ONGOING
}
