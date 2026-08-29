/**
 * RuleVM·검증기·셀렉터의 골든 테스트 (TDD §5, 게이트 G3).
 *
 * "그럴듯한 판단인가" 가 아니라 "파이썬 코어와 같은 답인가" 를 본다. 기준값은
 * `scripts/export_rules_golden.py` 가 파이썬 코어에서 뽑아 둔 것이며, 여기서 값을 고쳐
 * 통과시키는 것은 검증을 지우는 것과 같다 — 기준을 바꾸려면 파이썬 쪽을 먼저 본다.
 *
 * 위반 메시지와 조건 문자열은 **목록을 통째로** 대조한다. 항목마다 `toContain` 으로 보면
 * 순서가 뒤집혀도, 있어야 할 메시지가 하나 빠져도 통과한다. 규칙 에디터는 첫 줄을 띄우고
 * 로그는 항을 이어 붙이므로 순서가 곧 화면이다 (P1).
 *
 * 세계는 골든에 적힌 엔티티 배치로 여기서 직접 세운다. 서비스 계층이 아직 이식되지
 * 않아 `build_engine` 에 대응하는 것이 없기 때문이며, 같은 파일을 양쪽이 읽으므로 입력이
 * 갈릴 여지가 없다.
 */

import { beforeAll, describe, expect, it } from 'vitest'

import goldenRaw from '../golden/rules_golden.json'
import { DeterministicRng } from '../rng'
import {
  BENCHMARK_RULESETS,
  BLOCK_CATALOG,
  ENEMY_RULESETS,
  G0_RULESETS,
  ROOM_TEMPLATES,
} from '../resources'
import {
  type Condition,
  type RawRuleSet,
  type RoomTemplate,
  type RuleSet,
  parseRuleSet,
} from '../schemas'
import { type PerceptionSnapshot, buildSnapshot } from '../sim/perception'
import type { PlannedAction } from '../sim/plan'
import { type Entity, WorldState, createEntity } from '../sim/state'

import { FallbackPolicy } from './fallbackPolicy'
import { RHS_STAT_READERS, buildRuleVm, countCpuUsage, evaluateCondition } from './ruleVm'
import { ALL_SELECTORS, resolveTarget } from './selectors'
import { validateRuleSet } from './validator'

interface GoldenEntity {
  readonly entity_id: string
  readonly kind_id: string
  readonly faction: string
  readonly position: readonly number[]
  readonly hp: number
  readonly hp_max: number
  readonly attack: number
  readonly defense: number
  readonly attack_range: number
  readonly initiative: number
  readonly regen_base: number
  readonly cpu_budget: number
  readonly potions: number
}

interface GoldenWorld {
  readonly world_id: string
  readonly room_id: string
  readonly tick: number
  readonly casting_ids: readonly string[]
  readonly entities: readonly GoldenEntity[]
}

interface GoldenSnapshot {
  readonly world_id: string
  readonly entity_id: string
  readonly values: readonly (readonly (string | number | boolean)[])[]
}

interface GoldenSelector {
  readonly world_id: string
  readonly actor_id: string
  readonly selector: string
  readonly picked_id: string | null
}

interface GoldenValidator {
  readonly name: string
  readonly ruleset?: RawRuleSet
  readonly ruleset_ref?: readonly string[]
  readonly cpu_budget: number
  readonly rule_slots: number
  readonly unlocked: readonly string[] | null
  readonly problems: readonly string[]
}

interface GoldenCondition {
  readonly name: string
  readonly world_id: string
  readonly target_id: string | null
  readonly cpu_headroom: number | null
  readonly condition: { readonly op: string; readonly terms: readonly unknown[] }
  readonly fired: boolean
  readonly expr: string
}

interface GoldenPlan {
  readonly entity_id: string
  readonly action_id: string
  readonly target_id: string | null
  readonly rule_index: number | null
  readonly expr: string
  readonly set_flag: string | null
}

interface GoldenRuleVm {
  readonly name: string
  readonly world_id: string
  readonly ruleset?: RawRuleSet
  readonly ruleset_ref?: readonly string[]
  readonly cpu_usage: number
  readonly plan: GoldenPlan
}

interface GoldenFallback {
  readonly world_id: string
  readonly plan: GoldenPlan
}

interface GoldenDocument {
  readonly kind_types: readonly (readonly string[])[]
  readonly worlds: readonly GoldenWorld[]
  readonly snapshots: readonly GoldenSnapshot[]
  readonly selectors: readonly GoldenSelector[]
  readonly validator: readonly GoldenValidator[]
  readonly conditions: readonly GoldenCondition[]
  readonly rule_vm: readonly GoldenRuleVm[]
  readonly fallback: readonly GoldenFallback[]
}

