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
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { App, buildInitialRuleSet, checkRunOver, buildChainPosition, buildNextRoomSetup, buildRunSetup, resolvePlayerLimits, describeRunResult, findLaunchBlocker, formatLocation, readPlayerLimits } from './App'
import { buildBattleSession, checkOngoing, resolveRoomFloor, type BattleSetup } from './battle'
import { BALANCE, BLOCK_CATALOG, G0_RULESETS } from './core/resources'
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

  it('코드 라이브러리는 「서고」 탭에 있다 — 짠 것을 둘 곳이 화면에 있다', () => {
    // 서랍은 한 번에 하나만 세우므로 첫 화면 마크업에는 탭 이름만 있다. 내용이 실제로
    // 그려지는지는 아래 서랍 검사가 본다.
    expect(markup).toContain('>서고<')
  })

  it('★ 곁다리 패널이 서랍으로 갈려 있다 — 아홉을 쌓으면 규칙 에디터에 닿지 못한다', () => {
    // 쌓기를 그만둔 이유는 두 가지다. 높이가 안 나와 아래쪽이 하단 바를 뚫고 나갔고,
    // 규칙 에디터에 닿기 전에 스크롤을 아홉 번 지나야 했다.
    expect(markup).toContain('서랍')
    for (const label of ['나', '가방', '세계', '배움', '서고']) {
      expect(markup).toContain(`>${label}<`)
    }
  })

  it('★ 관리 탭은 관리자에게만 생긴다 — 빈 탭도 경로의 존재를 알려 준다', () => {
    expect(markup).not.toContain('>관리<')
  })

  it('처음 열려 있는 서랍이 자기 내용을 보여준다 — 빈 패널은 고장으로 읽힌다', () => {
    // 첫 칸은 「나」다. 계정과 캐릭터가 거기 있다.
    expect(markup).toContain('캐릭터')
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

describe('티켓 → 전투 조립 (E4, 결정 #13)', () => {
  const ISSUED = {
    ticketId: 't1',
    seed: 42,
    roomId: 'corridor',
    floor: 1,
    roomsPerFloor: 3,
    coreVersion: 'b5.v2.e1',
    mode: 'PRACTICE' as const,
    roomIds: ['corridor', 'corridor', 'corridor'],
    snapshots: [
      {
        entityId: 'goblin_archer_1',
        recordId: 2,
        kindId: 'goblin_archer',
        tier: 'BOSS' as const,
        level: 12,
        hpMax: 140,
        attack: 24,
        defense: 9,
        ruleSlots: 6,
        cpuBudget: 10,
      },
    ],
    loadout: {
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
    },
  }

  it('★ 스냅샷을 흘리지 않는다 — E4 에서 실제로 여기서 샜다', () => {
    expect(buildRunSetup(ISSUED, 'g0_pressure').snapshots).toEqual(ISSUED.snapshots)
  })

  it('★ 로드아웃을 흘리지 않는다', () => {
    // 흘리면 화면은 맨몸으로 싸우고 서버는 장비를 낀 채로 재시뮬한다 —
    // 정상적으로 이긴 판이 전부 불일치로 반려된다.
    expect(buildRunSetup(ISSUED, 'g0_pressure').loadout).toEqual(ISSUED.loadout)
  })

  it('규칙표는 티켓이 아니라 기기가 정한다', () => {
    expect(buildRunSetup(ISSUED, 'g0_pressure').rulesetId).toBe('g0_pressure')
    expect(buildRunSetup(ISSUED, 'g0_range').rulesetId).toBe('g0_range')
  })

  it('로드아웃 없는 티켓은 필드 자체가 없다 — 구버전 서버가 이 경우다', () => {
    const { loadout: _omitted, ...bare } = ISSUED
    expect(buildRunSetup({ ...bare, loadout: undefined }, 'g0_pressure').loadout).toBeUndefined()
  })
})

describe('규칙 한도 (결정 #51, #13)', () => {
  const BASE = { cpuBudget: 8, ruleSlots: 5 }
  const PROGRESS = {
    level: 9,
    totalXp: 0,
    remainingXp: 0,
    nextXp: 1,
    stats: {},
    statKeys: [],
    statPoints: 0,
    spentPoints: 0,
    bonusRuleSlots: 1,
    bonusCpu: 3,
    reachedFloor: 1,
    floorCap: 10,
  }

  it('★ 서버가 아는 한도를 쓴다 — 성장이 에디터에 닿는 유일한 경로다', () => {
    // 기본값으로 두면 늘어난 CPU 가 에디터에 안 보이고, 서버는 로드아웃 한도로
    // 검증하므로 화면에서 통과한 규칙표가 제출에서 반려된다.
    const limits = resolvePlayerLimits(BASE, {
      ...PROGRESS,
      loadout: {
        hpMax: 100,
        attack: 12,
        defense: 5,
        attackRange: 1,
        initiative: 50,
        cpuBudget: 12,
        ruleSlots: 7,
        skillPowerPct: 100,
        consumables: [],
        skills: ['ATTACK'],
      },
    })
    expect(limits.cpuBudget).toBe(12)
    expect(limits.ruleSlots).toBe(7)
  })

  it('서버에 못 닿으면 기본값으로 선다 — 오프라인 연습이 이 경우다', () => {
    expect(resolvePlayerLimits(BASE, undefined)).toEqual(BASE)
    expect(resolvePlayerLimits(BASE, { ...PROGRESS, loadout: undefined })).toEqual(BASE)
  })
})

describe('층 사슬 진행 (W3)', () => {
  const SETUP: BattleSetup = {
    roomId: 'corridor',
    rulesetId: 'g0_kite',
    seed: 4242,
    chain: buildChainPosition('corridor'),
  }

  it('★ 이기면 다음 방으로 넘어간다 — 이게 없으면 한 판이 방 하나로 끝난다', () => {
    const next = buildNextRoomSetup(SETUP, 'PLAYER_WIN')
    expect(next?.chain?.index).toBe(1)
    expect(next?.seed).toBe(SETUP.seed)
  })

  it('★ 지면 넘어가지 않는다 — 죽은 캐릭터가 다음 방을 돌면 안 된다', () => {
    expect(buildNextRoomSetup(SETUP, 'PLAYER_LOSS')).toBeUndefined()
  })

  it('★ 마지막 방을 이기면 거기서 끝이다', () => {
    const last = { ...SETUP, chain: { roomIds: ['corridor', 'corridor'], index: 1 } }
    expect(buildNextRoomSetup(last, 'PLAYER_WIN')).toBeUndefined()
  })

  it('★ HP 를 setup 에 적어 나르지 않는다 — 적으면 손으로 고쳐 강한 판을 만든다', () => {
    // 인계는 ChainCursor 가 앞 방을 다시 돌려 계산한다. 그래야 "같은 setup 이면 같은
    // 판"(R5)이 유지되고 사후 분석이 관전한 것과 같은 판을 본다.
    const next = buildNextRoomSetup(SETUP, 'PLAYER_WIN')
    expect(JSON.stringify(next)).not.toMatch(/hp/i)
  })

  it('★ 연쇄가 실제로 체력을 이어 받는다 — 조립까지 닿는지 본다', () => {
    const first = buildBattleSession(SETUP, G0_RULESETS)
    const second = buildBattleSession(
      buildNextRoomSetup(SETUP, 'PLAYER_WIN') as BattleSetup,
      G0_RULESETS,
    )
    const before = first.engine.state.entities.get('player')
    const after = second.engine.state.entities.get('player')
    expect(after?.hp).toBeLessThan(before?.hp ?? 0)
  })

  it('연쇄가 없는 판은 넘어갈 곳이 없다 — 부품 확인 페이지가 이 경우다', () => {
    const bare: BattleSetup = { roomId: 'corridor', rulesetId: 'g0_kite', seed: 1 }
    expect(buildNextRoomSetup(bare, 'PLAYER_WIN')).toBeUndefined()
  })
})

describe('서버가 정한 방 목록 (W3)', () => {
  it('★ 티켓의 방 목록을 그대로 쓴다 — 기기가 정하면 서버가 다른 방을 재시뮬한다', () => {
    const setup = buildRunSetup(
      {
        ticketId: 't9',
        seed: 1,
        roomId: 'corridor',
        floor: 1,
        roomsPerFloor: 3,
        coreVersion: 'x',
        mode: 'PRACTICE',
        snapshots: [],
        loadout: undefined,
        roomIds: ['corridor', 'pillars', 'open_field'],
      },
      'g0_kite',
    )
    expect(setup.chain?.roomIds).toEqual(['corridor', 'pillars', 'open_field'])
    expect(setup.chain?.index).toBe(0)
  })
})

describe('계정이 바뀌면 화면도 바뀐다', () => {
  it('★ **로그인이 계정 상태를 다시 읽는다**', () => {
    // 안 읽으면 다른 기기에서 로그인했을 때 화면이 익명 계정의 값을 계속 보여준다 —
    // 레벨과 CPU 가 사라진 것처럼 보인다. 서버에는 그대로 있고 화면만 낡은 것이다.
    const source = readFileSync(fileURLToPath(new URL('./App.tsx', import.meta.url)), 'utf8')
    const login = source.slice(source.indexOf('async function applyLogin'))
    expect(login.slice(0, login.indexOf("return ''"))).toContain('loadAccountState')
  })

  it('★ 승격도 다시 읽는다 — 토큰이 바뀌면 그 뒤 조회가 옛 토큰을 쓴다', () => {
    const source = readFileSync(fileURLToPath(new URL('./App.tsx', import.meta.url)), 'utf8')
    const register = source.slice(source.indexOf('async function applyRegister'))
    expect(register.slice(0, register.indexOf("return ''"))).toContain('loadAccountState')
  })

  it('★ 한 자리에서 읽는다 — 갈라 두면 한쪽만 고치고 끝난다', () => {
    // 실제로 그렇게 됐다. 첫 접속만 읽고 로그인은 안 읽는 상태로 배포됐다.
    const source = readFileSync(fileURLToPath(new URL('./App.tsx', import.meta.url)), 'utf8')
    const loader = source.slice(source.indexOf('async function loadAccountState'))
    const body = loader.slice(0, loader.indexOf('\n  }'))
    for (const call of ['readProgress', 'readInventory', 'readBestiary', 'readAdminOverview']) {
      expect(body).toContain(call)
    }
  })
})


describe('연속 하강 (로드맵 W14)', () => {
  it('★ 층을 다 깨도 갈 방이 남았으면 런이 안 끝난다 — 정산하면 티켓이 소비돼 못 이어간다', () => {
    const next = { roomId: 'corridor', rulesetId: 'x', seed: 1 }
    expect(checkRunOver('PLAYER_WIN', next)).toBe(false)
  })

  it('★ 갈 방이 없으면 끝난다 — 하강의 마지막이다', () => {
    expect(checkRunOver('PLAYER_WIN', undefined)).toBe(true)
  })

  it('★ 지면 끝난다 — 다음 방이 남아 있어도 죽었으면 런이다', () => {
    const next = { roomId: 'corridor', rulesetId: 'x', seed: 1 }
    expect(checkRunOver('ENEMY_WIN', next)).toBe(true)
  })

  it('★ 방 순번에서 층을 판다 — 파이썬과 같은 식이어야 한다 (G3)', () => {
    expect(resolveRoomFloor(1, 0, 3)).toBe(1)
    expect(resolveRoomFloor(1, 2, 3)).toBe(1)
    expect(resolveRoomFloor(1, 3, 3)).toBe(2)
    expect(resolveRoomFloor(1, 29, 3)).toBe(10)
  })

  it('★ 층당 방 수가 0 이면 전체가 한 층이다 — 구버전 티켓이 그 길로 온다', () => {
    expect(resolveRoomFloor(4, 7, 0)).toBe(4)
  })
})
