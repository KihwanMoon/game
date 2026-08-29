/**
 * 사후 분석 집계가 파이썬과 같은 값을 내는가 (게이트 G3 의 연장).
 *
 * 대조 방식이 골든 리플레이와 다르다. 로그를 파일에 담아 비교하는 것이 아니라 **같은
 * 조합을 TS 코어로 다시 돌린 뒤 그 로그로 집계**해 파이썬의 집계와 맞춘다. 이렇게 하면
 * 두 가지가 한 번에 걸린다 — 전투가 갈렸는지, 집계가 갈렸는지. 앞이 어긋나면 뒤도 어긋
 * 나므로 실패 메시지의 순서(승패 → 틱 → 로그 수 → 피격 → 집계)가 곧 좁혀 가는 순서다.
 *
 * 기준 파일은 `__golden__/analysis.json` 이고 파이썬이 만든다. **손으로 고치지 마라** —
 * 값이 어긋나면 TS 쪽이 틀린 것이다. 재생성은
 * `uv run python -m scripts.export_analysis_golden`.
 */
import { describe, expect, it } from 'vitest'

import type { BattleSetup } from '../battle'
import { formatOutcome as battleFormatOutcome } from '../battle'
import { createLogEntry } from '../core/eventLog'
import type { LogEntry } from '../core/eventLog'
import { BLOCK_CATALOG, G0_RULESETS } from '../core/resources'
import { PHASE_ACT, PHASE_DECIDE, PHASE_TELEGRAPH, PHASE_UPKEEP } from '../core/sim/phases'

import golden from './__golden__/analysis.json'
import {
  buildDamageHeatmap,
  buildRuleStats,
  extractDamageHits,
  findHeatmapPeakCell,
  getWastePercent,
} from './analysis'
import type { DamageHit } from './analysis'
import {
  describeRuleStat,
  formatHeatValue,
  formatOutcome,
  formatTickLabel,
  getHeatLevel,
} from './analysisText'
import { recordBattle } from './battleRecorder'
import type { BattleRecording } from './battleRecorder'
import { filterRecentEntries, groupLogRows, selectLogWindow } from './logWindow'
import { buildReplayTrace, findDecision } from './replayTrace'

/** 기준 문서의 케이스 하나. */
interface GoldenCase {
  readonly case_id: string
  readonly room_id: string
  readonly ruleset_id: string
  readonly seed: number
  readonly extra_enemies: readonly { kind: string; x: number; y: number }[]
  readonly outcome: string
  readonly ticks: number
  readonly player_hp: number
  readonly width: number
  readonly height: number
  readonly log_count: number
  readonly rule_stats: Readonly<
    Record<string, readonly { label: string; fired: number; acted: number; wasted: number; waste_pct: number }[]>
  >
  readonly hits: readonly { tick: number; target_id: string; x: number; y: number; amount: number }[]
  readonly heatmap_player: readonly string[]
  readonly heatmap_all: readonly string[]
  readonly recent_ticks: number
  readonly recent_count: number
  readonly recent_first_tick: number | null
}

const CASES = golden.cases as readonly GoldenCase[]

/**
 * 기준 케이스를 전투 설정으로 바꾼다.
 *
 * @param one 기준 케이스.
 * @returns 같은 판을 내는 설정.
 */
function buildSetup(one: GoldenCase): BattleSetup {
  return {
    roomId: one.room_id,
    rulesetId: one.ruleset_id,
    seed: one.seed,
    extraEnemies: one.extra_enemies.map((extra) => ({ kind: extra.kind, x: extra.x, y: extra.y })),
  }
}

/**
 * 히트맵을 기준 문서와 같은 문자열 배열로 편다.
 *
 * @param grid buildDamageHeatmap 결과.
 * @returns 행마다 쉼표로 이은 문자열.
 */
function formatHeatmapRows(grid: readonly (readonly number[])[]): readonly string[] {
  return grid.map((row) => row.join(','))
}

/** 케이스마다 판을 한 번만 돌린다. 여섯 판을 테스트마다 다시 돌리면 느려진다. */
const RECORDINGS = new Map<string, BattleRecording>(
  CASES.map((one) => [one.case_id, recordBattle(buildSetup(one), G0_RULESETS)]),
)

