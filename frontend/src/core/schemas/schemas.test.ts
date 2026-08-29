/**
 * 스키마 이식의 무결성 검사 — `tests/test_resources.py` 의 대응물이다.
 *
 * 보는 것은 "값이 좋은가"가 아니라 "파이썬 로더와 같은 것을 읽어 내는가"다. 두 코어가
 * 같은 JSON 을 서로 다르게 해석하면 게이트 G3 는 RNG 만 맞고 결과는 갈라진다.
 */
import { describe, expect, it } from 'vitest'

import {
  BENCHMARK_RULESETS,
  BLOCK_CATALOG,
  ENEMY_RULESETS,
  G0_RULESETS,
  ROOM_TEMPLATES,
} from '../resources'
import {
  ACTION_COUNT,
  PERCEPTION_COUNT,
  RHS_STAT_COUNT,
  SELECTOR_COUNT,
  TILE_WALL,
  checkRoomReachability,
  convertRowsToTiles,
  getRoomTile,
  getTermKey,
  isStatRef,
  loadBlockCatalog,
  loadRoomTemplates,
  parseRhs,
  parseRuleSet,
} from './index'
import type { RawBlockCatalog, RawRoomFile } from './index'

const ROOM_TEMPLATE_COUNT = 5
const ROOM_WIDTH = 12
const ROOM_HEIGHT = 9
const ENEMY_KIND_COUNT = 8

describe('블록 카탈로그', () => {
  it('개수가 동결값과 같다', () => {
    expect(BLOCK_CATALOG.perceptions.size).toBe(PERCEPTION_COUNT)
    expect(BLOCK_CATALOG.actions.size).toBe(ACTION_COUNT)
    expect(BLOCK_CATALOG.selectors.size).toBe(SELECTOR_COUNT)
    expect(BLOCK_CATALOG.rhsStats.size).toBe(RHS_STAT_COUNT)
  })

  it('SUMMON 이 일급 행동이다', () => {
    const summon = BLOCK_CATALOG.actions.get('SUMMON')
    expect(summon?.category).toBe('control')
    expect(summon?.targeted).toBe(false)
  })

  it('쿨타임 블록이 SUMMON 을 가리킬 수 있다', () => {
    const cooldown = BLOCK_CATALOG.perceptions.get('self_cooldown_ready')
    expect(cooldown?.param?.values).toContain('SUMMON')
  })

  it('값 범위가 붙은 인지 변수는 두 값으로 읽힌다', () => {
    expect(BLOCK_CATALOG.perceptions.get('self_hp_percent')?.valueRange).toEqual([0, 100])
  })

  it('개수가 어긋나면 로드가 실패한다', () => {
    const broken = {
      block_list_version: 3,
      perceptions: [],
      actions: [],
      selectors: [],
      rhs_stats: [],
    } satisfies RawBlockCatalog
    expect(() => loadBlockCatalog(broken)).toThrow(/동결값과 다르다/)
  })

  it('id 가 중복되면 로드가 실패한다', () => {
    const twin = { id: 'NEAREST', label_ko: '가장 가까운 적' }
    const broken: RawBlockCatalog = {
      block_list_version: 3,
      perceptions: [],
      actions: [],
      selectors: [twin, twin],
      rhs_stats: [],
    }
    expect(() => loadBlockCatalog(broken)).toThrow(/중복/)
  })
})

describe('룸 템플릿', () => {
  it('12x9 템플릿 5개를 읽는다', () => {
    expect(ROOM_TEMPLATES).toHaveLength(ROOM_TEMPLATE_COUNT)
    for (const template of ROOM_TEMPLATES) {
      expect([template.width, template.height]).toEqual([ROOM_WIDTH, ROOM_HEIGHT])
    }
  })

  it('모든 템플릿이 도달 가능하다', () => {
    for (const template of ROOM_TEMPLATES) {
      expect(checkRoomReachability(template)).toEqual([])
    }
  })

  it('격자 밖은 벽으로 읽힌다', () => {
    const first = ROOM_TEMPLATES[0]
    expect(first).toBeDefined()
    if (first === undefined) {
      return
    }
    expect(getRoomTile(first, -1, 0)).toBe(TILE_WALL)
    expect(getRoomTile(first, ROOM_WIDTH, ROOM_HEIGHT)).toBe(TILE_WALL)
  })

  it('legend 에 없는 글자는 거부한다', () => {
    expect(() => convertRowsToTiles(['?'], { '.': 0 })).toThrow(/legend/)
  })

  it('선언 크기와 다른 템플릿은 거부한다', () => {
    const broken: RawRoomFile = {
      size: [ROOM_WIDTH, ROOM_HEIGHT],
      legend: { '.': 0 },
      templates: [
        {
          id: 'too_small',
          purpose: '테스트',
          rows: ['..'],
          player_spawn: [0, 0],
          enemy_spawns: [],
        },
      ],
    }
    expect(() => loadRoomTemplates(broken)).toThrow(/크기가 선언/)
  })

  it('갇힌 방은 도달성 검사가 잡는다', () => {
    const walled = loadRoomTemplates({
      size: [3, 3],
      legend: { '.': 0, '#': 1, D: 4 },
      templates: [
        {
          id: 'sealed',
          purpose: '테스트',
          rows: ['#D#', '#.#', '###'],
          player_spawn: [1, 1],
          enemy_spawns: [],
        },
      ],
    })
    const sealed = walled[0]
    expect(sealed).toBeDefined()
    if (sealed === undefined) {
      return
    }
    expect(checkRoomReachability(sealed)).toEqual([])

    const isolated = loadRoomTemplates({
      size: [3, 3],
      legend: { '.': 0, '#': 1, D: 4 },
      templates: [
        {
          id: 'isolated',
          purpose: '테스트',
          rows: ['.#D', '###', '###'],
          player_spawn: [0, 0],
          enemy_spawns: [],
        },
      ],
    })[0]
    expect(isolated).toBeDefined()
    if (isolated === undefined) {
      return
    }
    expect(checkRoomReachability(isolated)).toEqual([
      'isolated: 출구 (2, 0) 에 시작점에서 닿을 수 없다',
    ])
  })
})

