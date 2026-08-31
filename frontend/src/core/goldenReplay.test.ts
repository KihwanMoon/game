/**
 * 골든 리플레이 대조 — 게이트 G3.
 *
 * 보는 것은 "그럴듯하게 도는가" 가 아니라 "파이썬 코어와 **같은 결과**를 내는가" 다.
 * 기준은 `scripts/export_golden.py` 가 파이썬 쪽에서 뽑아 둔 `__golden__/cases.json` 이고,
 * 여기서는 같은 방·같은 시드·같은 규칙표로 돌려 이벤트 로그 전문까지 필드 단위로 맞춘다.
 *
 * `sim/sim.test.ts` 와 겹치지 않는다. 그쪽은 폴백·순환 정책으로 엔진의 실행 경로를 고정하고,
 * 이쪽은 **RuleVM 이 걸린 실제 배선** — 플레이어 규칙표 + 적 규칙표 + 소환물 공장 — 을 고정한다.
 * RuleVM 이 규칙 하나를 다르게 평가하면 이 대조만 깨진다.
 *
 * 어긋났을 때 첫 번째로 갈라진 지점을 지목하는 것이 이 파일의 설계 목표다. 로그 3천 줄을
 * 통째로 diff 로 뱉으면 읽을 수 없으므로, `findFirstMismatch` 가 최초 불일치의 인덱스·틱·
 * 필드·양쪽 값을 한 줄로 만들어 그것만 실패 메시지에 싣는다.
 *
 * 기준 파일이 틀렸다고 판단해 손으로 고치지 않는다 — 값이 어긋나면 이 쪽이 틀린 것이다.
 */
import { describe, expect, it } from 'vitest'

import golden from './__golden__/cases.json'
import {
  BALANCE,
  BENCHMARK_RULESETS,
  BLOCK_CATALOG,
  ENEMY_RULESETS,
  G0_RULESETS,
  ROOM_TEMPLATES,
} from './resources'
import { buildRuleVm } from './rules/ruleVm'
import type { RuleSet } from './schemas'
import type { TickEngine } from './sim/engine'
import { OUTCOME_ONGOING } from './sim/plan'
import { getScaledEnemyStats } from './sim/scaling'
import {
  assignEnemyPolicies,
  buildEngine,
  parseBalance,
  type BalanceData,
} from './services/runBattle'
import { countItem, FACTION_ENEMY, createEntity } from './sim/state'

/** 기준 문서에 적힌 로그 한 줄. 필드 이름은 파이썬 `LogEntry` 를 그대로 따른다. */
interface GoldenLogRow {
  readonly tick: number
  readonly entity_id: string
  readonly phase: string
  readonly expr: string
  readonly outcome: string
  readonly rule: number | null
  readonly delta: number | null
  readonly fired: boolean
  readonly target_id: string | null
}

/** 기준 문서에 적힌, 템플릿 밖에서 덧붙인 적 하나. */
interface GoldenExtra {
  readonly kind: string
  readonly x: number
  readonly y: number
}

/** 기준 문서에 적힌 개체의 최종 상태. */
interface GoldenEntity {
  readonly entity_id: string
  readonly kind_id: string
  readonly hp: number
  readonly x: number
  readonly y: number
  readonly attack: number
  readonly potions: number
  readonly cooldowns: Readonly<Record<string, number>>
  readonly flags: Readonly<Record<string, boolean>>
}

/** 기준 문서의 케이스 하나. */
interface GoldenCase {
  readonly case_id: string
  readonly room_id: string
  readonly ruleset_id: string
  readonly seed: number
  readonly extra_enemies: readonly GoldenExtra[]
  readonly max_ticks: number
  readonly floor: number
  readonly outcome: string
  readonly ticks: number
  readonly player_hp: number
  readonly spawn_counter: number
  readonly entities: readonly GoldenEntity[]
  readonly log_count: number
  readonly log: readonly GoldenLogRow[]
}

const PLAYER_ID: string = golden.player_id
const CASES = golden.cases as readonly GoldenCase[]

/** 최소 케이스 수. 방 5개 × 규칙표 3종이 하한이며, 줄어들면 대조 범위가 조용히 좁아진다. */
const MIN_CASE_COUNT = 12

/** 규칙표를 찾을 곳들. g0 예시가 먼저이고, 없으면 벤치마크에서 찾는다. */
const RULESET_SOURCES: readonly ReadonlyMap<string, RuleSet>[] = [G0_RULESETS, BENCHMARK_RULESETS]

const BALANCE_DATA: BalanceData = parseBalance(BALANCE)

/**
 * id 로 규칙표를 찾는다.
 *
 * @param rulesetId 찾을 규칙표 id.
 * @returns 찾은 규칙표.
 * @throws 어느 파일에도 그 id 가 없는 경우.
 */