/**
 * 그 케이스의 기록을 집는다.
 *
 * @param caseId 케이스 id.
 * @returns 기록.
 * @throws 돌려 두지 않은 케이스인 경우.
 */
function getRecording(caseId: string): BattleRecording {
  const recording = RECORDINGS.get(caseId)
  if (recording === undefined) {
    throw new Error(`돌려 두지 않은 케이스다: ${caseId}`)
  }
  return recording
}

describe('파이썬 대조 — 전투 자체', () => {
  it.each(CASES.map((one) => one.case_id))('%s 의 승패·틱·HP 가 같다', (caseId) => {
    const one = CASES.find((item) => item.case_id === caseId)
    expect(one).toBeDefined()
    const recording = getRecording(caseId)
    expect({
      outcome: recording.outcome,
      ticks: recording.ticks,
      playerHp: recording.playerHp,
      logCount: recording.entries.length,
    }).toEqual({
      outcome: one?.outcome,
      ticks: one?.ticks,
      playerHp: one?.player_hp,
      logCount: one?.log_count,
    })
  })
})

describe('파이썬 대조 — 규칙별 발동 횟수', () => {
  it.each(CASES.map((one) => one.case_id))('%s 의 성적표가 같다', (caseId) => {
    const one = CASES.find((item) => item.case_id === caseId)
    const recording = getRecording(caseId)
    for (const [entityId, expected] of Object.entries(one?.rule_stats ?? {})) {
      const actual = buildRuleStats(recording.entries, entityId).map((stat) => ({
        label: stat.label,
        fired: stat.fired,
        acted: stat.acted,
        wasted: stat.wasted,
        waste_pct: getWastePercent(stat),
      }))
      expect({ entityId, stats: actual }).toEqual({ entityId, stats: expected })
    }
  })
})

describe('파이썬 대조 — 피격 좌표와 히트맵', () => {
  it.each(CASES.map((one) => one.case_id))('%s 의 피격 기록이 같다', (caseId) => {
    const one = CASES.find((item) => item.case_id === caseId)
    const recording = getRecording(caseId)
    const rows = recording.hits.map((hit) => ({
      tick: hit.tick,
      target_id: hit.targetId,
      x: hit.position.x,
      y: hit.position.y,
      amount: hit.amount,
    }))
    expect(rows).toEqual(one?.hits)
  })

  it.each(CASES.map((one) => one.case_id))('%s 의 히트맵이 같다', (caseId) => {
    const one = CASES.find((item) => item.case_id === caseId)
    const recording = getRecording(caseId)
    const width = recording.template.width
    const height = recording.template.height
    expect(width).toBe(one?.width)
    expect(height).toBe(one?.height)
    expect(
      formatHeatmapRows(buildDamageHeatmap(recording.hits, width, height, recording.playerId)),
    ).toEqual(one?.heatmap_player)
    expect(formatHeatmapRows(buildDamageHeatmap(recording.hits, width, height))).toEqual(
      one?.heatmap_all,
    )
  })
})

describe('파이썬 대조 — 직전 15틱', () => {
  it.each(CASES.map((one) => one.case_id))('%s 의 되돌아본 구간이 같다', (caseId) => {
    const one = CASES.find((item) => item.case_id === caseId)
    const recording = getRecording(caseId)
    const recent = filterRecentEntries(recording.entries, one?.recent_ticks)
    expect(recent.length).toBe(one?.recent_count)
    expect(recent[0]?.tick ?? null).toBe(one?.recent_first_tick)
  })
})

