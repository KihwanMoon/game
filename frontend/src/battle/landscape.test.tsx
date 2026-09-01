/**
 * 가로 모바일 전투 화면(844×390)의 계약 — 명세 B.
 *
 * 세로와 같은 수단으로 본다(`portrait.test.tsx` 의 주석 참조) — jsdom 이 없으므로
 * `renderToStaticMarkup` 으로 마크업을 읽고, 훅이 없는 순수 함수인 `BattleLandscape` 는
 * 직접 불러 핸들러를 눌러 본다. 치수는 선언이므로 스타일시트와 토큰 파일을 읽는다.
 *
 * **이 배치에서 가장 쉽게 깨지는 것은 높이다.** 390px 에서 상단 40 + 하단 40 을 빼면
 * 본문이 310px 이고 도면이 306px 를 쓴다. 남는 4px 안에서 무엇도 자라면 안 된다. 그래서
 * 여기 있는 산술 단언들은 미관이 아니라 **도면이 잘리지 않는다**는 사실을 지킨다 —
 * 도면이 잘리면 이 화면은 관전용으로 쓸 수 없다.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { isValidElement, type ReactElement, type ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { OUTCOME_ONGOING, OUTCOME_PLAYER_LOSS } from '../core/sim/phases'
import { BLOCK_CATALOG, G0_RULESETS } from '../core/resources'
import type { RuleSet } from '../core/schemas'
import {
  BattleLandscape,
  RULE_OFF_SUFFIX,
  buildRuleRows,
  formatLogTabCount,
  formatOutcomeNotice,
  formatRulesTabCount,
  formatTick,
  type BattleLandscapeProps,
  type RuleRowView,
} from '.'

const BATTLE_DIR = fileURLToPath(new URL('.', import.meta.url))
const DESIGN_DIR = fileURLToPath(new URL('../../../design/', import.meta.url))

/** 명세 B 가 기준으로 삼은 화면. */
const VIEW = { width: 844, height: 390 } as const

/** 도면 격자. 토큰 `--plan-cols`·`--plan-rows` 와 같은 수다. */
const PLAN_COLS = 12
const PLAN_ROWS = 9

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

/**
 * 가로 미디어쿼리 안에서 토큰 하나의 값을 읽는다. 단위는 px 뿐이다.
 *
 * @param name 토큰 이름.
 * @returns 값(px). 그 블록에 없으면 NaN.
 */
function readLandscapeToken(name: string): number {
  const tokens = readFileSync(`${DESIGN_DIR}tokens/spacing.css`, 'utf8')
  const start = tokens.indexOf('@media (max-width:1023px)')
  expect(start, '가로 미디어쿼리가 토큰 CSS 에 없다').toBeGreaterThan(-1)
  const block = tokens.slice(start, tokens.indexOf('}\n}', start))
  const found = new RegExp(`${name}:\\s*(\\d+)px`).exec(block)
  return found === null ? Number.NaN : Number.parseInt(found[1] ?? '', 10)
}

/**
 * 루트(:root) 에서 토큰 하나의 값을 읽는다. 배치 무관 상수를 볼 때 쓴다.
 *
 * @param name 토큰 이름.
 * @returns 값(px).
 */
function readRootToken(name: string): number {
  const tokens = readFileSync(`${DESIGN_DIR}tokens/spacing.css`, 'utf8')
  const root = tokens.split('@media')[0] ?? ''
  const found = new RegExp(`${name}:\\s*(\\d+)px`).exec(root)
  return found === null ? Number.NaN : Number.parseInt(found[1] ?? '', 10)
}

const PRESSURE = G0_RULESETS.get('g0_pressure') as RuleSet

/** 규칙 줄들. 실제 규칙표에서 만들어 조건문에 실측값 자리가 그대로 있다. */
const ROWS: readonly RuleRowView[] = buildRuleRows({
  rules: PRESSURE.rules,
  trace: undefined,
  catalog: BLOCK_CATALOG,
  cpuBudget: 8,
  disabled: [],
})

/** 두 번째 규칙을 끈 줄들. */
const ROWS_OFF: readonly RuleRowView[] = buildRuleRows({
  rules: PRESSURE.rules,
  trace: undefined,
  catalog: BLOCK_CATALOG,
  cpuBudget: 8,
  disabled: [2],
})

