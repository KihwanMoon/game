/**
 * 마법 타격 자국 (2026-09-19).
 *
 * **예고 칸은 있었는데 터지는 순간이 없었다.** 붉은 칸이 그냥 사라지고 맞은 말에 고리만
 * 남아서, 관전자는 「비켜서서 피했는지」와 「맞았는지」를 같은 그림으로 봤다.
 *
 * 판은 발동과 동시에 예고를 버리므로 엔진이 **한 틱만** 들고 있는다(`lastBlasts`).
 * 로그에 안 싣는 이유는 골든이다 — 로그 줄은 두 코어가 비트 단위로 대조하는 값이라,
 * 화면 때문에 칸 목록을 실으면 대조 대상이 연출을 따라 움직인다.
 */
import { describe, expect, it } from 'vitest'

import { buildPlanScene } from './planScene'
import { BALANCE, ROOM_TEMPLATES } from '../core/resources'
import { PLAYER_ENTITY_ID, buildEngine, parseBalance } from '../core/services/runBattle'
import { CAST_FREE } from '../core/skills/catalog'
import { createPlannedAction } from '../core/sim/plan'

const METEOR = 'METEOR'

function buildCasting(telegraph: number) {
  const template = ROOM_TEMPLATES.find((one) => one.templateId === 'open_field')
  if (template === undefined) {
    throw new Error('방이 없다')
  }
  const engine = buildEngine({ template, balance: parseBalance(BALANCE), seed: 3 })
  const skills = engine.config.skills as Map<string, unknown>
  skills.set(METEOR, {
    skillId: METEOR,
    family: '',
    shape: { kind: 'AREA', radius: 2, length: 0 },
    targetFaction: '',
    coefPct: 200,
    cooldown: 0,
    reach: null,
    telegraph,
    castAct: CAST_FREE,
    cancelOnHit: false,
    healPct: 0,
    guardPct: 0,
    guardTicks: 0,
    tags: [],
    effects: [],
  })
  return engine
}

function castAt(engine: ReturnType<typeof buildCasting>, targetId: string) {
  engine.applyActions([
    createPlannedAction({
      entityId: PLAYER_ENTITY_ID,
      actionId: 'USE_SKILL',
      skillId: METEOR,
      targetId,
    }),
  ])
}

describe('마법 타격 자국', () => {
  it('★ 터진 틱에 칸이 남는다 — 예고가 사라지는 것과 같은 틱이다', () => {
    const engine = buildCasting(1)
    const player = engine.state.entities.get(PLAYER_ENTITY_ID)
    if (player === undefined) {
      throw new Error('플레이어가 없다')
    }
    const foe = engine.state.listHostiles(player)[0]
    if (foe === undefined) {
      throw new Error('적이 없다')
    }
    castAt(engine, foe.entityId)
    engine.runTick()
    const scene = buildPlanScene(engine)
    expect(scene.hazards).toEqual([])
    expect(scene.blasts.length).toBeGreaterThan(0)
  })

  it('★ 안 터진 틱에는 자국이 없다 — 예고만 있을 때 터짐을 그리면 거짓이다', () => {
    const engine = buildCasting(3)
    const player = engine.state.entities.get(PLAYER_ENTITY_ID)
    if (player === undefined) {
      throw new Error('플레이어가 없다')
    }
    const foe = engine.state.listHostiles(player)[0]
    if (foe === undefined) {
      throw new Error('적이 없다')
    }
    castAt(engine, foe.entityId)
    const scene = buildPlanScene(engine)
    expect(scene.hazards.length).toBeGreaterThan(0)
    expect(scene.blasts).toEqual([])
  })

  it('★ 맞은 칸과 빈 칸을 가른다 — 반경 안이 전부 같으면 누가 맞았는지 안 보인다', () => {
    const engine = buildCasting(1)
    const player = engine.state.entities.get(PLAYER_ENTITY_ID)
    if (player === undefined) {
      throw new Error('플레이어가 없다')
    }
    const foe = engine.state.listHostiles(player)[0]
    if (foe === undefined) {
      throw new Error('적이 없다')
    }
    castAt(engine, foe.entityId)
    engine.runTick()
    const scene = buildPlanScene(engine)
    expect(scene.blasts.some((one) => one.isHit)).toBe(true)
    expect(scene.blasts.some((one) => !one.isHit)).toBe(true)
  })

  it('★ 다음 틱에는 지워진다 — 자국이 남으면 지형처럼 읽힌다', () => {
    const engine = buildCasting(1)
    const player = engine.state.entities.get(PLAYER_ENTITY_ID)
    if (player === undefined) {
      throw new Error('플레이어가 없다')
    }
    const foe = engine.state.listHostiles(player)[0]
    if (foe === undefined) {
      throw new Error('적이 없다')
    }
    castAt(engine, foe.entityId)
    engine.runTick()
    expect(buildPlanScene(engine).blasts.length).toBeGreaterThan(0)
    engine.runTick()
    expect(buildPlanScene(engine).blasts).toEqual([])
  })

  it('★ 좌표 순으로 정렬된다 — 순서가 흔들리면 같은 판이 다르게 그려진다', () => {
    const engine = buildCasting(1)
    const player = engine.state.entities.get(PLAYER_ENTITY_ID)
    if (player === undefined) {
      throw new Error('플레이어가 없다')
    }
    const foe = engine.state.listHostiles(player)[0]
    if (foe === undefined) {
      throw new Error('적이 없다')
    }
    castAt(engine, foe.entityId)
    engine.runTick()
    const keys = buildPlanScene(engine).blasts.map((one) => one.y * 100 + one.x)
    expect([...keys].sort((a, b) => a - b)).toEqual(keys)
  })
})