describe('규칙 성적표의 계산', () => {
  /**
   * 로그 한 줄을 만든다.
   *
   * @param phase 페이즈.
   * @param rule 규칙 번호.
   * @param outcome 결과 문구.
   * @returns 로그 레코드.
   */
  function createRow(phase: string, rule: number | null, outcome: string): LogEntry {
    return createLogEntry({ tick: 1, entityId: 'player', phase, expr: '', outcome, rule })
  }

  it('DECIDE 는 발동으로, ACT 는 성공이나 헛돔으로 센다', () => {
    const stats = buildRuleStats(
      [
        createRow(PHASE_DECIDE, 1, 'MOVE'),
        createRow(PHASE_ACT, 1, '이동'),
        createRow(PHASE_DECIDE, 1, 'MOVE'),
        createRow(PHASE_ACT, 1, '사거리 밖 — 낭비'),
      ],
      'player',
    )
    expect(stats).toEqual([{ label: '[1]', fired: 2, acted: 1, wasted: 1 }])
    expect(getWastePercent(stats[0] as never)).toBe(50)
  })

  it('규칙 없이 나온 행동은 DEFAULT 로 묶여 맨 뒤에 온다', () => {
    const stats = buildRuleStats(
      [createRow(PHASE_DECIDE, null, 'MOVE'), createRow(PHASE_DECIDE, 2, 'MOVE')],
      'player',
    )
    expect(stats.map((stat) => stat.label)).toEqual(['[2]', 'DEFAULT'])
  })

  it('다른 엔티티의 줄은 세지 않는다', () => {
    const mine = createRow(PHASE_DECIDE, 1, 'MOVE')
    const other = createLogEntry({
      tick: 1,
      entityId: 'goblin_rusher_0',
      phase: PHASE_DECIDE,
      expr: '',
      outcome: 'MOVE',
      rule: 1,
    })
    expect(buildRuleStats([mine, other], 'player')).toEqual([
      { label: '[1]', fired: 1, acted: 0, wasted: 0 },
    ])
  })

  it('시도가 없으면 헛돔 비율은 0 이다 — 0 으로 나누지 않는다', () => {
    expect(getWastePercent({ label: '[1]', fired: 3, acted: 0, wasted: 0 })).toBe(0)
  })

  it('진단 문구가 파이썬의 분기 순서를 따른다', () => {
    expect(describeRuleStat({ label: '[1]', fired: 3, acted: 0, wasted: 0 })).toBe(
      '발동했지만 실행 단계에 도달하지 않음',
    )
    expect(describeRuleStat({ label: '[2]', fired: 4, acted: 1, wasted: 3 })).toBe(
      '시도의 75% 가 헛돎 — 조건을 의심할 것',
    )
    expect(describeRuleStat({ label: '[3]', fired: 0, acted: 0, wasted: 0 })).toBe(
      '한 번도 발동하지 않음 — 조건이 너무 좁다',
    )
    expect(describeRuleStat({ label: '[4]', fired: 5, acted: 5, wasted: 0 })).toBe('')
  })
})

