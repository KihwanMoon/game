/**
 * 대상 연결선 검사 (규칙 행 상태 시트, P1).
 *
 * **말만 봐서는 누가 누구를 때렸는지 알 수 없었다.** 격자에 다섯이 서 있고 HP 가 줄면
 * 그것이 어느 말의 짓인지 화면 어디에도 없었다 — 로그를 눈으로 따라가야 했다.
 *
 * 색이 방향을 말한다. 황동은 이 화면에서 언제나 「이것이 너다」이고 녹슨 붉은색은 언제나
 * 「이것이 아프다」라, 새 뜻을 만들지 않고 있던 뜻을 그대로 쓴다.
 *
 * 여기서 지키는 것은 다섯이다.
 *
 * 1. **로그의 `targetId` 에서 나온다** — 코어를 건드릴 이유가 없는 자리다.
 * 2. **방향이 색을 가른다.**
 * 3. **죽어 사라진 말로는 안 긋는다** — 없는 자리로 그으면 격자 밖으로 나간다.
 * 4. **자기 자신에게 거는 것은 안 긋는다** — 선이 점이 된다.
 * 5. **말보다 먼저 긋는다** — 선이 글리프를 덮으면 무엇이 서 있는지 못 읽는다.
 */
import { describe, expect, it } from 'vitest'

import { EventLog, createLogEntry } from '../core/eventLog'
import { PHASE_ACT, PHASE_DECIDE } from '../core/sim/phases'

import type { PlanActorView, PlanLinkView } from './planScene'

/** 검사용 말 하나. */
function buildActor(over: Partial<PlanActorView> = {}): PlanActorView {
  return {
    entityId: 'player',
    kindId: 'player',
    x: 1,
    y: 1,
    kind: 'self',
    tier: 'NORMAL',
    label: 'PL',
    hpPercent: 100,
    isSelf: true,
    ...over,
  }
}

/** 로그 하나를 담은 가짜 엔진. */
function buildEngine(entries: readonly { from: string; to: string | null; phase?: string }[]) {
  const log = new EventLog()
  for (const entry of entries) {
    log.record(
      createLogEntry({
        tick: 3,
        entityId: entry.from,
        phase: entry.phase ?? PHASE_ACT,
        expr: 'ATTACK',
        outcome: '',
        targetId: entry.to,
      }),
    )
  }
  return { log, state: { tick: 3 } }
}

/** 장면 만들기를 흉내 내지 않고, 링크 수집만 떼어 본다. */
async function collect(
  entries: readonly { from: string; to: string | null; phase?: string }[],
  actors: readonly PlanActorView[],
): Promise<readonly PlanLinkView[]> {
  const { buildLinksFromLog } = await import('./planScene')
  return buildLinksFromLog(buildEngine(entries) as never, actors)
}

const PLAYER = buildActor()
const FOE = buildActor({ entityId: 'goblin_0', kindId: 'goblin_rusher', x: 4, y: 3, isSelf: false })

describe('대상 연결선', () => {
  it('★ 로그가 이미 아는 것을 쓴다 — 코어를 고칠 이유가 없는 자리다', async () => {
    const links = await collect([{ from: 'player', to: 'goblin_0' }], [PLAYER, FOE])
    expect(links).toEqual([{ fromX: 1, fromY: 1, toX: 4, toY: 3, isFromSelf: true }])
  })

  it('★ 방향이 색을 가른다 — 내가 하는 것과 나에게 오는 것은 다른 사건이다', async () => {
    const mine = await collect([{ from: 'player', to: 'goblin_0' }], [PLAYER, FOE])
    const theirs = await collect([{ from: 'goblin_0', to: 'player' }], [PLAYER, FOE])
    expect(mine[0]?.isFromSelf).toBe(true)
    expect(theirs[0]?.isFromSelf).toBe(false)
  })

  it('★ 죽어 사라진 말로는 안 긋는다 — 없는 자리로 그으면 격자 밖으로 나간다', async () => {
    expect(await collect([{ from: 'player', to: 'ghost_9' }], [PLAYER, FOE])).toEqual([])
  })

  it('★ 자기 자신에게 거는 것은 안 긋는다 — 선이 점이 된다', async () => {
    expect(await collect([{ from: 'player', to: 'player' }], [PLAYER, FOE])).toEqual([])
  })

  it('★ 대상 없는 행동은 안 긋는다 — 이동·대기까지 이으면 격자가 선으로 덮인다', async () => {
    expect(await collect([{ from: 'player', to: null }], [PLAYER, FOE])).toEqual([])
  })

  it('★ ACT 만 본다 — DECIDE 까지 세면 실행 안 된 계획이 선으로 뜬다', async () => {
    const links = await collect(
      [{ from: 'player', to: 'goblin_0', phase: PHASE_DECIDE }],
      [PLAYER, FOE],
    )
    expect(links).toEqual([])
  })
})

