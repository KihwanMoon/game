/**
 * 앱 조립 검사 (W13, M3).
 *
 * 두 가지를 지킨다.
 *
 * 1. **첫 화면이 규칙 에디터이고 거기서 출격할 수 있다.** M3 의 정의가 "JSON 없이
 *    플레이 가능" 이므로, 앱을 열었을 때 규칙표와 출격 버튼이 함께 보이지 않으면 그
 *    정의가 깨진다.
 * 2. **관전한 판과 사후 분석이 보는 판이 같다.** 앱은 관전 중에는 엔진을 앞으로 밀고,
 *    판이 끝나면 같은 setup 을 한 번 더 돌려 되감기용 기록을 만든다. 그 두 실행이
 *    같다는 것이 이 설계의 유일한 전제이며, 여기서 배속(한 번에 4틱)까지 바꿔 가며
 *    같은지 확인한다 (R5).
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { App, buildInitialRuleSet, describeRunResult, findLaunchBlocker, formatLocation, readPlayerLimits } from './App'
import { buildBattleSession, checkOngoing, type BattleSetup } from './battle'
import { BALANCE, BLOCK_CATALOG } from './core/resources'
import type { LogEntry } from './core/eventLog'
import { validateRuleSet } from './core/rules/validator'
import { runTickBatch } from './core/services/runSteppedBattle'
import { OUTCOME_ONGOING } from './core/sim/phases'
import { formatCrash } from './ErrorBoundary'
import { recordBattle } from './hud'

/** 관전 배속 4x 에 해당한다. 한 번에 4틱을 돌린다. */
const WATCH_BATCH = 4

/** 무한 루프 방지. 400틱 상한이라 이 안에서 반드시 끝난다. */
const BATCH_LIMIT = 500

/**
 * 한 판을 관전 화면처럼(배치 단위로) 끝까지 돌린다.
 *
 * @param setup 방·규칙표·시드.
 * @returns 판정·틱·로그.
 */
function runAsWatched(setup: BattleSetup): {
  outcome: string
  ticks: number
  entries: readonly LogEntry[]
} {
  const rulesets = new Map([[setup.rulesetId, buildInitialRuleSet()]])
  const session = buildBattleSession(setup, rulesets)
  let outcome = OUTCOME_ONGOING
  for (let step = 0; step < BATCH_LIMIT && checkOngoing(outcome); step += 1) {
    outcome = runTickBatch(session.engine, WATCH_BATCH).outcome
  }
  return { outcome, ticks: session.engine.state.tick, entries: session.engine.log.entries }
}

describe('첫 화면', () => {
  const markup = renderToStaticMarkup(<App />)

  it('규칙 에디터가 먼저 뜬다', () => {
    expect(markup).toContain('규칙 에디터')
    expect(markup).toContain('우선순위 리스트')
  })

  it('출격 조작부가 상단 바에 붙는다', () => {
    expect(markup).toContain('출격')
    expect(markup).toContain('launch__field')
    expect(markup).toContain('id="launch-seed"')
  })

  it('처음 실린 규칙표는 검증을 통과하므로 출격 버튼이 잠기지 않는다', () => {
    const limits = readPlayerLimits(BALANCE)
    const problems = validateRuleSet(
      buildInitialRuleSet(),
      BLOCK_CATALOG,
      limits.cpuBudget,
      limits.ruleSlots,
    )
    expect(problems).toEqual([])
    expect(findLaunchBlocker(problems)).toBe('')
  })

  it('사후 분석은 판이 끝나기 전에는 그려지지 않는다', () => {
    expect(markup).not.toContain('사후 분석')
  })

  it('코드 라이브러리가 팔레트 아래에 함께 뜬다 — 짠 것을 둘 곳이 화면에 있다', () => {
    expect(markup).toContain('코드 라이브러리')
    expect(markup).toContain('id="library-name"')
    expect(markup).toContain('id="library-code"')
  })

  it('되돌리기 조작이 상단 바에 있고, 되돌릴 것이 없으면 잠겨 있다', () => {
    expect(markup).toContain('되돌리기 (Ctrl+Z)')
    expect(markup).toContain('다시 실행 (Ctrl+Shift+Z)')
    expect(markup).toContain('disabled="" title="되돌리기 (Ctrl+Z)"')
  })
})

describe('출격 차단', () => {
  it('첫 번째 위반을 그대로 버튼에 적는다', () => {
    expect(findLaunchBlocker(['CPU 9 가 예산 8 을 넘는다', '다른 것'])).toBe(
      'CPU 9 가 예산 8 을 넘는다',
    )
  })
})

describe('표기', () => {
  it('층과 방을 함께 적는다', () => {
    expect(formatLocation('open_field')).toBe('1층 · open_field')
  })

  it('직전 판이 없으면 아무것도 적지 않는다', () => {
    expect(describeRunResult(undefined)).toBe('')
  })

  it('직전 판은 판정·틱·HP 를 함께 적는다', () => {
    const text = describeRunResult({ outcome: 'PLAYER_LOSS', ticks: 37, playerHp: 0 })
    expect(text).toContain('37틱')
    expect(text).toContain('HP 0')
  })

  it('Error 가 아닌 던짐도 문구로 만든다', () => {
    expect(formatCrash(new Error('없는 방 id 다: nope'))).toBe('없는 방 id 다: nope')
    expect(formatCrash('맨 문자열')).toBe('맨 문자열')
  })
})

describe('관전한 판과 사후 분석이 보는 판이 같다', () => {
  const setup: BattleSetup = { roomId: 'open_field', rulesetId: 'g0_pressure', seed: 1 }
  const rulesets = new Map([[setup.rulesetId, buildInitialRuleSet()]])

  it('같은 setup 을 두 번 돌리면 로그가 줄 단위로 같다', () => {
    const first = recordBattle(setup, rulesets)
    const second = recordBattle(setup, rulesets)
    expect(second.outcome).toBe(first.outcome)
    expect(second.ticks).toBe(first.ticks)
    expect(second.playerHp).toBe(first.playerHp)
    expect(second.entries).toEqual(first.entries)
  })

  it('배속을 4x 로 몰아 돌려도 한 틱씩 돌린 기록과 같다', () => {
    const watched = runAsWatched(setup)
    const recorded = recordBattle(setup, rulesets)
    expect(watched.outcome).toBe(recorded.outcome)
    expect(watched.ticks).toBe(recorded.ticks)
    expect(watched.entries).toEqual(recorded.entries)
  })

  it('기록은 틱마다 한 장씩 남는다 — 되감기가 그 위를 걷는다', () => {
    const recorded = recordBattle(setup, rulesets)
    expect(recorded.frames).toHaveLength(recorded.ticks + 1)
    expect(recorded.frames[0]?.tick).toBe(0)
  })
})
