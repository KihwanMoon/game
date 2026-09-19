/**
 * 행동의 인자가 성립하는가 — 그리고 화면이 그것을 정직하게 말하는가.
 *
 * **2026-09-19 의 사고.** 운영 슬롯에 재주 없는 `USE_SKILL` 이 9줄 있었다. 「메테오」라고
 * 이름 붙인 슬롯 안의 규칙에 메테오가 없었다. 세 겹이 겹쳐서 조용했다.
 *
 *   1. 파이썬이 저장할 때 `action_param` 을 버렸다 (2026-09-17 수정).
 *   2. **검증이 행동의 인자를 안 봤다** — 조건 항의 인자는 처음부터 봤는데 이쪽만 비었다.
 *   3. 고르개가 값이 없으면 **목록의 첫 칸**을 띄웠다.
 *
 * 그래서 저장된 것(없음)·보이는 것(일격)·도는 것(미장착으로 걸러 안 돎)이 셋 다 달랐고,
 * 쓰는 사람에게는 「저장했다 불러오면 사용 규칙이 바뀐다」로 보였다.
 *
 * 1 은 이미 막혔다. 여기서는 2 와 3 을 지킨다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { readActivePack } from '../content/pack'
import { validateRuleSet } from '../core/rules/validator'
import type { Rule, RuleSet } from '../core/schemas'
import { applyParamChoice, createRule } from './draft'
import { LEGACY_ACTION_GROUP, listWritableActions } from './blockOptions'
import { ORPHAN_SUFFIX, UNSET_LABEL } from './EditParts'
import { RuleEditMobile } from './RuleEditMobile'

const CATALOG = readActivePack().catalog
const BUDGET = 99

function buildSet(patch: Partial<Rule>): RuleSet {
  const base = createRule(CATALOG, 1)
  return { rulesetId: 'probe', version: 1, rules: [{ ...base, ...patch }] }
}

function check(patch: Partial<Rule>): readonly string[] {
  return validateRuleSet(buildSet(patch), CATALOG, BUDGET, BUDGET)
}

/**
 * 규칙 하나짜리 편집 화면을 정적 마크업으로 굽는다.
 *
 * @param patch 규칙에 덮어쓸 필드들.
 * @returns 마크업.
 */
function renderRule(patch: Partial<Rule>): string {
  const noop = {
    update: vi.fn(), changeLhs: vi.fn(), changeTerm: vi.fn(), changeAction: vi.fn(),
    changeParam: vi.fn(), addTerm: vi.fn(), removeTerm: vi.fn(), addRule: vi.fn(),
    duplicate: vi.fn(), remove: vi.fn(), move: vi.fn(),
  }
  return renderToStaticMarkup(
    RuleEditMobile({
      mode: 'portrait', ruleset: buildSet(patch), catalog: CATALOG, cpuBudget: BUDGET,
      ruleSlots: BUDGET, problems: new Map(), globalProblems: [], editIndex: 0,
      readings: new Map(), actions: noop, onOpen: vi.fn(), onAdd: vi.fn(),
      onReorder: vi.fn(), onCancel: vi.fn(), onSave: vi.fn(), backLabel: '내력',
    }),
  )
}

describe('행동 인자 검증', () => {
  it('★ 재주를 안 고른 USE_SKILL 을 반려한다', () => {
    expect(check({ action: 'USE_SKILL', actionParam: null, target: 'NEAREST' })).toContain(
      '[1] USE_SKILL 의 재주 를 안 골랐다',
    )
  })

  it('★ 목록에 없는 재주를 반려한다 — 예전에는 무엇을 적든 통과했다', () => {
    expect(check({ action: 'USE_SKILL', actionParam: '있지도 않은 재주', target: 'NEAREST' })).toContain(
      '[1] USE_SKILL 의 인자 있지도 않은 재주 는 허용되지 않는다',
    )
  })

  it('제대로 고른 것은 통과한다', () => {
    expect(check({ action: 'USE_SKILL', actionParam: 'METEOR', target: 'NEAREST' })).toEqual([])
  })

  it('인자를 안 받는 행동에 인자가 붙어 있으면 반려한다', () => {
    expect(check({ action: 'HOLD', actionParam: 'METEOR', target: null })).toContain(
      '[1] HOLD 는 인자를 받지 않는다',
    )
  })

  it('인자를 안 받는 행동에 인자가 없는 것은 통과한다', () => {
    expect(check({ action: 'HOLD', actionParam: null, target: null })).toEqual([])
  })
})

