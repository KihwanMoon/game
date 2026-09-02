/**
 * 규칙 에디터의 왕복 검증.
 *
 * 텍스트 뷰가 프리셋 공유의 통로다(GDD §10 A등급). 그래서 이 파일이 지키는 것은 하나다 —
 * **내보낸 텍스트를 다시 붙여넣으면 같은 규칙표가 나온다.** 여기서 한 필드라도 흘리면 남의
 * 규칙표를 붙여넣은 사람은 원본과 다른 것을 원본이라 믿고 돌리게 된다.
 *
 * 자원 JSON 의 규칙표 전부를 왕복시킨다. 손으로 만든 사례만 돌리면 실제 규칙표에만 있는
 * 조합(스탯 우변, OR, SET 절, 인자 있는 좌변)이 검증에서 빠진다.
 */
import { describe, expect, it } from 'vitest'

import {
  BENCHMARK_RULESETS,
  BLOCK_CATALOG,
  ENEMY_RULESETS,
  G0_RULESETS,
} from '../core/resources'
import { validateRuleSet } from '../core/rules/validator'
import { listSelectorsForAction } from './blockOptions'
import type { RuleSet } from '../core/schemas'
import {
  addRule,
  addTerm,
  applyActionChoice,
  applyLhsChoice,
  calculateTotalCpu,
  duplicateRule,
  moveRule,
  removeRule,
  updateTerm,
} from './draft'
import { formatRuleText, parseRuleText } from './ruleText'

const CPU_BUDGET = 8
const RULE_SLOTS = 5
const EMPTY: RuleSet = { rulesetId: 'draft', version: 1, rules: [] }

/**
 * 규칙표를 텍스트로 내보내고 다시 읽는다.
 *
 * @param ruleset 왕복시킬 규칙표.
 * @returns 다시 읽어 낸 규칙표.
 */
function runRoundTrip(ruleset: RuleSet): RuleSet {
  const text = formatRuleText(ruleset)
  const parsed = parseRuleText(text, 'lost', 0)
  expect(parsed.errors).toEqual([])
  expect(parsed.ruleset).toBeDefined()
  return parsed.ruleset as RuleSet
}

describe('텍스트 뷰 왕복', () => {
  const sources: readonly (readonly [string, ReadonlyMap<string, RuleSet>])[] = [
    ['g0', G0_RULESETS],
    ['enemies', ENEMY_RULESETS],
    ['benchmark', BENCHMARK_RULESETS],
  ]

  for (const [group, rulesets] of sources) {
    for (const [rulesetId, ruleset] of rulesets) {
      it(`${group}/${rulesetId} 이 왕복해도 같다`, () => {
        expect(runRoundTrip(ruleset)).toEqual(ruleset)
      })
    }
  }

  it('머리글이 규칙표 id 와 세대를 나른다', () => {
    const source = G0_RULESETS.get('g0_kite') as RuleSet
    const text = formatRuleText(source)
    expect(text.split('\n')[0]).toBe('# ruleset g0_kite v1')
    const parsed = parseRuleText(text, 'other_id', 99)
    expect(parsed.ruleset?.rulesetId).toBe('g0_kite')
    expect(parsed.ruleset?.version).toBe(1)
  })

  it('머리글이 없으면 부르는 쪽의 이름을 쓴다', () => {
    const parsed = parseRuleText('[1] IF self_hp_percent < 30 THEN USE_POTION', 'fallback', 7)
    expect(parsed.ruleset?.rulesetId).toBe('fallback')
    expect(parsed.ruleset?.version).toBe(7)
  })

  it('번호를 생략하면 줄 순서로 매긴다', () => {
    const parsed = parseRuleText(
      ['IF self_hp_percent < 30 THEN USE_POTION', 'IF room_elapsed_ticks > 35 THEN HOLD'].join('\n'),
      'draft',
      1,
    )
    expect(parsed.ruleset?.rules.map((rule) => rule.priority)).toEqual([1, 2])
  })

  it('빈 줄과 주석을 건너뛴다', () => {
    const parsed = parseRuleText(
      ['# 붙여넣은 설명', '', '[1] IF self_hp_percent < 30 THEN USE_POTION', '   '].join('\n'),
      'draft',
      1,
    )
    expect(parsed.ruleset?.rules).toHaveLength(1)
  })
})

