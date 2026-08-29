/**
 * 디자인 시스템 부품 테스트.
 *
 * DOM 을 띄우지 않고 `renderToStaticMarkup` 으로 마크업 문자열을 얻어 본다. jsdom 을
 * 새 의존성으로 들이지 않으려는 것이고, 여기서 확인할 것은 상호작용이 아니라 **계약**
 * 이기 때문이다 — 어떤 상태가 어떤 클래스·글리프로 나가는가.
 *
 * 토큰 규율 검사가 이 파일에 함께 있는 이유: 생 hex 나 생 px 는 리뷰에서 놓치기 쉽고
 * 한 번 새면 화면마다 다른 값이 자란다. 사람 눈이 아니라 테스트가 막는 편이 싸다.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { LogEntry } from '../core/eventLog'
import { createLogEntry } from '../core/eventLog'

import {
  Button,
  GlyphState,
  HpGauge,
  LOW_HP_PERCENT,
  LogPanel,
  Panel,
  PlanActor,
  PlanGrid,
  ResourceCount,
  RuleRow,
  RuleTable,
  SEGMENT_LIMIT,
  STATE_GLYPHS,
  SegmentedGauge,
  SpeedControl,
  StatusBar,
  ThreatNotice,
  TopBar,
  ValueExpr,
  buildSegments,
  calculatePercent,
  checkCpuOver,
  formatCpu,
  formatDelta,
  resolveGlyphKind,
  splitExprSegments,
} from './index'

/** 주석을 걷어낸 CSS 를 읽는다. 주석 안의 `4px 모듈` 같은 설명글을 위반으로 세지 않기 위해서다. */
function readStrippedCss(name: string): string {
  const path = fileURLToPath(new URL(name, import.meta.url))
  return readFileSync(path, 'utf-8').replace(/\/\*[\s\S]*?\*\//g, '')
}

describe('토큰 규율', () => {
  it.each(['ds.css', 'gallery.css'])('%s 에 생 hex 색이 없다', (name) => {
    expect(readStrippedCss(name).match(/#[0-9a-fA-F]{3,8}\b/g)).toBeNull()
  })

  it.each(['ds.css', 'gallery.css'])('%s 에 생 px 값이 없다', (name) => {
    expect(readStrippedCss(name).match(/\d+px/g)).toBeNull()
  })

  it('그림자를 쓰지 않는다 — 층위는 명도차와 괘선으로만 만든다', () => {
    const declared = [...readStrippedCss('ds.css').matchAll(/box-shadow:\s*([^;]+);/g)].map(
      (match) => match[1]?.trim(),
    )
    expect(declared.length).toBeGreaterThan(0)
    expect(new Set(declared)).toEqual(new Set(['var(--shadow-none)']))
  })
})

describe('GlyphState', () => {
  it('다섯 상태의 글리프가 서로 다르다 — 색을 못 봐도 구분된다', () => {
    expect(new Set(STATE_GLYPHS.values()).size).toBe(STATE_GLYPHS.size)
  })

  it('상태 이름을 보조 기술용 텍스트로 함께 싣는다', () => {
    const html = renderToStaticMarkup(<GlyphState state="armed" label="발동" />)
    expect(html).toContain('ds-glyph--armed')
    expect(html).toContain('◆')
    expect(html).toContain('이번 틱 발동')
  })

  it('거짓과 대기는 명도를 낮추는 수식자를 단다', () => {
    expect(renderToStaticMarkup(<GlyphState state="false" />)).toContain('ds-glyph--false')
    expect(renderToStaticMarkup(<GlyphState state="pending" />)).toContain('ds-glyph--pending')
  })
})

describe('SegmentedGauge', () => {
  it('예산 안에서는 초과 칸이 없다', () => {
    expect(buildSegments(3, 8)).toEqual(['on', 'on', 'on', 'off', 'off', 'off', 'off', 'off'])
  })

  it('예산을 넘으면 넘은 만큼 초과 칸이 늘어난다 — 오류가 아니라 수치다', () => {
    const segments = buildSegments(10, 8)
    expect(segments).toHaveLength(10)
    expect(segments.filter((fill) => fill === 'over')).toHaveLength(2)
  })

  it('눈금 수에 상한이 있다', () => {
    expect(buildSegments(SEGMENT_LIMIT * 2, SEGMENT_LIMIT * 2)).toHaveLength(SEGMENT_LIMIT)
  })

  it('readout=true 면 값과 예산을 스스로 적는다', () => {
    const html = renderToStaticMarkup(<SegmentedGauge value={10} max={8} tone="cpu" readout />)
    expect(html).toContain('10 / 8')
    expect(html).toContain('ds-gauge__readout--over')
  })

  it('readout 에 문자열을 주면 그대로 쓴다', () => {
    const html = renderToStaticMarkup(<SegmentedGauge value={2} max={8} readout="누적 5 / 8" />)
    expect(html).toContain('누적 5 / 8')
  })
})

describe('ValueExpr', () => {
  it('조각을 이어 붙이면 원문과 같다', () => {
    const text = '적거리(2) <= 사거리(3)'
    expect(
      splitExprSegments(text)
        .map((segment) => segment.text)
        .join(''),
    ).toBe(text)
  })

  it('괄호 안 실측값만 값 조각으로 표시된다', () => {
    expect(
      splitExprSegments('적거리(2) <= 사거리(3)')
        .filter((segment) => segment.isValue)
        .map((segment) => segment.text),
    ).toEqual(['(2)', '(3)'])
  })

  it('괄호가 없어도 원문을 잃지 않는다', () => {
    expect(splitExprSegments('항상')).toEqual([{ text: '항상', isValue: false }])
  })

  it('dim 은 수식자 클래스로 나간다', () => {
    expect(renderToStaticMarkup(<ValueExpr text="항상" dim />)).toContain('ds-expr--dim')
  })
})

describe('HpGauge', () => {
  it('비율은 내림한 정수다 — 부동소수를 남기지 않는다', () => {
    expect(calculatePercent(1, 3)).toBe(33)
    expect(calculatePercent(2, 3)).toBe(66)
  })

  it('최대치가 0 이면 0% 다', () => {
    expect(calculatePercent(5, 0)).toBe(0)
  })

  it('값이 최대치를 넘어도 100% 를 넘지 않는다', () => {
    expect(calculatePercent(99, 10)).toBe(100)
  })

  it('낮은 체력은 색 말고 글리프와 숫자로도 알린다', () => {
    const low = renderToStaticMarkup(<HpGauge value={LOW_HP_PERCENT} max={100} />)
    expect(low).toContain('ds-hp--low')
    expect(low).toContain('▽')
    expect(low).toContain(`${String(LOW_HP_PERCENT)} / 100`)
    expect(renderToStaticMarkup(<HpGauge value={99} max={100} />)).not.toContain('ds-hp--low')
  })
})

describe('ResourceCount', () => {
  it('남은 수를 낱개 글리프와 숫자 둘 다로 적는다', () => {
    const html = renderToStaticMarkup(
      <ResourceCount label="물약" count={2} max={3} glyph="◍" />,
    )
    expect(html.match(/◍/g)).toHaveLength(2)
    expect(html).toContain('○')
    expect(html).toContain('2 / 3')
  })
})

describe('RuleRow — 여섯 상태', () => {
  it('01 기본은 배경도 세로바도 없다', () => {
    const html = renderToStaticMarkup(<RuleRow index={1} state="pending" condition="항상" action="접근" />)
    expect(html).toContain('ds-rule-row--pending')
    expect(html).not.toContain('ds-rule-row--armed')
    expect(html).not.toContain('ds-rule-row--over')
  })

  it('02 참·미발동은 글리프만 참이고 armed 수식자가 붙지 않는다', () => {
    const html = renderToStaticMarkup(<RuleRow index={2} state="true" condition="항상" action="사격" />)
    expect(html).toContain('ds-glyph--true')
    expect(html).not.toContain('ds-rule-row--armed')
  })

  it('03 거짓은 조건문까지 명도를 낮춘다', () => {
    const html = renderToStaticMarkup(<RuleRow index={3} state="false" condition="항상" action="후퇴" />)
    expect(html).toContain('ds-rule-row--false')
    expect(html).toContain('ds-expr--dim')
  })

  it('04 발동은 armed 글리프와 armed 행을 함께 낸다', () => {
    const html = renderToStaticMarkup(<RuleRow index={4} state="true" armed condition="항상" action="사격" />)
    expect(html).toContain('ds-rule-row--armed')
    expect(html).toContain('ds-glyph--armed')
  })

  it('05 초과는 초과 수식자를 달되 거짓으로 흐리지 않는다', () => {
    const html = renderToStaticMarkup(
      <RuleRow index={5} state="true" condition="항상" action="사격" cpu={{ used: 10, budget: 8 }} />,
    )
    expect(html).toContain('ds-rule-row--over')
    expect(html).not.toContain('ds-rule-row--false')
    expect(html).toContain('cpu 10 / 8')
    expect(html).toContain('예산 초과')
  })

  it('06 포커스는 네이티브 버튼이라 키보드로 닿는다', () => {
    expect(renderToStaticMarkup(<RuleRow index={6} state="pending" condition="항상" action="접근" />)).toContain(
      '<button type="button"',
    )
  })

  it('CPU 표시는 숫자만 줘도 되고 그때는 초과 판정을 하지 않는다', () => {
    expect(formatCpu(2)).toBe('cpu 2')
    expect(checkCpuOver(2)).toBe(false)
    expect(formatCpu(undefined)).toBeUndefined()
    expect(checkCpuOver({ used: 8, budget: 8 })).toBe(false)
    expect(checkCpuOver({ used: 9, budget: 8 })).toBe(true)
  })

  it('발동 여부가 글리프 상태를 가른다', () => {
    expect(resolveGlyphKind('true', true)).toBe('armed')
    expect(resolveGlyphKind('true', false)).toBe('true')
    expect(resolveGlyphKind('false', true)).toBe('false')
  })
})

describe('LogPanel', () => {
  it('코어의 LogEntry 를 변환 없이 받는다', () => {
    const entries: readonly LogEntry[] = [
      createLogEntry({
        tick: 7,
        entityId: 'player',
        phase: 'DECIDE',
        expr: '적거리(2) <= 사거리(3)',
        outcome: '사격',
        rule: 1,
        delta: -4,
        fired: true,
      }),
    ]
    const html = renderToStaticMarkup(<LogPanel entries={entries} />)
    expect(html).toContain('T007')
    expect(html).toContain('[1]')
    expect(html).toContain('-4')
    expect(html).not.toContain('ds-log-row--idle')
  })

  it('미발동 줄은 글리프와 명도 둘 다로 표시된다', () => {
    const html = renderToStaticMarkup(
      <LogPanel entries={[{ tick: 1, expr: '항상', outcome: '건너뜀' }]} />,
    )
    expect(html).toContain('ds-log-row--idle')
    expect(html).toContain('미발동')
  })

  it('비어 있으면 빈 상태를 적는다', () => {
    expect(renderToStaticMarkup(<LogPanel entries={[]} />)).toContain('기록 없음')
  })

  it('증감은 부호를 반드시 붙인다', () => {
    expect(formatDelta(3)).toBe('+3')
    expect(formatDelta(-3)).toBe('-3')
    expect(formatDelta(0)).toBe('+0')
  })
})

describe('Button', () => {
  it('황동은 primary 만 쓴다', () => {
    expect(renderToStaticMarkup(<Button variant="primary">실행</Button>)).toContain('ds-button--primary')
    expect(renderToStaticMarkup(<Button variant="secondary">실행</Button>)).not.toContain(
      'ds-button--primary',
    )
  })

  it('눌린 상태는 클래스와 aria-pressed 두 채널로 나간다', () => {
    const html = renderToStaticMarkup(<Button active>×2</Button>)
    expect(html).toContain('ds-button--active')
    expect(html).toContain('aria-pressed="true"')
  })

  it('토글이 아닌 버튼에는 aria-pressed 를 붙이지 않는다', () => {
    expect(renderToStaticMarkup(<Button>실행</Button>)).not.toContain('aria-pressed')
  })

  it('비활성은 네이티브 disabled 다', () => {
    expect(renderToStaticMarkup(<Button disabled>실행</Button>)).toContain('disabled')
  })
})

describe('레이아웃 부품', () => {
  it('Panel 은 tone 별 수식자를 낸다', () => {
    expect(renderToStaticMarkup(<Panel tone="plan">본문</Panel>)).toContain('ds-panel--plan')
  })

  it('Panel 은 문자열 meta 와 노드 meta 를 모두 받는다', () => {
    expect(renderToStaticMarkup(<Panel title="로그" meta="T027" />)).toContain('T027')
    expect(
      renderToStaticMarkup(
        <Panel title="로그" meta={<Button size="sm">복사</Button>} />,
      ),
    ).toContain('ds-button')
  })

  it('PlanActor 는 토큰 배수로 좌표를 잡는다 — 생 px 를 쓰지 않는다', () => {
    const html = renderToStaticMarkup(<PlanActor x={3} y={4} kind="self" label="me" />)
    expect(html).toContain('calc(var(--plan-cell) * 3)')
    expect(html).toContain('calc(var(--plan-cell) * 4)')
    expect(html).toContain('ds-plan-actor--self')
    expect(html).toContain('◉')
  })

  it('PlanGrid 가 말들을 담는다', () => {
    const html = renderToStaticMarkup(
      <PlanGrid>
        <PlanActor x={0} y={0} kind="charge" />
      </PlanGrid>,
    )
    expect(html).toContain('ds-plan')
    expect(html).toContain('ds-plan-actor--charge')
  })

  it('RuleTable 은 목록이다', () => {
    const html = renderToStaticMarkup(
      <RuleTable>
        <RuleRow index={1} state="true" condition="항상" action="사격" />
      </RuleTable>,
    )
    expect(html).toContain('<ul class="ds-rule-table"')
  })

  it('TopBar 는 위치·틱·속도를 낸다', () => {
    const html = renderToStaticMarkup(
      <TopBar location="1층 · 파수실" tick={27} speed={2} onSpeedChange={() => undefined} />,
    )
    expect(html).toContain('1층 · 파수실')
    expect(html).toContain('27')
    expect(html).toContain('×2')
  })

  it('StatusBar 는 위협이 없으면 위협 칸을 그리지 않는다', () => {
    const bare = renderToStaticMarkup(<StatusBar hp={18} hpMax={30} potions={2} potionsMax={3} />)
    expect(bare).not.toContain('ds-threat')
    const armed = renderToStaticMarkup(
      <StatusBar hp={18} hpMax={30} potions={2} potionsMax={3} threat="폭발 예고" />,
    )
    expect(armed).toContain('ds-threat--danger')
  })

  it('ThreatNotice 는 남은 틱을 낸다', () => {
    const html = renderToStaticMarkup(<ThreatNotice text="폭발" ticks={3} />)
    expect(html).toContain('3틱')
    expect(html).toContain('ds-threat--danger')
  })

  it('SpeedControl 은 고른 단계만 눌린 상태로 낸다', () => {
    const html = renderToStaticMarkup(<SpeedControl value={2} onChange={() => undefined} />)
    expect(html.match(/aria-pressed="true"/g)).toHaveLength(1)
  })
})