function findRuleSet(rulesetId: string): RuleSet {
  for (const source of RULESET_SOURCES) {
    const found = source.get(rulesetId)
    if (found !== undefined) {
      return found
    }
  }
  throw new Error(`규칙표가 없다: ${rulesetId}`)
}

/**
 * id 로 룸 템플릿을 찾는다.
 *
 * @param roomId 찾을 방 id.
 * @returns 찾은 템플릿.
 * @throws 그 id 의 템플릿이 없는 경우.
 */
function findRoomTemplate(roomId: string) {
  const found = ROOM_TEMPLATES.find((template) => template.templateId === roomId)
  if (found === undefined) {
    throw new Error(`룸 템플릿이 없다: ${roomId}`)
  }
  return found
}

/**
 * 파이썬 `export_golden.build_case_engine` 과 같은 순서로 엔진을 조립한다.
 *
 * 플레이어 규칙표를 먼저 걸고 적 규칙표를 나중에 붙인다. 순서를 바꾸면
 * `assignEnemyPolicies` 안의 `registerNewcomers` 가 플레이어 자리를 공장으로 먼저 채워
 * 규칙표가 조용히 덮인다.
 *
 * @param goldenCase 재현할 케이스.
 * @returns 첫 틱을 돌릴 준비가 된 엔진.
 */
function buildCaseEngine(goldenCase: GoldenCase): TickEngine {
  const engine = buildEngine({
    template: findRoomTemplate(goldenCase.room_id),
    balance: BALANCE_DATA,
    seed: goldenCase.seed,
    maxTicks: goldenCase.max_ticks,
    floor: goldenCase.floor,
  })
  engine.policies.set(
    PLAYER_ID,
    buildRuleVm(findRuleSet(goldenCase.ruleset_id), BLOCK_CATALOG, engine.config.kindTypes),
  )
  assignEnemyPolicies(engine, BALANCE_DATA, BLOCK_CATALOG, ENEMY_RULESETS)
  if (goldenCase.extra_enemies.length > 0) {
    addExtraEnemies(engine, goldenCase.extra_enemies)
  }
  return engine
}

/**
 * 템플릿에 없는 적을 방에 덧붙인다 (파이썬 `add_extra_enemies` 의 이식).
 *
 * 방 다섯 개의 스폰이 전부 고블린 3종이라, 이것이 없으면 폭탄 슬라임·수복사·대소환사·
 * 장궁병의 규칙표가 한 번도 돌지 않는다. id 는 `{종류}_x{순번}` 이며 템플릿 스폰의
 * `_{index}` 와 겹치지 않아야 한 쪽이 조용히 덮이지 않는다.
 *
 * @param engine 조립된 엔진.
 * @param extras 덧붙일 적 목록.
 * @throws 그 종류가 balance.json 에 없는 경우.
 */
function addExtraEnemies(engine: TickEngine, extras: readonly GoldenExtra[]): void {
  const byId = new Map(BALANCE_DATA.enemies.map((one) => [one.id, one]))
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
        consumables: new Map([['POTION', kind.potions ?? 0]]),
      }),
    )
  })
  engine.registerNewcomers()
}

/**
 * 엔진의 로그를 기준 문서와 같은 형태로 편다.
 *
 * @param engine 다 돌린 엔진.
 * @returns 남긴 순서 그대로의 행들.
 */
function buildLogRows(engine: TickEngine): GoldenLogRow[] {
  return engine.log.entries.map((entry) => ({
    tick: entry.tick,
    entity_id: entry.entityId,
    phase: entry.phase,
    expr: entry.expr,
    outcome: entry.outcome,
    rule: entry.rule,
    delta: entry.delta,
    fired: entry.fired,
    target_id: entry.targetId,
  }))
}

/**
 * 엔진의 최종 개체 상태를 기준 문서와 같은 형태로 편다.
 *
 * @param engine 다 돌린 엔진.
 * @returns entity_id 사전순의 상태 목록. 죽은 개체도 남긴다.
 */
function buildEntityRows(engine: TickEngine): GoldenEntity[] {
  const ids = [...engine.state.entities.keys()].sort()
  return ids.map((entityId) => {
    const entity = engine.state.entities.get(entityId)
    if (entity === undefined) {
      throw new Error(`엔티티가 사라졌다: ${entityId}`)
    }
    return {
      entity_id: entityId,
      kind_id: entity.kindId,
      hp: entity.hp,
      x: entity.position.x,
      y: entity.position.y,
      attack: entity.attack,
      potions: countItem(entity, 'POTION'),
      cooldowns: sortMapEntries(entity.cooldowns),
      flags: sortMapEntries(entity.flags),
    }
  })
}

/**
 * Map 을 열쇠 사전순의 평범한 객체로 편다. 파이썬의 `sorted(dict)` 와 같은 순서다.
 *
 * @param source 펼 대응표.
 * @returns 열쇠 사전순의 객체.
 */
