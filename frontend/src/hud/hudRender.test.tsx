/**
 * HUD 의 렌더 계약과 토큰 규율.
 *
 * jsdom 없이 `renderToStaticMarkup` 으로 마크업 문자열만 본다(`ds/ds.test.tsx` 와 같은
 * 방식). 확인하는 것은 상호작용이 아니라 **화면에 무엇이 나가는가** 다 — 로그가 틱으로
 * 묶여 나가는가, 실측값이 병기된 조건문이 그대로 실리는가, 사후 분석이 세 가지(성적표·
 * 히트맵·되감기)를 다 내는가.
 *
 * 정적 렌더에는 `useEffect` 가 돌지 않으므로 도면 테마가 undefined 다. 그래서 캔버스는
 * 그려지지 않는다 — 여기서 볼 것은 캔버스가 아니라 그 둘레의 골격이다.
 *
 * 토큰 규율 검사가 함께 있는 이유는 생 hex·생 px 가 리뷰에서 잘 안 보이기 때문이다.
 * 한 번 새면 화면마다 다른 값이 자란다.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { createLogEntry } from '../core/eventLog'
import type { LogEntry } from '../core/eventLog'
import { G0_RULESETS } from '../core/resources'
import { PHASE_ACT, PHASE_DECIDE } from '../core/sim/phases'

import { buildDamageHeatmap, buildRuleStats } from './analysis'
import { recordBattle } from './battleRecorder'
import { DamageHeatmap } from './DamageHeatmap'
import { HudScreen } from './HudScreen'
import { LogStream } from './LogStream'
import { PostMortem } from './PostMortem'
import { RuleStatsTable } from './RuleStatsTable'
import { TickScrubber } from './TickScrubber'

/** 사망으로 끝나는 판. 사후 분석이 저절로 뜨는 경로를 태운다. */
const DEFEAT = recordBattle({ roomId: 'hazard_field', rulesetId: 'g0_cover', seed: 99 }, G0_RULESETS)

/** 승리로 끝나는 판. */
const VICTORY = recordBattle(
  { roomId: 'open_field', rulesetId: 'g0_pressure', seed: 1 },
  G0_RULESETS,
)

/**
 * 주석을 걷어 낸 스타일 시트를 읽는다.
 *
 * 주석 안의 `4px 모듈` 같은 설명글을 위반으로 세지 않기 위해서다.
 *
 * @param name 파일 이름.
 * @returns 주석이 빠진 내용.
 */
