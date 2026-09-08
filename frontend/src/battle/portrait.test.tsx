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
  it('★ 탭은 셋이다 — 정산이 로그와 같은 급으로 붙었다', () => {
    // 층 정산이 상단 알림이던 때는 뜰 때마다 도면·규칙표·로그가 전부 밀렸다.
    expect(SHEET_TABS).toEqual(['rules', 'log', 'reward'])
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

    // 도면과 상태 줄은 두 탭에서 한 글자도 다르지 않다.
    for (const html of [rules, log]) {
      expect(html).toContain('battle__col--plan')
      expect(html).toContain('battle-plan__canvas')
      expect(html).toContain('battle__vitals')
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
    expect(tabs).toHaveLength(3)
    for (const tab of tabs) {
      ;(tab.props as { onClick: () => void }).onClick()
    }
    expect(picked).toEqual(['rules', 'log', 'reward'])
  })

  it('지금 탭만 눌린 상태로 나간다', () => {
    const html = renderToStaticMarkup(<BattlePortrait {...buildProps({ tab: 'log' })} />)
    expect(html).toContain('aria-selected="true"')
    expect((html.match(/aria-selected="true"/g) ?? []).length).toBe(1)
  })
})

describe('상한이 아니라 흐름이다 (실제 피드백)', () => {
  it('★ 세로는 문서 흐름이다 — 격자 상한이 구역을 자르거나 짜부라뜨리면 안 된다', () => {
    const block = cutRule('.battle--portrait')
    expect(block).toContain('display: block')
    expect(block).toContain('min-height: 100dvh')
    expect(block).not.toContain('grid-template-rows')
  })

  it('★ 상단·캔버스에 max-height 가 없다 — 잘린 문구는 「짧은 문구」로 읽힌다', () => {
    expect(cutRule('.battle--portrait .battle__bar--top')).not.toContain('max-height')
    expect(cutRule('.battle--portrait .battle__frame canvas')).not.toContain('max-height')
  })

  it('★ 캔버스는 가로만 화면에 맞춘다 — 세로는 자연 높이다', () => {
    const block = cutRule('.battle-frame .battle__frame canvas')
    expect(block).toContain('max-width: 100%')
    expect(block).toContain('height: auto')
  })

  it('★ 껍데기도 함께 흐른다 — 가두면 흐름의 아래가 없는 화면이 된다', () => {
    // 예전에는 `.app:has(.battle--portrait)` 로 그때만 껍데기를 풀었다. 이제 껍데기
    // 자체가 상한이 아니라 바닥이라(`styles/shell.test.ts`) 그 되돌림이 필요 없다.
    const shell = readFileSync(
      fileURLToPath(new URL('../styles/app.css', import.meta.url)),
      'utf-8',
    )
    const block = shell.slice(shell.indexOf('.app {'), shell.indexOf('}', shell.indexOf('.app {')))
    expect(block).toContain('min-block-size: 100dvh')
    expect(block).not.toContain('overflow: hidden')
  })

  it('★ 안에서 흐르는 곳은 시트 몸통 하나다 — 로그는 수백 줄이다', () => {
    const block = cutRule('.battle__sheet-body')
    expect(block).toContain('min-height: calc(var(--log-row-h) * 10)')
    expect(block).toContain('overflow-y: auto')
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
  it('★ 진행 중에는 판정을 안 적는다 — 「전투 중」은 늘 참이라 정보가 아니다', () => {
    // 전용 줄(34px)에 늘 참인 문구를 세워 두던 자리다. 그 34px 이 곧 체력 게이지를
    // 화면 밖으로 미는 34px 이었다 — 세로에서 고정 줄 하나는 그만큼 비싸다.
    const html = renderToStaticMarkup(<BattlePortrait {...buildProps()} />)
    expect(html).not.toContain('◆ 전투 중')
    expect(html).toContain('battle__over')
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
  it('★ 예산을 넘으면 색만 넘어간다 — 오류가 아니라 수치다', () => {
    // 게이지 한 덩이(48px)를 쓰던 것을 상태 줄의 글자 하나로 줄였다. 전투 중에는
    // 예산이 변하지 않으므로 눈금이 필요 없고, 그 자리는 체력이 더 급하다.
    const under = renderToStaticMarkup(<BattlePortrait {...buildProps({ cpuUsed: 5 })} />)
    expect(under).toContain('cpu 5/8')
    expect(under).not.toContain('battle__cpu--over')
    const over = renderToStaticMarkup(<BattlePortrait {...buildProps({ cpuUsed: 10 })} />)
    expect(over).toContain('cpu 10/8')
    expect(over).toContain('battle__cpu--over')
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
    // 배속은 이제 시트 하단의 시간 조작 줄에 있다 — 도면 위 전용 줄(44px)이 사라졌다.
    const box = html.slice(html.indexOf('battle__speed'), html.indexOf('battle__time-acts'))
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

/** 도면 격자의 행 수. 토큰 `--plan-rows` 와 같은 수다. */
const PLAN_ROWS = 9

/**
 * `:root` 에서 토큰 하나를 px 로 읽는다. 세로가 기본 배치라 여기가 세로 값이다.
 *
 * @param name 토큰 이름.
 * @returns 값(px). 없으면 NaN.
 */
function readToken(name: string): number {
  const tokens = readFileSync(
    fileURLToPath(new URL('../../../design/tokens/spacing.css', import.meta.url)),
    'utf8',
  )
  const root = tokens.split('@media')[0] ?? ''
  const found = new RegExp(`${name}:\\s*(\\d+)px`).exec(root)
  return found === null ? Number.NaN : Number.parseInt(found[1] ?? '', 10)
}

describe('★ 한정된 화면의 공간 예산', () => {
  // **고정 줄의 합이 곧 시트에 남는 높이다.** 고치기 전에는 640px 을 고정으로 쓰고
  // 있어서 기준 화면(390x844)에서도 16px 넘쳤고, 넘친 만큼 밀려나는 것이 늘 체력
  // 게이지였다 — 전투에서 가장 자주 보는 수치가 접힌 자리 아래에 있었다.
  const SCREENS = [
    { name: 'iPhone SE', height: 667 },
    { name: '기준 390x844', height: 844 },
  ] as const

  /** 화면 하나를 채우고 남는 시트 높이. 토큰 합이 곧 이 회계다. */
  const buildBudget = (height: number): number =>
    height -
    readToken('--bar-top') -
    readToken('--bar-vitals') -
    readToken('--plan-cell') * PLAN_ROWS -
    readToken('--plan-pad') * 2 -
    readToken('--sheet-tab-h') -
    readToken('--bar-time')

  it('★ 가장 작은 화면에서도 시트가 여덟 줄을 낸다', () => {
    // 실측: SE(667) 189px = 여덟 줄, 기준(844) 366px = 열여섯 줄. 고치기 전에는 각각
    // 27px·204px 이었고 둘 다 열 줄(220)에 못 미쳐 체력이 화면 밖으로 밀렸다.
    //
    // 여덟 줄로 잡은 것은 그것이 「무슨 일이 있었는지」가 읽히는 하한이기 때문이다.
    // 더 받으려면 도면 셀을 줄여야 하는데, 도면이 작아지면 이 화면의 주어가 흐려진다.
    const rows = readToken('--log-row-h') * 8
    for (const screen of SCREENS) {
      expect(buildBudget(screen.height), `${screen.name} 에서 시트가 모자란다`)
        .toBeGreaterThanOrEqual(rows)
    }
  })

  it('★ 시트 높이가 하한과 상한이 같다 — 자라면 아래 전부가 밀린다', () => {
    // 예전에는 하한 10줄·상한 14줄이라 로그가 차는 동안 88px 이 한 번 밀렸다.
    const block = cutRule('.battle-frame:not(.battle-frame--panel) .battle__sheet-body')
    expect(block).toContain('min-height: var(--sheet-body-h)')
    expect(block).toContain('max-height: var(--sheet-body-h)')
  })

  it('★ 상태 줄이 한 줄에 갇힌다 — 접히면 도면과 시트가 그만큼 내려간다', () => {
    const block = cutRule('.battle__vitals')
    expect(block).toContain('height: var(--bar-vitals)')
    expect(cutRule('.battle__supply')).toContain('white-space: nowrap')
  })

  it('★ 머리 두 줄이 스크롤에 안 딸려 간다', () => {
    for (const selector of ['.battle--portrait .battle__bar--top', '.battle--portrait .battle__vitals']) {
      expect(cutRule(selector), selector).toContain('position: sticky')
    }
  })
})
