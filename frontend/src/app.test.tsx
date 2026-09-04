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

import { App, CHAIN_LENGTH, LOCAL_FLOOR_CAP, buildInitialRuleSet, checkFloorCleared, checkLaunchLocked, checkRunOver, formatLaunchLabel, buildChainPosition, buildNextRoomSetup, buildRunSetup, resolvePlayerLimits, describeRunResult, findLaunchBlocker, formatLocation, readPlayerLimits } from './App'
import { buildBattleSession, checkOngoing, resolveRoomFloor, type BattleSetup } from './battle'
import { checkShouldAutoAdvance, OFFLINE_PREFIX } from './editor'
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

  // **첫 페인트가 경보를 띄우면 안 된다.** 앱은 서버에 붙어 보기도 전에
  // 「서버에 닿지 못했다」를 ◈ 위험으로 적고 가입·로그인을 잠그고 있었다. 매번 뜨는
  // 경보는 곧 아무도 안 읽는 경보가 되고, 진짜로 서버가 죽은 날 그 줄은 배경이 된다.
  it('★ 서버에 물어보기 전에는 경보를 띄우지 않는다', () => {
    expect(markup).not.toContain('ds-glyph--danger')
    expect(markup).not.toContain(OFFLINE_PREFIX)
    // 「물어보는 중」 문구 자체는 패널의 것이라 `characterRender` 가 지킨다. 예전에는
    // 서랍의 첫 칸이 늘 열려 있어 여기서도 보였는데, 그것은 설계가 아니라 우연이었다 —
    // 서랍을 다른 탭으로 옮겨 두면 그때도 안 보였다.
  })

  it('출격 조작부가 상단 바에 붙는다', () => {
    expect(markup).toContain('출격')
    expect(markup).toContain('launch__field')
  })

  it('★ 방 고르개가 줄어들 수 있는 클래스를 단다 — 없으면 가장 긴 option 만큼 벌어진다', () => {
    // `select` 는 가장 긴 option 만큼 폭을 잡는다. 방 라벨이 「open_field · 엄폐가 없어
    // 포위가 성립한다」 처럼 길어서, 이 하나가 좁은 화면의 폭을 넘겼다.
    expect(markup).toContain('launch__field--room')
  })

  it('★ 시드 칸이 처음에는 숫자가 아니다 — 기본은 판마다 새 시드다', () => {
    // 숫자 칸이 처음부터 보이면 그 수로 도는 줄 알고, 실제로 늘 1번 판만 돌았다.
    expect(markup).not.toContain('id="launch-seed"')
    expect(markup).toContain('판마다 새로')
    expect(markup).toContain('고정')
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

  it('★ 규칙표와 곁다리가 한 탭 줄에 동위로 선다', () => {
    // 예전에는 탭 줄이 둘이었다 — 규칙표 탭(전투·정비)이 상단 바에 있고, 곁다리는
    // 「서랍」이라는 또 하나의 탭 줄 안에 갇혀 있었다. 가방에 가려면 어느 탭 안의 어느
    // 탭인지를 외워야 했고, 두 줄이 서로 다른 것을 뜻한다는 근거도 없었다.
    expect(markup).not.toContain('>서랍<')
    expect(markup).toContain('editor__tabs')
    // 묶음은 「무엇에 대한 것인가」로 가른다. 「나」가 「캐릭터」가 되고 스킬이 가방에서
    // 갈라진 것은, 레벨·능력치가 세계에서 이쪽으로 오면서 탭의 뜻이 분명해져서다.
    for (const label of ['전투 규칙', '정비 규칙', '캐릭터', '가방', '스킬', '경매', '세계', '배움']) {
      expect(markup).toContain(`>${label}<`)
    }
  })

  it('★ 탭 줄이 출격 조작부보다 아래에 선다 — 접히면 출격이 밀린다', () => {
    // 탭이 여덟이라 좁은 폭에서 두세 줄로 접힌다. 그것이 위에 있으면 이 화면에서 가장
    // 자주 누르는 출격 버튼이 그만큼 아래로 밀린다.
    expect(markup.indexOf('launch__field')).toBeLessThan(markup.indexOf('editor__tabs'))
  })

  it('★ 처음 열리는 것은 전투 규칙이다 — 이 게임의 규칙표는 전투가 중심이다', () => {
    expect(markup).toContain('우선순위 리스트')
    // 안 열린 탭의 내용은 안 그려진다 — 그려지면 탭이 갈린 뜻이 없다.
    expect(markup).not.toContain('>성장<')
    expect(markup).not.toContain('장비와 가방')
  })

  it('★ 코드 라이브러리는 규칙을 고치는 열에 있다', () => {
    // 이 슬롯이 원래 그것을 위해 만들어졌는데(RuleEditor 의 `library` 주석) 곁다리 탭
    // 하나로 들어가 있었다. 규칙표를 저장하고 불러오는 일은 탭을 고르는 일이 아니라
    // 편집의 일부다.
    expect(markup).toContain('코드 라이브러리')
    expect(markup).not.toContain('>서고<')
    expect(markup.slice(markup.indexOf('editor__col--palette'))).toContain('코드 라이브러리')
  })

  it('★ 관리 탭은 관리자에게만 생긴다 — 빈 탭도 경로의 존재를 알려 준다', () => {
    expect(markup).not.toContain('>관리<')
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
  it('★ 층과 방을 함께 적는다 — **층이 박혀 있었다**', () => {
    // 하강이 층을 넘어가는데 머리글은 늘 `1층` 이라고 적었다 — 화면에서 가장 크게
    // 적히는 자리가 거짓말을 하고 있었다.
    expect(formatLocation(4, 'open_field')).toBe('4층 · open_field')
    expect(formatLocation(1, 'corridor')).toBe('1층 · corridor')
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
        zoneFloor: 1,
        attackRange: 0,
        skills: [],
        potions: -1,
        ruleset: null,
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
    // 스킬 v3(쿨타임 2배) 뒤 g0_kite 는 corridor 1방을 무피해로 깨서 인계가 안
    // 보인다 — 깨면서 다치는 (g0_pressure, open_field, 4242) 로 갈았다. 연쇄 골든과
    // 같은 표본이다.
    roomId: 'open_field',
    rulesetId: 'g0_pressure',
    seed: 4242,
    chain: buildChainPosition('open_field'),
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
    // `readBagState` 는 가방과 소모품 칸을 함께 읽는 하나뿐인 문이다. 여기서 가방만
    // 읽던 시절에 소모품 칸이 영원히 「서버에 닿지 못했다」로 굳어 있었다.
    for (const call of ['readProgress', 'readBagState', 'readBestiary', 'readAdminOverview']) {
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


describe('하강하며 층이 오른다', () => {
  it('★ 네 번째 방부터 2층이다 — 안 오르면 화면이 계속 1층이라고 말한다', () => {
    const ticket = {
      ticketId: 't', seed: 1, roomId: 'open_field', floor: 1, roomsPerFloor: 3,
      coreVersion: 'x', mode: 'PRACTICE',
      roomIds: ['a', 'b', 'c', 'd', 'e', 'f'],
      snapshots: [],
      loadout: undefined,
    }
    let setup = buildRunSetup(ticket, 'r')
    const floors = [resolveRoomFloor(setup.floor ?? 1, setup.chain?.index ?? 0, setup.roomsPerFloor ?? 0)]
    for (let step = 0; step < 5; step += 1) {
      const next = buildNextRoomSetup(setup, 'PLAYER_WIN')
      if (next === undefined) {
        break
      }
      setup = next
      floors.push(
        resolveRoomFloor(setup.floor ?? 1, setup.chain?.index ?? 0, setup.roomsPerFloor ?? 0),
      )
    }
    expect(floors).toEqual([1, 1, 1, 2, 2, 2])
  })
})


describe('런 중 편집 (GDD §2.2)', () => {
  it('★ 편집 중에는 자동 진행이 멈춘다 — 뒤에서 방이 넘어가면 고친 규칙이 어디 쓰였는지 모른다', () => {
    const ready = { isFinished: true, hasNext: true, isEnabled: true, isStopped: false }
    expect(checkShouldAutoAdvance(ready)).toBe(true)
    // 편집 중이면 「끝난 판」으로 안 친다 — App 이 그렇게 넘긴다.
    expect(checkShouldAutoAdvance({ ...ready, isFinished: false })).toBe(false)
  })
})


describe('서버 없이 도는 판도 하강이다', () => {
  it('★ 로컬 연쇄도 층 수만큼 길다 — 셋으로 끊으면 화면이 계속 1층이라고 말한다', () => {
    // 서버가 없어도 게임이 도는 것이 이 저장소의 규율인데, 여기만 한 층이면 **다른
    // 게임이 돈다** — 실제로 「방 3개까지만 진행하고 계속 1층」으로 드러났다.
    const position = buildChainPosition('open_field')
    expect(position.roomIds.length).toBe(CHAIN_LENGTH * LOCAL_FLOOR_CAP)
    expect(position.index).toBe(0)
  })

  it('★ 로컬 마지막 층이 밸런스의 마지막 층과 같다 — 갈리면 오프라인만 다른 깊이를 돈다', () => {
    const scale = (BALANCE as { floor_scale?: { max_floor?: number } }).floor_scale
    expect(LOCAL_FLOOR_CAP).toBe(scale?.max_floor)
  })
})


describe('출격 진입 (첫 방이 스킵돼 보이던 자리)', () => {
  it('★ 티켓을 기다리는 동안 출격이 잠긴다 — 두 번 누르면 티켓이 둘 발급된다', () => {
    expect(checkLaunchLocked('', false)).toBe(false)
    expect(checkLaunchLocked('', true)).toBe(true)
  })

  it('★ 막는 사유가 있으면 기다리지 않아도 잠긴다', () => {
    expect(checkLaunchLocked('CPU 초과', false)).toBe(true)
  })

  it('★ 기다리는 중임을 글자로 말한다 — 잠기기만 하면 고장으로 읽힌다', () => {
    expect(formatLaunchLabel(true)).not.toBe(formatLaunchLabel(false))
    expect(formatLaunchLabel(true)).toContain('티켓')
  })

  it('★ 로컬 판도 하강으로 건다 — 서버 티켓과 다른 모양이면 갈아 끼울 때 방이 바뀐다', () => {
    // 갈아 끼우기를 없앤 것이 진짜 고침이고, 이 검사는 **두 경로가 같은 모양인지**를
    // 본다. 길이가 다르면 로컬로 시작한 판과 서버로 시작한 판이 다른 게임이 된다.
    expect(buildChainPosition('open_field').roomIds.length).toBe(CHAIN_LENGTH * LOCAL_FLOOR_CAP)
  })
})


describe('층 단위 보상 (로드맵 W14)', () => {
  it('★ 층의 마지막 방을 깨면 정산한다 — 안 하면 죽거나 다 깨야만 보상을 받는다', () => {
    // 하강으로 바꾸면서 한 런이 방 30개가 됐다. 정산이 런 끝에 한 번뿐이면 보상 주기가
    // 3방에서 30방으로 늘어난다 — 실제로 그렇게 신고됐다.
    expect(checkFloorCleared(2, 3)).toBe(true)
    expect(checkFloorCleared(5, 3)).toBe(true)
  })

  it('★ 층 중간에서는 정산하지 않는다 — 매 방 청구하면 층 단위가 아니다', () => {
    expect(checkFloorCleared(0, 3)).toBe(false)
    expect(checkFloorCleared(1, 3)).toBe(false)
  })

  it('★ 층 개념이 없으면 정산하지 않는다 — 옛 티켓은 런 끝에 한 번이다', () => {
    expect(checkFloorCleared(2, 0)).toBe(false)
  })
})
