/**
 * 시뮬레이션 이식의 골든 대조 — 게이트 G3.
 *
 * 보는 것은 "그럴듯하게 도는가" 가 아니라 "파이썬 코어와 **같은 결과**를 내는가" 다.
 * 기준은 `scripts/export_sim_golden.py` 가 파이썬 쪽에서 뽑아 둔 `sim_golden.json` 이고,
 * 여기서는 같은 방·같은 시드·같은 정책으로 돌려 로그 전문까지 줄 단위로 맞춘다.
 *
 * 로그를 통째로 비교하는 이유는 어긋난 지점을 좁히기 위해서다. 승패만 보면 난수를 한 번
 * 더 뽑는 버그가 대개 통과하고, 통과하지 않을 때는 어디서 갈렸는지 알 수 없다.
 *
 * 기준 파일이 틀렸다고 판단해 손으로 고치지 않는다 — 값이 어긋나면 이 쪽이 틀린 것이다.
 */
import { describe, expect, it } from 'vitest'

import golden from '../golden/sim_golden.json'
import { BALANCE, ROOM_TEMPLATES } from '../resources'
import { getManhattanDistance } from '../grid/geometry'
import { ACTION_COUNT } from '../schemas'
import {
  buildEngine,
  parseBalance,
  runBattle,
  type BalanceData,
} from '../services/runBattle'
import type { TickEngine } from './engine'
import type { PerceptionSnapshot } from './perception'
import {
  type DecisionPolicy,
  type PlannedAction,
  type RawEnemyKind,
  createPlannedAction,
} from './plan'
import { getScaledEnemyStats } from './scaling'
import { SELECTOR_NEAREST, resolveTarget } from './selectors'
import { FACTION_ENEMY, type Entity, type WorldState, createEntity } from './state'

const POLICY_CYCLE = 'cycle'

/** 기준 문서에 적힌 덧붙일 적 하나. */
interface GoldenExtra {
  readonly kind: string
  readonly x: number
  readonly y: number
}

/** 기준 문서에 적힌 개체의 최종 상태. */
interface GoldenEntity {
  readonly entity_id: string
  readonly hp: number
  readonly x: number
  readonly y: number
  readonly attack: number
  readonly potions: number
  readonly cooldowns: Readonly<Record<string, number>>
  readonly flags: Readonly<Record<string, boolean>>
}

/** 기준 문서의 전투 한 판. */
interface GoldenBattle {
  readonly template_id: string
  readonly seed: number
  readonly policy: string
  readonly max_ticks: number
  readonly floor: number
  readonly extra_enemies: readonly GoldenExtra[]
  readonly outcome: string
  readonly ticks: number
  readonly player_hp: number
  readonly spawn_counter: number
  readonly entities: readonly GoldenEntity[]
  readonly log_line_count: number
  readonly log_lines: readonly string[]
}

const ACTION_CYCLE: readonly string[] = golden.action_cycle

/** 행동별 대상 셀렉터. 파이썬 쪽 `CYCLE_SELECTORS` 와 같은 표다. */
const CYCLE_SELECTORS: ReadonlyMap<string, string> = new Map(
  (golden.cycle_selectors as readonly string[][]).map((pair) => [pair[0] ?? '', pair[1] ?? '']),
)
const CYCLE_FLAG: string = golden.cycle_flag
const BATTLES = golden.battles as readonly GoldenBattle[]

/**
 * 틱과 엔티티 id 만 보고 행동 14개를 차례로 내는 대조 전용 결정기.
 *
 * `scripts/export_sim_golden.py` 의 `CyclingPolicy` 와 같은 것이어야 한다. 폴백 정책은
 * 접근·공격·포션·대기 넷만 내므로 나머지 행동 아홉 개 — 소환·예고·엄폐 이동·플래그 —
 * 는 이 정책으로만 검증된다.
 */
class CyclingPolicy implements DecisionPolicy {
  /**
   * 대상 선택에 쓸 종류 표를 받는다.
   *
   * @param kindTypes 엔티티 종류에서 적 유형으로의 대응표.
   */
  constructor(private readonly kindTypes: ReadonlyMap<string, string>) {}

  /**
   * 이번 틱의 행동을 정한다. 부작용을 내지 않는다.
   *
   * @param entity 결정 대상.
   * @param snapshot PERCEPTION 이 고정한 값들. 이 정책은 틱만 읽는다.
   * @param state 세계 상태. 읽기만 한다.
   * @returns 실행할 계획.
   */
  planAction(entity: Entity, snapshot: PerceptionSnapshot, state: WorldState): PlannedAction {
    let offset = 0
    for (const char of entity.entityId) {
      offset += char.codePointAt(0) ?? 0
    }
    const index = (snapshot.tick + offset) % ACTION_CYCLE.length
    const actionId = ACTION_CYCLE[index] as string
    const selectorId = CYCLE_SELECTORS.get(actionId) ?? SELECTOR_NEAREST
    const target = resolveTarget(selectorId, entity, state, this.kindTypes)
    return createPlannedAction({
      entityId: entity.entityId,
      actionId,
      targetId: target === undefined ? null : target.entityId,
      ruleIndex: index,
      expr: `틱(${snapshot.tick}) + 오프셋(${offset}) % ${ACTION_CYCLE.length} = ${index}`,
      setFlag: actionId === 'SET_FLAG' ? CYCLE_FLAG : null,
    })
  }
}

/**
 * 템플릿에 없는 적을 방에 덧붙인다. 파이썬 쪽 `add_extra_enemies` 와 같은 순서·같은 id 다.
 *
 * @param engine 조립된 엔진.
 * @param balance 밸런스 값.
 * @param extras 덧붙일 적 목록.
 */