const golden = goldenRaw as unknown as GoldenDocument

/** 세계 상태가 난수원을 요구하지만 이 테스트는 난수를 뽑지 않는다. */
const RNG_SEED = 0

const KIND_TYPES: ReadonlyMap<string, string> = new Map(
  golden.kind_types.map((pair) => [pair[0] as string, pair[1] as string]),
)

const ROOMS: ReadonlyMap<string, RoomTemplate> = new Map(
  ROOM_TEMPLATES.map((template) => [template.templateId, template]),
)

/** 자원 파일 별칭에서 규칙표 목록으로. 골든의 `ruleset_ref` 가 이 이름을 쓴다. */
const RULESET_FILES: ReadonlyMap<string, ReadonlyMap<string, RuleSet>> = new Map([
  ['g0', G0_RULESETS],
  ['enemies', ENEMY_RULESETS],
  ['benchmark', BENCHMARK_RULESETS],
])

/**
 * 골든의 세계 명세로 세계 상태를 세운다.
 *
 * @param spec 세계 명세.
 * @returns 엔티티가 배치된 세계 상태.
 */
function createWorld(spec: GoldenWorld): WorldState {
  const room = ROOMS.get(spec.room_id)
  if (room === undefined) {
    throw new Error(`골든이 가리키는 룸 템플릿이 없다: ${spec.room_id}`)
  }
  const state = new WorldState(room, new DeterministicRng(RNG_SEED))
  for (const raw of spec.entities) {
    const entity = createEntity({
      entityId: raw.entity_id,
      kindId: raw.kind_id,
      faction: raw.faction,
      position: { x: raw.position[0] as number, y: raw.position[1] as number },
      hp: raw.hp,
      hpMax: raw.hp_max,
      attack: raw.attack,
      defense: raw.defense,
      attackRange: raw.attack_range,
      initiative: raw.initiative,
      regenBase: raw.regen_base,
      cpuBudget: raw.cpu_budget,
      potions: raw.potions,
    })
    state.entities.set(entity.entityId, entity)
  }
  state.tick = spec.tick
  state.castingIds = [...spec.casting_ids]
  return state
}

/** 세계 id 에서 세계 상태로. 케이스마다 다시 세우지 않도록 한 번만 만든다. */
const worlds = new Map<string, WorldState>()

/** 세계 id 에서 파이썬이 기록한 스냅샷으로. */
const snapshots = new Map<string, PerceptionSnapshot>()

beforeAll(() => {
  for (const spec of golden.worlds) {
    worlds.set(spec.world_id, createWorld(spec))
  }
  for (const record of golden.snapshots) {
    snapshots.set(record.world_id, {
      entityId: record.entity_id,
      tick: worlds.get(record.world_id)?.tick ?? 0,
      values: new Map(
        record.values.map((pair) => [pair[0] as string, pair[1] as number | boolean]),
      ),
    })
  }
})

/**
 * 세계 상태를 꺼낸다. 없으면 골든이 어긋난 것이므로 즉시 실패시킨다.
 *
 * @param worldId 세계 id.
 * @returns 세계 상태.
 */
function getWorld(worldId: string): WorldState {
  const state = worlds.get(worldId)
  if (state === undefined) {
    throw new Error(`골든에 없는 세계다: ${worldId}`)
  }
  return state
}

/**
 * 그 세계 플레이어의 스냅샷을 꺼낸다.
 *
 * @param worldId 세계 id.
 * @returns 파이썬이 기록한 값으로 만든 스냅샷.
 */
function getSnapshot(worldId: string): PerceptionSnapshot {
  const snapshot = snapshots.get(worldId)
  if (snapshot === undefined) {
    throw new Error(`골든에 스냅샷이 없는 세계다: ${worldId}`)
  }
  return snapshot
}

/**
 * 그 세계의 엔티티를 꺼낸다.
 *
 * @param worldId 세계 id.
 * @param entityId 엔티티 id.
 * @returns 찾은 엔티티.
 */
function getEntity(worldId: string, entityId: string): Entity {
  const entity = getWorld(worldId).entities.get(entityId)
  if (entity === undefined) {
    throw new Error(`골든에 없는 엔티티다: ${worldId}/${entityId}`)
  }
  return entity
}

/**
 * 케이스가 가리키는 규칙표를 얻는다. 인라인이거나 자원 파일 참조다.
 *
 * @param spec 인라인 `ruleset` 또는 `ruleset_ref` 를 가진 케이스.
 * @returns 우선순위 순으로 정렬된 규칙표.
 */
