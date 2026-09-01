/**
 * 전투 화면 테스트 (W13).
 *
 * 캔버스는 브라우저 API 라 노드에서 돌지 않는다. 그래서 jsdom 을 새 의존성으로 들이는
 * 대신 **호출을 받아 적는 가짜 문맥**을 끼운다. 확인할 것이 화소가 아니라 계약이기
 * 때문이다 — 벽에 해칭을 그었는가, 예고 칸에 남은 틱을 적었는가, 말 여덟 종이 서로
 * 구분되는가.
 *
 * 가장 중요한 것은 마지막의 결정론 검사다. 화면을 켜려고 끼운 `TracingRuleVm` 이 전투
 * 결과를 **한 글자도** 바꾸지 않아야 한다. 바꾸면 화면을 켜고 돌린 판과 헤드리스로 돌린
 * 판이 갈리고, 그 순간 게이트 G3 가 지키는 두 코어 동일성이 뜻을 잃는다 (R5).
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { BLOCK_CATALOG, BALANCE, ENEMY_RULESETS, G0_RULESETS, ROOM_TEMPLATES } from '../core/resources'
import { recordBattle } from '../hud'
import { buildRuleVm } from '../core/rules/ruleVm'
import {
  PLAYER_ENTITY_ID,
  assignEnemyPolicies,
  buildEngine,
  parseBalance,
} from '../core/services/runBattle'
import {
  SPEED_INSTANT,
  SPEED_PAUSE,
  getStepTicks,
  runTickBatch,
} from '../core/services/runSteppedBattle'
import {
  TILE_BREAKABLE_WALL,
  TILE_COVER,
  TILE_DOOR,
  TILE_FLOOR,
  TILE_LAVA,
  TILE_SPRING,
  TILE_STAIRS,
  TILE_THORNS,
  TILE_TRAP,
  TILE_WALL,
} from '../core/schemas'
import { OUTCOME_ONGOING } from '../core/sim/phases'
import type { LogEntry } from '../core/eventLog'
import {
  BattleView,
  KIND_BY_ENEMY_TYPE,
  resizePlanCanvas,
  LeaderLine,
  SHORT_LABEL_BY_KIND_ID,
  TILE_DRAWERS,
  addExtraEnemies,
  buildBattleSession,
  buildLeaderPath,
  buildPlanScene,
  resolveTierColor,
  describeScene,
  getStepTicksByStep,
  parseDurationMs,
  OUTCOME_GLYPHS,
  OUTCOME_LABELS,
  OUTCOME_NOTICES,
  checkPlanThemeSame,
  formatOutcome,
  formatOutcomeNotice,
  readBatchIntervalMs,
  readPlanTheme,
  renderPlan,
  resolveActorKind,
  resolveActorLabel,
  PLAN_COLOR_TOKENS,
  PLAN_FONT_TOKEN,
  PLAN_LENGTH_TOKENS,
  RING_RATIO,
  SHOULDER_MODULES,
} from '.'
import type { PlanScene, PlanTheme } from '.'

const BATTLE_DIR = fileURLToPath(new URL('.', import.meta.url))
const DESIGN_DIR = fileURLToPath(new URL('../../../design/', import.meta.url))

/** 확인용 전투. BattleCheck 와 같은 조합이라 페이지에서 본 것을 여기서 되짚을 수 있다. */
const CHECK_SETUP = {
  roomId: 'pillars',
  rulesetId: 'g0_cover',
  seed: 4242,
  extraEnemies: [
    { kind: 'bomb_slime', x: 9, y: 1 },
    { kind: 'mender_acolyte', x: 10, y: 4 },
    { kind: 'arch_summoner', x: 9, y: 7 },
  ],
} as const

/**
 * 주석을 걷어 낸 CSS 를 읽는다. 주석 안의 예시가 규율 검사에 걸리지 않게 한다.
 *
 * @param name 읽을 파일 이름.
 * @returns 주석이 빠진 본문.
 */
