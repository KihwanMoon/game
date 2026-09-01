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
  const css = readStrippedCss('../styles/app.css')

  it('★ 폰에서 두 줄로 접힌다 — 한 줄이면 오른쪽이 잘리고 층 번호가 먼저 사라진다', () => {
    // **`.launch` 안에서 본다.** 그냥 `flex-wrap: wrap` 을 찾으면 관리 화면의 다른
    // 규칙이 걸려 통과한다 — 실제로 그렇게 통과했다.
    const block = /@media \(max-width: 840px\) \{[\s\S]*?\.launch \{([\s\S]*?)\}/.exec(css)
    expect(block?.[1] ?? '').toContain('flex-wrap: wrap')
  })

  it('★ 읽는 것과 누르는 것을 가른다 — 정보가 위, 조작이 아래다', () => {
    // `order` 로 가른다. DOM 순서를 바꾸면 탭 순서가 흔들린다.
    expect(css).toMatch(/\.launch > \.ds-expr[\s\S]*?order: 0/)
    expect(css).toMatch(/\.launch > \.ds-button[\s\S]*?order: 1/)
  })

  it('★ 경계가 세로 배치와 같은 840px 다 — 다르면 한 화면이 두 규칙을 받는다', () => {
    expect(css).toContain('@media (max-width: 840px)')
  })
})