function readStrippedCss(name: string): string {
  const path = fileURLToPath(new URL(name, import.meta.url))
  return readFileSync(path, 'utf-8').replace(/\/\*[\s\S]*?\*\//g, '')
}

/**
 * 로그 한 줄을 만든다.
 *
 * @param tick 틱.
 * @param entityId 엔티티.
 * @param rule 규칙 번호.
 * @returns 로그 레코드.
 */
function createRow(tick: number, entityId: string, rule: number | null): LogEntry {
  return createLogEntry({
    tick,
    entityId,
    phase: PHASE_DECIDE,
    expr: '적거리(2) <= 사거리(3)',
    outcome: 'SHOOT',
    rule,
    fired: true,
  })
}

describe('토큰 규율', () => {
  it('hud.css 에 생 hex 색이 없다', () => {
    expect(readStrippedCss('hud.css').match(/#[0-9a-fA-F]{3,8}\b/g)).toBeNull()
  })

  it('hud.css 에 생 px 값이 없다', () => {
    expect(readStrippedCss('hud.css').match(/\d+px/g)).toBeNull()
  })

  it('그림자를 쓰지 않는다 — 층위는 명도차와 괘선으로만 만든다', () => {
    expect(readStrippedCss('hud.css')).not.toContain('box-shadow')
  })

  it('황동은 발동 로그 세로바 한 자리에만 쓴다', () => {
    const brass = [...readStrippedCss('hud.css').matchAll(/var\(--(brass|line-accent|state-armed|text-accent)[^)]*\)/g)]
    expect(brass).toHaveLength(1)
  })
})

describe('LogStream', () => {
  it('틱으로 묶고 그 안에서 엔티티 구간을 적는다', () => {
    const html = renderToStaticMarkup(
      <LogStream
        entries={[createRow(7, 'player', 1), createRow(7, 'goblin_rusher_0', 2)]}
        follow
        onFollowChange={() => undefined}
      />,
    )
    expect(html).toContain('T007')
    expect(html).toContain('goblin_rusher_0')
    expect(html).toContain('hud-log__group')
  })

  it('실측값이 병기된 조건문을 그대로 싣는다 (P1)', () => {
    const html = renderToStaticMarkup(
      <LogStream entries={[createRow(3, 'player', 1)]} follow onFollowChange={() => undefined} />,
    )
    expect(html).toContain('적거리')
    expect(html).toContain('2')
    expect(html).toContain('사거리')
  })

  it('황동 세로바는 지금 보고 있는 틱의 발동 줄에만 붙는다', () => {
    const html = renderToStaticMarkup(
      <LogStream
        entries={[createRow(1, 'player', 1), createRow(2, 'player', 1)]}
        follow
        currentTick={2}
        onFollowChange={() => undefined}
      />,
    )
    expect(html.match(/hud-log__row--armed/g)).toHaveLength(1)
    expect(html.match(/hud-log__row--fired/g)).toHaveLength(1)
  })

  it('규칙 없이 나온 줄에는 세로바가 붙지 않는다', () => {
    const html = renderToStaticMarkup(
      <LogStream entries={[createRow(1, 'player', null)]} follow onFollowChange={() => undefined} />,
    )
    expect(html).not.toContain('hud-log__row--fired')
    expect(html).not.toContain('hud-log__row--armed')
  })

  it('잘라 낸 줄 수를 화면에 적는다 — 숨기면 로그가 거짓말을 한다', () => {
    const rows = Array.from({ length: 30 }, (_, index) => createRow(index + 1, 'player', 1))
    const html = renderToStaticMarkup(
      <LogStream entries={rows} follow maxRows={5} onFollowChange={() => undefined} />,
    )
    expect(html).toContain('앞의 25줄 접힘')
  })

  it('고정 상태에서는 기준 줄부터 보여 주고 뒤에 남은 줄 수를 적는다', () => {
    const rows = Array.from({ length: 30 }, (_, index) => createRow(index + 1, 'player', 1))
    const html = renderToStaticMarkup(
      <LogStream
        entries={rows}
        follow={false}
        anchorIndex={0}
        maxRows={5}
        onFollowChange={() => undefined}
      />,
    )
    expect(html).toContain('T001')
    expect(html).toContain('뒤의 25줄 접힘')
  })

  it('빈 로그도 자리를 지킨다', () => {
    const html = renderToStaticMarkup(
      <LogStream entries={[]} follow onFollowChange={() => undefined} />,
    )
    expect(html).toContain('기록 없음')
  })
})

describe('RuleStatsTable', () => {
  const stats = buildRuleStats(
    [
      createRow(1, 'player', 3),
      createLogEntry({
        tick: 1,
        entityId: 'player',
        phase: PHASE_ACT,
        expr: '',
        outcome: '사거리 밖 — 낭비',
        rule: 3,
      }),
    ],
    'player',
  )

  it('규칙·발동·성공·헛돔·진단 다섯 열을 낸다', () => {
    const html = renderToStaticMarkup(<RuleStatsTable stats={stats} />)
    for (const column of ['규칙', '발동', '성공', '헛돔', '진단']) {
      expect(html).toContain(column)
    }
    expect(html).toContain('[3]')
  })

  it('헛도는 규칙에 진단 문구를 붙인다', () => {
    expect(renderToStaticMarkup(<RuleStatsTable stats={stats} />)).toContain('헛돎')
  })

  it('기록이 없으면 빈 표 대신 그렇게 적는다', () => {
    expect(renderToStaticMarkup(<RuleStatsTable stats={[]} />)).toContain('기록 없음')
  })
})

describe('DamageHeatmap', () => {
  it('칸마다 수치를 적는다 — 색은 정보의 유일한 채널이 될 수 없다', () => {
    const grid = buildDamageHeatmap(
      [{ tick: 1, targetId: 'player', position: { x: 1, y: 1 }, amount: 12 }],
      3,
      3,
    )
    const html = renderToStaticMarkup(<DamageHeatmap grid={grid} caption="플레이어" />)
    expect(html).toContain('12')
    expect(html).toContain('최다 (1, 1) 12')
    expect(html).toContain('hud-heat__cell--l4')
    expect(html).toContain('hud-heat__cell--l0')
  })

  it('피해가 없으면 그렇게 적는다', () => {
    const html = renderToStaticMarkup(
      <DamageHeatmap grid={buildDamageHeatmap([], 2, 2)} caption="플레이어" />,
    )
    expect(html).toContain('피해 없음')
  })
})

describe('TickScrubber', () => {
  it('손잡이 위치만이 아니라 몇 틱인지를 적는다', () => {
    const html = renderToStaticMarkup(
      <TickScrubber min={0} max={21} value={7} onChange={() => undefined} label="되감기" />,
    )
    expect(html).toContain('T007 / T021')
    expect(html).toContain('type="range"')
  })
})

describe('PostMortem', () => {
  const html = renderToStaticMarkup(
    <PostMortem recording={DEFEAT} theme={undefined} onClose={() => undefined} />,
  )

  it('세 가지를 함께 낸다 — 성적표·히트맵·되감기', () => {
    expect(html).toContain('규칙별 발동')
    expect(html).toContain('피해 히트맵')
    expect(html).toContain('직전 15틱 리플레이')
    expect(html).toContain('되감기')
  })

  it('승패와 틱을 머리에 적는다', () => {
    expect(html).toContain('사후 분석 — 쓰러짐')
    expect(html).toContain('hazard_field')
  })

  it('도면 테마를 아직 못 읽었으면 캔버스 대신 그렇게 적는다', () => {
    expect(html).toContain('그 틱의 화면이 없다')
  })
})

describe('HudScreen', () => {
  const html = renderToStaticMarkup(
    <HudScreen recording={VICTORY} location="1층 · 개활지" />,
  )

  it('골격 다섯 자리를 낸다 — 상단·규칙표·도면·로그·하단', () => {
    expect(html).toContain('ds-topbar')
    expect(html).toContain('hud__cols')
    expect(html).toContain('ds-rule-table')
    expect(html).toContain('hud__plan')
    expect(html).toContain('hud-log')
    expect(html).toContain('ds-statusbar')
  })

  it('열 사이는 괘선 하나씩 둘이다', () => {
    expect(html.match(/hud__gap/g)).toHaveLength(2)
  })

  it('황동 예산 때문에 primary 버튼을 쓰지 않는다', () => {
    expect(html).not.toContain('ds-button--primary')
  })

  it('사망이 아니면 사후 분석이 저절로 뜨지 않는다', () => {
    expect(html).not.toContain('사후 분석 — 승리')
  })

  it('사망으로 끝난 판은 마지막 프레임에서 사후 분석이 저절로 뜬다', () => {
    // 정적 렌더는 첫 프레임에 멈춰 있으므로, 자동 표시는 마지막 프레임에서만 확인된다.
    const single = { ...DEFEAT, frames: DEFEAT.frames.slice(-1) }
    const dead = renderToStaticMarkup(<HudScreen recording={single} location="1층" />)
    expect(dead).toContain('사후 분석 — 쓰러짐')
  })
})