function readStrippedCss(name: string): string {
  return readFileSync(`${BATTLE_DIR}${name}`, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')
}

/**
 * 디자인 토큰 CSS 를 통째로 읽는다.
 *
 * @returns 토큰 파일 여덟 개를 이어 붙인 문자열.
 */
function readDesignTokens(): string {
  const names = [
    'base.css',
    'borders.css',
    'colors.css',
    'fonts.css',
    'motion.css',
    'spacing.css',
    'typography.css',
  ]
  return names.map((name) => readFileSync(`${DESIGN_DIR}tokens/${name}`, 'utf8')).join('\n')
}

/**
 * 세로 배치 블록의 @media 머리를 찾는다.
 *
 * 폭 리터럴을 박지 않는 이유는 경계가 실측을 따르기 때문이다 — 599 로 뒀더니
 * iPad 세로(768·810·834)가 desktop 배치를 받아 가로로 넘쳤고, 데스크톱 골격이
 * 841px 부터 성립한다는 실측에 맞춰 840 으로 옮겼다. 이 블록의 정체는 폭이 아니라
 * `--layout-mode:portrait` 다.
 *
 * @returns `@media (...)` 머리 문자열.
 */
function findPortraitMedia(): string {
  const found = /@media[^{]*(?=\{[^}]*--layout-mode:\s*portrait)/.exec(readDesignTokens())
  expect(found, '--layout-mode:portrait 를 정의하는 @media 블록이 없다').not.toBeNull()
  return (found?.[0] ?? '').trimEnd()
}

/** 캔버스 호출 한 건. */
interface DrawCall {
  readonly op: string
  readonly args: readonly unknown[]
}

/**
 * 호출을 받아 적는 가짜 2D 문맥을 만든다.
 *
 * 브라우저 API 를 흉내 내는 것이라 단언이 한 번 필요하다. 이 파일 밖으로 나가지 않는다.
 *
 * @returns 문맥과 기록된 호출들.
 */
function createRecordingContext(): {
  ctx: CanvasRenderingContext2D
  calls: DrawCall[]
  styles: string[]
} {
  const calls: DrawCall[] = []
  const styles: string[] = []
  const noop = (op: string) => {
    return (...args: unknown[]): void => {
      calls.push({ op, args })
    }
  }
  const recorder = {
    save: noop('save'),
    restore: noop('restore'),
    beginPath: noop('beginPath'),
    closePath: noop('closePath'),
    moveTo: noop('moveTo'),
    lineTo: noop('lineTo'),
    quadraticCurveTo: noop('quadraticCurveTo'),
    arc: noop('arc'),
    rect: noop('rect'),
    clip: noop('clip'),
    fill: noop('fill'),
    stroke: noop('stroke'),
    fillRect: noop('fillRect'),
    strokeRect: noop('strokeRect'),
    clearRect: noop('clearRect'),
    fillText: noop('fillText'),
    setLineDash: noop('setLineDash'),
    set fillStyle(value: string) {
      styles.push(value)
    },
    set strokeStyle(value: string) {
      styles.push(value)
    },
    lineWidth: 1,
    font: '',
    textAlign: 'left',
    textBaseline: 'top',
  }
  return { ctx: recorder as unknown as CanvasRenderingContext2D, calls, styles }
}

/** 토큰 이름에서 값으로. 실제 토큰과 같은 꼴의 가짜다. */
const FAKE_TOKENS: ReadonlyMap<string, string> = new Map([
  ['--surface-plan', '#0E131C'],
  ['--line-grid', '#2C3849'],
  ['--plan-wall', '#2C3849'],
  ['--plan-floor-dot', '#7C889A'],
  ['--plan-door', '#7C889A'],
  ['--surface-raised', '#1F2836'],
  ['--line-strong', '#7C889A'],
  ['--state-heal', '#4F8F7E'],
  ['--plan-hazard', '#A65A42'],
  ['--plan-actor-self', '#C89A4E'],
  ['--plan-actor-enemy', '#C6CFDC'],
  ['--plan-actor-elite', '#F2D14A'],
  ['--plan-actor-boss', '#F08A3C'],
  ['--text-dim', '#7C889A'],
  ['--plan-cell', '64px'],
  ['--hatch-gap', '4px'],
  ['--bw', '1px'],
  ['--fs-num-l', '18px'],
  ['--fs-label', '11px'],
  ['--font-mono', '"IBM Plex Mono", monospace'],
  ['--dur-tick', '140ms'],
])

/**
 * 가짜 토큰을 읽는 함수.
 *
 * @param name 토큰 이름.
 * @returns 값. 표에 없으면 빈 문자열.
 */
function readFakeToken(name: string): string {
  return FAKE_TOKENS.get(name) ?? ''
}

const FAKE_THEME: PlanTheme = readPlanTheme(readFakeToken)


describe('토큰 규율', () => {
  it('battle.css 에 생 hex 색이 없다', () => {
    expect(readStrippedCss('battle.css').match(/#[0-9a-fA-F]{3,8}\b/g)).toBeNull()
  })

  it('battle.css 에 생 px 값이 없다', () => {
    expect(readStrippedCss('battle.css').match(/\d+px/g)).toBeNull()
  })

  it('battle.css 는 그림자를 쓰지 않는다 — 층위는 명도차와 괘선으로만 만든다', () => {
    expect(readStrippedCss('battle.css')).not.toContain('box-shadow')
  })

  it('움직임은 명도 전환뿐이다 — transform 애니메이션을 쓰지 않는다', () => {
    const css = readStrippedCss('battle.css')
    expect(css).not.toContain('transform')
    expect(css).toContain('var(--dur-tick)')
    expect(css).toContain('var(--ease)')
  })

  it('렌더러가 읽는 토큰이 design/ 에 실제로 있다', () => {
    const tokens = readDesignTokens()
    const names = [...PLAN_COLOR_TOKENS.values(), ...PLAN_LENGTH_TOKENS.values(), PLAN_FONT_TOKEN]
    for (const name of names) {
      expect(tokens, `${name} 가 토큰 CSS 에 없다`).toContain(`${name}:`)
    }
  })

  it('없는 토큰은 조용히 넘기지 않고 이름을 달고 던진다', () => {
    expect(() => readPlanTheme(() => '')).toThrow('--plan-cell')
  })

  it('격자 토큰 12x9 가 룸 템플릿과 맞는다 (design/README.md D-2)', () => {
    const tokens = readDesignTokens()
    const cols = Number.parseInt(/--plan-cols:\s*(\d+)/.exec(tokens)?.[1] ?? '', 10)
    const rows = Number.parseInt(/--plan-rows:\s*(\d+)/.exec(tokens)?.[1] ?? '', 10)
    expect(cols).toBe(12)
    expect(rows).toBe(9)
    for (const template of ROOM_TEMPLATES) {
      expect(template.width, `${template.templateId} 의 폭이 토큰과 다르다`).toBe(cols)
      expect(template.height, `${template.templateId} 의 높이가 토큰과 다르다`).toBe(rows)
    }
  })

  it('캔버스의 CSS 크기는 셀 토큰의 배수로 준다 — 자바스크립트에도 생 px 를 두지 않는다', () => {
    const canvas = {
      style: { width: '', height: '' },
      width: 0,
      height: 0,
      getContext: () => null,
    }
    const scene: PlanScene = { tick: 0, cols: 12, rows: 9, tiles: [], actors: [], hazards: [] }
    resizePlanCanvas(canvas as unknown as HTMLCanvasElement, scene, FAKE_THEME, 2)
    expect(canvas.style.width).toBe('calc(var(--plan-cell) * 12)')
    expect(canvas.style.height).toBe('calc(var(--plan-cell) * 9)')
    // 백버퍼만 배율을 곱한다. 여기서 배율을 빼면 1px 괘선이 흐려진다.
    expect(canvas.width).toBe(12 * FAKE_THEME.cell * 2)
    expect(canvas.height).toBe(9 * FAKE_THEME.cell * 2)
  })
})

describe('적 유형 접기 (design/README.md D-1)', () => {
  it('balance.json 의 유형이 전부 도면 말로 접힌다', () => {
    const types = new Set(parseBalance(BALANCE).enemies.map((kind) => kind.type))
    for (const type of types) {
      expect(KIND_BY_ENEMY_TYPE.has(type), `${type} 매핑이 없다`).toBe(true)
    }
  })

  it('글리프가 겹치는 자리를 두 글자 표기가 가른다 — 여덟 종이 서로 다르다', () => {
    const kinds = parseBalance(BALANCE).enemies.map((kind) => kind.id)
    const labels = kinds.map(resolveActorLabel)
    expect(new Set(labels).size).toBe(kinds.length)
  })

  it('자폭형은 돌진형과 같은 말이고 치유형은 소환형과 같은 말이다', () => {
    const kindTypes = new Map(parseBalance(BALANCE).enemies.map((one) => [one.id, one.type]))
    expect(resolveActorKind('bomb_slime', kindTypes)).toBe('charge')
    expect(resolveActorKind('mender_acolyte', kindTypes)).toBe('summon')
    expect(resolveActorKind('longbow_archer', kindTypes)).toBe('shoot')
    expect(SHORT_LABEL_BY_KIND_ID.get('bomb_slime')).toBe('자폭')
  })

  it('모르는 종류도 말은 나온다 — 빈칸으로 두지 않는다', () => {
    expect(resolveActorKind('없는_종류', new Map())).toBe('charge')
    expect(resolveActorLabel('없는_종류')).toBe('없는')
  })
})

describe('도면 렌더러', () => {
  it('타일 열 종이 전부 그려진다', () => {
    const tiles = [
      TILE_FLOOR,
      TILE_WALL,
      TILE_BREAKABLE_WALL,
      TILE_THORNS,
      TILE_DOOR,
      TILE_SPRING,
      TILE_STAIRS,
      TILE_LAVA,
      TILE_TRAP,
      TILE_COVER,
    ]
    for (const tile of tiles) {
      expect(TILE_DRAWERS.has(tile), `타일 ${String(tile)} 의 드로어가 없다`).toBe(true)
    }
    expect(TILE_DRAWERS.size).toBe(tiles.length)
  })

  it('타일마다 그리는 꼴이 다르다 — 색을 못 봐도 구분된다', () => {
    // 좌표까지 넣어 비교한다. 호출 이름만 보면 가시덤불(대각선 여섯)과 계단(수평선 여섯)이
    // 같은 자취를 남기지만 그려지는 그림은 전혀 다르다.
    const shapes = [...TILE_DRAWERS.values()].map((draw) => {
      const { ctx, calls } = createRecordingContext()
      draw(ctx, { left: 0, top: 0, size: FAKE_THEME.cell }, FAKE_THEME)
      return JSON.stringify(calls)
    })
    expect(new Set(shapes).size).toBe(shapes.length)
  })

  it('예고 칸에 남은 틱을 적는다 — 색만으로 알리지 않는다', () => {
    const scene: PlanScene = {
      tick: 3,
      cols: 1,
      rows: 1,
      tiles: [[TILE_FLOOR]],
      actors: [],
      hazards: [{ x: 0, y: 0, ticks: 2, isSensed: true }],
    }
    const { ctx, calls, styles } = createRecordingContext()
    renderPlan(ctx, scene, FAKE_THEME)
    const texts = calls.filter((call) => call.op === 'fillText').map((call) => call.args[0])
    expect(texts).toContain('2')
    expect(styles).toContain(FAKE_THEME.hazard)
  })

  it('아직 인지하지 못한 예고는 점선으로 그린다', () => {
    const build = (isSensed: boolean): DrawCall[] => {
      const { ctx, calls } = createRecordingContext()
      renderPlan(
        ctx,
        {
          tick: 1,
          cols: 1,
          rows: 1,
          tiles: [[TILE_FLOOR]],
          actors: [],
          hazards: [{ x: 0, y: 0, ticks: 3, isSensed }],
        },
        FAKE_THEME,
      )
      return calls
    }
    const dashed = build(false).filter((call) => call.op === 'setLineDash')
    const solid = build(true).filter((call) => call.op === 'setLineDash')
    expect(dashed.length).toBeGreaterThan(solid.length)
  })

  it('플레이어 말만 황동을 쓴다 — 예산 한 자리다', () => {
    const scene: PlanScene = {
      tick: 1,
      cols: 2,
      rows: 1,
      tiles: [[TILE_FLOOR, TILE_FLOOR]],
      actors: [
        {
          entityId: 'player',
          kindId: 'player',
          x: 0,
          y: 0,
          kind: 'self',
          tier: 'NORMAL',
          label: '자신',
          hpPercent: 100,
          isSelf: true,
        },
        {
          entityId: 'goblin_rusher_0',
          kindId: 'goblin_rusher',
          x: 1,
          y: 0,
          kind: 'charge',
          tier: 'NORMAL',
          label: '돌진',
          hpPercent: 50,
          isSelf: false,
        },
      ],
      hazards: [],
    }
    const { ctx, calls, styles } = createRecordingContext()
    renderPlan(ctx, scene, FAKE_THEME)
    expect(styles.filter((one) => one === FAKE_THEME.actorSelf)).toHaveLength(2)
    const glyphs = calls.filter((call) => call.op === 'fillText').map((call) => call.args[0])
    expect(glyphs).toContain('◉')
    expect(glyphs).toContain('▲')
    expect(glyphs).toContain('돌진')
  })
})

describe('장면 만들기', () => {
  it('실제 엔진에서 방과 말이 그대로 나온다', () => {
    const session = buildBattleSession(CHECK_SETUP, G0_RULESETS)
    const scene = buildPlanScene(session.engine)
    expect(scene.cols).toBe(session.template.width)
    expect(scene.rows).toBe(session.template.height)
    expect(scene.tiles).toHaveLength(session.template.height)
    const self = scene.actors.find((actor) => actor.isSelf)
    expect(self?.x).toBe(session.template.playerSpawn.x)
    expect(self?.y).toBe(session.template.playerSpawn.y)
    // 템플릿 스폰 둘 + 덧붙인 셋 + 플레이어.
    expect(scene.actors).toHaveLength(6)
  })

  it('폭탄 슬라임이 붙으면 예고 칸이 실제로 생긴다 (GDD §4.2)', () => {
    const session = buildBattleSession(CHECK_SETUP, G0_RULESETS)
    let marked = 0
    for (let tick = 0; tick < 60 && marked === 0; tick += 1) {
      runTickBatch(session.engine, 1)
      marked = buildPlanScene(session.engine).hazards.length
    }
    expect(marked).toBeGreaterThan(0)
  })

  it('예고 칸은 행 우선으로 정렬돼 순서가 흔들리지 않는다', () => {
    const session = buildBattleSession(CHECK_SETUP, G0_RULESETS)
    for (let tick = 0; tick < 60; tick += 1) {
      runTickBatch(session.engine, 1)
      const { hazards } = buildPlanScene(session.engine)
      const keys = hazards.map((one) => one.y * 100 + one.x)
      expect([...keys].sort((left, right) => left - right)).toEqual(keys)
    }
  })

  it('보조 기술이 읽을 한 줄을 낸다', () => {
    const session = buildBattleSession(CHECK_SETUP, G0_RULESETS)
    const text = describeScene(buildPlanScene(session.engine))
    expect(text).toContain('틱 0')
    expect(text).toContain('자신')
  })
})

describe('배속 — 틱은 정수 단위로만 는다 (GDD §2.1)', () => {
  it('파이썬과 같은 표를 쓴다', () => {
    expect(getStepTicks(SPEED_PAUSE)).toBe(0)
    expect(getStepTicks('1x')).toBe(1)
    expect(getStepTicks('2x')).toBe(2)
    expect(getStepTicks('4x')).toBe(4)
    expect(getStepTicks(SPEED_INSTANT)).toBeGreaterThan(4)
  })

  it('모르는 배속은 조용히 정지하지 않고 던진다', () => {
    expect(() => getStepTicks('8x')).toThrow('모르는 배속이다')
  })

  it('ds 의 숫자 단계가 그 표로 이어진다', () => {
    expect(getStepTicksByStep(0)).toBe(0)
    expect(getStepTicksByStep(4)).toBe(4)
    expect(getStepTicksByStep(3)).toBe(0)
  })

  it('일시정지는 한 틱도 돌리지 않는다', () => {
    const session = buildBattleSession(CHECK_SETUP, G0_RULESETS)
    const batch = runTickBatch(session.engine, getStepTicks(SPEED_PAUSE))
    expect(session.engine.state.tick).toBe(0)
    expect(batch.entries).toHaveLength(0)
  })

  it('4배속은 정확히 네 틱을 돌린다', () => {
    const session = buildBattleSession(CHECK_SETUP, G0_RULESETS)
    runTickBatch(session.engine, 4)
    expect(session.engine.state.tick).toBe(4)
  })

  it('배치 간격은 틱 교체 시간의 배수다 — 전환이 끝나기 전에 값이 또 바뀌지 않는다', () => {
    expect(readBatchIntervalMs(readFakeToken)).toBe(280)
    expect(readBatchIntervalMs(() => '')).toBeGreaterThan(0)
  })

  it('브라우저가 정규화한 초 표기도 같은 간격으로 읽는다', () => {
    // 크롬의 getComputedStyle 은 `140ms` 를 `.14s` 로 돌려준다. 단위를 보지 않으면
    // 간격이 0.28ms 가 되어 매 프레임 한 틱씩 돌고 배속 선택이 무의미해진다.
    expect(parseDurationMs('140ms')).toBe(140)
    expect(parseDurationMs('.14s')).toBeCloseTo(140)
    expect(parseDurationMs('0.14s')).toBeCloseTo(140)
    expect(parseDurationMs('없음')).toBeNaN()
    expect(readBatchIntervalMs(() => '.14s')).toBeCloseTo(280)
  })
})

describe('규칙 추적 — 상태 셋 (design/README.md §2)', () => {
  it('발동한 줄을 경계로 앞은 거짓, 뒤는 미평가다', () => {
    const session = buildBattleSession(CHECK_SETUP, G0_RULESETS)
    runTickBatch(session.engine, 1)
    const trace = session.tracer.trace
    expect(trace).toBeDefined()
    const armed = trace?.rows.filter((row) => row.armed) ?? []
    expect(armed.length).toBeLessThanOrEqual(1)
    if (armed[0] !== undefined) {
      const boundary = armed[0].priority
      for (const row of trace?.rows ?? []) {
        if (row.priority < boundary) {
          expect(row.state).toBe('false')
        } else if (row.priority > boundary) {
          expect(row.state).toBe('pending')
        } else {
          expect(row.state).toBe('true')
        }
      }
    }
  })

  it('발동한 줄의 조건문은 코어가 만든 것 그대로다 — 실측값이 병기된다', () => {
    const session = buildBattleSession(CHECK_SETUP, G0_RULESETS)
    for (let tick = 0; tick < 20; tick += 1) {
      runTickBatch(session.engine, 1)
      const armed = session.tracer.trace?.rows.find((row) => row.armed)
      if (armed !== undefined) {
        const decide = session.engine.log.entries.find(
          (entry) =>
            entry.entityId === PLAYER_ENTITY_ID &&
            entry.phase === 'DECIDE' &&
            entry.tick === session.engine.state.tick,
        )
        expect(armed.condition).toBe(decide?.expr)
        return
      }
    }
    throw new Error('20틱 안에 발동한 규칙이 하나도 없다')
  })

  it('누적 CPU 는 줄을 따라 는다', () => {
    const session = buildBattleSession(CHECK_SETUP, G0_RULESETS)
    runTickBatch(session.engine, 1)
    const rows = session.tracer.trace?.rows ?? []
    for (let index = 1; index < rows.length; index += 1) {
      expect(rows[index]?.cpuUsed).toBeGreaterThanOrEqual(rows[index - 1]?.cpuUsed ?? 0)
    }
  })
})

describe('지시선', () => {
  it('고리 바깥에서 멈춘다 — 글리프를 가로지르지 않는다', () => {
    const path = buildLeaderPath({
      from: { x: 0, y: 100 },
      to: { x: 600, y: 300 },
      cell: 64,
      module: 4,
    })
    expect(path).toBeDefined()
    const distance = Math.hypot(
      (path?.end.x ?? 0) - (path?.center.x ?? 0),
      (path?.end.y ?? 0) - (path?.center.y ?? 0),
    )
    expect(distance).toBeCloseTo(64 * RING_RATIO)
  })

  it('어깨는 4px 모듈의 배수만큼 나간다', () => {
    const path = buildLeaderPath({
      from: { x: 10, y: 10 },
      to: { x: 600, y: 300 },
      cell: 64,
      module: 4,
    })
    expect(path?.shoulder.x).toBe(10 + 4 * SHOULDER_MODULES)
    expect(path?.shoulder.y).toBe(10)
  })

  it('말이 어깨 바로 옆이면 선을 긋지 않는다', () => {
    expect(
      buildLeaderPath({ from: { x: 0, y: 0 }, to: { x: 20, y: 0 }, cell: 64, module: 4 }),
    ).toBeUndefined()
  })

  it('황동은 클래스로만 준다 — 인라인 색이 없다', () => {
    const html = renderToStaticMarkup(
      <LeaderLine
        path={{
          start: { x: 0, y: 0 },
          shoulder: { x: 16, y: 0 },
          end: { x: 100, y: 50 },
          center: { x: 120, y: 60 },
          radius: 23,
        }}
        label="규칙 2"
      />,
    )
    expect(html).toContain('battle__leader-line')
    expect(html).toContain('battle__leader-ring')
    expect(html).not.toContain('stroke=')
  })

  it('그릴 것이 없으면 아무것도 그리지 않는다', () => {
    expect(renderToStaticMarkup(<LeaderLine path={undefined} label="없음" />)).toBe('')
  })
})

/**
 * 규칙표를 붙인 판을 조립한다. 추적기 없이 파이썬과 같은 배선만 쓴다.
 *
 * @returns 끝까지 돌릴 준비가 된 엔진.
 */
function buildPlainSession(): ReturnType<typeof buildEngine> {
  const balance = parseBalance(BALANCE)
  const template = buildBattleSession(CHECK_SETUP, G0_RULESETS).template
  const engine = buildEngine({ template, balance, seed: CHECK_SETUP.seed })
  const ruleset = G0_RULESETS.get(CHECK_SETUP.rulesetId)
  if (ruleset === undefined) {
    throw new Error('확인용 규칙표가 없다')
  }
  engine.policies.set(
    PLAYER_ENTITY_ID,
    buildRuleVm(ruleset, BLOCK_CATALOG, engine.config.kindTypes),
  )
  assignEnemyPolicies(engine, balance, BLOCK_CATALOG, ENEMY_RULESETS)
  addExtraEnemies(engine, balance, CHECK_SETUP.extraEnemies)
  return engine
}

describe('결정론 — 화면을 켜도 판이 달라지지 않는다 (R5)', () => {
  it('추적기를 끼운 판과 끼우지 않은 판의 로그가 한 글자도 다르지 않다', () => {
    const traced = buildBattleSession(CHECK_SETUP, G0_RULESETS).engine
    const plain = buildPlainSession()

    let outcome = OUTCOME_ONGOING
    while (outcome === OUTCOME_ONGOING) {
      outcome = traced.runTick()
    }
    let plainOutcome = OUTCOME_ONGOING
    while (plainOutcome === OUTCOME_ONGOING) {
      plainOutcome = plain.runTick()
    }

    expect(outcome).toBe(plainOutcome)
    expect(traced.state.tick).toBe(plain.state.tick)
    expect(traced.log.count()).toBe(plain.log.count())
    const fields = (entry: LogEntry): unknown[] => [
      entry.tick,
      entry.entityId,
      entry.phase,
      entry.expr,
      entry.outcome,
      entry.rule,
      entry.delta,
      entry.fired,
      entry.targetId,
    ]
    expect(traced.log.entries.map(fields)).toEqual(plain.log.entries.map(fields))
  })

  it('같은 시드는 같은 판을 낸다', () => {
    const first = buildBattleSession(CHECK_SETUP, G0_RULESETS).engine
    const second = buildBattleSession(CHECK_SETUP, G0_RULESETS).engine
    runTickBatch(first, 40)
    runTickBatch(second, 40)
    expect(first.log.formatLines()).toEqual(second.log.formatLines())
  })
})

describe('전투 화면 골격', () => {
  it('세 열과 위아래 바가 실제 전투 상태로 그려진다', () => {
    // 서버 렌더에는 화면이 없으므로 캔버스는 나오지 않는다. 여기서 보는 것은 골격과
    // 규칙표·로그가 **실제 엔진 값**으로 채워지는가다.
    const html = renderToStaticMarkup(
      <BattleView setup={CHECK_SETUP} rulesets={G0_RULESETS} location="1층 · pillars" />,
    )
    expect(html).toContain('class="battle"')
    expect(html).toContain('battle__rule-line')
    expect(html).toContain('ds-topbar')
    expect(html).toContain('ds-rule-table')
    expect(html).toContain('ds-statusbar')
    expect(html).toContain('1층 · pillars')
    // 아직 한 틱도 돌지 않았으므로 규칙 줄은 전부 미평가다.
    expect(html).toContain('ds-rule-row--pending')
    expect(html).not.toContain('ds-rule-row--armed')
  })

  it('상단의 버튼은 primary 를 쓰지 않는다 — 황동 예산 셋은 도면·규칙·지시선이다', () => {
    const html = renderToStaticMarkup(
      <BattleView setup={CHECK_SETUP} rulesets={G0_RULESETS} location="1층 · pillars" />,
    )
    expect(html).not.toContain('ds-button--primary')
  })
})

describe('반응형 토큰 (design/tokens/spacing.css)', () => {
  /** 토큰 CSS 에서 미디어쿼리 블록 하나를 잘라 낸다. */
  const cutMedia = (query: string): string => {
    const tokens = readDesignTokens()
    const start = tokens.indexOf(query)
    expect(start, `${query} 가 토큰 CSS 에 없다`).toBeGreaterThan(-1)
    return tokens.slice(start, tokens.indexOf('}\n}', start))
  }

  it('데스크톱 기본값은 그대로 64px 이다 — 기존 화면이 흔들리지 않는다', () => {
    const root = readDesignTokens().split('@media')[0] ?? ''
    expect(root).toContain('--plan-cell:64px')
    expect(root).toContain('--bar-top:56px')
    expect(root).toContain('--bar-bottom:48px')
    expect(root).toContain('--col-rules:320px')
    expect(root).toContain('--col-log:300px')
  })

  it('세로 모바일은 셀 30px 로 12x9 를 390px 안에 넣는다', () => {
    // 폭 리터럴로 찾지 않는다. 경계는 실측에 따라 바뀌지만(599 → 840, 데스크톱
    // 골격이 841px 부터 성립한다) 이 블록의 정체는 --layout-mode:portrait 다.
    const block = cutMedia(findPortraitMedia())
    expect(block).toContain('--layout-mode:portrait')
    expect(block).toContain('--plan-cell:30px')
    expect(block).toContain('--bar-top:44px')
    expect(block).toContain('--bar-status:34px')
    expect(block).toContain('--row-h:54px')
    // 12x30 = 360 에 좌우 여백을 더해도 390 을 넘지 않아야 한다.
    const cell = 30
    const pad = 14
    expect(cell * 12 + pad * 2).toBeLessThanOrEqual(390)
    expect(cell * 9).toBe(270)
  })

  it('가로 모바일은 셀 32px 로 12x9 를 도면 열 안에 넣는다', () => {
    const block = cutMedia('@media (max-width:1023px)')
    expect(block).toContain('--layout-mode:landscape')
    expect(block).toContain('--plan-cell:32px')
    expect(block).toContain('--bar-top:40px')
    expect(block).toContain('--col-sheet:340px')
    expect(block).toContain('--row-h:50px')
    // 844 에서 우측 시트 340 을 뺀 자리에 384x288 도면이 들어간다.
    const cell = 32
    expect(cell * 12 + 340).toBeLessThanOrEqual(844)
    expect(cell * 9 + 40 * 2).toBeLessThanOrEqual(390)
  })

  it('브레이크포인트는 토큰 한 곳에만 있다 — 화면 CSS 는 미디어쿼리를 적지 않는다', () => {
    expect(readStrippedCss('battle.css')).not.toContain('@media')
  })
})

describe('판정 라벨은 한 벌이다', () => {
  it('전투 화면에 라벨표가 따로 없다', () => {
    const source = readFileSync(`${BATTLE_DIR}BattleView.tsx`, 'utf8')
    expect(source).not.toContain('OUTCOME_LABELS')
    expect(source).toContain('formatOutcome')
  })

  it('쓰러짐을 쓴다 — 명세의 판정 표시가 정본이다', () => {
    expect(formatOutcome('PLAYER_LOSS')).toBe('쓰러짐')
    expect(formatOutcome('PLAYER_WIN')).toBe('승리')
    expect(formatOutcome('TIMEOUT')).toBe('시간 초과')
    expect(formatOutcome('ONGOING')).toBe('진행 중')
  })

  it('모르는 판정은 원문 그대로 낸다 — 조용히 빈 칸이 되지 않는다', () => {
    expect(formatOutcome('NOPE')).toBe('NOPE')
    expect(formatOutcomeNotice('NOPE')).toBe('NOPE')
  })

  it('판정 한 줄은 글리프와 다음에 할 일을 함께 적는다', () => {
    expect(formatOutcomeNotice('PLAYER_LOSS')).toBe('✕ 쓰러짐 · 규칙을 고쳐 다시')
    expect(formatOutcomeNotice('PLAYER_WIN')).toBe('✓ 방 클리어 · 다음 실로')
    expect(formatOutcomeNotice('ONGOING')).toBe('◆ 전투 중')
    expect(formatOutcomeNotice('TIMEOUT')).toBe('◈ 추격자 도착')
  })

  it('세 표가 같은 판정 집합을 덮는다', () => {
    const keys = [...OUTCOME_LABELS.keys()]
    expect([...OUTCOME_GLYPHS.keys()]).toEqual(keys)
    expect([...OUTCOME_NOTICES.keys()]).toEqual(keys)
  })

  it('진행 중에는 판정을 적지 않는다', () => {
    const html = renderToStaticMarkup(
      <BattleView setup={CHECK_SETUP} rulesets={G0_RULESETS} location="1층 · pillars" />,
    )
    expect(html).not.toContain('battle__outcome')
  })
})

describe('토큰을 다시 읽어도 같은 값이면 도면을 다시 그리지 않는다', () => {
  it('같은 값이면 참, 셀 크기가 달라지면 거짓', () => {
    expect(checkPlanThemeSame(FAKE_THEME, { ...FAKE_THEME })).toBe(true)
    expect(checkPlanThemeSame(FAKE_THEME, { ...FAKE_THEME, cell: 30 })).toBe(false)
    expect(checkPlanThemeSame(FAKE_THEME, { ...FAKE_THEME, surface: '#000' })).toBe(false)
  })

  it('아직 읽은 적이 없으면 거짓이다 — 첫 값은 반드시 들어간다', () => {
    expect(checkPlanThemeSame(undefined, FAKE_THEME)).toBe(false)
  })
})

describe('지속 몬스터 스냅샷 배선 (E4)', () => {
  const SETUP = { roomId: 'corridor', rulesetId: 'g0_pressure', seed: 7 }
  const SNAPSHOT = {
    entityId: 'goblin_rusher_0',
    recordId: 1,
    kindId: 'goblin_rusher',
    tier: 'ELITE',
    level: 7,
    hpMax: 96,
    attack: 17,
    defense: 5,
    ruleSlots: 4,
    cpuBudget: 7,
  }

  it('★ 조립이 스냅샷을 실제로 반영한다', () => {
    // **골든은 이것을 못 잡는다.** 골든은 코어 함수를 직접 부르므로 앱의 배선이 그
    // 경로 밖이고, 실제로 한 번 빠뜨려 화면과 서버가 다른 판을 돌 뻔했다.
    const plain = buildBattleSession(SETUP, G0_RULESETS)
    const withSnapshot = buildBattleSession({ ...SETUP, snapshots: [SNAPSHOT] }, G0_RULESETS)
    const before = plain.engine.state.entities.get('goblin_rusher_0')
    const after = withSnapshot.engine.state.entities.get('goblin_rusher_0')
    expect(before).toBeDefined()
    expect(after).toBeDefined()
    expect(after?.hpMax).toBe(SNAPSHOT.hpMax)
    expect(after?.attack).toBe(SNAPSHOT.attack)
    expect(after?.hpMax).not.toBe(before?.hpMax)
  })

  it('스냅샷이 없으면 방 배치 그대로다 — 로컬 티켓이 이 경우다', () => {
    const plain = buildBattleSession(SETUP, G0_RULESETS)
    const empty = buildBattleSession({ ...SETUP, snapshots: [] }, G0_RULESETS)
    expect(empty.engine.state.entities.get('goblin_rusher_0')?.hpMax).toBe(
      plain.engine.state.entities.get('goblin_rusher_0')?.hpMax,
    )
  })

  it('없는 자리를 겨냥한 스냅샷은 조용히 지나간다', () => {
    // entity_id 가 갈리면 아무에게도 적용되지 않는다. 조립이 죽으면 안 된다.
    const session = buildBattleSession(
      { ...SETUP, snapshots: [{ ...SNAPSHOT, entityId: 'nobody_9' }] },
      G0_RULESETS,
    )
    expect(session.engine.state.entities.get('goblin_rusher_0')?.hpMax).not.toBe(SNAPSHOT.hpMax)
  })

  it('기록도 같은 setup 을 쓰므로 함께 반영된다', () => {
    const recording = recordBattle({ ...SETUP, snapshots: [SNAPSHOT] }, G0_RULESETS)
    expect(recording.frames.length).toBeGreaterThan(0)
  })
})

describe('로드아웃 배선 (결정 #13)', () => {
  const SETUP = { roomId: 'corridor', rulesetId: 'g0_pressure', seed: 7 }
  const LOADOUT = {
    hpMax: 132,
    attack: 18,
    defense: 8,
    attackRange: 4,
    initiative: 56,
    cpuBudget: 11,
    ruleSlots: 6,
    skillPowerPct: 100,
    consumables: [],
    skills: ['ATTACK', 'SKILL_2'],
  }

  it('★ 조립이 로드아웃을 실제로 반영한다', () => {
    // 넘기지 않으면 화면은 맨몸으로 싸우고 서버는 장비를 낀 채로 재시뮬한다.
    // E4 에서 같은 자리를 한 번 빠뜨렸다.
    const plain = buildBattleSession(SETUP, G0_RULESETS)
    const geared = buildBattleSession({ ...SETUP, loadout: LOADOUT }, G0_RULESETS)
    const before = plain.engine.state.entities.get('player')
    const after = geared.engine.state.entities.get('player')
    expect(after?.hpMax).toBe(LOADOUT.hpMax)
    expect(after?.attackRange).toBe(LOADOUT.attackRange)
    expect(after?.hpMax).not.toBe(before?.hpMax)
  })

  it('★ 로드아웃이 장착 스킬을 정한다 — 미장착이면 「불가」가 실제로 뜬다', () => {
    const geared = buildBattleSession({ ...SETUP, loadout: LOADOUT }, G0_RULESETS)
    expect(geared.engine.state.entities.get('player')?.skills).toEqual(['ATTACK', 'SKILL_2'])
  })

  it('로드아웃이 없으면 기본 스탯이고 스킬 제한이 없다 — 오프라인 연습이 이 경우다', () => {
    const plain = buildBattleSession(SETUP, G0_RULESETS)
    expect(plain.engine.state.entities.get('player')?.skills).toBeNull()
  })
})


describe('적 등급 표기 (설계/6_몬스터 §1)', () => {
  it('★ 엘리트와 보스가 서로 다른 색을 받는다 — 같은 색이면 가른 것이 아니다', () => {
    const normal = resolveTierColor('NORMAL', FAKE_THEME)
    const elite = resolveTierColor('ELITE', FAKE_THEME)
    const boss = resolveTierColor('BOSS', FAKE_THEME)
    expect(new Set([normal, elite, boss]).size).toBe(3)
  })

  it('★ 모르는 등급은 일반으로 그린다 — 아무 색이나 주면 등급이 있는 것처럼 보인다', () => {
    expect(resolveTierColor('MYTHIC', FAKE_THEME)).toBe(FAKE_THEME.actorEnemy)
  })

  it('★ 아이템 등급과 같은 색을 쓴다 — 「한 단 위」가 화면 전체에서 한 뜻이어야 한다', () => {
    const css = readFileSync(`${DESIGN_DIR}tokens/colors.css`, 'utf8')
    expect(css).toContain('--plan-actor-elite:var(--grade-fine)')
    expect(css).toContain('--plan-actor-boss:var(--grade-relic)')
  })

  it('★ 등급이 개체에서 도면 장면까지 온다 — 중간에서 끊기면 색이 안 바뀐다', () => {
    // 정예가 실제로 서는 방을 쓴다. 밸런스에서 `tier` 를 읽어 개체에 싣고, 개체에서
    // 장면으로 옮기는 두 걸음 중 하나라도 빠지면 여기서 잡힌다.
    const session = buildBattleSession(
      { ...CHECK_SETUP, roomId: 'veteran_hall', extraEnemies: [] },
      G0_RULESETS,
    )
    const scene = buildPlanScene(session.engine)
    const tiers = scene.actors.filter((one) => !one.isSelf).map((one) => one.tier)
    expect(tiers).toContain('ELITE')
    expect(tiers).toContain('NORMAL')
  })
})
