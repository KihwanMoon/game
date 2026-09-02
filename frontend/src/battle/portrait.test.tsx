/**
 * 세로 모바일 전투 화면(390×844)의 계약 — 명세 A·D.
 *
 * jsdom 이 없으므로(vitest environment 는 node 다) 두 가지 수단으로 본다.
 *
 *   1. `renderToStaticMarkup` — 무엇이 화면에 나가는가. 탭에 따라 시트 **본문만** 갈리고
 *      도면은 그대로인가, 꺼진 줄에 표시가 붙는가.
 *   2. **컴포넌트 함수를 직접 불러** 반환된 트리에서 핸들러를 집어 누른다. `BattlePortrait`
 *      은 훅이 없는 순수 함수라 이것이 된다 — 탭을 누르면 어느 탭이 올라오는지, 규칙 줄을
 *      누르면 어느 우선순위가 넘어오는지를 클릭 그대로 확인할 수 있다.
 *
 * 「도면이 스크롤되지 않는다」는 CSS 선언이므로 스타일시트를 읽어 본다. 브라우저에서
 * 실제로 그렇게 되는지는 `e2e/viewport.spec.ts` 가 390px 폭에서 따로 본다.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { isValidElement, type ReactElement, type ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { RuleRow } from '../ds'
import { OUTCOME_ONGOING, OUTCOME_PLAYER_LOSS, OUTCOME_PLAYER_WIN } from '../core/sim/phases'
import { BLOCK_CATALOG, G0_RULESETS } from '../core/resources'
import type { RuleSet } from '../core/schemas'
import {
  BattlePortrait,
  OUTCOME_LABELS,
  OUTCOME_TONES,
  RULE_OFF_SUFFIX,
  SHEET_TABS,
  buildRunRulesets,
  buildRuleRows,
  checkRuleEnabled,
  formatLogTabCount,
  formatRuleCondition,
  formatRulesTabCount,
  formatTick,
  resolveOutcomeTone,
  toggleRulePriority,
  type BattlePortraitProps,
  type RuleRowView,
  type SheetTab,
} from '.'

const BATTLE_DIR = fileURLToPath(new URL('.', import.meta.url))

/** 주석을 걷어 낸 CSS. 주석 안의 설명 수치를 규율 위반으로 세지 않는다. */
function readStrippedCss(name: string): string {
  return readFileSync(`${BATTLE_DIR}${name}`, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')
}

/**
 * 선택자 하나의 선언 블록을 잘라 낸다.
 *
 * @param selector 찾을 선택자.
 * @returns 중괄호 안. 없으면 빈 문자열.
 */
function cutRule(selector: string): string {
  const css = readStrippedCss('battle.css')
  const start = css.indexOf(`${selector} {`)
  if (start < 0) {
    return ''
  }
  return css.slice(start, css.indexOf('}', start))
}

const PRESSURE = G0_RULESETS.get('g0_pressure') as RuleSet

/** 규칙 줄 셋. 실제 규칙표에서 만든 것이라 조건문에 실측값 자리가 그대로 있다. */
const ROWS: readonly RuleRowView[] = buildRuleRows({
  rules: PRESSURE.rules,
  trace: undefined,
  catalog: BLOCK_CATALOG,
  cpuBudget: 8,
  disabled: [],
})

/**
 * 화면 하나를 세운다. 바꿀 것만 넘긴다.
 *
 * @param patch 덮어쓸 props.
 * @returns 완성된 props.
 */
function buildProps(patch: Partial<BattlePortraitProps> = {}): BattlePortraitProps {
  return {
    location: '1층 · pillars',
    tick: 27,
    speed: 1,
    onSpeedChange: () => undefined,
    onInstant: () => undefined,
    onStep: () => undefined,
    onRestart: () => undefined,
    outcome: OUTCOME_ONGOING,
    plan: <canvas className="battle-plan__canvas" />,
    rows: ROWS,
    onToggleRule: () => undefined,
    cpuUsed: 5,
    cpuBudget: 8,
    entries: [{ tick: 27, rule: 1, expr: '적거리(2) <= 사거리(3)', outcome: 'SKILL_1 @goblin_runner', delta: -18, fired: true }],
    hp: 40,
    hpMax: 100,
    potions: 2,
    potionsMax: 3,
    scrolls: 1,
    scrollsMax: 1,
    tab: 'rules',
    onTabChange: () => undefined,
    ...patch,
  }
}

/**
 * 렌더 트리를 납작하게 편다. 훅이 없으므로 컴포넌트 함수를 직접 부를 수 있다.
 *
 * @param node 훑을 노드.
 * @returns 트리 안의 모든 엘리먼트.
 */
function collectElements(node: ReactNode): readonly ReactElement[] {
  if (Array.isArray(node)) {
    return node.flatMap((one: ReactNode) => collectElements(one))
  }
  if (!isValidElement(node)) {
    return []
  }
  const element = node as ReactElement<{ children?: ReactNode }>
  const rendered =
    typeof element.type === 'function'
      ? (element.type as (props: unknown) => ReactNode)(element.props)
      : element.props.children
  return [element, ...collectElements(rendered)]
}

describe('세로 시트 — 탭과 카운트 (명세 A·D)', () => {
  it('탭은 규칙표와 로그 둘뿐이다', () => {
    expect(SHEET_TABS).toEqual(['rules', 'log'])
  })

  it('탭 라벨에 카운트를 함께 적는다', () => {
    expect(formatRulesTabCount(4, 5)).toBe('4/5')
    expect(formatLogTabCount(27)).toBe('T027')
    expect(formatTick(27)).toBe('027')
    expect(formatTick(1027)).toBe('1027')
  })

  it('규칙표 탭은 켜진 줄만 센다 — 끄면 카운트가 줄어든다', () => {
    const rows = ROWS.map((row, index) => ({ ...row, enabled: index !== 0 }))
    const html = renderToStaticMarkup(<BattlePortrait {...buildProps({ rows })} />)
    expect(html).toContain(formatRulesTabCount(ROWS.length - 1, ROWS.length))
  })

  it('활성 탭은 명도와 굵기로만 표시한다 — 황동을 쓰지 않는다', () => {
    const on = cutRule('.battle__tab--on')
    expect(on).toContain('var(--fw-semibold)')
    expect(on).toContain('var(--text-body)')
    expect(on).toContain('var(--surface-raised)')
    expect(on).not.toContain('brass')
    expect(on).not.toContain('accent')
  })

  it('탭이 바뀌면 시트 본문만 바뀌고 도면은 그대로다', () => {
    const rules = renderToStaticMarkup(<BattlePortrait {...buildProps({ tab: 'rules' })} />)
    const log = renderToStaticMarkup(<BattlePortrait {...buildProps({ tab: 'log' })} />)

    expect(rules).toContain('ds-rule-table')
    expect(rules).not.toContain('ds-log-row')
    expect(log).toContain('ds-log-row')
    expect(log).not.toContain('ds-rule-table')

    // 도면과 그 둘레는 두 탭에서 한 글자도 다르지 않다.
    for (const html of [rules, log]) {
      expect(html).toContain('battle__col--plan')
      expect(html).toContain('battle-plan__canvas')
      expect(html).toContain('battle__status')
    }
  })

  it('탭을 누르면 그 탭이 올라온다', () => {
    const picked: SheetTab[] = []
    const elements = collectElements(
      <BattlePortrait {...buildProps({ onTabChange: (tab) => picked.push(tab) })} />,
    )
    const tabs = elements.filter(
      (element) => (element.props as { role?: string }).role === 'tab',
    )
    expect(tabs).toHaveLength(2)
    for (const tab of tabs) {
      ;(tab.props as { onClick: () => void }).onClick()
    }
    expect(picked).toEqual(['rules', 'log'])
  })

  it('지금 탭만 눌린 상태로 나간다', () => {
    const html = renderToStaticMarkup(<BattlePortrait {...buildProps({ tab: 'log' })} />)
    expect(html).toContain('aria-selected="true"')
    expect((html.match(/aria-selected="true"/g) ?? []).length).toBe(1)
  })
})

describe('도면은 고정이고 스크롤되지 않는다', () => {
  it('세로 도면 칸은 overflow 를 잠근다', () => {
    const block = cutRule('.battle--portrait .battle__col--plan')
    expect(block, '세로 도면 칸 규칙을 찾지 못했다').not.toBe('')
    expect(block).toContain('overflow: hidden')
    expect(block).toContain('padding: var(--plan-pad)')
  })

  it('도면은 시트 밖에 있다 — 시트가 바뀌어도 도면이 밀리지 않는다', () => {
    const html = renderToStaticMarkup(<BattlePortrait {...buildProps()} />)
    const plan = html.indexOf('battle__col--plan')
    const sheet = html.indexOf('battle__sheet')
    expect(plan).toBeGreaterThan(-1)
    expect(sheet).toBeGreaterThan(plan)
    // 시트 본문만 스크롤 영역이다.
    expect(cutRule('.battle__sheet-body')).toContain('overflow-y: auto')
  })

  it('여섯 줄 골격을 토큰으로 짠다 — 상단과 도면만 내용 높이다', () => {
    // **상단이 `auto` 인 것은 두 줄을 받기 위해서다** — 층·틱은 헤더로 고정하고 조작을
    // 아래 줄로 내린다. 치수는 여전히 토큰이 정한다: `min-height: var(--bar-top)` 이
    // **도면이 줄어들고 시트가 바닥을 지킨다.** 도면이 제 크기를 고집하면 시트가 0 까지
    // 짜부라지고, 바닥만 깔면 화면이 통째로 스크롤된다 — 스크롤되는 화면은 보이는
    // 화면이 아니다(실제 피드백 두 번).
    const block = cutRule('.battle--portrait')
    expect(block).toContain('minmax(calc(var(--plan-cell) * 5), 1fr) var(--bar-status)')
    expect(block).toContain('0.6fr')
    expect(block).toContain('var(--bar-bottom)')
  })

  it('도면 캔버스가 남는 높이에 맞춰 줄어든다 — 인라인 크기는 max-* 가 이긴다', () => {
    const block = cutRule('.battle--portrait .battle__frame canvas')
    expect(block).toContain('max-width: 100%')
    expect(block).toContain('max-height: 100%')
    expect(block).toContain('object-fit: contain')
  })

  it('상단 묶음에 상한이 있다 — 층 정산 문구가 길어도 도면·시트를 못 밀어낸다', () => {
    const block = cutRule('.battle--portrait .battle__bar--top')
    expect(block).toContain('max-height: calc(var(--bar-top) * 3)')
    expect(block).toContain('overflow-y: auto')
  })

  it('시트 몸통에 바닥이 있다 — 탭·CPU·발이 규칙표·로그를 0 으로 밀 수 없다', () => {
    expect(cutRule('.battle__sheet-body')).toContain('min-height: calc(var(--log-row-h) * 4)')
  })

  it('하단 바는 줄을 바꾼다 — 폭을 쥐어짜면 글자가 세로로 부서진다', () => {
    const block = cutRule('.battle__bar--bottom')
    expect(block).toContain('flex-wrap: wrap')
  })

  it('높이 100% 가 사슬로 이어진다 — 끊기면 축소가 아니라 절단이 된다', () => {
    expect(cutRule('.battle--portrait .battle__frame')).toContain('height: 100%')
  })

  it('시트가 바닥을 지켜도 모자라면 화면이 통째로 흐른다 — 닿을 수 없는 줄을 안 만든다', () => {
    expect(cutRule('.battle--portrait')).toContain('overflow-y: auto')
  })

  it('주소창이 접히는 모바일을 따라간다 — 100vh 는 접히기 전 높이다', () => {
    expect(cutRule('.battle')).toContain('100dvh')
  })
})

describe('규칙 행을 눌러 켜고 끈다 (명세 D)', () => {
  it('누르면 꺼지고 다시 누르면 켜진다', () => {
    expect(toggleRulePriority([], 2)).toEqual([2])
    expect(toggleRulePriority([2], 2)).toEqual([])
    expect(checkRuleEnabled([2], 2)).toBe(false)
    expect(checkRuleEnabled([2], 1)).toBe(true)
  })

  it('꺼진 목록은 오름차순이다 — 집합을 순회해 규칙표를 만들지 않는다 (R5)', () => {
    expect(toggleRulePriority(toggleRulePriority([3], 1), 2)).toEqual([1, 2, 3])
  })

  it('꺼진 줄은 조건문 뒤에 꺼짐을 적는다 — 명도만으로 알리지 않는다', () => {
    expect(formatRuleCondition('적거리(2) <= 사거리(3)', true)).toBe('적거리(2) <= 사거리(3)')
    expect(formatRuleCondition('적거리(2) <= 사거리(3)', false)).toBe(
      `적거리(2) <= 사거리(3)${RULE_OFF_SUFFIX}`,
    )
  })

  it('꺼진 줄에 꺼짐 수식자와 표기가 함께 나간다', () => {
    const rows = ROWS.map((row, index) => ({ ...row, enabled: index !== 1 }))
    const html = renderToStaticMarkup(<BattlePortrait {...buildProps({ rows })} />)
    expect(html).toContain('ds-rule-row--off')
    expect(html).toContain('꺼짐')
    // 꺼진 줄은 하나뿐이다.
    expect((html.match(/ds-rule-row--off/g) ?? []).length).toBe(1)
  })

  it('ds RuleRow 가 꺼짐을 두 채널로 낸다 — 수식자와 aria-pressed', () => {
    const off = renderToStaticMarkup(
      <RuleRow index={1} state="pending" condition="항상" action="접근" enabled={false} />,
    )
    expect(off).toContain('ds-rule-row--off')
    expect(off).toContain('aria-pressed="false"')

    // 켜짐 여부를 주지 않는 화면(데스크톱)은 전과 같은 마크업을 얻는다.
    const plain = renderToStaticMarkup(
      <RuleRow index={1} state="pending" condition="항상" action="접근" />,
    )
    expect(plain).not.toContain('ds-rule-row--off')
    expect(plain).not.toContain('aria-pressed')
  })

  it('꺼짐은 불투명도로 그린다 — 부품 안의 지역 상수다', () => {
    const css = readFileSync(fileURLToPath(new URL('../ds/ds.css', import.meta.url)), 'utf8')
    expect(css).toContain('.ds-rule-row--off')
    expect(css).toContain('--rule-off-opacity')
  })

  it('규칙 줄을 누르면 그 우선순위가 넘어온다', () => {
    const pressed: number[] = []
    const elements = collectElements(
      <BattlePortrait {...buildProps({ onToggleRule: (priority) => pressed.push(priority) })} />,
    )
    const ruleRows = elements.filter((element) => element.type === RuleRow)
    expect(ruleRows).toHaveLength(ROWS.length)
    for (const row of ruleRows) {
      ;(row.props as { onClick: () => void }).onClick()
    }
    expect(pressed).toEqual(ROWS.map((row) => row.priority))
  })

  it('끈 규칙은 판에 실리지 않는다 — 그것이 가설을 시험하는 수단이다', () => {
    const rulesets = buildRunRulesets(G0_RULESETS, PRESSURE.rulesetId, [PRESSURE.rules[0]?.priority ?? 1])
    const ruleset = rulesets.get(PRESSURE.rulesetId)
    expect(ruleset?.rules).toHaveLength(PRESSURE.rules.length - 1)
    expect(ruleset?.rules.map((rule) => rule.priority)).not.toContain(PRESSURE.rules[0]?.priority)
    // 나머지 줄의 순서는 그대로다. 그 순서가 RuleVM 의 평가 순서다.
    expect(ruleset?.rules.map((rule) => rule.priority)).toEqual(
      PRESSURE.rules.slice(1).map((rule) => rule.priority),
    )
  })

  it('아무것도 끄지 않으면 받은 대응표를 그대로 돌려준다 — 판이 재조립되지 않는다', () => {
    expect(buildRunRulesets(G0_RULESETS, PRESSURE.rulesetId, [])).toBe(G0_RULESETS)
  })

  it('꺼진 줄은 추적 결과를 찾지 않는다 — 판에 없으므로 평가되지 않았다', () => {
    const rows = buildRuleRows({
      rules: PRESSURE.rules,
      trace: {
        tick: 3,
        entityId: 'player',
        rows: [
          {
            priority: PRESSURE.rules[0]?.priority ?? 1,
            state: 'true',
            armed: true,
            condition: '항상',
            action: '접근',
            cpuUsed: 1,
          },
        ],
      },
      catalog: BLOCK_CATALOG,
      cpuBudget: 8,
      disabled: [PRESSURE.rules[0]?.priority ?? 1],
    })
    expect(rows[0]?.enabled).toBe(false)
    expect(rows[0]?.armed).toBe(false)
    expect(rows[0]?.state).toBe('pending')
  })
})

describe('상태줄 — 판정 네 가지 (명세 D)', () => {
  it('진행 중에도 판정을 적는다 — 세로에는 판정이 들어갈 다른 자리가 없다', () => {
    const html = renderToStaticMarkup(<BattlePortrait {...buildProps()} />)
    expect(html).toContain('◆ 전투 중')
    expect(html).toContain('battle__verdict--dim')
  })

  it('이기면 녹청, 쓰러지면 위험색이다', () => {
    const win = renderToStaticMarkup(
      <BattlePortrait {...buildProps({ outcome: OUTCOME_PLAYER_WIN })} />,
    )
    expect(win).toContain('✓ 방 클리어 · 다음 실로')
    expect(win).toContain('battle__verdict--true')

    const loss = renderToStaticMarkup(
      <BattlePortrait {...buildProps({ outcome: OUTCOME_PLAYER_LOSS })} />,
    )
    expect(loss).toContain('✕ 쓰러짐 · 규칙을 고쳐 다시')
    expect(loss).toContain('battle__verdict--danger')
  })

  it('색 계열표가 판정 라벨표와 같은 키를 덮는다 — 표가 갈리지 않는다', () => {
    expect([...OUTCOME_TONES.keys()]).toEqual([...OUTCOME_LABELS.keys()])
    expect(resolveOutcomeTone('NOPE')).toBe('dim')
  })

  it('예고가 있으면 상태줄 오른쪽에 붙는다', () => {
    const html = renderToStaticMarkup(
      <BattlePortrait {...buildProps({ threat: '◈ 2칸 앞 폭발' })} />,
    )
    expect(html).toContain('ds-threat')
    expect(html).toContain('2칸 앞 폭발')
  })
})

describe('시트 하단 — CPU 와 두 버튼', () => {
  it('예산을 넘으면 게이지가 위험색으로 넘어간다 — 오류가 아니라 수치다', () => {
    const under = renderToStaticMarkup(<BattlePortrait {...buildProps({ cpuUsed: 5 })} />)
    expect(under).toContain('ds-gauge--cpu')
    const over = renderToStaticMarkup(<BattlePortrait {...buildProps({ cpuUsed: 10 })} />)
    expect(over).toContain('ds-gauge--danger')
    expect(over).toContain('10 / 8')
  })

  it('한 틱과 처음부터 두 버튼이 있고 각각이 제 콜백을 부른다', () => {
    const onStep = vi.fn()
    const onRestart = vi.fn()
    const html = renderToStaticMarkup(<BattlePortrait {...buildProps({ onStep, onRestart })} />)
    expect(html).toContain('한 틱')
    expect(html).toContain('처음부터')

    const elements = collectElements(<BattlePortrait {...buildProps({ onStep, onRestart })} />)
    const buttons = elements.filter(
      (element) => (element.props as { onClick?: unknown }).onClick === onStep,
    )
    expect(buttons).not.toHaveLength(0)
    for (const button of buttons) {
      ;(button.props as { onClick: () => void }).onClick()
    }
    expect(onStep).toHaveBeenCalled()
    expect(onRestart).not.toHaveBeenCalled()
  })

  it('버튼과 탭의 히트 영역이 44px 이상이다 — 토큰으로만 준다', () => {
    expect(cutRule('.battle__sheet-actions .ds-button')).toContain('height: var(--btn-h)')
    expect(cutRule('.battle__tab')).toContain('min-height: var(--tap-min)')
  })

  it('배속은 다섯 칸이고 즉시 실행이 마지막이다', () => {
    const html = renderToStaticMarkup(<BattlePortrait {...buildProps()} />)
    const box = html.slice(html.indexOf('battle__speed'), html.indexOf('battle__col--plan'))
    expect((box.match(/<button/g) ?? []).length).toBe(5)
    expect(box).toContain('≫')
    // 활성 칸은 색이 아니라 눌림 상태로도 나간다.
    expect(box).toContain('aria-pressed="true"')
  })
})

describe('앱 조작부는 세로에서도 손에 닿는다', () => {
  it('상단바에 조작부를 끼운다 — 없으면 에디터로 돌아갈 길이 사라진다', () => {
    const html = renderToStaticMarkup(
      <BattlePortrait {...buildProps({ controls: <button type="button">규칙 고치기</button> })} />,
    )
    expect(html).toContain('battle__controls')
    expect(html).toContain('규칙 고치기')
    // 층·실과 틱을 밀어내지 않는다. 넘치면 그 칸 안에서만 민다.
    expect(cutRule('.battle__controls')).toContain('overflow-x: auto')
  })

  it('조작부를 주지 않으면 그 칸을 그리지 않는다', () => {
    expect(renderToStaticMarkup(<BattlePortrait {...buildProps()} />)).not.toContain(
      'battle__controls',
    )
  })
})

describe('세로 화면은 황동 예산을 지킨다', () => {
  it('primary 버튼이 하나도 없다 — 예산 셋은 규칙 줄·도면 말·편집 화면이 쓴다', () => {
    for (const tab of SHEET_TABS) {
      expect(renderToStaticMarkup(<BattlePortrait {...buildProps({ tab })} />)).not.toContain(
        'ds-button--primary',
      )
    }
  })
})