describe('규칙표', () => {
  it('G0 예시 3종을 읽는다', () => {
    expect([...G0_RULESETS.keys()]).toEqual(['g0_pressure', 'g0_kite', 'g0_cover'])
  })

  it('적 규칙표가 8종이다', () => {
    expect(ENEMY_RULESETS.size).toBe(ENEMY_KIND_COUNT)
  })

  it('벤치마크 규칙표를 읽는다', () => {
    expect(BENCHMARK_RULESETS.size).toBeGreaterThan(0)
  })

  it('규칙이 우선순위 오름차순으로 정렬된다', () => {
    for (const ruleset of [...G0_RULESETS.values(), ...ENEMY_RULESETS.values()]) {
      const priorities = ruleset.rules.map((rule) => rule.priority)
      expect(priorities).toEqual([...priorities].sort((left, right) => left - right))
    }
  })

  it('스탯 참조 우변을 객체로 읽는다 (F-2)', () => {
    const rhs = parseRhs({ stat: 'attack_range' })
    expect(isStatRef(rhs)).toBe(true)
    expect(rhs).toEqual({ stat: 'attack_range' })
  })

  it('리터럴 우변은 그대로 읽는다', () => {
    expect(parseRhs(3)).toBe(3)
    expect(parseRhs(true)).toBe(true)
    expect(isStatRef(parseRhs(3))).toBe(false)
  })

  it('실수·문자열 우변은 거부한다', () => {
    expect(() => parseRhs(1.5)).toThrow(/우변은/)
    expect(() => parseRhs('attack_range')).toThrow(/우변은/)
    expect(() => parseRhs({ value: 1 })).toThrow(/stat 문자열/)
  })

  it('적 규칙표에 실제로 스탯 참조가 들어 있다', () => {
    const archer = ENEMY_RULESETS.get('ai_archer')
    expect(archer).toBeDefined()
    const refs = (archer?.rules ?? []).flatMap((rule) =>
      rule.conditions.terms.filter((term) => isStatRef(term.rhs)),
    )
    expect(refs.length).toBeGreaterThan(0)
  })

  it('항 키가 인자를 포함한다', () => {
    const parsed = parseRuleSet({
      ruleset_id: 'probe',
      version: 1,
      rules: [
        {
          priority: 2,
          cpu_cost: 1,
          action: 'ATTACK',
          target: 'NEAREST',
          conditions: {
            op: 'SINGLE',
            terms: [{ lhs: 'target_distance', lhs_param: 'NEAREST', cmp: '<=', rhs: 1 }],
          },
        },
        {
          priority: 1,
          cpu_cost: 1,
          action: 'WAIT',
          conditions: {
            op: 'SINGLE',
            terms: [{ lhs: 'self_hp_percent', cmp: '<', rhs: 25 }],
          },
        },
      ],
    })
    expect(parsed.rules.map((rule) => rule.priority)).toEqual([1, 2])
    const first = parsed.rules[1]?.conditions.terms[0]
    expect(first).toBeDefined()
    expect(first === undefined ? '' : getTermKey(first)).toBe('target_distance[NEAREST]')
    expect(parsed.rules[0]?.target).toBeNull()
  })

  it('알 수 없는 연산자는 거부한다', () => {
    expect(() =>
      parseRuleSet({
        ruleset_id: 'probe',
        version: 1,
        rules: [
          {
            priority: 1,
            cpu_cost: 1,
            action: 'WAIT',
            conditions: { op: 'XOR', terms: [] },
          },
        ],
      }),
    ).toThrow(/조건 연산자/)
  })
})
