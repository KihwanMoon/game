/**
 * 앱 조립 (W13, M3) — 규칙을 짜고, 내보내고, 죽은 이유를 보고, 고쳐서 다시 보내는 한 바퀴.
 *
 * 화면은 둘이고 그 사이를 잇는 것이 **한 벌의 규칙표**다. 규칙표 상태를 여기서 들고
 * 두 화면에 내려보낸다. 어느 한쪽이 자기 안에 사본을 만들면 고친 규칙이 전투에 반영되지
 * 않거나 그 반대가 되고, 그 순간 "고쳐서 다시 도전한다" 는 이 게임의 유일한 동사가
 * 끊긴다 (GDD §2.1).
 *
 *   규칙 에디터  ──[출격]──▶  전투 관전  ──[사망]──▶  사후 분석
 *        ▲                                                │
 *        └────────────────[규칙 고치기]────────────────────┘
 *
 * **판은 `run` 하나가 특정한다** — 방·시드·규칙표를 출격 순간에 얼어붙인다. 전투 중에
 * 규칙표를 바꿀 수 없게 하려는 것이 아니라(에디터로 나가면 바꿀 수 있다), 도는 판의
 * 입력이 도중에 흔들리면 같은 시드가 같은 결과를 내지 않기 때문이다 (R5).
 *
 * **사후 분석은 판을 한 번 더 돌려 만든다.** 관전 화면은 엔진을 앞으로만 밀어 지나간
 * 틱의 화면을 남기지 않는데, 되감기와 히트맵은 틱마다의 좌표가 있어야 한다. 결정론이
 * 보장하는 것이 정확히 이것이라 같은 setup 을 다시 돌리면 같은 판이 나온다 — 두 번째
 * 실행은 첫 번째의 재현이지 다른 판이 아니다. 400틱 상한이라 즉시 끝난다.
 *
 * 황동 예산(design/README.md, 화면당 3곳):
 *   에디터 — 출격 버튼(primary) · 선택된 규칙의 좌측 세로바 · 포커스 링
 *   전투   — 도면의 플레이어 말 · 발동한 규칙 줄 · 그 줄에서 말로 잇는 지시선
 * 그래서 전투 화면 쪽 조작부는 전부 ghost 다.
 *
 * **짠 것은 탭을 닫아도 남는다** (M3). 상태는 `session.ts` 의 세션 하나이고, 그 세션을
 * 그대로 구워 localStorage 에 디바운스 저장한다(`storage/`). 상태를 조각조각 들고 있으면
 * 새로 만든 조각을 저장에 넣는 것을 잊게 되고, 그런 결함은 새로고침을 해 봐야 드러난다.
 */
import { useEffect, useMemo, useState } from 'react'

import { BattleView, checkOngoing, type BattleSetup } from './battle'
import {
  BALANCE,
  BLOCK_CATALOG,
  ENEMY_RULESETS,
  G0_RULESETS,
  ROOM_TEMPLATES,
} from './core/resources'
import type { RawBalanceFile } from './core/resources'
import { validateRuleSet } from './core/rules/validator'
import type { RuleSet } from './core/schemas'
import { OUTCOME_ONGOING, OUTCOME_PLAYER_WIN } from './core/sim/phases'
import { Button, ValueExpr } from './ds'
import {
  RuleEditor,
  MetaPanel,
  RuleLibrary,
  checkCanRedo,
  checkCanUndo,
  checkTextEntry,
  resolveHistoryCommand,
} from './editor'
import { ErrorBoundary, formatCrash } from './ErrorBoundary'
import { PostMortem, formatOutcome, recordBattle, usePlanTheme } from './hud'
import type { BattleRecording } from './hud'
import {
  applyPresetImport,
  applyPresetLoad,
  applyPresetRemove,
  applyPresetSave,
  applyRedoStep,
  applyRoomChoice,
  applyRuleSetEdit,
  applyRunResult,
  applySeedChoice,
  applyUndoStep,
  buildSessionSave,
  createSession,
  exportSessionCode,
  exportSlotCode,
  getSessionRuleSet,
  type EditorSession,
} from './session'
import {
  createSaveScheduler,
  getLocalStorage,
  readMeta,
  readSave,
  writeMeta,
  type RunResult,
} from './storage'
import { createEmptyMeta, type MetaSave } from './core/schemas'
import { MAX_SEED, buildCoreVersion, createLocalTicket, type RunTicket } from './core/schemas'
import { applyRunSummary } from './core/services/manageMeta'
import { buildRunSummary, listEncounteredRulesets } from './core/services/runSummary'
import { parseBalance } from './core/services/runBattle'

