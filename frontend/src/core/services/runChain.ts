/**
 * 고정 맵 연쇄 실행 — 방 여러 개를 연속으로 돈다.
 *
 * **파이썬 `game/app/services/run_chain.py` 의 이식이다.** 같은 시드에서 비트 단위로
 * 같은 결과를 내야 한다 (게이트 G3).
 *
 * 규칙 편집은 방 사이에서만 가능하다는 규약(GDD §2.2)을 지키기 위해, 이 함수는 정책을
 * 방마다 다시 받지 않는다. 한 런 동안 같은 규칙표로 간다.
 *
 * 이식하면서 지켜야 하는 것이 셋이다. 하나라도 어긋나면 두 코어가 갈린다.
 *
 * 1. **방마다 시드를 가른다** (`seed + index * 1000`). 한 수열을 공유하면 앞 방의 전투
 *    길이가 바뀔 때 뒷 방의 이니셔티브 동률 처리까지 흔들려, 방 하나를 고쳤을 뿐인데
 *    전체가 달라진다 (R5).
 * 2. **압력 추적기는 층 단위다.** 방마다 새로 만들면 층 체류 스케일이 매 방 0 으로
 *    돌아가 GDD §7 의 '층 지연' 압력이 사라진다.
 * 3. **방을 넘어갈 때 방 체류 틱을 지운다.** entity_id 가 방마다 다시 붙으므로
 *    (어느 방에나 goblin_rusher_0 이 있다) 남기면 남의 기준값을 읽는다.
 */
import type { BlockCatalog } from '../schemas/blocks'
import type { PlayerLoadout } from '../schemas/loadout'
import type { MonsterSnapshot } from '../schemas/monsterSnapshot'
import type { RoomTemplate } from '../schemas/room'
import type { RuleSet } from '../schemas/ruleset'
import { buildRuleVm } from '../rules/ruleVm'
import type { DecisionPolicy } from '../sim/plan'
import type { TickEngine } from '../sim/engine'
import { OUTCOME_PLAYER_WIN } from '../sim/phases'
import { PressureTracker, buildPressureRules } from '../sim/pressure'
import type { Entity } from '../sim/state'
import {
  type BalanceData,
  type BattleResult,
  DEFAULT_MAX_TICKS,
  PLAYER_ENTITY_ID,
  assignEnemyPolicies,
  buildEngine,
  runBattle,
} from './runBattle'

/**
 * 방마다 시드를 가르는 간격.
 *
 * 파이썬과 **같은 값이어야 한다** — 다르면 두 코어가 두 번째 방부터 다른 판을 돈다.
 */
export const SEED_STRIDE = 1000

/**
 * 방 하나를 끝까지 돌리는 것.
 *
 * 기본값은 `runBattle` 이고, 관전은 틱을 끊어 도는 것을 넣는다 — 연쇄 진행 규칙
 * (시드 분기·HP 인계·층 압력)을 관전이 다시 구현하면 두 경로가 갈려 "재현" 이 재현이
 * 아니게 된다.
 */
export type RoomRunner = (engine: TickEngine) => BattleResult

/** 연쇄 한 판의 결과. */
export interface ChainResult {
  readonly clearedRooms: number
  readonly outcome: string
  readonly totalTicks: number
  readonly playerHp: number
  readonly perRoom: readonly BattleResult[]
}

/** `runRoomChain` 이 받는 값들. */
export interface ChainSetup {
  readonly templates: readonly RoomTemplate[]
  readonly balance: BalanceData
  readonly catalog: BlockCatalog
  /** 플레이어 규칙표. 없으면 폴백 정책을 쓴다. */
  readonly playerRuleset?: RuleSet
  readonly enemyRulesets: ReadonlyMap<string, RuleSet>
  readonly seed: number
  readonly maxTicks?: number
  /** 티켓이 얼려 둔 지속 몬스터 상태. 방마다 그 방의 것만 골라 쓴다. */
  readonly snapshots?: readonly MonsterSnapshot[]
  /** 티켓이 얼려 둔 플레이어 전투 입력. 첫 방에만 적용되고 이후는 인계된 HP 를 쓴다. */
  readonly loadout?: PlayerLoadout
  /** 방 하나를 돌리는 것. */
  readonly runRoom?: RoomRunner
}

/**
 * 플레이어 정책을 만드는 것.
 *
 * 화면은 규칙 추적기(`TracingRuleVm`)를 씌워야 규칙 상태를 그릴 수 있고, 헤드리스는
 * 그것이 필요 없다. **연쇄 규칙을 두 번 구현하지 않으려고** 이 자리만 갈아 끼운다.
 */
export type PlayerPolicyFactory = (engine: TickEngine, ruleset: RuleSet) => DecisionPolicy

/**
 * 연쇄를 한 방씩 진행시키는 커서.
 *
 * **연쇄 규칙(시드 분기·HP 인계·층 압력)이 사는 유일한 자리다.** 화면은 방을 끊어서
 * 관전하고 헤드리스는 한 번에 돌리는데, 둘이 각자 진행 규칙을 구현하면 두 경로가 갈려
 * "재현" 이 재현이 아니게 된다 — 파이썬 `run_chain.py` 가 `RoomRunner` 를 받는 것과
 * 같은 이유다.
 */