describe('텍스트 뷰 오류', () => {
  it('THEN 이 없으면 줄 번호와 함께 알린다', () => {
    const parsed = parseRuleText('[1] IF self_hp_percent < 30', 'draft', 1)
    expect(parsed.ruleset).toBeUndefined()
    expect(parsed.errors[0]).toContain('1행:')
  })

  it('AND 와 OR 를 섞으면 거부한다', () => {
    const parsed = parseRuleText(
      '[1] IF self_hp_percent < 30 AND self_potion_count > 0 OR room_elapsed_ticks > 5 THEN HOLD',
      'draft',
      1,
    )
    expect(parsed.errors[0]).toContain('AND 와 OR')
  })

  it('읽을 수 없는 우변을 거부한다', () => {
    const parsed = parseRuleText('[1] IF self_hp_percent < 대충 THEN HOLD', 'draft', 1)
    expect(parsed.errors).toHaveLength(1)
    expect(parsed.errors[0]).toContain('우변')
  })

  it('오류가 하나라도 있으면 규칙표를 내지 않는다', () => {
    const parsed = parseRuleText(
      ['[1] IF self_hp_percent < 30 THEN USE_POTION', '[2] 이건 규칙이 아니다'].join('\n'),
      'draft',
      1,
    )
    expect(parsed.ruleset).toBeUndefined()
  })
})