function addExtraEnemies(
  engine: TickEngine,
  balance: BalanceData,
  extras: readonly GoldenExtra[],
): void {
  const byId = new Map<string, RawEnemyKind>(balance.enemies.map((kind) => [kind.id, kind]))
  extras.forEach((extra, index) => {
    const kind = byId.get(extra.kind)
    if (kind === undefined) {
      throw new Error(`balance.json 에 없는 적 종류다: ${extra.kind}`)
    }
    // 층 깊이 스케일을 방 배치와 같은 함수로 건다 (파이썬 `add_extra_enemies` 와 같다).
    const scaled = getScaledEnemyStats(kind, engine.config.floorScale, engine.config.floor)
    const entityId = `${extra.kind}_x${index}`
    engine.state.entities.set(
      entityId,
      createEntity({
        entityId,
        kindId: extra.kind,
        faction: FACTION_ENEMY,
        position: { x: extra.x, y: extra.y },
        hp: scaled.hpMax,
        hpMax: scaled.hpMax,
        attack: scaled.attack,
        defense: kind.defense,
        attackRange: kind.attack_range,
        initiative: kind.initiative,
        regenBase: kind.regen_base ?? 0,
        cpuBudget: kind.cpu_budget ?? 0,
        potions: kind.potions ?? 0,
      }),
    )
  })
  engine.registerNewcomers()
}

/**
 * 기준 문서 한 건과 같은 조건으로 전투를 조립해 돌린다.
 *
 * @param battle 기준 전투.
 * @returns 결과와 엔진.
 */
function runGoldenBattle(battle: GoldenBattle): { engine: TickEngine } {
  const balance = parseBalance(BALANCE)
  const template = ROOM_TEMPLATES.find((item) => item.templateId === battle.template_id)
  if (template === undefined) {
    throw new Error(`룸 템플릿이 없다: ${battle.template_id}`)
  }
  const engine = buildEngine({
    template,
    balance,
    seed: battle.seed,
    maxTicks: battle.max_ticks,
    floor: battle.floor,
  })
  if (battle.policy === POLICY_CYCLE) {
    engine.policy = new CyclingPolicy(
      new Map(balance.enemies.map((kind) => [kind.id, kind.type])),
    )
  }
  if (battle.extra_enemies.length > 0) {
    addExtraEnemies(engine, balance, battle.extra_enemies)
  }
  return { engine }
}

/**
 * 전투가 끝난 시점의 개체 상태를 기준 문서와 같은 모양으로 편다.
 *
 * @param state 세계 상태.
 * @returns entityId 사전순의 상태 목록.
 */
function buildEntityRows(state: WorldState): GoldenEntity[] {
  return [...state.entities.keys()]
    .sort()
    .map((entityId) => {
      const entity = state.entities.get(entityId) as Entity
      return {
        entity_id: entityId,
        hp: entity.hp,
        x: entity.position.x,
        y: entity.position.y,
        attack: entity.attack,
        potions: entity.potions,
        cooldowns: Object.fromEntries([...entity.cooldowns.entries()].sort()),
        flags: Object.fromEntries([...entity.flags.entries()].sort()),
      }
    })
}

describe('시뮬레이션 골든 대조', () => {
  it('기준 문서가 두 정책을 모두 담고 있다', () => {
    expect(BATTLES.length).toBeGreaterThan(0)
    expect(BATTLES.some((battle) => battle.policy === POLICY_CYCLE)).toBe(true)
    expect(ACTION_CYCLE).toHaveLength(ACTION_COUNT)
  })

  for (const battle of BATTLES) {
    const label = `${battle.template_id} / seed ${battle.seed} / ${battle.policy}`

    it(`${label} — 결과와 로그가 파이썬과 같다`, () => {
      const { engine } = runGoldenBattle(battle)
      const result = runBattle(engine)

      // 줄 수를 먼저 본다. 어긋났을 때 1000줄짜리 diff 대신 개수부터 드러난다.
      expect(result.logLines.length).toBe(battle.log_line_count)
      for (let index = 0; index < battle.log_lines.length; index += 1) {
        expect(`${index}: ${result.logLines[index] ?? ''}`).toBe(
          `${index}: ${battle.log_lines[index] ?? ''}`,
        )
      }
      expect(result.outcome).toBe(battle.outcome)
      expect(result.ticks).toBe(battle.ticks)
      expect(result.playerHp).toBe(battle.player_hp)
      expect(engine.state.spawnCounter).toBe(battle.spawn_counter)
      expect(buildEntityRows(engine.state)).toEqual(battle.entities)
    })
  }
})

describe('결정론', () => {
  it('같은 시드를 두 번 돌리면 같은 로그가 나온다', () => {
    const battle = BATTLES[0] as GoldenBattle
    const first = runBattle(runGoldenBattle(battle).engine)
    const second = runBattle(runGoldenBattle(battle).engine)
    expect(second.logLines).toEqual(first.logLines)
  })

  it('시드가 다르면 난수를 쓰는 판의 로그가 갈린다', () => {
    const battle = BATTLES.find((item) => item.policy === POLICY_CYCLE) as GoldenBattle
    const same = runBattle(runGoldenBattle(battle).engine)
    const other = runBattle(runGoldenBattle({ ...battle, seed: battle.seed + 1 }).engine)
    expect(other.logLines).not.toEqual(same.logLines)
  })
})

describe('셀렉터와 거리', () => {
  it('맨해튼 거리는 대각을 두 칸으로 센다', () => {
    expect(getManhattanDistance({ x: 0, y: 0 }, { x: 1, y: 1 })).toBe(2)
  })
})
