/**
 * 규칙 에디터의 렌더 계약과 토큰 규율.
 *
 * jsdom 없이 `renderToStaticMarkup` 으로 마크업 문자열만 본다(`ds/ds.test.tsx` 와 같은
 * 방식). 여기서 확인하는 것은 상호작용이 아니라 **화면에 무엇이 나가는가** 다 —
 * 골격 세 열, 팔레트가 카탈로그 전량을 싣는가, 검증 메시지가 그 규칙 줄에 붙는가,
 * 예산 초과가 편집을 막지 않고 하단 게이지의 rust 로만 나가는가.
 *
 * 토큰 규율 검사가 함께 있는 이유는 생 hex·생 px 가 리뷰에서 잘 안 보이기 때문이다.
 * 한 번 새면 화면마다 다른 값이 자란다.
 *
 * **예산 초과 검사가 오래 죽어 있었다** (2026-09-16). `not.toContain('rule-row__bar--over')`
 * 였는데 그 클래스는 이 저장소에 없다 — ds 쪽 이름은 `ds-rule-row--over` 고, 게다가
 * 에디터는 세 열을 지울 때부터 ds `RuleRow` 를 안 쓴다. 초과의 rust 채널은 하단
 * `SegmentedGauge` 로 옮겨 갔다. 없는 글자를 찾는 `not.toContain` 은 화면이 어떻게
 * 바뀌든 통과하므로, 검사는 통과한 것이 아니라 아무것도 안 보고 있었던 것이다.
 *
 * 그래서 **부정 검사는 혼자 두지 않는다.** 같은 글자가 실제로 나오는 렌더를 짝으로
 * 붙여, 이름이 죽으면 그 짝이 먼저 빨개지게 한다.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { BLOCK_CATALOG, G0_RULESETS } from '../core/resources'
import type { RuleSet } from '../core/schemas'
import { MAX_PRESET_SLOTS, type RulePreset } from '../storage'
import { RuleEditor } from './RuleEditor'
import { RuleLibrary } from './RuleLibrary'

const CPU_BUDGET = 8
const RULE_SLOTS = 5

/**
 * 예산 초과의 rust 채널 셋. 게이지 색 계열 · 읽는 숫자 · 넘긴 눈금이다.
 *
 * 문자열 상수인 이름이 진짜인지는 아래 **초과 렌더가 보증한다** — 이름이 썩으면
 * `toContain` 쪽이 먼저 빨개진다.
 */
const OVER_TONE = 'ds-gauge--danger'
const OVER_READOUT = 'ds-gauge__readout--over'
const OVER_SEGMENT = 'ds-gauge__seg--over'

/**
 * 에디터를 마크업 문자열로 굽는다.
 *
 * @param ruleset 실을 규칙표.
 * @param cpuBudget CPU 예산. 생략하면 기본 예산.
 * @returns 정적 마크업.
 */
function renderEditor(ruleset: RuleSet, cpuBudget: number = CPU_BUDGET): string {
  return renderToStaticMarkup(
    <RuleEditor
      ruleset={ruleset}
      catalog={BLOCK_CATALOG}
      cpuBudget={cpuBudget}
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

/** 예제 규칙표의 누적 CPU. 박지 않고 센다 — 예제가 바뀌어도 초과·비초과가 갈린다. */
const PRESSURE_CPU = PRESSURE.rules.reduce((sum, rule) => sum + rule.cpuCost, 0)

/** 누적을 예산 밖으로 몰아 줄 예산. 딱 하나만큼 넘긴다. */
const TIGHT_BUDGET = PRESSURE_CPU - 1

describe('규칙 에디터 렌더', () => {
  it('규칙 줄마다 우선순위와 CPU 비용을 적는다', () => {
    const markup = renderEditor(PRESSURE)
    for (const rule of PRESSURE.rules) {
      expect(markup).toContain(`[${String(rule.priority)}]`)
    }
    expect(markup).toContain('cpu 2')
  })

  it('★ 예산을 넘기면 rust 로 적되 편집은 계속된다 (GDD §3.6)', () => {
    // 초과는 오류가 아니라 수치다. 넘긴 상태에서도 규칙 줄과 「규칙 추가」가 그대로
    // 서 있어야 하고, 얼마나 넘겼는지는 숫자로 읽힌다 — 색은 채널 하나일 뿐이다.
    const markup = renderEditor(PRESSURE, TIGHT_BUDGET)
    expect(markup).toContain(OVER_TONE)
    expect(markup).toContain(OVER_READOUT)
    expect(markup).toContain(OVER_SEGMENT)
    expect(markup).toContain(`${String(PRESSURE_CPU)} / ${String(TIGHT_BUDGET)}`)
    expect(markup).toContain('규칙 추가')
    expect(markup).not.toContain('disabled')
  })

  it('CPU 예산 안이면 rust 가 한 채널도 안 뜬다', () => {
    const markup = renderEditor(PRESSURE)
    expect(markup).toContain(`${String(PRESSURE_CPU)} / ${String(CPU_BUDGET)}`)
    expect(markup).not.toContain(OVER_TONE)
    expect(markup).not.toContain(OVER_READOUT)
    expect(markup).not.toContain(OVER_SEGMENT)
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
  it('★ 저장·조회·불러오기가 한 패널에 있다 — 라이브러리는 개인용이다', () => {
    // 한 번 목록만 「배움」 탭으로 떼어 봤다가 되돌렸다 (2026-09-15). 저장한 것을
    // 꺼내는 일은 규칙을 고치는 일의 한 부분이지 다른 화면으로 가는 일이 아니다.
    const markup = renderLibrary([{ name: '근접 압박', ruleset: PRESSURE }])
    expect(markup).toContain('저장')
    expect(markup).toContain('근접 압박')
    expect(markup).toContain('불러오기')
    expect(markup).toContain('공유 코드')
  })

  it('빈 라이브러리는 무엇을 하면 되는지 적는다', () => {
    const markup = renderLibrary([])
    expect(markup).toContain('저장한 내력이 없다')
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
