/**
 * 규칙 에디터의 렌더 계약과 토큰 규율.
 *
 * jsdom 없이 `renderToStaticMarkup` 으로 마크업 문자열만 본다(`ds/ds.test.tsx` 와 같은
 * 방식). 여기서 확인하는 것은 상호작용이 아니라 **화면에 무엇이 나가는가** 다 —
 * 골격 세 열, 팔레트가 카탈로그 전량을 싣는가, 검증 메시지가 그 규칙 줄에 붙는가,
 * 예산 초과가 편집을 막지 않고 rust 세로바로만 나가는가.
 *
 * 토큰 규율 검사가 함께 있는 이유는 생 hex·생 px 가 리뷰에서 잘 안 보이기 때문이다.
 * 한 번 새면 화면마다 다른 값이 자란다.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { BLOCK_CATALOG, G0_RULESETS } from '../core/resources'
import type { RuleSet } from '../core/schemas'
import { MAX_PRESET_SLOTS, type RulePreset } from '../storage'
import { checkWideTab } from './editorTabs'
import { RuleEditor } from './RuleEditor'
import { RuleLibrary } from './RuleLibrary'

const CPU_BUDGET = 8
const RULE_SLOTS = 5

/**
 * 에디터를 마크업 문자열로 굽는다.
 *
 * @param ruleset 실을 규칙표.
 * @returns 정적 마크업.
 */
function renderEditor(ruleset: RuleSet): string {
  return renderToStaticMarkup(
    <RuleEditor
      ruleset={ruleset}
      catalog={BLOCK_CATALOG}
      cpuBudget={CPU_BUDGET}
      ruleSlots={RULE_SLOTS}
      onChange={() => undefined}
    />,
  )
}

/**
 * 주석을 걷어 낸 스타일 시트를 읽는다.
 *
 * @param name 파일 이름.
 * @returns 주석이 빠진 내용.
 */