/** 에디터가 알아야 하는 플레이어 제약. */
interface PlayerLimits {
  readonly cpuBudget: number
  readonly ruleSlots: number
}

/** 출격 순간에 얼려 둔 판. 이 값이 있으면 전투 화면, 없으면 에디터다. */
interface RunSpec {
  readonly setup: BattleSetup
  /** 규칙표 대응표. 출격 시점의 규칙표 하나만 든다. */
  readonly rulesets: ReadonlyMap<string, RuleSet>
  /**
   * 이 런을 시작할 권한. 시드의 출처이며, 서버가 붙으면 여기 몬스터 스냅샷이 함께 온다.
   *
   * 판이 도는 동안 티켓을 들고 있는 이유는 제출이 티켓 id 를 요구하기 때문이다 —
   * 결과를 보낼 때 시드를 다시 싣지 않는다 (docs/설계/7_변조방지 §4).
   */
  readonly ticket: RunTicket
}

/** 사후 분석 패널의 표시 상태. auto 는 "판이 끝나면 저절로 뜬다" 다. */
type PostState = 'auto' | 'open' | 'closed'

/** 처음 열었을 때 실을 규칙표. G0 예시 중 근접 압박. */
const INITIAL_RULESET_ID = 'g0_pressure'

/** 처음 열었을 때의 방과 시드. 같은 시드는 같은 판을 낸다 (R5). */
const INITIAL_ROOM_ID = 'open_field'
const INITIAL_SEED = 1

/** 시드를 한 칸 옮기는 폭. Math.random 을 쓰지 않는다 — 판은 늘 사람이 고른 수에서 나온다. */
const SEED_STEP = 1

/** 시드가 음수로 내려가지 않게 막는 하한. */
const MIN_SEED = 0

/** 시드 상한. 이식 제약이며 이유는 `core/schemas/runTicket` 의 MAX_SEED 에 있다. */
const SEED_LIMIT = MAX_SEED

const DECIMAL_RADIX = 10

const PLAYER_SECTION = 'player'
const CPU_BUDGET_KEY = 'cpu_budget'
const RULE_SLOTS_KEY = 'rule_slots'

/** 상단 바의 층 표기. 층 진행(Phase 4)이 붙기 전까지는 1층 하나뿐이다. */
const FLOOR_LABEL = '1층'

/**
 * 밸런스 파일에서 플레이어 제약을 읽는다.
 *
 * @param raw balance.json 을 읽은 값.
 * @returns CPU 예산과 규칙 슬롯 수.
 * @throws player 절이 없거나 두 값이 정수가 아닌 경우.
 */
export function readPlayerLimits(raw: RawBalanceFile): PlayerLimits {
  const section = raw[PLAYER_SECTION]
  if (typeof section !== 'object' || section === null) {
    throw new TypeError('balance.json 의 player 절이 객체가 아니다')
  }
  const values = section as Record<string, unknown>
  const cpuBudget = values[CPU_BUDGET_KEY]
  const ruleSlots = values[RULE_SLOTS_KEY]
  if (typeof cpuBudget !== 'number' || typeof ruleSlots !== 'number') {
    throw new TypeError('balance.json 의 player 절에 cpu_budget·rule_slots 가 없다')
  }
  return { cpuBudget, ruleSlots }
}

/**
 * 처음 실을 규칙표를 집는다.
 *
 * @returns G0 예시 규칙표. 없으면 빈 규칙표.
 */
export function buildInitialRuleSet(): RuleSet {
  return (
    G0_RULESETS.get(INITIAL_RULESET_ID) ?? {
      rulesetId: INITIAL_RULESET_ID,
      version: 1,
      rules: [],
    }
  )
}

/**
 * 상단 바에 적을 위치 표기를 만든다.
 *
 * @param roomId 방 id.
 * @returns `1층 · open_field` 꼴의 표기.
 */
export function formatLocation(roomId: string): string {
  return `${FLOOR_LABEL} · ${roomId}`
}

/**
 * 직전 판의 결과를 한 줄로 적는다.
 *
 * @param result 직전 판. 아직 한 판도 돌리지 않았으면 undefined.
 * @returns 에디터 상단에 적을 문구. 직전 판이 없으면 빈 문자열.
 */
export function describeRunResult(result: RunResult | undefined): string {
  if (result === undefined) {
    return ''
  }
  return `직전 판 ${formatOutcome(result.outcome)} · ${String(result.ticks)}틱 · HP ${String(result.playerHp)}`
}

