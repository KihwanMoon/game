/**
 * 모바일 규칙 편집 화면의 계약 — 명세 C.
 *
 * jsdom 이 없으므로(vitest environment 는 node 다) `battle/portrait.test.tsx` 와 같은 두
 * 수단으로 본다.
 *
 *   1. `renderToStaticMarkup` — 무엇이 화면에 나가는가. 카드 넷이 서는가, 인자를 받는
 *      인지 변수에 인자칸이 함께 뜨는가, 실측 줄이 값과 판정을 함께 적는가.
 *   2. **컴포넌트 함수를 직접 불러** 반환된 트리에서 칸을 고르고 버튼을 누른다.
 *      `RuleEditMobile` 은 훅이 없는 순수 함수라 이것이 된다 — 좌변을 고르면 어떤 조작이
 *      규칙표로 넘어가는지를 클릭 그대로 확인할 수 있다.
 *
 * 「390px 폭에 세 조각이 들어간다」는 토큰 산수라 토큰 파일을 읽어 계산한다. 브라우저에서
 * 실제로 그렇게 되는지는 e2e 가 따로 볼 몫이다.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { isValidElement, type ReactElement, type ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { BLOCK_CATALOG, G0_RULESETS } from '../core/resources'
import { renderTerm } from '../core/rules/ruleVm'
import type { Rule, RuleSet, Term } from '../core/schemas'
import { PRIORITY_NOTE } from './RuleEditCards'
import { RuleEditMobile, type RuleEditMobileProps } from './RuleEditMobile'
import type { RuleRowActions } from './RuleRowEditor'
import {
  MEASURE_SOURCE,
  UNMEASURED,
  formatMeasuredTerm,
  resolveMeasureState,
  type TermReadings,
} from './termMeasure'

const EDITOR_DIR = fileURLToPath(new URL('.', import.meta.url))
const DESIGN_DIR = fileURLToPath(new URL('../../../design/', import.meta.url))

const CPU_BUDGET = 8
const RULE_SLOTS = 5
const DECIMAL_RADIX = 10

/** 주석을 걷어 낸 CSS. 주석 안의 설명 수치를 규율 위반으로 세지 않는다. */
function readStrippedCss(name: string): string {
  return readFileSync(`${EDITOR_DIR}${name}`, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')
}

/**
 * 선택자 하나의 선언 블록을 잘라 낸다.
 *
 * @param selector 찾을 선택자.
 * @returns 중괄호 안. 없으면 빈 문자열.
 */
function cutRule(selector: string): string {
  const css = readStrippedCss('editor.css')
  const start = css.indexOf(`${selector} {`)
  if (start < 0) {
    return ''
  }
  return css.slice(start, css.indexOf('}', start))
}

/**
 * 토큰 하나의 값을 읽는다. 단위는 px 뿐이다.
 *
 * @param name 토큰 이름.
 * @param media 읽을 미디어쿼리의 머리. 생략하면 :root.
 * @returns 값(px). 그 블록에 없으면 NaN.
 */
function readToken(name: string, media?: string): number {
  const tokens = readFileSync(`${DESIGN_DIR}tokens/spacing.css`, 'utf8')
  const block =
    media === undefined
      ? (tokens.split('@media')[0] ?? '')
      : tokens.slice(tokens.indexOf(media), tokens.indexOf('}\n}', tokens.indexOf(media)))
  const found = new RegExp(`${name}:\\s*(\\d+)px`).exec(block)
  return found === null ? Number.NaN : Number.parseInt(found[1] ?? '', DECIMAL_RADIX)
}

// 폭 리터럴을 박지 않는다. 경계는 실측을 따라 바뀐다(599 → 840: 데스크톱 골격이
// 841px 부터 성립하고 그 아래는 iPad 세로가 가로로 넘쳤다). 이 블록의 정체는
// 폭이 아니라 --layout-mode:portrait 다.
const PORTRAIT_MEDIA = (
  /@media[^{]*(?=\{[^}]*--layout-mode:\s*portrait)/.exec(
    readFileSync(`${DESIGN_DIR}tokens/spacing.css`, 'utf8'),
  )?.[0] ?? ''
).trimEnd()
const LANDSCAPE_MEDIA = '@media (max-width:1023px)'

const PRESSURE = G0_RULESETS.get('g0_pressure') as RuleSet

/**
 * 규칙표를 고치는 조작 전부를 기록하는 가짜를 만든다.
 *
 * @returns 호출을 세는 `RuleRowActions`.
 */
function buildActions(): RuleRowActions {
  return {
    select: vi.fn(),
    update: vi.fn(),
    changeLhs: vi.fn(),
    changeTerm: vi.fn(),
    changeAction: vi.fn(),
    changeParam: vi.fn(),
    addTerm: vi.fn(),
    removeTerm: vi.fn(),
    addRule: vi.fn(),
    duplicate: vi.fn(),
    remove: vi.fn(),
    move: vi.fn(),
  }
}

/**
 * 화면 하나를 세운다. 바꿀 것만 넘긴다.
 *
 * @param patch 덮어쓸 props.
 * @returns 완성된 props.
 */
function buildProps(patch: Partial<RuleEditMobileProps> = {}): RuleEditMobileProps {
  return {
    mode: 'portrait',
    ruleset: PRESSURE,
    catalog: BLOCK_CATALOG,
    cpuBudget: CPU_BUDGET,
    ruleSlots: RULE_SLOTS,
    problems: new Map(),
    globalProblems: [],
    editIndex: 0,
    readings: new Map(),
    actions: buildActions(),
    onOpen: vi.fn(),
    onAdd: vi.fn(),
    onReorder: vi.fn(),
    onCancel: vi.fn(),
    onSave: vi.fn(),
    backLabel: '규칙표',
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

/** 화면에서 이름으로 찾은 조작부. */
type Handled = ReactElement<{
  readonly onChange?: (event: { readonly target: { readonly value: string } }) => void
  readonly onClick?: () => void
  readonly children?: ReactNode
}>

/**
 * 보조 기술이 읽는 이름으로 조작부 하나를 찾는다.
 *
 * @param props 화면 props.
 * @param label 찾을 이름.
 * @returns 찾은 엘리먼트. 없으면 undefined.
 */
function findByLabel(props: RuleEditMobileProps, label: string): Handled | undefined {
  const found = collectElements(RuleEditMobile(props)).find(
    (element) => (element.props as { readonly 'aria-label'?: string })['aria-label'] === label,
  )
  return found as Handled | undefined
}

/**
 * 글자로 버튼 하나를 찾는다.
 *
 * @param props 화면 props.
 * @param text 버튼에 적힌 글자.
 * @returns 찾은 엘리먼트. 없으면 undefined.
 */
function findByText(props: RuleEditMobileProps, text: string): Handled | undefined {
  const found = collectElements(RuleEditMobile(props)).find(
    (element) => element.type === 'button' && (element.props as { children?: ReactNode }).children === text,
  )
  return found as Handled | undefined
}

/**
 * 선택 칸 하나를 고른다.
 *
 * @param props 화면 props.
 * @param label 칸의 이름.
 * @param value 고를 값.
 */
function choose(props: RuleEditMobileProps, label: string, value: string): void {
  const field = findByLabel(props, label)
  expect(field, `${label} 칸이 화면에 없다`).toBeDefined()
  field?.props.onChange?.({ target: { value } })
}

/**
 * 화면을 마크업 문자열로 굽는다.
 *
 * @param props 화면 props.
 * @returns 정적 마크업.
 */
function render(props: RuleEditMobileProps): string {
  return renderToStaticMarkup(<RuleEditMobile {...props} />)
}

describe('세로 편집 화면 — 명세 C 의 카드 넷', () => {
  it('조건·행동·우선순위·CPU 네 카드가 선다', () => {
    const markup = render(buildProps())
    for (const title of ['조건', '행동', '우선순위', 'cpu']) {
      expect(markup).toContain(`edit-card__title">${title}<`)
    }
  })

  it('조건 카드 헤더가 값의 출처를 적는다', () => {
    expect(render(buildProps())).toContain(MEASURE_SOURCE)
  })

  it('조건은 좌변·비교·우변 세 조각이다', () => {
    const markup = render(buildProps())
    expect(markup).toContain('edit-cond__row')
    for (const label of ['조건 1 인지 변수', '조건 1 비교', '조건 1 우변 값', '조건 1 우변 종류']) {
      expect(markup).toContain(label)
    }
  })

  it('우선순위 카드가 순서의 뜻을 적는다', () => {
    expect(render(buildProps())).toContain(PRIORITY_NOTE)
  })

  it('상단바는 규칙 번호를, 하단바는 되돌리기와 저장을 낸다', () => {
    const markup = render(buildProps())
    expect(markup).toContain('edit-m__heading-num')
    expect(markup).toContain('번 규칙 편집')
    expect(markup).toContain('되돌리기')
    expect(markup).toContain('edit-m__btn--save')
  })

  it('황동은 규칙 번호와 저장 버튼 둘뿐이다', () => {
    // 화면당 3곳이 상한이고 편집 화면은 둘을 쓴다 (모바일 원본). 나머지 자리는 명도로만
    // 말하므로, 황동을 읽는 선언이 이 화면의 클래스 둘에만 있어야 한다.
    const brass = ['.edit-m__heading-num', '.edit-m__btn--save']
    for (const selector of brass) {
      expect(cutRule(selector)).toMatch(/--text-accent|--border-accent/)
    }
    expect(cutRule('.edit-seg__cell--on')).not.toContain('accent')
    expect(cutRule('.edit-op--on')).not.toContain('accent')
  })
})

describe('조건 세 조각을 고른다', () => {
  it('좌변을 고르면 인자와 우변이 함께 따라간다', () => {
    const props = buildProps()
    choose(props, '조건 1 인지 변수', 'target_distance')
    expect(props.actions.changeLhs).toHaveBeenCalledWith(0, 0, 'target_distance')
  })

  it('비교 연산자를 고른다', () => {
    const props = buildProps()
    choose(props, '조건 1 비교', '>=')
    expect(props.actions.changeTerm).toHaveBeenCalledWith(0, 0, { comparison: '>=' })
  })

  it('우변에 리터럴을 넣는다', () => {
    const props = buildProps()
    choose(props, '조건 1 우변 값', '7')
    expect(props.actions.changeTerm).toHaveBeenCalledWith(0, 0, { rhs: 7 })
  })

  it('우변을 자기 스탯 참조로 바꾼다 (F-2)', () => {
    const props = buildProps()
    choose(props, '조건 1 우변 종류', 'stat')
    expect(props.actions.changeTerm).toHaveBeenCalledWith(0, 0, { rhs: { stat: 'attack_range' } })
  })

  it('스탯 우변에서는 스탯 목록이 뜨고 다시 값으로 돌아올 수 있다', () => {
    const statRule: Rule = {
      ...(PRESSURE.rules[0] as Rule),
      conditions: {
        op: 'SINGLE',
        terms: [
          { lhs: 'self_hp_percent', comparison: '<', rhs: { stat: 'hp_max' }, lhsParam: null },
        ],
      },
    }
    const props = buildProps({
      ruleset: { ...PRESSURE, rules: [statRule] },
      editIndex: 0,
    })
    choose(props, '조건 1 우변 스탯', 'attack_range')
    expect(props.actions.changeTerm).toHaveBeenCalledWith(0, 0, { rhs: { stat: 'attack_range' } })

    choose(props, '조건 1 우변 종류', 'literal')
    // 범위가 있는 블록은 가운데 값이 기본이다 (내 HP% 는 0~100).
    expect(props.actions.changeTerm).toHaveBeenCalledWith(0, 0, { rhs: 50 })
  })

  it('불리언 좌변은 비교가 둘뿐이고 우변이 참·거짓이다', () => {
    // 규칙 2 의 둘째 항은 `내 쿨타임[SKILL_1] == true` 다.
    const props = buildProps({ editIndex: 1 })
    const markup = render(props)
    expect(markup).toContain('조건 2 우변')
    expect(markup).not.toContain('조건 2 우변 종류')
    choose(props, '조건 2 우변', 'false')
    expect(props.actions.changeTerm).toHaveBeenCalledWith(1, 1, { rhs: false })
  })

  it('항을 더하고 지운다', () => {
    const props = buildProps()
    findByText(props, '＋ 조건 추가')?.props.onClick?.()
    expect(props.actions.addTerm).toHaveBeenCalledWith(0)

    findByLabel(props, '조건 2 삭제')?.props.onClick?.()
    expect(props.actions.removeTerm).toHaveBeenCalledWith(0, 1)
  })

  it('항이 둘 이상일 때만 연산자를 고를 수 있다', () => {
    const many = buildProps()
    findByText(many, 'OR')?.props.onClick?.()
    expect(many.actions.update).toHaveBeenCalledWith(0, {
      conditions: { op: 'OR', terms: (PRESSURE.rules[0] as Rule).conditions.terms },
    })

    // 규칙 3 은 항이 하나다. 연산자는 뜻이 없으므로 눌리지 않는다.
    const single = buildProps({ editIndex: 2 })
    const found = collectElements(RuleEditMobile(single)).find(
      (element) =>
        element.type === 'button' && (element.props as { children?: ReactNode }).children === 'AND',
    )
    expect((found?.props as { disabled?: boolean } | undefined)?.disabled).toBe(true)
  })
})

describe('인자를 받는 인지 변수는 인자칸이 함께 뜬다', () => {
  it('대상 거리[셀렉터]에는 셀렉터 칸이 붙는다', () => {
    // 규칙 2 의 첫 항이 `대상 거리[NEAREST]` 다.
    const props = buildProps({ editIndex: 1 })
    expect(render(props)).toContain('조건 1 selector 인자')
    choose(props, '조건 1 selector 인자', 'LOWEST_HP')
    expect(props.actions.changeTerm).toHaveBeenCalledWith(1, 0, { lhsParam: 'LOWEST_HP' })
  })

  it('쿨타임[스킬]에도 붙는다', () => {
    expect(render(buildProps({ editIndex: 1 }))).toContain('조건 2 skill 인자')
  })

  it('인자가 없는 인지 변수에는 붙지 않는다', () => {
    // 규칙 1 의 두 항(내 HP% · 내 포션 수)은 인자를 받지 않는다.
    expect(render(buildProps())).not.toContain('인자')
  })
})

describe('실측 줄 — 값이 없으면 pending, 있으면 병기한다', () => {
  const term: Term = { lhs: 'self_hp_percent', comparison: '<', rhs: 25, lhsParam: null }

  it('아직 평가되지 않은 항은 값 자리에 – 를 둔다', () => {
    expect(formatMeasuredTerm(term, BLOCK_CATALOG, new Map())).toBe(`내 HP%(${UNMEASURED}) < 25`)
    expect(resolveMeasureState(term, new Map())).toBe('pending')
  })

  it('측정값이 있으면 코어가 만드는 문자열과 **같은 줄**을 적는다', () => {
    const readings: TermReadings = new Map([['self_hp_percent', 41]])
    expect(formatMeasuredTerm(term, BLOCK_CATALOG, readings)).toBe(
      renderTerm(term, 41, BLOCK_CATALOG, 25),
    )
    expect(formatMeasuredTerm(term, BLOCK_CATALOG, readings)).toBe('내 HP%(41) < 25')
  })

  it('참·거짓을 코어와 같은 비교로 낸다', () => {
    expect(resolveMeasureState(term, new Map([['self_hp_percent', 41]]))).toBe('false')
    expect(resolveMeasureState(term, new Map([['self_hp_percent', 11]]))).toBe('true')
  })

  it('스탯 우변은 양변에 값을 병기한다', () => {
    const statTerm: Term = {
      lhs: 'target_distance',
      comparison: '<=',
      rhs: { stat: 'attack_range' },
      lhsParam: 'NEAREST',
    }
    const readings: TermReadings = new Map([
      ['target_distance[NEAREST]', 2],
      ['$attack_range', 3],
    ])
    // 인자는 좌변의 일부다 — `대상 거리[NEAREST]` 와 `대상 거리[LOWEST_HP]` 는 다른 항이다.
    expect(formatMeasuredTerm(statTerm, BLOCK_CATALOG, readings)).toBe(
      '대상 거리[NEAREST](2) <= 사거리(3)',
    )
    expect(resolveMeasureState(statTerm, readings)).toBe('true')
  })

  it('화면의 실측 줄이 글리프와 값을 함께 낸다 — 색만으로 적지 않는다', () => {
    const markup = render(buildProps())
    expect(markup).toContain('edit-measure')
    expect(markup).toContain('ds-glyph--pending')
    // ValueExpr 은 괄호 안 실측값을 따로 감싼다 — 항 이름보다 한 단 밝게 적기 위해서다.
    expect(markup).toContain('>내 HP%<')
    expect(markup).toContain(`ds-expr__value">(${UNMEASURED})<`)
    expect(markup).toContain('&lt; 25')

    const measured = render(
      buildProps({ readings: new Map([['self_hp_percent', 11]]) }),
    )
    expect(measured).toContain('ds-glyph--true')
    expect(measured).toContain('ds-expr__value">(11)<')
  })
})

describe('행동과 우선순위와 CPU', () => {
  it('행동과 셀렉터를 고른다', () => {
    const props = buildProps({ editIndex: 1 })
    choose(props, '규칙 2 행동', 'ATTACK')
    expect(props.actions.changeAction).toHaveBeenCalledWith(1, 'ATTACK')

    choose(props, '규칙 2 대상', 'LOWEST_HP')
    expect(props.actions.update).toHaveBeenCalledWith(1, { target: 'LOWEST_HP' })
  })

  it('대상을 받지 않는 행동에는 셀렉터 칸이 없다', () => {
    // 규칙 1 은 USE_POTION 이라 TARGET 절을 받지 않는다.
    expect(render(buildProps())).not.toContain('규칙 1 대상')
  })

  it('SET 절도 고를 수 있다 — 모바일에서 만든 규칙표가 플래그를 잃지 않는다', () => {
    const props = buildProps()
    choose(props, '규칙 1 플래그', 'A')
    expect(props.actions.update).toHaveBeenCalledWith(0, { setFlag: 'A=true' })
  })

  it('우선순위 세그먼트가 자리를 옮긴다', () => {
    const props = buildProps()
    const cells = collectElements(RuleEditMobile(props)).filter((element) =>
      String((element.props as { className?: string }).className ?? '').includes('edit-seg__cell'),
    )
    expect(cells).toHaveLength(PRESSURE.rules.length)
    ;(cells[2] as Handled | undefined)?.props.onClick?.()
    expect(props.onReorder).toHaveBeenCalledWith(2)
  })

  it('CPU 는 이 규칙과 저장 후 합계를 함께 적는다 — 초과해도 막지 않는다', () => {
    const markup = render(buildProps())
    expect(markup).toContain('이 규칙 cpu 2')
    expect(markup).toContain(`저장 후 6 / ${String(CPU_BUDGET)}`)

    const heavy = render(
      buildProps({
        ruleset: { ...PRESSURE, rules: PRESSURE.rules.map((rule) => ({ ...rule, cpuCost: 4 })) },
      }),
    )
    expect(heavy).toContain('ds-gauge--danger')
    expect(heavy).toContain('조건 1 인지 변수')
  })
})

describe('저장과 취소', () => {
  it('저장은 확정하고 목록으로 돌아간다', () => {
    const props = buildProps()
    findByText(props, '저장')?.props.onClick?.()
    expect(props.onSave).toHaveBeenCalledTimes(1)
    expect(props.onCancel).not.toHaveBeenCalled()
  })

  it('되돌리기는 되돌린다 — 되돌리는 문은 이것 하나뿐이다', () => {
    const props = buildProps()
    findByText(props, '되돌리기')?.props.onClick?.()
    expect(props.onCancel).toHaveBeenCalledTimes(1)
  })

  it('★ 뒤로 화살표는 고친 것을 지키고 나간다 — 되돌리지 않는다', () => {
    // 예전에는 이 화살표가 `onCancel` 이었다. 규칙을 고치고 목록으로 돌아가면 고친 것이
    // 조용히 사라졌고, 그것이 "수정해도 저장이 안 된다" 로 보고됐다. 뒤로는 어디서나
    // "여기까지" 라는 뜻이지 "없던 일로" 가 아니다.
    const props = buildProps()
    const back = collectElements(RuleEditMobile(props)).find((element) =>
      String((element.props as { className?: string }).className ?? '').includes('edit-m__back'),
    )
    ;(back as Handled | undefined)?.props.onClick?.()
    expect(props.onSave).toHaveBeenCalledTimes(1)
    expect(props.onCancel).not.toHaveBeenCalled()
  })

  it('지워진 규칙을 편집하던 중이면 목록으로 접힌다', () => {
    const markup = render(buildProps({ editIndex: 9 }))
    expect(markup).toContain('edit-m--list')
  })
})

describe('규칙표 목록 — 편집 화면으로 가는 문', () => {
  const listProps = (patch: Partial<RuleEditMobileProps> = {}): RuleEditMobileProps =>
    buildProps({ editIndex: -1, ...patch })

  it('규칙 줄을 누르면 그 규칙의 편집 화면이 열린다', () => {
    const props = listProps()
    findByLabel(props, '규칙 2 편집')?.props.onClick?.()
    expect(props.onOpen).toHaveBeenCalledWith(1)
  })

  it('규칙을 더하고 복제하고 지운다', () => {
    const props = listProps()
    findByText(props, '＋ 규칙 추가')?.props.onClick?.()
    expect(props.onAdd).toHaveBeenCalledTimes(1)

    findByLabel(props, '규칙 1 복제')?.props.onClick?.()
    expect(props.actions.duplicate).toHaveBeenCalledWith(0)

    findByLabel(props, '규칙 1 삭제')?.props.onClick?.()
    expect(props.actions.remove).toHaveBeenCalledWith(0)
  })

  it('출격 조작부와 코드 라이브러리에 손이 닿는다', () => {
    const markup = render(
      listProps({
        controls: <div className="launch-probe" />,
        library: <div className="library-probe" />,
      }),
    )
    expect(markup).toContain('launch-probe')
    expect(markup).toContain('library-probe')
  })

  it('검증 위반을 그 규칙 줄 아래에 적는다', () => {
    const markup = render(
      listProps({
        problems: new Map([[2, ['TARGET 셀렉터가 필요하다']]]),
        globalProblems: ['규칙 6개가 슬롯 5개를 넘었다'],
      }),
    )
    expect(markup).toContain('TARGET 셀렉터가 필요하다')
    expect(markup).toContain('규칙 6개가 슬롯 5개를 넘었다')
    expect(markup).toContain('위반 2')
  })

  it('조건문은 잘리지 않는다 — 실측값 병기가 줄의 존재 이유다', () => {
    expect(cutRule('.edit-m__lines')).toContain('overflow-wrap: anywhere')
    expect(cutRule('.edit-m__lines')).not.toContain('text-overflow')
    expect(cutRule('.edit-measure .ds-expr')).toContain('overflow-wrap: anywhere')
  })
})

describe('가로 편집 — 1fr 300px', () => {
  it('두 열이 서고 취소·저장이 우열로 들어간다', () => {
    const markup = render(buildProps({ mode: 'landscape' }))
    expect(markup).toContain('edit-ls__body')
    expect(markup).toContain('edit-ls__col--main')
    expect(markup).toContain('edit-ls__col--side')
    // 하단바를 쌓지 않는다 — 높이가 390px 뿐이다.
    expect(markup).not.toContain('edit-m__bar--edit')
    // 조건·행동은 좌열, 우선순위·CPU·버튼은 우열이다.
    const side = markup.indexOf('edit-ls__col--side')
    expect(markup.indexOf('edit-cond__row')).toBeLessThan(side)
    expect(markup.indexOf('edit-m__btn--save')).toBeGreaterThan(side)
  })

  it('우열 폭은 토큰이 정한다', () => {
    expect(cutRule('.edit-ls__body')).toContain('var(--edit-col)')
    expect(readToken('--edit-col')).toBe(300)
  })
})

describe('토큰 규율', () => {
  it('editor.css 는 미디어쿼리를 스스로 적지 않는다 — 경계는 토큰 한 곳이다', () => {
    expect(readStrippedCss('editor.css')).not.toContain('@media')
  })

  it('명세 C 의 치수가 토큰에 있다', () => {
    expect(readToken('--field-h')).toBe(40)
    expect(readToken('--card-head-h')).toBe(32)
    expect(readToken('--edit-cmp-w')).toBe(78)
    expect(readToken('--edit-op-h')).toBe(36)
    expect(readToken('--bar-edit', PORTRAIT_MEDIA)).toBe(60)
    expect(readToken('--edit-btn-h', PORTRAIT_MEDIA)).toBe(44)
    expect(readToken('--edit-btn-h')).toBe(36)
    expect(readToken('--bar-edit', LANDSCAPE_MEDIA)).toBe(0)
  })

  it('세로 취소·저장은 히트 영역 하한을 넘는다', () => {
    expect(readToken('--edit-btn-h', PORTRAIT_MEDIA)).toBeGreaterThanOrEqual(readToken('--tap-min'))
    expect(cutRule('.edit-m__btn')).toContain('height: var(--edit-btn-h)')
    expect(cutRule('.edit-m__hit')).toContain('min-height: var(--row-h)')
  })

  it('조건 세 조각이 390px 안에 들어간다', () => {
    // 화면 390 − 본문 여백(--plan-pad) 좌우 − 카드 테두리 2 − 카드 본문 여백(--sp-3) 좌우.
    const screen = 390
    const inner =
      screen - readToken('--plan-pad', PORTRAIT_MEDIA) * 2 - 2 - readToken('--sp-3') * 2
    // 비교 칸은 고정이고 좌·우변이 남는 자리를 나눈다. 사이 간격은 --sp-2 둘.
    const sides = inner - readToken('--edit-cmp-w') - readToken('--sp-2') * 2
    expect(sides).toBeGreaterThan(0)
    expect(cutRule('.edit-cond__row')).toContain('var(--edit-cmp-w)')
  })
})

describe('좁은 화면의 규칙표 탭', () => {
  // **모바일은 세 열을 못 편다.** 데스크톱처럼 팔레트·본문·검증을 나란히 두지 않고
  // 세로로 쌓는다 (명세 C) — 그래도 **한 번에 한 규칙표**라는 규약은 같다.
  const UPKEEP_TAB = {
    id: 'upkeep',
    label: '정비 규칙',
    palette: <div>정비 팔레트다</div>,
    main: <div>정비 본문이다</div>,
    check: <div>정비 검증이다</div>,
    gauge: <span>정비 계량이다</span>,
    foot: <span>정비 안내다</span>,
  }

  it('★ 탭 줄이 본문에 선다 — 좁은 상단 바에는 자리가 없다', () => {
    const html = renderToStaticMarkup(
      RuleEditMobile(
        buildProps({ editIndex: -1, tabs: [UPKEEP_TAB], tabId: 'combat', onTab: vi.fn() }),
      ),
    )
    expect(html).toContain('edit-m__tabs')
    expect(html).toContain('전투 규칙')
    expect(html).toContain('정비 규칙')
  })

  it('★ 탭 줄이 출격 조작부 **아래**다 — 접히면 출격 버튼이 그만큼 밀린다', () => {
    // 탭이 여덟이면 좁은 폭에서 두세 줄로 접힌다. 그것이 위에 있으면 이 화면에서 가장
    // 자주 누르는 출격이 화면 밖으로 나간다.
    for (const tabId of ['combat', 'upkeep']) {
      const html = renderToStaticMarkup(
        RuleEditMobile(
          buildProps({
            editIndex: -1,
            tabs: [UPKEEP_TAB],
            tabId,
            onTab: vi.fn(),
            controls: <button type="button">출격</button>,
          }),
        ),
      )
      expect(html.indexOf('출격')).toBeLessThan(html.indexOf('edit-m__tabs'))
    }
  })

  it('★ 본문 하나뿐인 탭은 본문만 쌓는다 — 없는 팔레트 자리를 비워 두지 않는다', () => {
    const html = renderToStaticMarkup(
      RuleEditMobile(
        buildProps({
          editIndex: -1,
          tabs: [{ id: 'bag', label: '가방', main: <div>가방 본문이다</div> }],
          tabId: 'bag',
          onTab: vi.fn(),
        }),
      ),
    )
    expect(html).toContain('가방 본문이다')
    expect(html).not.toContain('edit-m__rules')
  })

  it('★ 정비 탭을 열면 세 조각이 세로로 쌓인다 — 좁은 화면에는 열이 하나뿐이다', () => {
    const html = renderToStaticMarkup(
      RuleEditMobile(
        buildProps({ editIndex: -1, tabs: [UPKEEP_TAB], tabId: 'upkeep', onTab: vi.fn() }),
      ),
    )
    expect(html).toContain('정비 본문이다')
    expect(html).toContain('정비 팔레트다')
    expect(html).toContain('정비 검증이다')
  })

  it('★ 정비 탭에서는 전투 규칙 줄이 안 보인다 — 한 번에 한 규칙표다', () => {
    const html = renderToStaticMarkup(
      RuleEditMobile(
        buildProps({ editIndex: -1, tabs: [UPKEEP_TAB], tabId: 'upkeep', onTab: vi.fn() }),
      ),
    )
    expect(html).not.toContain('edit-m__rules')
  })

  it('★ 출격 조작부는 두 탭에 다 남는다 — 없으면 정비 탭에서 나갈 길이 사라진다', () => {
    const html = renderToStaticMarkup(
      RuleEditMobile(
        buildProps({
          editIndex: -1,
          tabs: [UPKEEP_TAB],
          tabId: 'upkeep',
          onTab: vi.fn(),
          controls: <button type="button">출격</button>,
        }),
      ),
    )
    expect(html).toContain('출격')
  })
})

describe('★ 좁은 화면이 가로로 밀리지 않는다', () => {
  // 탭 여덟이 한 줄에 들어가려다 화면 폭을 넘겨 **페이지 전체가 가로로 밀렸다** — 왼쪽이
  // 잘려 규칙 조건문의 앞머리가 사라졌다(실제 신고). 원인은 둘이었고 둘 다 여기서 본다.
  it('탭 줄이 접힌다 — 안 접히면 여덟 칸이 한 줄을 고집한다', () => {
    expect(cutRule('.edit-m__tabs')).toContain('flex-wrap: wrap')
  })

  it('탭 한 칸이 폭을 나눠 갖지 않는다 — `flex: 1 1 0` 은 탭이 둘이던 시절 값이다', () => {
    // 플렉스 항목은 min-content 아래로 안 줄어든다. 여덟을 8분의 1로 누르면 줄 전체가
    // 화면을 넘는다.
    const rule = cutRule('.edit-m__tab')
    expect(rule).toContain('flex: 0 1 auto')
    expect(rule).not.toContain('flex: 1 1 0')
  })

  it('라벨을 글자 단위로 쪼개지 않는다 — 「정비 규칙」이 세로로 서면 못 읽는다', () => {
    expect(cutRule('.edit-m__tab')).toContain('white-space: nowrap')
  })

  it('몸통이 내용보다 좁아질 수 있다 — 격자 칸의 기본은 안 줄어드는 auto 다', () => {
    expect(cutRule('.edit-m__body')).toContain('min-width: var(--sp-0)')
  })
})
