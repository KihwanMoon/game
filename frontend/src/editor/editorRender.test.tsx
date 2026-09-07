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
  it('규칙 줄마다 우선순위와 CPU 비용을 적는다', () => {
    const markup = renderEditor(PRESSURE)
    for (const rule of PRESSURE.rules) {
      expect(markup).toContain(`[${String(rule.priority)}]`)
    }
    expect(markup).toContain('cpu 2')
  })

  it('CPU 예산 안이면 세로바가 rust 가 아니다', () => {
    const markup = renderEditor(PRESSURE)
    expect(markup).not.toContain('rule-row__bar--over')
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