describe('연결선 그리기', () => {
  /** 캔버스 호출을 순서대로 받아 적는 가짜 문맥. */
  function buildFakeContext(): { calls: string[]; ctx: unknown } {
    const calls: string[] = []
    const noop = (): void => undefined
    return {
      calls,
      ctx: {
        save: noop,
        restore: noop,
        beginPath: noop,
        closePath: noop,
        moveTo: noop,
        lineTo: noop,
        arc: noop,
        rect: noop,
        clip: noop,
        translate: noop,
        setLineDash: noop,
        fill: noop,
        fillRect: noop,
        clearRect: noop,
        fillText: (text: string) => calls.push(`text:${text}`),
        measureText: () => ({ width: 4 }),
        stroke: () => calls.push('stroke'),
        strokeRect: noop,
        set strokeStyle(value: string) {
          calls.push(`stroke=${value}`)
        },
        set fillStyle(_value: string) {
          /* 배경·글리프 채움은 검사 대상이 아니다 */
        },
        set lineWidth(_value: number) {
          /* 굵기는 토큰이 정한다 */
        },
        set font(_value: string) {
          /* 활자는 토큰이 정한다 */
        },
        set textAlign(_value: string) {
          /* 정렬은 검사 대상이 아니다 */
        },
        set textBaseline(_value: string) {
          /* 정렬은 검사 대상이 아니다 */
        },
        set globalAlpha(_value: number) {
          /* 투명도는 검사 대상이 아니다 */
        },
      },
    }
  }

  /** 토큰 이름을 가짜 값으로 바꾼다. 색은 이름을 그대로 돌려줘 어느 색인지 보이게 한다. */
  function readFake(name: string): string {
    if (name === '--font-mono') {
      return 'mono'
    }
    const isLength =
      name.startsWith('--fs') || name === '--plan-cell' || name === '--hatch-gap' || name === '--bw'
    return isLength ? '12px' : name
  }

  async function render(links: readonly PlanLinkView[]): Promise<string[]> {
    const { renderPlan } = await import('./planRenderer')
    const { readPlanTheme } = await import('./planTheme')
    const fake = buildFakeContext()
    renderPlan(
      fake.ctx as never,
      { tick: 1, cols: 6, rows: 6, tiles: [], actors: [PLAYER, FOE], hazards: [], links, pulses: [] },
      readPlanTheme(readFake),
    )
    return fake.calls
  }

  it('★ 선이 말보다 먼저 그려진다 — 나중에 그으면 글리프를 덮어 무엇인지 못 읽는다', async () => {
    const calls = await render([{ fromX: 1, fromY: 1, toX: 4, toY: 3, isFromSelf: true }])
    const link = calls.indexOf('stroke=--plan-link-self')
    const glyph = calls.findIndex((call) => call.startsWith('text:'))
    expect(link).toBeGreaterThanOrEqual(0)
    expect(glyph).toBeGreaterThanOrEqual(0)
    expect(link).toBeLessThan(glyph)
  })

  it('★ 내가 건 것은 황동, 나에게 온 것은 녹슨 붉은색이다', async () => {
    const mine = await render([{ fromX: 1, fromY: 1, toX: 4, toY: 3, isFromSelf: true }])
    const theirs = await render([{ fromX: 4, fromY: 3, toX: 1, toY: 1, isFromSelf: false }])
    expect(mine).toContain('stroke=--plan-link-self')
    expect(mine).not.toContain('stroke=--plan-link-enemy')
    expect(theirs).toContain('stroke=--plan-link-enemy')
    expect(theirs).not.toContain('stroke=--plan-link-self')
  })

  it('★ 화살촉을 그린다 — 방향을 색만으로 말하면 색을 못 가르는 사람이 못 읽는다', async () => {
    const plain = await render([])
    const linked = await render([{ fromX: 1, fromY: 1, toX: 4, toY: 3, isFromSelf: true }])
    const strokes = (list: readonly string[]): number =>
      list.filter((call) => call === 'stroke').length
    // 몸통 한 번 + 화살촉 한 번 = 선 하나에 stroke 가 둘이다.
    expect(strokes(linked) - strokes(plain)).toBe(2)
  })

  it('★ 이을 것이 없으면 아무 선도 안 긋는다', async () => {
    expect(await render([])).not.toContain('stroke=--plan-link-self')
  })
})

describe('수치 이펙트 (간단한 표시)', () => {
  it('★ 피해는 대상에게 붉게, 회복은 자신에게 초록으로 — 뜻은 기존 색 그대로다', async () => {
    const { buildPulsesFromLog } = await import('./planScene')
    const { EventLog, createLogEntry } = await import('../core/eventLog')
    const { PHASE_ACT } = await import('../core/sim/phases')
    const log = new EventLog()
    log.record(createLogEntry({
      tick: 3, entityId: 'player', phase: PHASE_ACT, expr: 'ATTACK', outcome: '',
      targetId: 'goblin_0', delta: -7,
    }))
    log.record(createLogEntry({
      tick: 3, entityId: 'goblin_0', phase: PHASE_ACT, expr: 'USE_ITEM', outcome: '',
      delta: 12,
    }))
    // delta 없는 줄은 이펙트가 아니다 — 전부 그리면 매 틱 온 화면이 고리가 된다.
    log.record(createLogEntry({
      tick: 3, entityId: 'player', phase: PHASE_ACT, expr: 'MOVE_TO', outcome: '',
    }))
    const pulses = buildPulsesFromLog({ log, state: { tick: 3 } } as never, [PLAYER, FOE])
    expect(pulses).toEqual([
      { x: 4, y: 3, isGain: false },
      { x: 4, y: 3, isGain: true },
    ])
  })
})