function resolveCaseRuleSet(spec: {
  readonly ruleset?: RawRuleSet
  readonly ruleset_ref?: readonly string[]
}): RuleSet {
  if (spec.ruleset !== undefined) {
    return parseRuleSet(spec.ruleset)
  }
  const reference = spec.ruleset_ref
  if (reference === undefined) {
    throw new Error('케이스에 규칙표가 없다')
  }
  const [alias, rulesetId] = reference
  const found = RULESET_FILES.get(alias as string)?.get(rulesetId as string)
  if (found === undefined) {
    throw new Error(`골든이 가리키는 규칙표가 없다: ${String(alias)}/${String(rulesetId)}`)
  }
  return found
}

/**
 * 계획을 골든과 같은 모양으로 편다.
 *
 * @param plan 대조할 계획.
 * @returns 골든의 plan 절과 같은 키를 가진 객체.
 */
function renderPlanDocument(plan: PlannedAction): GoldenPlan {
  return {
    entity_id: plan.entityId,
    action_id: plan.actionId,
    target_id: plan.targetId,
    rule_index: plan.ruleIndex,
    expr: plan.expr,
    set_flag: plan.setFlag,
  }
}

/**
 * 골든의 조건 절을 파싱된 조건식으로 옮긴다.
 *
 * 조건식만 담은 스키마 진입점이 따로 없으므로 규칙 한 줄로 감싸 `parseRuleSet` 을 태운다.
 * 파서를 우회해 손으로 항을 만들면 대조 대상이 아니라 대조 도구가 갈라진다.
 *
 * @param raw 골든의 condition 절.
 * @returns 파싱된 조건식.
 */
function parseGoldenCondition(raw: GoldenCondition['condition']): Condition {
  const wrapper = {
    ruleset_id: 'golden',
    version: 1,
    rules: [
      {
        priority: 1,
        cpu_cost: 1,
        action: 'HOLD',
        conditions: raw,
      },
    ],
  } as unknown as RawRuleSet
  const rule = parseRuleSet(wrapper).rules[0]
  if (rule === undefined) {
    throw new Error('골든의 조건 절이 비었다')
  }
  return rule.conditions
}

describe('셀렉터', () => {
  it.each(golden.selectors)(
    '$world_id / $selector 는 파이썬과 같은 대상을 고른다',
    (expected: GoldenSelector) => {
      const state = getWorld(expected.world_id)
      const actor = getEntity(expected.world_id, expected.actor_id)
      const picked = resolveTarget(expected.selector, actor, state, KIND_TYPES)
      expect(picked?.entityId ?? null).toBe(expected.picked_id)
    },
  )

  it('셀렉터 7종을 빠짐없이 다룬다', () => {
    const covered = new Set(golden.selectors.map((entry) => entry.selector))
    expect([...covered].sort()).toEqual([...ALL_SELECTORS].sort())
  })

  it('같은 스냅샷을 두 번 물으면 같은 답이 나온다', () => {
    // 조건 평가는 순수해야 한다 (TDD §5.2). PRNG 가 끼면 여기서 갈린다.
    const state = getWorld('field_mixed')
    const actor = getEntity('field_mixed', 'player')
    for (const selectorId of ALL_SELECTORS) {
      const first = resolveTarget(selectorId, actor, state, KIND_TYPES)
      const second = resolveTarget(selectorId, actor, state, KIND_TYPES)
      expect(second?.entityId).toBe(first?.entityId)
    }
  })
})

describe('검증기', () => {
  it.each(golden.validator)('$name — 위반 목록이 순서까지 같다', (expected: GoldenValidator) => {
    const problems = validateRuleSet(
      resolveCaseRuleSet(expected),
      BLOCK_CATALOG,
      expected.cpu_budget,
      expected.rule_slots,
      expected.unlocked === null ? null : new Set(expected.unlocked),
    )
    expect(problems).toEqual([...expected.problems])
  })

  it('알 수 없는 연산자를 걸러낸다', () => {
    // 파서가 먼저 막으므로 골든에는 담기지 않는다. 그러나 규칙 에디터는 타이핑 도중의
    // 값을 그대로 넘기므로 검증기가 두 번째 방어선으로 남아 있어야 한다.
    const broken = {
      rulesetId: 'x',
      version: 1,
      rules: [
        {
          priority: 1,
          conditions: {
            op: 'XOR',
            terms: [{ lhs: 'self_hp_percent', comparison: '=~', rhs: 1, lhsParam: null }],
          },
          action: 'HOLD',
          target: null,
          setFlag: null,
          cpuCost: 1,
        },
      ],
    } as unknown as RuleSet
    expect(validateRuleSet(broken, BLOCK_CATALOG, 99, 5)).toEqual([
      '[1] 알 수 없는 조건 연산자 XOR',
      '[1] 알 수 없는 비교 연산자 =~',
    ])
  })

  it('예산을 넘겨도 목록 하나로 돌아올 뿐 던지지 않는다', () => {
    // CPU 초과는 오류가 아니라 수치다. 그 상태에서도 편집이 계속돼야 한다 (GDD §3.6).
    const overflowing = golden.validator.find((entry) => entry.name === 'CPU 초과')
    expect(overflowing).toBeDefined()
    const ruleset = resolveCaseRuleSet(overflowing as GoldenValidator)
    expect(() => validateRuleSet(ruleset, BLOCK_CATALOG, 2, 5)).not.toThrow()
  })
})