describe('피격 좌표를 어느 시점에서 읽는가', () => {
  const start = new Map([['player', { x: 1, y: 1 }]])
  const end = new Map([['player', { x: 4, y: 4 }]])

  /**
   * 피해 한 줄을 만든다.
   *
   * @param phase 페이즈.
   * @returns 로그 레코드.
   */
  function createDamage(phase: string): LogEntry {
    return createLogEntry({
      tick: 3,
      entityId: 'lava',
      phase,
      expr: '',
      outcome: '피해',
      delta: -4,
      targetId: 'player',
    })
  }

  it('이동보다 앞선 페이즈는 틱 시작 좌표에서 맞은 것으로 센다', () => {
    for (const phase of [PHASE_UPKEEP, PHASE_TELEGRAPH]) {
      const hits = extractDamageHits([createDamage(phase)], start, end)
      expect(hits[0]?.position).toEqual({ x: 1, y: 1 })
      expect(hits[0]?.amount).toBe(4)
    }
  })

  it('그 뒤의 페이즈는 틱 종료 좌표를 쓴다', () => {
    expect(extractDamageHits([createDamage(PHASE_ACT)], start, end)[0]?.position).toEqual({
      x: 4,
      y: 4,
    })
  })

  it('그 틱에 등장한 개체는 시작 표에 없으므로 종료 좌표로 대신한다', () => {
    const summoned = createLogEntry({
      tick: 3,
      entityId: 'arch_summoner_0',
      phase: PHASE_UPKEEP,
      expr: '',
      outcome: '피해',
      delta: -2,
      targetId: 'slime_4',
    })
    const late = new Map([['slime_4', { x: 7, y: 2 }]])
    expect(extractDamageHits([summoned], new Map(), late)[0]?.position).toEqual({ x: 7, y: 2 })
  })

  it('회복과 피해 아닌 줄은 세지 않는다', () => {
    const heal = createLogEntry({
      tick: 3,
      entityId: 'spring',
      phase: PHASE_UPKEEP,
      expr: '',
      outcome: '회복',
      delta: 2,
      targetId: 'player',
    })
    const decided = createLogEntry({
      tick: 3,
      entityId: 'player',
      phase: PHASE_DECIDE,
      expr: '',
      outcome: 'MOVE',
    })
    expect(extractDamageHits([heal, decided], start, end)).toEqual([])
  })

  it('방 밖 좌표는 히트맵에서 버린다', () => {
    const outside: DamageHit = { tick: 1, targetId: 'player', position: { x: 99, y: 0 }, amount: 5 }
    const inside: DamageHit = { tick: 1, targetId: 'player', position: { x: 1, y: 1 }, amount: 5 }
    const grid = buildDamageHeatmap([outside, inside], 3, 3)
    expect(formatHeatmapRows(grid)).toEqual(['0,0,0', '0,5,0', '0,0,0'])
  })

  it('최다 피격 칸은 같은 값이 여럿이면 행 우선으로 먼저 나온 칸이다', () => {
    const grid = [
      [0, 3],
      [3, 0],
    ]
    expect(findHeatmapPeakCell(grid)).toEqual({ position: { x: 1, y: 0 }, amount: 3 })
    expect(findHeatmapPeakCell([[0, 0]])).toBeUndefined()
  })

  it('강도는 정수 단계이고 피해가 있으면 최소 1 이다 — 색만으로 읽게 하지 않는다', () => {
    expect(getHeatLevel(0, 100)).toBe(0)
    expect(getHeatLevel(1, 100)).toBe(1)
    expect(getHeatLevel(100, 100)).toBe(4)
    expect(formatHeatValue(0)).toBe('·')
    expect(formatHeatValue(7)).toBe('7')
  })
})

describe('로그 창 고르기', () => {
  const rows: readonly LogEntry[] = Array.from({ length: 10 }, (_, index) =>
    createLogEntry({
      tick: Math.floor(index / 2) + 1,
      entityId: index % 2 === 0 ? 'player' : 'goblin_rusher_0',
      phase: PHASE_DECIDE,
      expr: '',
      outcome: 'MOVE',
    }),
  )

  it('기준이 없으면 꼬리를 보여 준다', () => {
    const view = selectLogWindow(rows, { maxRows: 4 })
    expect(view.startIndex).toBe(6)
    expect(view.hiddenBefore).toBe(6)
    expect(view.hiddenAfter).toBe(0)
  })

  it('기준을 주면 그 줄부터 보여 주고 꼬리를 넘지 않는다', () => {
    expect(selectLogWindow(rows, { maxRows: 4, anchorIndex: 2 }).startIndex).toBe(2)
    expect(selectLogWindow(rows, { maxRows: 4, anchorIndex: 9 }).startIndex).toBe(6)
    expect(selectLogWindow(rows, { maxRows: 4, anchorIndex: -3 }).startIndex).toBe(0)
  })

  it('틱으로 묶고 틱 안에서는 같은 엔티티의 연속 구간으로 다시 묶는다', () => {
    const groups = groupLogRows(rows)
    expect(groups.map((group) => group.tick)).toEqual([1, 2, 3, 4, 5])
    expect(groups[0]?.count).toBe(2)
    expect(groups[0]?.runs.map((run) => run.entityId)).toEqual(['player', 'goblin_rusher_0'])
  })

  it('빈 로그는 묶음도 창도 비어 있다', () => {
    expect(groupLogRows([])).toEqual([])
    expect(selectLogWindow([], { maxRows: 4 }).rows).toEqual([])
    expect(filterRecentEntries([], 15)).toEqual([])
  })

  it('틱 표기는 자릿수를 채운다 — 컬럼이 어긋나면 눈이 세로로 훑지 못한다', () => {
    expect(formatTickLabel(7)).toBe('T007')
    expect(formatTickLabel(120)).toBe('T120')
  })
})