function readStrippedCss(name: string): string {
  const path = fileURLToPath(new URL(name, import.meta.url))
  return readFileSync(path, 'utf-8').replace(/\/\*[\s\S]*?\*\//g, '')
}

const PRESSURE = G0_RULESETS.get('g0_pressure') as RuleSet

describe('규칙 에디터 렌더', () => {
  it('팔레트·리스트·검증 세 열을 낸다', () => {
    const markup = renderEditor(PRESSURE)
    expect(markup).toContain('editor__col--palette')
    expect(markup).toContain('editor__col--main')
    expect(markup).toContain('editor__col--check')
    expect(markup).toContain('editor__rule-line')
  })

  it('팔레트가 카탈로그 전량을 싣는다', () => {
    const markup = renderEditor(PRESSURE)
    for (const block of BLOCK_CATALOG.perceptions.values()) {
      expect(markup).toContain(block.labelKo)
    }
    for (const block of BLOCK_CATALOG.selectors.values()) {
      expect(markup).toContain(block.labelKo)
    }
  })

  it('★ 팔레트의 수마다 무엇을 세는지 붙어 있다', () => {
    // 예전에는 머리에 `21·16·10` 세 개가 붙어 있었고, 무엇을 세는지가 화면 어디에도
    // 없었다 — 봇 관리창의 「0 / 13」이 받은 것과 같은 질문이다.
    const markup = renderEditor(PRESSURE)
    expect(markup).not.toContain(
      `${String(BLOCK_CATALOG.perceptions.size)}·${String(BLOCK_CATALOG.actions.size)}`,
    )
    const total =
      BLOCK_CATALOG.perceptions.size + BLOCK_CATALOG.actions.size + BLOCK_CATALOG.selectors.size
    expect(markup).toContain(`블록 ${String(total)}`)
    // 수는 그것이 세는 것 옆에 선다.
    expect(markup).toContain('palette__count')
    for (const size of [
      BLOCK_CATALOG.perceptions.size,
      BLOCK_CATALOG.actions.size,
      BLOCK_CATALOG.selectors.size,
    ]) {
      expect(markup).toContain(`palette__count">${String(size)}<`)
    }
  })

  it('규칙 줄마다 우선순위와 CPU 비용을 적는다', () => {
    const markup = renderEditor(PRESSURE)
    for (const rule of PRESSURE.rules) {
      expect(markup).toContain(`[${String(rule.priority)}]`)
    }
    expect(markup).toContain('cpu 2')
  })

  it('인자를 받는 인지 변수는 인자 선택칸이 함께 뜬다', () => {
    const markup = renderEditor(PRESSURE)
    expect(markup).toContain('term__field--param')
  })

  it('CPU 예산 안이면 세로바가 rust 가 아니다', () => {
    const markup = renderEditor(PRESSURE)
    expect(markup).not.toContain('rule-row__bar--over')
  })

  it('예산을 넘기면 넘긴 줄부터 세로바가 rust 로 바뀌고 편집은 계속된다', () => {
    const heavy: RuleSet = {
      ...PRESSURE,
      rules: PRESSURE.rules.map((rule) => ({ ...rule, cpuCost: CPU_BUDGET })),
    }
    const markup = renderEditor(heavy)
    expect(markup).toContain('rule-row__bar--over')
    // 초과해도 입력칸은 그대로 살아 있다 — 초과는 오류가 아니라 수치다 (GDD §3.6).
    expect(markup).not.toContain('disabled=""><select')
    expect(markup).toContain('term__field--lhs')
  })

  it('검증 위반을 그 규칙 줄 아래에 적는다', () => {
    const broken: RuleSet = {
      ...PRESSURE,
      rules: [
        {
          priority: 1,
          conditions: { op: 'SINGLE', terms: [{ lhs: 'self_hp_percent', comparison: '<', rhs: 20, lhsParam: null }] },
          action: 'ATTACK',
          actionParam: null,
          target: null,
          setFlag: null,
          cpuCost: 1,
        },
      ],
    }
    const markup = renderEditor(broken)
    expect(markup).toContain('rule-row__problems')
    expect(markup).toContain('TARGET 셀렉터가 필요하다')
  })

  it('빈 규칙표에서도 화면이 선다', () => {
    const markup = renderEditor({ rulesetId: 'draft', version: 1, rules: [] })
    expect(markup).toContain('규칙 추가')
  })
})

/**
 * 코드 라이브러리를 마크업 문자열로 굽는다.
 *
 * @param presets 실을 슬롯들.
 * @returns 정적 마크업.
 */
function renderLibrary(presets: readonly RulePreset[]): string {
  return renderToStaticMarkup(
    <RuleLibrary
      presets={presets}
      onSave={() => undefined}
      onLoad={() => undefined}
      onRemove={() => undefined}
      onImport={() => ''}
      onExport={() => 'v2:code'}
      onExportSlot={() => 'v2:code'}
    />,
  )
}

describe('코드 라이브러리', () => {
  it('빈 라이브러리는 무엇을 하면 되는지 적는다', () => {
    const markup = renderLibrary([])
    expect(markup).toContain('저장한 규칙표가 없다')
    expect(markup).toContain(`0 / ${String(MAX_PRESET_SLOTS)}`)
  })

  it('슬롯마다 이름과 세 조작이 나간다', () => {
    const markup = renderLibrary([{ name: '근접 압박', ruleset: PRESSURE }])
    expect(markup).toContain('근접 압박')
    expect(markup).toContain('불러오기')
    expect(markup).toContain('코드')
    expect(markup).toContain('삭제')
    expect(markup).toContain(`1 / ${String(MAX_PRESET_SLOTS)}`)
  })

  it('입력칸에 라벨이 붙는다 — 키보드와 보조 기술로 닿아야 한다', () => {
    const markup = renderLibrary([])
    expect(markup).toContain('for="library-name"')
    expect(markup).toContain('id="library-name"')
    expect(markup).toContain('for="library-code"')
    expect(markup).toContain('id="library-code"')
  })

  it('에디터의 팔레트 열에 끼워 넣을 수 있다', () => {
    const markup = renderToStaticMarkup(
      <RuleEditor
        ruleset={PRESSURE}
        catalog={BLOCK_CATALOG}
        cpuBudget={CPU_BUDGET}
        ruleSlots={RULE_SLOTS}
        onChange={() => undefined}
        library={<div className="library-slot-probe" />}
      />,
    )
    expect(markup).toContain('library-slot-probe')
    expect(markup).toContain('Ctrl+Z 되돌리기')
  })
})

describe('토큰 규율', () => {
  it('editor.css 에 생 hex 색이 없다', () => {
    expect(readStrippedCss('editor.css').match(/#[0-9a-fA-F]{3,8}\b/g)).toBeNull()
  })

  it('editor.css 에 생 px 값이 없다', () => {
    expect(readStrippedCss('editor.css').match(/\d+px/g)).toBeNull()
  })

  it('editor.css 에 그림자가 없다', () => {
    expect(readStrippedCss('editor.css').match(/box-shadow/g)).toBeNull()
  })
})


describe('좁은 화면의 상단 조작부', () => {
  it('★ 넘치면 접힌다 — 한 줄이면 오른쪽이 잘리고 마지막에 놓인 것부터 사라진다', () => {
    const css = readStrippedCss('../styles/app.css')
    const block = /\.launch \{([\s\S]*?)\}/.exec(css)
    expect(block?.[1] ?? '').toContain('flex-wrap: wrap')
  })

  it('★ 경계를 컴포넌트 CSS 에 안 적는다 — 이 저장소는 breakpoint 를 토큰 한 곳에 둔다', () => {
    expect(readStrippedCss('../styles/app.css')).not.toContain('@media')
  })
})

describe('화면 탭 — 규칙표와 곁다리가 동위다', () => {
  // **정비가 가방 탭에서 규칙표로 왔고, 곁다리가 서랍에서 나왔다.** 예전에는 탭 줄이
  // 둘이라 「어느 탭 안의 어느 탭」을 외워야 했다 — 규칙표든 가방이든 답하는 질문은
  // 하나다: 「지금 무슨 화면을 보는가」.
  const UPKEEP_TAB = {
    id: 'upkeep',
    label: '정비 규칙',
    palette: <div>정비 팔레트다</div>,
    main: <div>정비 본문이다</div>,
    check: <div>정비 검증이다</div>,
    gauge: <span>정비 계량이다</span>,
    foot: <span>정비 안내다</span>,
  }

  const withTab = renderToStaticMarkup(
    <RuleEditor
      ruleset={PRESSURE}
      catalog={BLOCK_CATALOG}
      cpuBudget={CPU_BUDGET}
      ruleSlots={RULE_SLOTS}
      onChange={() => undefined}
      tabs={[UPKEEP_TAB]}
    />,
  )

  it('★ 탭 줄이 머리 바 밖에 있다 — 안에 두면 출격 버튼부터 밀려 나간다', () => {
    // 머리 바는 고정 높이라 넘치는 것을 감춘다(`editor__top`). 탭 여덟을 거기 넣으면
    // 가장 중요한 것(출격·CPU)이 먼저 사라진다.
    expect(withTab).toContain('editor__tabs')
    expect(withTab).toContain('전투 규칙')
    expect(withTab).toContain('정비 규칙')
    const head = withTab.slice(withTab.indexOf('editor__top'), withTab.indexOf('</header>'))
    expect(head).not.toContain('editor__tabs')
  })

  it('★ 탭 줄이 출격 조작부보다 아래다 — 접히면 출격이 밀린다', () => {
    const withControls = renderToStaticMarkup(
      <RuleEditor
        ruleset={PRESSURE}
        catalog={BLOCK_CATALOG}
        cpuBudget={CPU_BUDGET}
        ruleSlots={RULE_SLOTS}
        onChange={() => undefined}
        tabs={[UPKEEP_TAB]}
        controls={<button type="button">출격</button>}
      />,
    )
    expect(withControls.indexOf('출격')).toBeLessThan(withControls.indexOf('editor__tabs'))
  })

  it('★ 본문 하나뿐인 탭은 열을 하나만 쓴다 — 빈 열 둘을 세우면 화면 3분의 2가 빈다', () => {
    const panelTab = { id: 'bag', label: '가방', main: <div>가방 본문이다</div> }
    const html = renderToStaticMarkup(
      <RuleEditor
        ruleset={PRESSURE}
        catalog={BLOCK_CATALOG}
        cpuBudget={CPU_BUDGET}
        ruleSlots={RULE_SLOTS}
        onChange={() => undefined}
        tabs={[panelTab]}
      />,
    )
    // 전투 탭이 열려 있으므로 세 열이다. 한 열짜리는 그 탭을 골랐을 때다 —
    // 여기서는 계약만 본다: 팔레트도 검증도 없는 탭이 `checkWideTab` 에 거짓이다.
    expect(checkWideTab(panelTab)).toBe(false)
    expect(checkWideTab(UPKEEP_TAB)).toBe(true)
    expect(html).toContain('editor__tabs')
  })

  it('★ 전투 탭이 처음 열린다 — 이 게임의 규칙표는 여전히 전투가 중심이다', () => {
    expect(withTab).toContain('우선순위 리스트')
  })

  it('★ 안 열린 탭의 세 열이 통째로 빠진다 — 본문만 갈면 안 보이는 규칙표가 바뀐다', () => {
    // 정비 탭이 닫혀 있으므로 팔레트도 본문도 검증도 없다. 특히 **팔레트**가 중요하다 —
    // 남아 있으면 정비를 고치는 동안 전투 블록 팔레트가 서 있고, 그것을 누르면 안 보이는
    // 규칙표가 바뀐다.
    expect(withTab).not.toContain('정비 팔레트다')
    expect(withTab).not.toContain('정비 본문이다')
    expect(withTab).not.toContain('정비 검증이다')
  })

  it('★ 계량도 탭을 따라간다 — 전투 탭에서는 CPU 게이지가 선다', () => {
    expect(withTab).toContain('cpu')
    expect(withTab).not.toContain('정비 계량이다')
  })

  it('★ 코드 라이브러리는 전투 탭의 것이다 — 프리셋은 전투 규칙표를 담는다', () => {
    const html = renderToStaticMarkup(
      <RuleEditor
        ruleset={PRESSURE}
        catalog={BLOCK_CATALOG}
        cpuBudget={CPU_BUDGET}
        ruleSlots={RULE_SLOTS}
        onChange={() => undefined}
        tabs={[UPKEEP_TAB]}
        library={<div>코드 라이브러리다</div>}
      />,
    )
    expect(html).toContain('코드 라이브러리다')
  })

  it('탭을 안 주면 탭 줄이 아예 없다 — 갈아 낄 것이 하나뿐이면 고를 일도 없다', () => {
    expect(renderEditor(PRESSURE)).not.toContain('editor__tabs')
  })
})

describe('★ 출격 조작부가 가로 폭을 안 넘긴다', () => {
  // 좁은 화면에서 페이지 전체가 오른쪽으로 밀렸다. 탭 줄을 접게 고친 뒤에도 남았고,
  // 남은 원인이 **방 고르개**였다 — `select` 는 가장 긴 option 만큼 폭을 잡는다.
  const css = readStrippedCss('../styles/app.css')

  it('방 고르개가 줄어들 수 있다 — flex-wrap 은 항목 자체를 못 줄인다', () => {
    const block = /\.launch__field \{([\s\S]*?)\}/.exec(css)?.[1] ?? ''
    expect(block).toContain('min-inline-size: var(--sp-0)')
    expect(block).toContain('max-inline-size: 100%')
  })

  it('방 고르개가 줄의 남는 폭을 쓴다', () => {
    const block = /\.launch__field--room \{([\s\S]*?)\}/.exec(css)?.[1] ?? ''
    expect(block).toContain('flex: 1 1 var(--sp-0)')
  })

  it('조작부 자신도 줄어들 수 있다', () => {
    const block = /\.launch \{([\s\S]*?)\}/.exec(css)?.[1] ?? ''
    expect(block).toContain('min-inline-size: var(--sp-0)')
  })
})