/**
 * 화면 하나를 세운다. 바꿀 것만 넘긴다.
 *
 * @param patch 덮어쓸 props.
 * @returns 완성된 props.
 */
function buildProps(patch: Partial<BattleLandscapeProps> = {}): BattleLandscapeProps {
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
    entries: [
      {
        tick: 27,
        rule: 1,
        expr: '적거리(2) <= 사거리(3)',
        outcome: 'SKILL_1 @goblin_runner',
        delta: -18,
        fired: true,
      },
    ],
    hp: 40,
    hpMax: 100,
    potions: 2,
    potionsMax: 3,
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

describe('가로는 2열이다 (명세 B)', () => {
  it('본문이 도면 열과 시트 열 둘로 선다 — 좌측 규칙표 열은 시트 안으로 들어갔다', () => {
    const block = cutRule('.battle-ls__body')
    expect(block, '가로 본문 규칙을 찾지 못했다').not.toBe('')
    expect(block).toContain('grid-template-columns: minmax(var(--sp-0), 1fr) var(--col-sheet)')
  })

  it('우열 폭은 토큰이 정한 340 이다', () => {
    expect(readLandscapeToken('--col-sheet')).toBe(340)
  })

  it('도면이 먼저, 시트가 그다음이다 — 도면은 시트 밖에 있다', () => {
    const html = renderToStaticMarkup(<BattleLandscape {...buildProps()} />)
    const plan = html.indexOf('battle__col--plan')
    const sheet = html.indexOf('battle__sheet')
    expect(plan).toBeGreaterThan(-1)
    expect(sheet).toBeGreaterThan(plan)
  })

  it('규칙표와 로그가 한 시트를 나눠 쓴다 — 두 열이 동시에 서지 않는다', () => {
    const rules = renderToStaticMarkup(<BattleLandscape {...buildProps({ tab: 'rules' })} />)
    expect(rules).toContain('ds-rule-table')
    expect(rules).not.toContain('ds-log')

    const log = renderToStaticMarkup(<BattleLandscape {...buildProps({ tab: 'log' })} />)
    expect(log).toContain('ds-log')
    expect(log).not.toContain('ds-rule-table')
  })

  it('세로의 배속바·상태줄은 가로에 없다 — 그 자리는 상단 바와 하단 바가 겸한다', () => {
    expect(readLandscapeToken('--bar-speed')).toBe(0)
    expect(readLandscapeToken('--bar-status')).toBe(0)
    const html = renderToStaticMarkup(<BattleLandscape {...buildProps()} />)
    expect(html).not.toContain('battle__speed-bar')
    expect(html).not.toContain('battle__status')
    // 배속은 상단 바 안에 있고 판정은 하단 바 안에 있다.
    expect(html).toContain('battle__speed')
    expect(html).toContain('battle-ls__verdict')
  })
})

describe('도면이 잘리지 않는다 — 390px 높이가 이 배치의 유일한 제약이다', () => {
  it('도면 12×9 가 셀 32 로 남는 폭 안에 들어간다', () => {
    const cell = readLandscapeToken('--plan-cell')
    const pad = readLandscapeToken('--plan-pad')
    expect(cell).toBe(32)
    const sheet = readLandscapeToken('--col-sheet')
    // 시트 340 + 그 왼쪽 1px 괘선을 뺀 자리에 도면과 좌우 여백·테두리가 들어간다.
    const planColumn = VIEW.width - sheet - 1
    expect(cell * PLAN_COLS + pad * 2 + 2).toBeLessThanOrEqual(planColumn)
  })

  it('도면 높이가 상단·하단 바를 뺀 본문 안에 들어간다 — 남는 자리는 4px 뿐이다', () => {
    const cell = readLandscapeToken('--plan-cell')
    const pad = readLandscapeToken('--plan-pad')
    const body = VIEW.height - readLandscapeToken('--bar-top') - readLandscapeToken('--bar-bottom')
    expect(body).toBe(310)
    const plan = cell * PLAN_ROWS + pad * 2 + 2
    expect(plan).toBe(306)
    expect(plan).toBeLessThanOrEqual(body)
  })

  it('가로 도면 칸은 스크롤하지 않는다 — 규칙을 읽는 동안에도 유닛 위치가 보여야 한다', () => {
    const block = cutRule('.battle--landscape .battle__col--plan')
    expect(block, '가로 도면 칸 규칙을 찾지 못했다').not.toBe('')
    expect(block).toContain('overflow: hidden')
    expect(block).toContain('padding: var(--plan-pad)')
  })

  it('스크롤하는 것은 시트 본문 하나뿐이다', () => {
    expect(cutRule('.battle__sheet-body')).toContain('overflow-y: auto')
  })

  it('골격의 세 줄은 토큰이 정한다 — 가로에서 위아래가 40 이다', () => {
    expect(cutRule('.battle')).toContain(
      'grid-template-rows: var(--bar-top) 1fr var(--bar-bottom)',
    )
    expect(readLandscapeToken('--bar-top')).toBe(40)
    expect(readLandscapeToken('--bar-bottom')).toBe(40)
  })
})

describe('가로 치수는 전부 토큰에서 온다 (명세 B)', () => {
  it('규칙 행 50 · 탭 36 · 시트 버튼 30 · 배속 박스 28', () => {
    expect(readLandscapeToken('--row-h')).toBe(50)
    expect(readLandscapeToken('--sheet-tab-h')).toBe(36)
    expect(readLandscapeToken('--btn-h')).toBe(30)
    expect(readLandscapeToken('--speed-box-h')).toBe(28)
  })

  it('배속 칸은 44px 고정이다 — 세로처럼 폭을 나누지 않는다', () => {
    expect(readLandscapeToken('--speed-cell-w')).toBe(44)
    expect(cutRule('.battle--landscape .battle__speed .ds-button')).toContain(
      'flex: 0 0 var(--speed-cell-w)',
    )
    expect(cutRule('.battle--landscape .battle__speed')).toContain('flex: 0 0 auto')
  })

  it('탭 줄이 36 이므로 세로의 44 히트 영역 하한을 가로에서만 푼다', () => {
    expect(cutRule('.battle--landscape .battle__tab')).toContain(
      'min-height: var(--sheet-tab-h)',
    )
  })

  it('시트 하단은 한 줄이다 — 게이지 140 고정 + 남는 폭에 버튼 둘', () => {
    const block = cutRule('.battle--landscape .battle__sheet-foot')
    expect(block, '가로 시트 하단 규칙을 찾지 못했다').not.toBe('')
    expect(block).toContain('grid-template-columns: var(--sheet-gauge-w) minmax(var(--sp-0), 1fr)')
    expect(readRootToken('--sheet-gauge-w')).toBe(140)
  })

  it('시트 하단이 우열 안에 들어간다 — 탭 36 + 하단이 도면 높이를 넘지 않는다', () => {
    const tab = readLandscapeToken('--sheet-tab-h')
    // 하단 = 위아래 여백 8 + 버튼 높이(--btn-h). 게이지는 그보다 낮다.
    const foot = 8 * 2 + readLandscapeToken('--btn-h')
    expect(tab + foot).toBeLessThan(310)
  })

  it('가로 CSS 는 미디어쿼리를 적지 않는다 — 경계는 토큰 한 곳이다', () => {
    expect(readStrippedCss('battle.css')).not.toContain('@media')
  })
})

describe('상단 바 (명세 B)', () => {
  it('층·실 · 틱 · 배속 박스가 이 순서로 선다', () => {
    const html = renderToStaticMarkup(<BattleLandscape {...buildProps()} />)
    const location = html.indexOf('1층 · pillars')
    const tick = html.indexOf('battle__tick')
    const speed = html.indexOf('battle__speed')
    expect(location).toBeGreaterThan(-1)
    expect(tick).toBeGreaterThan(location)
    expect(speed).toBeGreaterThan(tick)
  })

  it('틱은 세 자리로 적는다 — 폭이 흔들리면 옆 글자가 밀린다', () => {
    const html = renderToStaticMarkup(<BattleLandscape {...buildProps({ tick: 27 })} />)
    expect(html).toContain(formatTick(27))
    expect(formatTick(27)).toBe('027')
  })

  it('앱의 조작부가 상단 바에 들어간다 — 없으면 에디터로 돌아갈 길이 사라진다', () => {
    const bare = renderToStaticMarkup(<BattleLandscape {...buildProps()} />)
    expect(bare).not.toContain('battle-ls__controls')
    const withControls = renderToStaticMarkup(
      <BattleLandscape {...buildProps({ controls: <button type="button">규칙 고치기</button> })} />,
    )
    expect(withControls).toContain('battle-ls__controls')
    expect(withControls).toContain('규칙 고치기')
  })

  it('배속 다섯 칸의 마지막이 즉시 실행이다', () => {
    const onInstant = vi.fn()
    const onSpeedChange = vi.fn()
    const elements = collectElements(
      <BattleLandscape {...buildProps({ onInstant, onSpeedChange })} />,
    )
    const group = elements.find((one) => {
      const props = one.props as { readonly className?: string }
      return props.className === 'battle__speed'
    })
    expect(group, '배속 박스를 찾지 못했다').toBeDefined()
    // 박스 안의 함수 컴포넌트가 곧 칸이다 — 배속 넷 + 즉시 실행 하나.
    const cells = collectElements(group).filter((one) => typeof one.type === 'function')
    expect(cells).toHaveLength(5)
    const last = cells[4]?.props as { readonly onClick?: () => void }
    last.onClick?.()
    expect(onInstant).toHaveBeenCalledTimes(1)
    expect(onSpeedChange).not.toHaveBeenCalled()
  })
})

describe('하단 바가 상태줄을 겸한다 (명세 B·D)', () => {
  it('체력 · 구분선 · 물약 · 판정이 한 줄에 선다', () => {
    const html = renderToStaticMarkup(<BattleLandscape {...buildProps()} />)
    expect(html).toContain('ds-hp')
    expect(html).toContain('battle-ls__rule-line')
    expect(html).toContain('ds-resource')
    expect(html).toContain(formatOutcomeNotice(OUTCOME_ONGOING))
  })

  it('체력 막대 폭은 명세가 정한 150 이다 — 세로의 90 과 다르다', () => {
    const html = renderToStaticMarkup(<BattleLandscape {...buildProps()} />)
    expect(html).toContain('width:150px')
  })

  it('판정은 진행 중에도 적는다 — 다음에 할 일까지 함께 말한다', () => {
    const ongoing = renderToStaticMarkup(<BattleLandscape {...buildProps()} />)
    expect(ongoing).toContain('◆ 전투 중')
    expect(ongoing).toContain('battle__verdict--dim')

    const lost = renderToStaticMarkup(
      <BattleLandscape {...buildProps({ outcome: OUTCOME_PLAYER_LOSS })} />,
    )
    expect(lost).toContain('✕ 쓰러짐 · 규칙을 고쳐 다시')
    expect(lost).toContain('battle__verdict--danger')
  })

  it('예고가 없으면 위협 칸을 그리지 않는다', () => {
    expect(renderToStaticMarkup(<BattleLandscape {...buildProps()} />)).not.toContain('ds-threat')
    expect(
      renderToStaticMarkup(<BattleLandscape {...buildProps({ threat: '◈ 폭발 2틱' })} />),
    ).toContain('ds-threat--danger')
  })
})

describe('시트 — 탭과 규칙 토글은 세로와 같은 부품이다', () => {
  it('탭 라벨에 카운트를 함께 적는다', () => {
    const html = renderToStaticMarkup(<BattleLandscape {...buildProps()} />)
    expect(html).toContain(formatRulesTabCount(ROWS.length, ROWS.length))
    expect(html).toContain(formatLogTabCount(27))
  })

  it('규칙표 탭은 켜진 줄만 센다', () => {
    const html = renderToStaticMarkup(<BattleLandscape {...buildProps({ rows: ROWS_OFF })} />)
    expect(html).toContain(formatRulesTabCount(ROWS.length - 1, ROWS.length))
  })

  it('꺼진 줄은 명도와 문구 두 채널로 적는다', () => {
    const html = renderToStaticMarkup(<BattleLandscape {...buildProps({ rows: ROWS_OFF })} />)
    expect(html).toContain('ds-rule-row--off')
    expect(html).toContain(RULE_OFF_SUFFIX.trim())
  })

  it('규칙 줄을 누르면 그 우선순위가 넘어온다', () => {
    const onToggleRule = vi.fn()
    const elements = collectElements(<BattleLandscape {...buildProps({ onToggleRule })} />)
    const hit = elements.find((one) => {
      const props = one.props as { readonly className?: string }
      return props.className === 'ds-rule-row__hit'
    })
    expect(hit, '규칙 줄의 히트 영역을 찾지 못했다').toBeDefined()
    ;(hit?.props as { readonly onClick?: () => void }).onClick?.()
    expect(onToggleRule).toHaveBeenCalledTimes(1)
  })

  it('탭을 누르면 그 탭이 올라온다', () => {
    const onTabChange = vi.fn()
    const elements = collectElements(<BattleLandscape {...buildProps({ onTabChange })} />)
    const tabs = elements.filter((one) => {
      const props = one.props as { readonly role?: string }
      return props.role === 'tab'
    })
    expect(tabs).toHaveLength(2)
    ;(tabs[1]?.props as { readonly onClick?: () => void }).onClick?.()
    expect(onTabChange).toHaveBeenCalledWith('log')
  })

  it('시트 하단의 두 버튼이 한 틱과 처음부터다', () => {
    const onStep = vi.fn()
    const onRestart = vi.fn()
    const elements = collectElements(<BattleLandscape {...buildProps({ onStep, onRestart })} />)
    const actions = elements.filter((one) => {
      const children = (one.props as { readonly children?: ReactNode }).children
      return children === '한 틱' || children === '처음부터'
    })
    expect(actions).toHaveLength(2)
    ;(actions[0]?.props as { readonly onClick?: () => void }).onClick?.()
    ;(actions[1]?.props as { readonly onClick?: () => void }).onClick?.()
    expect(onStep).toHaveBeenCalledTimes(1)
    expect(onRestart).toHaveBeenCalledTimes(1)
  })
})

describe('가로 화면도 황동 예산을 지킨다', () => {
  it('primary 버튼을 쓰지 않는다 — 예산 셋은 규칙 번호·좌측바·도면의 말이다', () => {
    const html = renderToStaticMarkup(<BattleLandscape {...buildProps()} />)
    expect(html).not.toContain('ds-button--primary')
  })

  it('활성 탭은 명도와 굵기로만 표시한다', () => {
    const block = cutRule('.battle__tab--on')
    expect(block, '활성 탭 규칙을 찾지 못했다').not.toBe('')
    expect(block).not.toContain('--brass')
    expect(block).not.toContain('--line-accent')
    expect(block).toContain('var(--fw-semibold)')
  })

  it('가로 절에 황동이 없다', () => {
    const css = readStrippedCss('battle.css')
    const start = css.indexOf('.battle-ls__top {')
    expect(start).toBeGreaterThan(-1)
    expect(css.slice(start)).not.toContain('--brass')
  })
})


describe('세로 배치의 상단 (층·틱은 헤더, 조작은 아래 줄)', () => {
  const css = readStrippedCss('battle.css')

  it('★ 조작이 둘째 줄로 내려간다 — 44px 한 줄에 다 넣으면 층과 틱이 먼저 잘린다', () => {
    expect(css).toMatch(/\.battle--portrait \.battle__controls \{[\s\S]*?flex-basis: 100%/)
  })

  it('★ 상단 행이 두 줄을 받는다 — 44px 로 고정하면 둘째 줄이 밖으로 나간다', () => {
    const block = /\.battle--portrait \{([\s\S]*?)\}/.exec(css)
    expect(block?.[1] ?? '').toContain('auto var(--bar-speed)')
  })

  it('★ 그래도 44px 아래로는 안 줄어든다 — 층·틱 한 줄은 늘 그 높이다', () => {
    const block = /\.battle--portrait \.battle__bar--top \{([\s\S]*?)\}/.exec(css)
    expect(block?.[1] ?? '').toContain('min-height: var(--bar-top)')
  })

  it('★ 둘째 줄이 잘리지 않는다 — 바가 한 줄 전제로 잘라 두었다', () => {
    const block = /\.battle--portrait \.battle__bar--top \{([\s\S]*?)\}/.exec(css)
    expect(block?.[1] ?? '').toContain('overflow: visible')
  })
})