export class ChainCursor {
  private readonly setup: ChainSetup

  private readonly pressure: PressureTracker

  private readonly results: BattleResult[] = []

  private carriedHp: number | undefined

  private carriedPotions: ReadonlyMap<string, number> = new Map()

  private index = 0

  private cleared = 0

  private outcome: string = OUTCOME_PLAYER_WIN

  private current: Entity | undefined

  /**
   * 커서를 만든다.
   *
   * @param setup 방 목록·밸런스·규칙표·시드.
   */
  constructor(setup: ChainSetup) {
    this.setup = setup
    // 층 단위 객체다. 방마다 새로 만들면 층 체류 스케일이 매 방 0 으로 돌아가
    // GDD §7 의 '층 지연' 압력이 사라진다.
    this.pressure = new PressureTracker(
      buildPressureRules(setup.balance.antiAbuse),
      new Map(setup.balance.enemies.map((kind) => [kind.id, kind])),
    )
  }

  /** 이제 돌 방이 남아 있는가. 진 판이면 남아 있어도 끝이다. */
  get isDone(): boolean {
    return this.outcome !== OUTCOME_PLAYER_WIN || this.index >= this.setup.templates.length
  }

  /** 지금까지 돈 방 수 (0부터). */
  get roomIndex(): number {
    return this.index
  }

  /**
   * 다음 방의 엔진을 조립한다. 인계와 압력이 여기서 적용된다.
   *
   * @param buildPolicy 플레이어 정책을 만드는 것. 생략하면 규칙 VM 을 그대로 쓴다.
   * @returns 조립된 엔진. 남은 방이 없으면 undefined.
   * @throws 플레이어 엔티티가 없는 경우. 조립이 잘못된 것이다.
   */
  buildNext(buildPolicy?: PlayerPolicyFactory): TickEngine | undefined {
    if (this.isDone) {
      return undefined
    }
    const template = this.setup.templates[this.index]
    if (template === undefined) {
      return undefined
    }
    // 방을 넘어가면 방 체류 틱과 기준 공격력을 지운다. entity_id 가 방마다 다시
    // 붙으므로(어느 방에나 goblin_rusher_0 이 있다) 남기면 남의 기준값을 읽는다.
    this.pressure.resetRoom()
    const engine = buildEngine({
      template,
      balance: this.setup.balance,
      seed: this.setup.seed + this.index * SEED_STRIDE,
      maxTicks: this.setup.maxTicks ?? DEFAULT_MAX_TICKS,
      pressure: this.pressure,
      snapshots: this.setup.snapshots ?? [],
      ...(this.setup.loadout === undefined ? {} : { loadout: this.setup.loadout }),
    })
    const player = engine.state.entities.get(PLAYER_ENTITY_ID)
    if (player === undefined) {
      throw new Error(`플레이어 엔티티가 없다: ${PLAYER_ENTITY_ID}`)
    }
    if (this.carriedHp !== undefined) {
      // **HP 와 포션만 인계한다.** 스탯까지 인계하면 압력 스케일이 두 번 얹힌다.
      player.hp = this.carriedHp
      player.consumables = new Map(this.carriedPotions)
    }
    const ruleset = this.setup.playerRuleset
    if (ruleset !== undefined) {
      const factory =
        buildPolicy ??
        ((target: TickEngine, rules: RuleSet) =>
          buildRuleVm(rules, this.setup.catalog, target.config.kindTypes))
      engine.policies.set(PLAYER_ENTITY_ID, factory(engine, ruleset))
    }
    assignEnemyPolicies(engine, this.setup.balance, this.setup.catalog, this.setup.enemyRulesets)
    this.current = player
    return engine
  }

  /**
   * 방 하나의 결과를 반영한다.
   *
   * @param result 그 방의 결과.
   */
  recordRoom(result: BattleResult): void {
    this.results.push(result)
    this.outcome = result.outcome
    this.index += 1
    if (result.outcome !== OUTCOME_PLAYER_WIN) {
      return
    }
    this.cleared += 1
    this.carriedHp = result.playerHp
    this.carriedPotions = new Map(this.current?.consumables ?? [])
  }

  /** 지금까지의 연쇄 결과. */
  get result(): ChainResult {
    return {
      clearedRooms: this.cleared,
      outcome: this.results.length === 0 ? OUTCOME_PLAYER_WIN : this.outcome,
      totalTicks: this.results.reduce((sum, result) => sum + result.ticks, 0),
      playerHp: this.results.length === 0 ? 0 : (this.results[this.results.length - 1]?.playerHp ?? 0),
      perRoom: [...this.results],
    }
  }
}

/**
 * 방들을 순서대로 돌고 결과를 모은다.
 *
 * @param setup 방 목록·밸런스·규칙표·시드.
 * @returns 연쇄 결과. 진 방에서 멈추고 그때까지의 것을 담는다.
 */
export function runRoomChain(setup: ChainSetup): ChainResult {
  const runRoom = setup.runRoom ?? runBattle
  const cursor = new ChainCursor(setup)
  for (;;) {
    const engine = cursor.buildNext()
    if (engine === undefined) {
      break
    }
    cursor.recordRoom(runRoom(engine))
  }
  return cursor.result
}