describe('되감기용 규칙표 상태', () => {
  const ruleset = G0_RULESETS.get('g0_kite')

  it('발동한 줄 위는 거짓, 아래는 평가 대기다 — 둘을 구분하는 것이 핵심이다', () => {
    expect(ruleset).toBeDefined()
    const recording = getRecording('corridor__g0_kite__12345')
    const decision = recording.entries.find(
      (entry) => entry.phase === PHASE_DECIDE && entry.entityId === 'player' && entry.rule !== null,
    )
    expect(decision).toBeDefined()
    const rows = buildReplayTrace(recording.ruleset, BLOCK_CATALOG, decision)
    const firedIndex = rows.findIndex((row) => row.armed)
    expect(firedIndex).toBeGreaterThanOrEqual(0)
    expect(rows.slice(0, firedIndex).every((row) => row.state === 'false')).toBe(true)
    expect(rows[firedIndex]?.state).toBe('true')
    expect(rows.slice(firedIndex + 1).every((row) => row.state === 'pending')).toBe(true)
  })

  it('발동한 줄만 실측값이 병기된 조건문을 받는다', () => {
    const recording = getRecording('corridor__g0_kite__12345')
    const decision = recording.entries.find(
      (entry) => entry.phase === PHASE_DECIDE && entry.entityId === 'player' && entry.rule !== null,
    )
    const rows = buildReplayTrace(recording.ruleset, BLOCK_CATALOG, decision)
    expect(rows.find((row) => row.armed)?.condition).toBe(decision?.expr)
  })

  it('그 틱에 결정이 없으면 전 줄이 평가 대기다', () => {
    const recording = getRecording('corridor__g0_kite__12345')
    const rows = buildReplayTrace(recording.ruleset, BLOCK_CATALOG, undefined)
    expect(rows.every((row) => row.state === 'pending')).toBe(true)
    expect(rows.every((row) => !row.armed)).toBe(true)
  })

  it('그 틱의 결정 한 줄을 엔티티별로 찾는다', () => {
    const recording = getRecording('corridor__g0_kite__12345')
    const found = findDecision(recording.entries, 1, recording.playerId)
    expect(found?.tick).toBe(1)
    expect(found?.entityId).toBe(recording.playerId)
    expect(findDecision(recording.entries, 0, recording.playerId)).toBeUndefined()
  })
})

describe('기록의 모양', () => {
  it('프레임은 틱 수보다 하나 많다 — 첫 원소가 첫 틱 이전이다', () => {
    const recording = getRecording('open_field__g0_pressure__1')
    expect(recording.frames).toHaveLength(recording.ticks + 1)
    expect(recording.frames[0]?.tick).toBe(0)
    expect(recording.frames.at(-1)?.tick).toBe(recording.ticks)
  })

  it('프레임의 로그 구간이 빈틈없이 이어진다', () => {
    const recording = getRecording('hazard_field__g0_cover__99')
    let cursor = 0
    for (const frame of recording.frames.slice(1)) {
      expect(frame.logStart).toBe(cursor)
      cursor = frame.logEnd
    }
    expect(cursor).toBe(recording.entries.length)
  })

  it('같은 조합을 두 번 돌리면 같은 프레임이 나온다 (R5)', () => {
    const setup: BattleSetup = { roomId: 'corridor', rulesetId: 'g0_kite', seed: 12345 }
    const first = recordBattle(setup, G0_RULESETS)
    const second = recordBattle(setup, G0_RULESETS)
    expect(second.entries).toEqual(first.entries)
    expect(second.hits).toEqual(first.hits)
    expect(second.frames.map((frame) => frame.scene)).toEqual(
      first.frames.map((frame) => frame.scene),
    )
  })
})

describe('사후 분석과 전투 화면이 같은 판정 문구를 쓴다', () => {
  it('두 화면의 formatOutcome 이 같은 함수다 — 라벨표가 한 벌이라는 뜻이다', () => {
    expect(formatOutcome).toBe(battleFormatOutcome)
  })

  it('사후 분석도 쓰러짐이라 적는다', () => {
    expect(formatOutcome('PLAYER_LOSS')).toBe('쓰러짐')
  })
})