function sortMapEntries<ValueT>(source: ReadonlyMap<string, ValueT>): Record<string, ValueT> {
  const result: Record<string, ValueT> = {}
  for (const key of [...source.keys()].sort()) {
    result[key] = source.get(key) as ValueT
  }
  return result
}

/**
 * 로그 두 벌에서 **처음** 어긋난 자리를 찾아 사람이 읽을 한 줄로 만든다.
 *
 * 3천 줄을 통째로 diff 로 뱉으면 어디서 갈렸는지 읽어 낼 수 없다. 최초 불일치 하나만
 * 지목하면 그 틱의 그 페이즈만 보면 된다.
 *
 * @param actual TS 코어가 낸 로그.
 * @param expected 파이썬 코어가 낸 기준 로그.
 * @returns 어긋난 자리를 적은 문자열. 완전히 같으면 빈 문자열.
 */
function findFirstMismatch(
  actual: readonly GoldenLogRow[],
  expected: readonly GoldenLogRow[],
): string {
  const shared = Math.min(actual.length, expected.length)
  for (let index = 0; index < shared; index += 1) {
    const left = actual[index] as unknown as Record<string, unknown>
    const right = expected[index] as unknown as Record<string, unknown>
    for (const field of golden.log_fields) {
      if (left[field] !== right[field]) {
        return (
          `로그 #${index} (틱 ${String(right.tick)}, ${String(right.entity_id)}, ` +
          `${String(right.phase)}) 의 ${field} 가 다르다 — ` +
          `TS=${JSON.stringify(left[field])} PY=${JSON.stringify(right[field])}\n` +
          `  TS 전체: ${JSON.stringify(left)}\n  PY 전체: ${JSON.stringify(right)}`
        )
      }
    }
  }
  if (actual.length !== expected.length) {
    const index = shared
    const extra = actual.length > expected.length ? actual[index] : expected[index]
    const side = actual.length > expected.length ? 'TS 에만' : 'PY 에만'
    return (
      `로그 길이가 다르다 — TS=${actual.length} PY=${expected.length}. ` +
      `#${index} 는 ${side} 있다: ${JSON.stringify(extra)}`
    )
  }
  return ''
}

describe('골든 리플레이 대조 (게이트 G3)', () => {
  it('기준 문서가 최소 케이스 수를 채운다', () => {
    expect(CASES.length).toBe(golden.case_count)
    expect(CASES.length).toBeGreaterThanOrEqual(MIN_CASE_COUNT)
    expect(new Set(CASES.map((one) => one.case_id)).size).toBe(CASES.length)
    expect(new Set(CASES.map((one) => one.room_id)).size).toBe(ROOM_TEMPLATES.length)
    expect(new Set(CASES.map((one) => one.ruleset_id)).size).toBeGreaterThanOrEqual(3)
  })

  it('기준 문서가 템플릿 밖 적까지 태운다', () => {
    // 방 다섯 개의 스폰은 전부 고블린 3종이다. 덧붙인 적이 없으면 폭탄 슬라임의 예고와
    // 대소환사의 소환이 한 번도 돌지 않아, 그 경로가 갈려도 대조가 통과한다.
    const kinds = new Set(CASES.flatMap((one) => one.extra_enemies.map((extra) => extra.kind)))
    expect(kinds.size).toBeGreaterThan(0)
    const phases = new Set(CASES.flatMap((one) => one.log.map((row) => row.phase)))
    expect(phases.has('TELEGRAPH')).toBe(true)
    expect(CASES.some((one) => one.spawn_counter > 0)).toBe(true)
  })

  it('기준 문서가 승·패 양쪽을 담는다', () => {
    const outcomes = new Set(CASES.map((one) => one.outcome))
    expect(outcomes.size).toBeGreaterThan(1)
  })

  for (const goldenCase of CASES) {
    describe(goldenCase.case_id, () => {
      const engine = buildCaseEngine(goldenCase)
      let outcome = OUTCOME_ONGOING
      while (outcome === OUTCOME_ONGOING) {
        outcome = engine.runTick()
      }
      const logRows = buildLogRows(engine)

      it('이벤트 로그가 필드까지 같다', () => {
        expect(findFirstMismatch(logRows, goldenCase.log)).toBe('')
        expect(logRows.length).toBe(goldenCase.log_count)
      })

      it('승패·틱·플레이어 HP 가 같다', () => {
        const player = engine.state.entities.get(PLAYER_ID)
        expect(player).toBeDefined()
        expect(outcome).toBe(goldenCase.outcome)
        expect(engine.state.tick).toBe(goldenCase.ticks)
        expect(player?.hp).toBe(goldenCase.player_hp)
      })

      it('최종 개체 상태와 소환 카운터가 같다', () => {
        expect(engine.state.spawnCounter).toBe(goldenCase.spawn_counter)
        expect(buildEntityRows(engine)).toEqual(goldenCase.entities)
      })
    })
  }
})