describe('편집 조작으로 만든 규칙표', () => {
  /**
   * 에디터 조작만으로 카이팅 규칙표 하나를 짠다. 화면에서 손이 하는 것과 같은 순서다.
   *
   * @returns 만들어진 규칙표.
   */
  function buildKiteRuleSet(): RuleSet {
    let draft = addRule(EMPTY, BLOCK_CATALOG, -1, 'self_hp_percent')
    draft = applyActionChoice(draft, BLOCK_CATALOG, 0, 'USE_POTION')
    draft = updateTerm(draft, 0, 0, { comparison: '<', rhs: 30 })
    draft = addTerm(draft, BLOCK_CATALOG, 0, 'self_potion_count')
    draft = updateTerm(draft, 0, 1, { comparison: '>', rhs: 0 })

    draft = addRule(draft, BLOCK_CATALOG, 0, 'target_distance')
    draft = updateTerm(draft, 1, 0, { comparison: '<=', rhs: { stat: 'attack_range' } })
    draft = applyActionChoice(draft, BLOCK_CATALOG, 1, 'RETREAT')
    draft = { ...draft, rules: draft.rules.map((rule, at) => (at === 1 ? { ...rule, setFlag: 'A=true' } : rule)) }
    return draft
  }

  it('만든 즉시 검증을 통과한다', () => {
    const draft = buildKiteRuleSet()
    expect(validateRuleSet(draft, BLOCK_CATALOG, CPU_BUDGET, RULE_SLOTS)).toEqual([])
  })

  it('만든 규칙표가 왕복해도 같다', () => {
    const draft = buildKiteRuleSet()
    expect(runRoundTrip(draft)).toEqual(draft)
  })

  it('스탯 우변과 SET 절이 텍스트에 남는다', () => {
    const text = formatRuleText(buildKiteRuleSet())
    expect(text).toContain('target_distance[NEAREST] <= $attack_range')
    expect(text).toContain('SET A=true')
  })

  it('CPU 비용이 항 수에서 다시 계산된다', () => {
    const draft = buildKiteRuleSet()
    expect(draft.rules[0]?.cpuCost).toBe(2)
    expect(draft.rules[1]?.cpuCost).toBe(1)
    expect(calculateTotalCpu(draft)).toBe(3)
  })

  it('순서를 바꾸면 우선순위가 1..n 으로 다시 매겨진다', () => {
    const moved = moveRule(buildKiteRuleSet(), 1, 0)
    expect(moved.rules.map((rule) => rule.priority)).toEqual([1, 2])
    expect(moved.rules[0]?.action).toBe('RETREAT')
  })

  it('복제와 삭제가 번호를 이어 준다', () => {
    const draft = buildKiteRuleSet()
    const cloned = duplicateRule(draft, 0)
    expect(cloned.rules.map((rule) => rule.priority)).toEqual([1, 2, 3])
    expect(cloned.rules[1]?.action).toBe(cloned.rules[0]?.action)
    const pruned = removeRule(cloned, 1)
    expect(pruned.rules.map((rule) => rule.priority)).toEqual([1, 2])
  })

  it('좌변을 바꾸면 인자와 우변이 함께 따라온다', () => {
    const draft = addRule(EMPTY, BLOCK_CATALOG, -1, 'self_hp_percent')
    const swapped = applyLhsChoice(draft, BLOCK_CATALOG, 0, 0, 'self_cooldown_ready')
    const term = swapped.rules[0]?.conditions.terms[0]
    expect(term?.lhsParam).toBe('SKILL_1')
    expect(term?.rhs).toBe(true)
    expect(term?.comparison).toBe('==')
    expect(validateRuleSet(swapped, BLOCK_CATALOG, CPU_BUDGET, RULE_SLOTS)).toEqual([])
  })

  it('행동을 바꾸면 TARGET 절이 함께 맞춰진다', () => {
    const draft = addRule(EMPTY, BLOCK_CATALOG, -1, 'self_hp_percent')
    const untargeted = applyActionChoice(draft, BLOCK_CATALOG, 0, 'HOLD')
    expect(untargeted.rules[0]?.target).toBeNull()
    const targeted = applyActionChoice(untargeted, BLOCK_CATALOG, 0, 'ATTACK')
    expect(targeted.rules[0]?.target).toBe('NEAREST')
  })

  it('회복으로 바꾸면 셀렉터도 아군 쪽으로 넘어간다', () => {
    // 블록 목록 v4. 적대 셀렉터를 그대로 두면 고르자마자 위반이 뜬다.
    const draft = addRule(EMPTY, BLOCK_CATALOG, -1, 'self_hp_percent')
    const attacking = applyActionChoice(draft, BLOCK_CATALOG, 0, 'ATTACK')
    const healing = applyActionChoice(attacking, BLOCK_CATALOG, 0, 'HEAL')
    expect(healing.rules[0]?.target).toBe('ALLY_WOUNDED')
    expect(validateRuleSet(healing, BLOCK_CATALOG, CPU_BUDGET, RULE_SLOTS)).toEqual([])
    const backToAttack = applyActionChoice(healing, BLOCK_CATALOG, 0, 'ATTACK')
    expect(backToAttack.rules[0]?.target).toBe('NEAREST')
  })

  it('행동이 고를 수 있는 셀렉터만 목록에 낸다', () => {
    const heal = BLOCK_CATALOG.actions.get('HEAL')
    const attack = BLOCK_CATALOG.actions.get('ATTACK')
    expect(listSelectorsForAction(BLOCK_CATALOG, heal).map((item) => item.blockId)).toEqual([
      'ALLY_WOUNDED',
    ])
    expect(listSelectorsForAction(BLOCK_CATALOG, attack).map((item) => item.blockId)).not.toContain(
      'ALLY_WOUNDED',
    )
  })

  it('예산을 넘겨도 편집이 막히지 않는다', () => {
    let draft = EMPTY
    for (let count = 0; count < RULE_SLOTS; count += 1) {
      draft = addRule(draft, BLOCK_CATALOG, draft.rules.length - 1, 'self_hp_percent')
      draft = addTerm(draft, BLOCK_CATALOG, draft.rules.length - 1, 'self_potion_count')
      draft = addTerm(draft, BLOCK_CATALOG, draft.rules.length - 1, 'visible_enemy_count')
    }
    expect(calculateTotalCpu(draft)).toBeGreaterThan(CPU_BUDGET)
    const problems = validateRuleSet(draft, BLOCK_CATALOG, CPU_BUDGET, RULE_SLOTS)
    expect(problems).toContain(`CPU ${String(calculateTotalCpu(draft))} 가 예산 ${String(CPU_BUDGET)} 을 넘는다`)
    expect(runRoundTrip(draft)).toEqual(draft)
  })

  it('조건 항은 3개를 넘지 않는다', () => {
    let draft = addRule(EMPTY, BLOCK_CATALOG, -1, 'self_hp_percent')
    for (let count = 0; count < 5; count += 1) {
      draft = addTerm(draft, BLOCK_CATALOG, 0, 'self_potion_count')
    }
    expect(draft.rules[0]?.conditions.terms).toHaveLength(3)
  })
})


describe('별칭 정리 (규칙 재정비)', () => {
  it('★ USE_POTION 은 고르는 목록에 없다 — 「소모품 사용」과 같은 일이 둘 보이면 헷갈린다', async () => {
    const { listActionGroups } = await import('./blockOptions')
    const { loadBlockCatalog } = await import('../core/schemas')
    const raw = await import('../../../game/resources/balance/blocks.json')
    const catalog = loadBlockCatalog(raw.default as never)
    const ids = listActionGroups(catalog).flatMap((group) =>
      group.blocks.map((block) => block.blockId),
    )
    expect(ids).not.toContain('USE_POTION')
    // 별칭만 뺀 것이다 — 소모품 사용 자체는 있어야 한다.
    expect(ids).toContain('USE_ITEM')
  })
})