describe('타격 자국을 실제로 그린다', () => {
  // **장면만 보면 안 그려져도 초록이다.** 값이 장면에 실리는 것과 캔버스에 닿는 것은
  // 다른 일이고, 여기가 그 사이를 잇는다.
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
        lineTo: (x: number, y: number) => calls.push(`line:${String(Math.round(x))},${String(Math.round(y))}`),
        arc: noop,
        rect: noop,
        clip: noop,
        translate: noop,
        setLineDash: noop,
        fill: noop,
        fillRect: (x: number, y: number) => calls.push(`fillRect:${String(Math.round(x))},${String(Math.round(y))}`),
        clearRect: noop,
        fillText: noop,
        measureText: () => ({ width: 4 }),
        stroke: () => calls.push('stroke'),
        strokeRect: noop,
        set fillStyle(_value: string) {},
        set strokeStyle(_value: string) {},
        set lineWidth(_value: number) {},
        set globalAlpha(value: number) {
          calls.push(`alpha:${String(value)}`)
        },
        set font(_value: string) {},
        set textAlign(_value: string) {},
        set textBaseline(_value: string) {},
      },
    }
  }

  function readFake(name: string): string {
    if (name === '--font-mono') {
      return 'mono'
    }
    const isLength =
      name.startsWith('--fs') || name === '--plan-cell' || name === '--hatch-gap' || name === '--bw'
    return isLength ? '12px' : name
  }

  async function render(blasts: { x: number; y: number; isHit: boolean; fromX: number; fromY: number }[]) {
    const { renderPlan } = await import('./planRenderer')
    const { readPlanTheme } = await import('./planTheme')
    const fake = buildFakeContext()
    renderPlan(
      fake.ctx as never,
      {
        tick: 1,
        cols: 6,
        rows: 6,
        tiles: [],
        actors: [],
        hazards: [],
        links: [],
        pulses: [],
        blasts,
      },
      readPlanTheme(readFake),
    )
    return fake.calls
  }

  it('★ 자국이 없으면 아무것도 안 그린다', async () => {
    expect(await render([])).not.toContain('alpha:0.5')
  })

  it('★ 맞은 칸과 빈 칸의 농도가 다르다 — 명도가 세 채널 중 하나다', async () => {
    const calls = await render([
      { x: 1, y: 1, isHit: true, fromX: 1, fromY: 1 },
      { x: 2, y: 1, isHit: false, fromX: 1, fromY: 1 },
    ])
    expect(calls).toContain('alpha:0.5')
    expect(calls).toContain('alpha:0.16')
  })

  it('★ 중심에서 금이 뻗는다 — 채움만으로는 지형과 구별되지 않는다', async () => {
    // **격자도 같은 `lineTo` 를 쓴다.** 그래서 절대 수가 아니라 **있을 때와 없을 때의
    // 차이**로 센다 — 렌더러가 무엇을 더 그렸는지를 묻는 것이 이 검사의 요점이다.
    const bare = (await render([])).filter((one) => one.startsWith('line:')).length
    const drawn = (await render([{ x: 1, y: 1, isHit: true, fromX: 1, fromY: 1 }])).filter((one) =>
      one.startsWith('line:'),
    ).length
    expect(drawn - bare).toBe(4)
  })
})