describe('안 고른 상태를 그대로 둔다', () => {
  it('★ 고르개의 빈 칸은 빈 문자열이 아니라 null 로 저장된다', () => {
    const chosen = applyParamChoice(buildSet({ action: 'USE_SKILL' }), CATALOG, 0, 'METEOR')
    expect(chosen.rules[0]?.actionParam).toBe('METEOR')
    const cleared = applyParamChoice(chosen, CATALOG, 0, '')
    // `''` 로 두면 절에 `action_param: ""` 이 실려 두 코어가 다른 것을 읽는다.
    expect(cleared.rules[0]?.actionParam).toBeNull()
  })
})

describe('별칭을 감춘 것이 없앤 것은 아니다', () => {
  it('★ 팔레트에서 뺀 행동은 전부 인자로 닿는다', () => {
    const writable = new Set(listWritableActions(CATALOG).map((one) => one.blockId))
    const byParam = new Set([...CATALOG.actions.values()].flatMap((one) => one.param?.values ?? []))
    const lost = [...CATALOG.actions.values()].filter(
      (one) => !writable.has(one.blockId) && !byParam.has(one.blockId) && one.aliasOf === null,
    )
    expect(lost.map((one) => one.blockId)).toEqual([])
  })

  it('감춘 것이 실제로 있다 — 검사가 빈 집합을 보고 통과하지 않는다', () => {
    expect(listWritableActions(CATALOG).length).toBeLessThan(CATALOG.actions.size)
  })
})

describe('고르개는 든 것을 그대로 보여 준다', () => {
  /**
   * 칸 하나를 굽고 `selected` 가 붙은 항목을 읽는다.
   *
   * **`value` 만 보면 안 된다.** 문제는 value 가 아니라 **맞는 option 이 없을 때** 생긴다 —
   * 브라우저가 첫 항목을 고른 것처럼 보여 주기 때문이다.
   */
  function readSelected(markup: string, label: string): string | undefined {
    for (const found of markup.matchAll(/<select[^>]*aria-label="([^"]*)"[\s\S]*?<\/select>/g)) {
      if (found[1] !== label) {
        continue
      }
      return /<option[^>]*selected[^>]*>([^<]*)</.exec(found[0])?.[1]
    }
    return undefined
  }

  it('★ 새 규칙의 행동이 팔레트 안에 있다 — 기본값이 고를 수 없는 값이면 안 된다', () => {
    const fresh = createRule(CATALOG, 1)
    expect(listWritableActions(CATALOG).map((one) => one.blockId)).toContain(fresh.action)
    expect(check(fresh)).toEqual([])
  })

  it('★ 팔레트에서 뺀 행동을 쓰는 규칙은 그 이름을 그대로 낸다', () => {
    const markup = renderRule({ action: 'SKILL_1', actionParam: null, target: 'NEAREST' })
    // 「일격」이 뜬다. 예전에는 맞는 항목이 없어 목록 첫 칸인 「대상에게 접근」이 떴다.
    expect(readSelected(markup, '규칙 1 행동')).toBe('일격')
    expect(markup).toContain(LEGACY_ACTION_GROUP)
  })

  it('★ 아무것도 안 고른 칸은 안 골랐다고 적는다', () => {
    const markup = renderRule({ action: 'USE_SKILL', actionParam: null, target: null })
    expect(readSelected(markup, '규칙 1 재주')).toBe(UNSET_LABEL)
    expect(readSelected(markup, '규칙 1 대상')).toBe(UNSET_LABEL)
  })

  it('카탈로그가 모르는 값은 목록에 없다고 적는다 — 마지막 방어선', () => {
    const markup = renderRule({ action: 'USE_SKILL', actionParam: '없는재주', target: 'NEAREST' })
    expect(readSelected(markup, '규칙 1 재주')).toBe(`없는재주${ORPHAN_SUFFIX}`)
  })
})