describe('조건식', () => {
  it.each(golden.conditions)('$name — 참거짓과 문자열이 같다', (expected: GoldenCondition) => {
    const state = getWorld(expected.world_id)
    const result = evaluateCondition(parseGoldenCondition(expected.condition), {
      snapshot: getSnapshot(expected.world_id),
      catalog: BLOCK_CATALOG,
      target:
        expected.target_id === null
          ? undefined
          : getEntity(expected.world_id, expected.target_id),
      cpuHeadroom: expected.cpu_headroom ?? undefined,
      actor: getEntity(expected.world_id, 'player'),
      castingIds: state.castingIds,
    })
    expect(result.fired).toBe(expected.fired)
    expect(result.expr).toBe(expected.expr)
  })

  it('스탯 우변은 양변에 실측값을 병기한다', () => {
    // GDD §8.2 — `적거리(2) <= 사거리(3)` 형태여야 죽고 나서 고칠 곳이 특정된다.
    const rendered = golden.conditions.find(
      (entry) => entry.name === '스탯 우변은 양변에 실측값이 붙는다',
    )
    expect(rendered?.expr).toMatch(/^대상 거리\[NEAREST\]\(\d+\) <= 사거리\(\d+\)$/)
  })
})

describe('RuleVM', () => {
  it.each(golden.rule_vm)('$name — 같은 계획이 나온다', (expected: GoldenRuleVm) => {
    const state = getWorld(expected.world_id)
    const ruleset = resolveCaseRuleSet(expected)
    const vm = buildRuleVm(ruleset, BLOCK_CATALOG, KIND_TYPES)
    const plan = vm.planAction(
      getEntity(expected.world_id, 'player'),
      getSnapshot(expected.world_id),
      state,
    )
    expect(countCpuUsage(ruleset)).toBe(expected.cpu_usage)
    expect(renderPlanDocument(plan)).toEqual(expected.plan)
  })

  it('스탯 읽기가 blocks.json 의 허용 목록을 그대로 덮는다', () => {
    // VM 이 읽지 못하는 스탯이 목록에 있으면 그 스탯을 쓴 규칙이 검증은 통과하고
    // 실행에서 조용히 거짓이 된다.
    expect([...RHS_STAT_READERS.keys()].sort()).toEqual([...BLOCK_CATALOG.rhsStats.keys()].sort())
  })

  it('같은 입력을 두 번 물으면 같은 계획이 나온다', () => {
    const spec = golden.rule_vm[0] as GoldenRuleVm
    const vm = buildRuleVm(resolveCaseRuleSet(spec), BLOCK_CATALOG, KIND_TYPES)
    const entity = getEntity(spec.world_id, 'player')
    const snapshot = getSnapshot(spec.world_id)
    const state = getWorld(spec.world_id)
    expect(vm.planAction(entity, snapshot, state)).toEqual(vm.planAction(entity, snapshot, state))
  })
})

describe('폴백 정책', () => {
  it.each(golden.fallback)('$world_id — 같은 계획이 나온다', (expected: GoldenFallback) => {
    const plan = new FallbackPolicy().planAction(
      getEntity(expected.world_id, 'player'),
      getSnapshot(expected.world_id),
      getWorld(expected.world_id),
    )
    expect(renderPlanDocument(plan)).toEqual(expected.plan)
  })
})

describe('인지 스냅샷', () => {
  it.each(golden.snapshots)(
    '$world_id — 파이썬과 같은 키를 같은 순서로 만든다',
    (expected: GoldenSnapshot) => {
      // RuleVM 대조는 파이썬이 기록한 값을 그대로 먹인다. 그래서 TS 쪽 PERCEPTION 이
      // 갈려도 위 테스트는 통과한다 — 그 틈을 여기서 막는다.
      const state = getWorld(expected.world_id)
      const actual = buildSnapshot({
        state,
        entity: getEntity(expected.world_id, expected.entity_id),
        kindTypes: KIND_TYPES,
      })
      const wanted = expected.values.map((pair) => [pair[0], pair[1]])
      expect([...actual.values.entries()]).toEqual(wanted)
    },
  )
})
