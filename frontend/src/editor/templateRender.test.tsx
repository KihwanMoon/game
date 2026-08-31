/**
 * 추천 규칙표 화면과 한국어 문장 표기.
 *
 * 여기서 지키는 것은 넷이다.
 *
 * 1. **16벌이 전부 화면에 닿는다.** 지금까지 저장소에만 있고 화면에서는 못 골랐다.
 * 2. **무엇을 하는 규칙표인지 한국어로 읽힌다.** 모르는 문법으로 적힌 목록에서는 무엇을
 *    고를지 정할 수 없다.
 * 3. **예산이 보인다.** 불러온 뒤에 "슬롯이 모자라다" 를 알면 늦다.
 * 4. **불러오기가 편집 한 단계다.** 되돌릴 수 있어야 눌러 볼 수 있다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { TemplatePanel, TemplateRow } from './TemplatePanel'
import { ALWAYS_TEXT, formatRuleSentence } from './ruleSentence'
import { BLOCK_CATALOG, RULE_TEMPLATES } from '../core/resources'
import type { Rule } from '../core/schemas'

const MARKUP = renderToStaticMarkup(
  <TemplatePanel
    templates={RULE_TEMPLATES}
    catalog={BLOCK_CATALOG}
    cpuBudget={8}
    ruleSlots={5}
    onLoad={() => undefined}
  />,
)

describe('추천 규칙표', () => {
  it('★ 저장소에 있는 규칙표가 하나도 안 빠진다 — 못 고르는 것은 없는 것과 같다', () => {
    expect(RULE_TEMPLATES.length).toBeGreaterThanOrEqual(16)
    for (const item of RULE_TEMPLATES) {
      expect(MARKUP).toContain(`<span class="tpl__name">${item.templateId}</span>`)
    }
  })

  it('★ 무엇을 노리는 규칙표인지 적는다 — 이름만으로는 못 고른다', () => {
    for (const item of RULE_TEMPLATES) {
      expect(item.strategyKo, `${item.templateId}: 전략 설명이 없다`).not.toBe('')
    }
    expect(MARKUP).toContain('소환사부터 지운다')
  })

  it('★ 전부 시작 예산 안에 든다 — 넘는 것을 추천하면 추천이 아니다', () => {
    for (const item of RULE_TEMPLATES) {
      expect(item.cpuTotal, `${item.templateId}: CPU 초과`).toBeLessThanOrEqual(8)
      expect(item.ruleset.rules.length, `${item.templateId}: 슬롯 초과`).toBeLessThanOrEqual(5)
    }
  })

  it('★ 예산을 화면에 함께 적는다 — 불러온 뒤에 알면 늦다', () => {
    expect(MARKUP).toContain('cpu 6 / 8')
  })

  it('★ 불러오기는 규칙표를 그대로 올려 준다', () => {
    const onLoad = vi.fn()
    const first = RULE_TEMPLATES[0]
    if (first === undefined) {
      throw new Error('템플릿이 없다')
    }
    const row = TemplateRow({
      template: first,
      catalog: BLOCK_CATALOG,
      cpuBudget: 8,
      ruleSlots: 5,
      isOpen: false,
      onToggle: () => undefined,
      onLoad,
    })
    const found = collectHandlers(row).find((item) => item.title.includes('편집기로 불러온다'))
    found?.onClick()
    expect(onLoad).toHaveBeenCalledWith(RULE_TEMPLATES[0]?.ruleset)
  })
})

interface Handler {
  readonly title: string
  readonly onClick: () => void
}

/**
 * 트리에서 onClick 을 가진 요소를 모은다.
 *
 * @param node 렌더 트리.
 * @returns 핸들러들.
 */
function collectHandlers(node: unknown): Handler[] {
  if (node === null || typeof node !== 'object') {
    return []
  }
  const element = node as { props?: Record<string, unknown> }
  const props = element.props ?? {}
  const found: Handler[] =
    typeof props.onClick === 'function'
      ? [
          {
            title: typeof props.title === 'string' ? props.title : '',
            onClick: props.onClick as () => void,
          },
        ]
      : []
  const children = props.children
  const list = Array.isArray(children) ? children : [children]
  return [...found, ...list.flatMap((child) => collectHandlers(child))]
}

describe('한국어 문장', () => {
  const rule = RULE_TEMPLATES.find((item) => item.templateId === 'g0_kite')?.ruleset.rules[0]

  it('★ 조건과 행동을 한 문장으로 읽는다', () => {
    if (rule === undefined) {
      throw new Error('g0_kite 가 없다')
    }
    const text = formatRuleSentence(rule, BLOCK_CATALOG)
    expect(text).toContain('→')
    // 블록 id 가 그대로 새어 나오면 문장이 아니다.
    expect(text).not.toContain('self_')
    expect(text).not.toContain('target_')
  })

  it('★ 조건이 없으면 「언제나」다 — 빈칸은 뜻을 말하지 않는다', () => {
    const bare: Rule = {
      priority: 1,
      conditions: { op: 'SINGLE', terms: [] },
      action: 'HOLD',
      actionParam: null,
      target: null,
      setFlag: null,
      cpuCost: 1,
    }
    expect(formatRuleSentence(bare, BLOCK_CATALOG)).toContain(ALWAYS_TEXT)
  })

  it('모르는 블록은 id 를 그대로 낸다 — 빈칸보다 낫다', () => {
    const odd: Rule = {
      priority: 1,
      conditions: { op: 'SINGLE', terms: [] },
      action: 'NOT_A_BLOCK',
      actionParam: null,
      target: null,
      setFlag: null,
      cpuCost: 1,
    }
    expect(formatRuleSentence(odd, BLOCK_CATALOG)).toContain('NOT_A_BLOCK')
  })
})