/**
 * 출격을 막는 이유를 고른다.
 *
 * 편집은 무엇도 막지 않는다(GDD §3.6). 막는 것은 **내보내기**다 — 목록에 없는 블록이나
 * 예산을 넘긴 규칙표를 그대로 던지면 엔진이 도중에 죽거나 규칙이 조용히 무시되고,
 * 플레이어는 자기 논리를 의심하게 된다 (P1). 그래서 첫 번째 위반을 버튼에 그대로 적는다.
 *
 * @param problems `validateRuleSet` 이 낸 목록.
 * @returns 버튼에 적을 사유. 출격할 수 있으면 빈 문자열.
 */
export function findLaunchBlocker(problems: readonly string[]): string {
  return problems[0] ?? ''
}

/**
 * 앱 화면. 규칙 에디터와 전투 관전을 한 벌의 규칙표로 잇는다.
 *
 * @returns 렌더 트리.
 */
export function App(): React.JSX.Element {
  const [session, setSession] = useState<EditorSession>(() =>
    createSession(readSave(getLocalStorage()), {
      ruleset: buildInitialRuleSet(),
      roomId: INITIAL_ROOM_ID,
      seed: INITIAL_SEED,
    }),
  )
  // 메타 세이브는 편집 세이브와 수명이 다르다 — 규칙표는 고치면 덮어쓰지만 해금과
  // 도감은 누적이다. 그래서 저장 열쇠도 디바운스 저장기도 따로 둔다.
  const [meta, setMeta] = useState<MetaSave>(() => readMeta(getLocalStorage()) ?? createEmptyMeta())
  const [run, setRun] = useState<RunSpec | undefined>(undefined)
  const [outcome, setOutcome] = useState(OUTCOME_ONGOING)
  const [postState, setPostState] = useState<PostState>('auto')
  const { theme } = usePlanTheme()

  const ruleset = getSessionRuleSet(session)
  const limits = useMemo(() => readPlayerLimits(BALANCE), [])
  // 결산이 적 종류에서 규칙표를 찾는 데 쓴다. parseBalance 는 절 형식을 검사하므로
  // 렌더마다 돌리지 않는다.
  const balanceData = useMemo(() => parseBalance(BALANCE), [])
  // 코어 버전은 블록·밸런스·엔진 세대의 조합이다. 하나라도 바뀌면 과거 기록이
  // 재현되지 않으므로 랭킹 시즌이 갈린다 (docs/설계/1 §2).
  const coreVersion = useMemo(
    () => buildCoreVersion(BLOCK_CATALOG.version, BALANCE.balance_version),
    [],
  )
  const problems = useMemo(
    () => validateRuleSet(ruleset, BLOCK_CATALOG, limits.cpuBudget, limits.ruleSlots),
    [ruleset, limits],
  )

  // 저장기는 앱이 사는 동안 하나다. 렌더마다 새로 만들면 앞선 예약이 사라져 디바운스가
  // "마지막 것 하나" 가 아니라 "아무것도 안 씀" 이 된다.
  const scheduler = useMemo(() => createSaveScheduler(getLocalStorage()), [])

  // 세션이 바뀔 때마다 예약한다. 화면을 떠날 때는 예약을 버리지 않고 즉시 쓴다 — 마지막
  // 편집이 400ms 안에 있었다는 이유로 사라지면 저장이 없는 것과 다르지 않다.
  useEffect(() => {
    scheduler.schedule(buildSessionSave(session))
  }, [scheduler, session])

  useEffect(() => {
    const target = globalThis.window as Window | undefined
    /** 탭이 닫히거나 뒤로 가기 전에 예약된 저장을 쓴다. */
    function handleHide(): void {
      scheduler.flush()
    }
    target?.addEventListener('pagehide', handleHide)
    return () => {
      target?.removeEventListener('pagehide', handleHide)
      scheduler.flush()
    }
  }, [scheduler])

  // 되돌리기는 화면 전체에서 듣는다. 규칙 행에 포커스가 없을 때도 눌리기 때문이다.
  // 전투 화면에서는 듣지 않는다 — 도는 판의 입력을 되돌릴 수는 없다 (R5).
  useEffect(() => {
    const target = globalThis.window as Window | undefined
    if (target === undefined || run !== undefined) {
      return undefined
    }
    /**
     * 되돌리기 단축키를 처리한다.
     *
     * @param event 키 입력.
     */
    function handleKeyDown(event: KeyboardEvent): void {
      const command = resolveHistoryCommand(event)
      const focused = event.target instanceof HTMLElement ? event.target.tagName : ''
      if (command === undefined || checkTextEntry(focused)) {
        return
      }
      event.preventDefault()
      setSession(command === 'undo' ? applyUndoStep : applyRedoStep)
    }
    target.addEventListener('keydown', handleKeyDown)
    return () => {
      target.removeEventListener('keydown', handleKeyDown)
    }
  }, [run])

  // 판이 끝난 뒤에만 다시 돌린다. 관전 중에 돌리면 매 틱 400틱짜리 재현이 따라 돈다.
  const finished = !checkOngoing(outcome)
  const recording = useMemo(
    () => (run === undefined || !finished ? undefined : recordBattle(run.setup, run.rulesets)),
    [run, finished],
  )

  /**
   * 지금 규칙표로 판을 시작한다. 방·시드·규칙표를 이 순간의 값으로 얼린다.
   */
  function startRun(): void {
    // 시드는 티켓을 거쳐서만 전투로 들어간다. 지금은 로컬이 연습 티켓을 발급하지만,
    // 서버가 붙으면 이 한 줄의 발급처만 바뀐다 — 순위·데일리는 로컬이 만들 수 없다
    // (core/schemas/runTicket). 이음매를 지금 두는 이유는 나중에 두면 그때까지의
    // 기록이 전부 무효가 되기 때문이다 (결정/1_결정대기목록 #01).
    const ticket = createLocalTicket(session.seed, session.roomId, coreVersion)
    setRun({
      setup: { roomId: ticket.roomId, rulesetId: ruleset.rulesetId, seed: ticket.seed },
      rulesets: new Map([[ruleset.rulesetId, ruleset]]),
      ticket,
    })
    setOutcome(OUTCOME_ONGOING)
    setPostState('auto')
  }

  /**
   * 판 하나를 영구 기록에 반영한다 (GDD §2.3).
   *
   * **진 판도 남긴다.** 해금과 도감은 이겼는지가 아니라 무엇을 접했는지로 쌓이며,
   * 그것이 "실패는 정보다" 를 저장 층에서 지키는 방식이다 (P1).
   *
   * 저장은 즉시 쓴다. 편집과 달리 결산은 한 판에 한 번뿐이라 디바운스할 것이 없고,
   * 여기서 미루면 탭을 닫는 순간 그 판의 기록이 통째로 사라진다.
   *
   * @param finishedRun 끝난 판의 기록.
   */
  function applyRunSettlement(finishedRun: BattleRecording): void {
    const enemyRulesets = listEncounteredRulesets(
      finishedRun.tally.encountered,
      balanceData.enemies,
      ENEMY_RULESETS,
    )
    const summary = buildRunSummary(
      finishedRun.tally,
      finishedRun.ruleset,
      finishedRun.outcome === OUTCOME_PLAYER_WIN,
      enemyRulesets,
    )
    setMeta((current) => {
      const next = applyRunSummary(current, summary, BLOCK_CATALOG)
      writeMeta(getLocalStorage(), next)
      return next
    })
  }

  /**
   * 에디터로 돌아간다. 판을 버리고 결과만 들고 나온다.
   */
  function goToEditor(): void {
    if (recording !== undefined) {
      const result = {
        outcome: recording.outcome,
        ticks: recording.ticks,
        playerHp: recording.playerHp,
      }
      setSession((current) => applyRunResult(current, result))
      applyRunSettlement(recording)
    }
    setRun(undefined)
    setOutcome(OUTCOME_ONGOING)
  }

  /**
   * 공유 코드를 읽어 들인다.
   *
   * @param code 붙여넣은 코드.
   * @returns 실패 사유. 성공이면 빈 문자열.
   */
  function readSharedCode(code: string): string {
    try {
      setSession((current) => applyPresetImport(current, code))
      return ''
    } catch (error) {
      return formatCrash(error)
    }
  }

  const blocker = findLaunchBlocker(problems)
  const resultText = describeRunResult(session.lastResult)

  const launchControls = (
    <div className="launch">
      {resultText === '' ? null : <ValueExpr text={resultText} size="sm" dim />}
      <Button
        size="sm"
        variant="ghost"
        glyph="↶"
        disabled={!checkCanUndo(session.history)}
        title="되돌리기 (Ctrl+Z)"
        onClick={() => {
          setSession(applyUndoStep)
        }}
      />
      <Button
        size="sm"
        variant="ghost"
        glyph="↷"
        disabled={!checkCanRedo(session.history)}
        title="다시 실행 (Ctrl+Shift+Z)"
        onClick={() => {
          setSession(applyRedoStep)
        }}
      />
      <label className="launch__label" htmlFor="launch-room">
        방
      </label>
      <select
        id="launch-room"
        className="launch__field"
        value={session.roomId}
        onChange={(event) => {
          const roomId = event.target.value
          setSession((current) => applyRoomChoice(current, roomId))
        }}
      >
        {ROOM_TEMPLATES.map((template) => (
          <option value={template.templateId} key={template.templateId}>
            {template.templateId}
          </option>
        ))}
      </select>
      <label className="launch__label" htmlFor="launch-seed">
        시드
      </label>
      <input
        id="launch-seed"
        className="launch__field launch__field--number"
        type="number"
        min={MIN_SEED}
        value={session.seed}
        onChange={(event) => {
          const parsed = Number.parseInt(event.target.value, DECIMAL_RADIX)
          const bounded = Number.isNaN(parsed) ? MIN_SEED : Math.max(MIN_SEED, parsed)
          const seed = Math.min(SEED_LIMIT, Math.trunc(bounded))
          setSession((current) => applySeedChoice(current, seed))
        }}
      />
      <Button
        size="sm"
        variant="ghost"
        glyph="＋"
        title="다음 시드 — 같은 규칙표를 다른 판에서 시험한다"
        onClick={() => {
          setSession((current) => applySeedChoice(current, current.seed + SEED_STEP))
        }}
      >
        시드
      </Button>
      <Button
        size="sm"
        variant="primary"
        glyph="▶"
        disabled={blocker !== ''}
        title={blocker === '' ? '이 규칙표로 던전에 내보낸다' : blocker}
        onClick={startRun}
      >
        출격
      </Button>
    </div>
  )

  if (run === undefined) {
    return (
      <div className="app">
        <RuleEditor
          ruleset={ruleset}
          catalog={BLOCK_CATALOG}
          cpuBudget={limits.cpuBudget}
          ruleSlots={limits.ruleSlots}
          onChange={(next) => {
            setSession((current) => applyRuleSetEdit(current, next))
          }}
          controls={launchControls}
          library={
            <>
              <MetaPanel meta={meta} baseSlots={limits.ruleSlots} />
              <RuleLibrary
              presets={session.presets}
              onSave={(name) => {
                setSession((current) => applyPresetSave(current, name))
              }}
              onLoad={(index) => {
                setSession((current) => applyPresetLoad(current, index))
              }}
              onRemove={(index) => {
                setSession((current) => applyPresetRemove(current, index))
              }}
              onImport={readSharedCode}
              onExport={(name) => exportSessionCode(session, name)}
                onExportSlot={(index) => exportSlotCode(session, index)}
              />
            </>
          }
        />
      </div>
    )
  }

  const battleControls = (
    <div className="launch">
      <ValueExpr text={`seed ${String(run.setup.seed)}`} size="sm" dim />
      {finished ? (
        <Button
          size="sm"
          variant="ghost"
          glyph="◱"
          title="규칙별 발동 통계·피해 히트맵·직전 15틱 되감기"
          onClick={() => {
            setPostState('open')
          }}
        >
          사후 분석
        </Button>
      ) : null}
      <Button
        size="sm"
        variant="ghost"
        glyph="↺"
        title="같은 방·같은 시드로 처음부터 다시 돌린다"
        onClick={startRun}
      >
        다시
      </Button>
      <Button size="sm" variant="ghost" glyph="↰" onClick={goToEditor}>
        규칙 고치기
      </Button>
    </div>
  )

  // 저절로 뜨는 것은 **이기지 못했을 때**다. 이긴 판까지 덮어 버리면 승리 화면을 볼 수
  // 없고, 사후 분석이 성적표가 아니라 방해물이 된다. 이긴 판의 분석은 버튼으로 연다.
  const showPost =
    postState === 'open' ||
    (postState === 'auto' && recording !== undefined && recording.outcome !== OUTCOME_PLAYER_WIN)

  return (
    <div className="app">
      <ErrorBoundary onReset={goToEditor}>
        <BattleView
          setup={run.setup}
          rulesets={run.rulesets}
          location={formatLocation(run.setup.roomId)}
          controls={battleControls}
          onOutcome={setOutcome}
        />
        {showPost && recording !== undefined ? (
          <PostMortem
            recording={recording}
            theme={theme}
            onClose={() => {
              setPostState('closed')
            }}
          />
        ) : null}
      </ErrorBoundary>
    </div>
  )
}
