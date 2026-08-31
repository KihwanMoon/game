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

import { BattleView, checkOngoing, type BattleSetup, type ChainPosition } from './battle'
import {
  BALANCE,
  BLOCK_CATALOG,
  CONTENT_VERSIONS,
  ENEMY_RULESETS,
  G0_RULESETS,
  ALL_ITEM_TAGS,
  ALL_SKILL_IDS,
  ROOM_TEMPLATES,
  TUTORIAL_STAGES,
} from './core/resources'
import type { RawBalanceFile } from './core/resources'
import { validateRuleSet } from './core/rules/validator'
import type { RuleSet } from './core/schemas'
import { OUTCOME_ONGOING, OUTCOME_PLAYER_WIN } from './core/sim/phases'
import { Button, ValueExpr } from './ds'
import {
  RuleEditor,
  AccountPanel,
  AdminPanel,
  BestiaryPanel,
  DiscoveryPanel,
  CatalogPanel,
  DrawerPanel,
  type DrawerTab,
  CharacterPanel,
  TutorialPanel,
  WorldPanel,
  InventoryPanel,
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
  applyTutorialStage,
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
  createLogin,
  createSaveScheduler,
  ensureToken,
  getLocalStorage,
  readMeta,
  readSave,
  readAccount,
  readAuction,
  readBestiary,
  readDiscovery,
  readLeaderboard,
  applyAdminAction,
  applyMonsterLevel,
  readAdminCatalog,
  readAdminOverview,
  readProgress,
  readServerMeta,
  applyAuctionAction,
  applyItemAction,
  buildRuleSetPayload,
  readInventory,
  registerAccount,
  requestTicket,
  submitRun,
  writeMeta,
  writeServerMeta,
  writeToken,
  type AccountState,
  type AuctionView,
  type BestiaryEntry,
  type DiscoveryView,
  type LeaderboardView,
  type ProgressView,
  type InventoryView,
  type RunResult,
  type RunVerdict,
  type AdminCatalog,
  type AdminOverview,
  type ServerTicket,
  type StorageLike,
} from './storage'
import {
  checkStageCleared,
  createEmptyMeta,
  type MetaSave,
  type TutorialStage,
} from './core/schemas'
import { MAX_SEED, buildCoreVersion, createLocalTicket, type RunTicket } from './core/schemas'
import { adoptServerMeta, applyRunSummary } from './core/services/manageMeta'
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
/**
 * 서버 티켓을 전투 조립 입력으로 옮긴다.
 *
 * **티켓이 실어 온 것을 하나도 흘리면 안 된다.** 서버는 이 티켓으로 판을 다시 돌려
 * 제출을 대조하므로, 여기서 빠진 항목이 하나라도 있으면 화면과 서버가 서로 다른 판을
 * 돌고 정상 제출이 전부 반려된다. 실제로 E4 에서 스냅샷이 이 자리에서 새어
 * 나갔다 — 그래서 이 옮김을 인라인으로 두지 않고 이름을 붙여 검사 대상으로 만들었다.
 *
 * @param issued 서버가 발급한 티켓.
 * @param rulesetId 이 판에 쓸 규칙표 id. 규칙표는 티켓이 아니라 기기가 정한다.
 * @returns 전투 조립 입력.
 */
export function buildRunSetup(issued: ServerTicket, rulesetId: string): BattleSetup {
  return {
    roomId: issued.roomId,
    rulesetId,
    seed: issued.seed,
    // 지속 몬스터 (docs/설계/6_몬스터 §5).
    snapshots: issued.snapshots,
    // **서버가 정한 방 목록을 쓴다.** 기기가 정하면 서버는 다른 방들을 재시뮬한다.
    chain: { roomIds: issued.roomIds, index: 0 },
    ...(issued.loadout === undefined ? {} : { loadout: issued.loadout }),
    // 장비·레벨이 확정한 플레이어 전투 입력 (결정 #13).
  }
}

/** 한 런이 도는 방 수 (로드맵 W3). */
export const CHAIN_LENGTH = 3

/**
 * 고른 방에서 시작하는 연쇄를 만든다.
 *
 * 지금은 같은 방을 이어 붙인다 — 층 DAG(W14)가 정해지면 그쪽이 방 목록을 정한다.
 * 그때까지도 **여러 방을 잇는 것 자체는 돌아야 한다**: 층 압력과 HP 인계가 난이도를
 * 만드는 유일한 장치이고, 방 하나로 끝나면 그 둘이 한 번도 작동하지 않는다.
 *
 * @param roomId 시작 방.
 * @returns 연쇄 위치.
 */
export function buildChainPosition(roomId: string): ChainPosition {
  return { roomIds: Array.from({ length: CHAIN_LENGTH }, () => roomId), index: 0 }
}

/**
 * 방을 이겼을 때 다음 방으로 넘어가는 setup 을 만든다.
 *
 * **여기서 HP 를 적어 나르지 않는다.** 연쇄 위치(방 목록 + 몇 번째)만 적고 인계는
 * `ChainCursor` 가 앞 방을 다시 돌려 계산한다. HP 를 setup 에 적으면 그 숫자를 손으로
 * 고쳐 강한 판을 만들 수 있고, "같은 setup 이면 같은 판" (R5) 도 깨진다.
 *
 * @param setup 방금 끝난 방의 setup.
 * @param outcome 그 방의 판정.
 * @returns 다음 방의 setup. 졌거나 마지막 방이었으면 undefined.
 */
export function buildNextRoomSetup(
  setup: BattleSetup,
  outcome: string,
): BattleSetup | undefined {
  const chain = setup.chain
  if (chain === undefined || outcome !== OUTCOME_PLAYER_WIN) {
    return undefined
  }
  const next = chain.index + 1
  const roomId = chain.roomIds[next]
  if (roomId === undefined) {
    return undefined
  }
  return { ...setup, roomId, chain: { roomIds: chain.roomIds, index: next } }
}

/** 튜토리얼 진행을 기기에 남기는 열쇠. */
export const TUTORIAL_PROGRESS_KEY = 'tutorial.cleared.v1'

/**
 * 통과한 단계 목록을 읽는다.
 *
 * 읽을 수 없으면 빈 목록이다. **여기서 던지면 앱이 안 뜬다** — 튜토리얼 진행은 게임을
 * 막을 만한 값이 아니다.
 *
 * @param storage 기기 저장소.
 * @returns 통과한 단계 id 들.
 */
export function readTutorialProgress(storage: StorageLike | undefined): readonly string[] {
  try {
    const raw = storage?.getItem(TUTORIAL_PROGRESS_KEY)
    const parsed: unknown = raw === null || raw === undefined ? [] : JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter((item) => typeof item === 'string') : []
  } catch {
    return []
  }
}

/**
 * 이 판이 지금 단계를 통과시켰는가.
 *
 * @param stage 열려 있는 단계. 없으면 통과할 것도 없다.
 * @param outcome 판정.
 * @param playerHp 남은 체력.
 * @returns 통과했으면 true.
 */
export function checkTutorialCleared(
  stage: TutorialStage | undefined,
  outcome: string,
  playerHp: number,
): boolean {
  return stage !== undefined && checkStageCleared(stage.goal, outcome, playerHp)
}

/**
 * 이 판에 적용할 CPU·슬롯 한도를 고른다.
 *
 * **서버가 아는 한도를 쓴다.** 레벨과 장비가 CPU·슬롯을 올리는데 기본값으로 두면 늘어난
 * 한도가 에디터에 안 보이고, 서버는 로드아웃 한도로 검증하므로 화면에서 통과한 규칙표가
 * 제출에서 반려된다 — 성장이 벌이 된다.
 *
 * 서버에 못 닿으면 기본값으로 선다. 오프라인 연습이 그 경우다.
 *
 * @param base balance.json 이 정한 기본 한도.
 * @param progress 서버가 준 성장 상태. 없거나 로드아웃이 없으면 기본값을 쓴다.
 * @returns 적용할 한도.
 */
export function resolvePlayerLimits(
  base: PlayerLimits,
  progress: ProgressView | undefined,
): PlayerLimits {
  const loadout = progress?.loadout
  if (loadout === undefined) {
    return base
  }
  return { cpuBudget: loadout.cpuBudget, ruleSlots: loadout.ruleSlots }
}

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
  // 서버 연결 상태. 오프라인이어도 게임은 돈다 — 코어가 브라우저 안에서 직접 돌기
  // 때문이며, 서버는 보관과 검증을 맡을 뿐이다.
  const [account, setAccount] = useState<string | undefined>(undefined)
  const [profile, setProfile] = useState<AccountState | undefined>(undefined)
  const [isOnline, setOnline] = useState(false)
  // 서버가 확정한 판정. 브라우저가 낸 결과와 다르면 두 코어가 갈린 것이다 (G3).
  const [verdict, setVerdict] = useState<RunVerdict | undefined>(undefined)
  // 아이템은 **서버가 발급한다** (결정 #02). 화면은 받아서 보여줄 뿐이다.
  const [inventory, setInventory] = useState<InventoryView | undefined>(undefined)
  const [itemDetail, setItemDetail] = useState('')
  // 도감. 세계의 몬스터는 서버가 알므로 오프라인에서는 비어 있다.
  const [bestiary, setBestiary] = useState<readonly BestiaryEntry[] | undefined>(undefined)
  const [discovery, setDiscovery] = useState<DiscoveryView | undefined>(undefined)
  // 세계 — 성장·순위·경매장. 전부 서버가 아는 것이라 오프라인에서는 비어 있다.
  const [progress, setProgress] = useState<ProgressView | undefined>(undefined)
  const [leaderboard, setLeaderboard] = useState<LeaderboardView | undefined>(undefined)
  const [auction, setAuction] = useState<AuctionView | undefined>(undefined)
  const [worldDetail, setWorldDetail] = useState('')
  // 관리자 현황. **관리자가 아니면 undefined 로 남고 패널이 아무것도 그리지 않는다** —
  // 서버가 404 로 답하므로 그 사실 자체가 화면에 드러나지 않는다.
  const [admin, setAdmin] = useState<AdminOverview | undefined>(undefined)
  const [adminDetail, setAdminDetail] = useState('')
  // 콘텐츠 카탈로그. 세계 현황과 달리 정적이라 접속할 때 한 번만 읽는다.
  const [catalog, setCatalog] = useState<AdminCatalog | undefined>(undefined)
  const [run, setRun] = useState<RunSpec | undefined>(undefined)
  const [outcome, setOutcome] = useState(OUTCOME_ONGOING)
  const [postState, setPostState] = useState<PostState>('auto')
  // 튜토리얼 진행. 기기에만 남긴다 — 보상도 순위도 없으니 서버가 알 이유가 없다.
  const [tutorialCleared, setTutorialCleared] = useState<readonly string[]>(() =>
    readTutorialProgress(getLocalStorage()),
  )
  const [tutorialId, setTutorialId] = useState<string | undefined>(undefined)
  const { theme } = usePlanTheme()

  const ruleset = getSessionRuleSet(session)
  const baseLimits = useMemo(() => readPlayerLimits(BALANCE), [])
  // **서버가 아는 한도를 쓴다.** 레벨과 장비가 CPU·슬롯을 올리는데 기본값으로 두면
  // 늘어난 한도가 에디터에 안 보이고, 서버는 그 한도로 검증하므로 성장이 벌이 된다.
  // 서버에 못 닿으면 기본값으로 선다 — 오프라인 연습이 그 경우다.
  const limits = useMemo(() => resolvePlayerLimits(baseLimits, progress), [baseLimits, progress])
  // 결산이 적 종류에서 규칙표를 찾는 데 쓴다. parseBalance 는 절 형식을 검사하므로
  // 렌더마다 돌리지 않는다.
  const balanceData = useMemo(() => parseBalance(BALANCE), [])
  // 코어 버전은 자산 여섯 세대와 엔진의 조합이다. 하나라도 바뀌면 과거 기록이
  // 재현되지 않으므로 랭킹 시즌이 갈린다 (docs/설계/1 §2).
  const coreVersion = useMemo(() => buildCoreVersion(CONTENT_VERSIONS), [])
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

  // 계정을 확보하고 서버 세이브를 합친다. **실패해도 아무 일도 일어나지 않는다** —
  // 서버가 없어도 게임은 돌아야 한다. 합치기는 최대값·합집합이라 몇 번을 해도 같은
  // 결과가 나온다(멱등).
  useEffect(() => {
    let isCurrent = true
    void (async () => {
      const storage = getLocalStorage()
      const token = await ensureToken(storage)
      if (!isCurrent || token === undefined) {
        return
      }
      setAccount(token)
      setOnline(true)
      await loadAccountState(token)
      const outcome = await readServerMeta(token)
      if (!isCurrent) {
        return
      }
      setMeta((current) => {
        const merged =
          outcome.meta === undefined ? current : adoptServerMeta(outcome.meta, current)
        writeMeta(storage, merged)
        void writeServerMeta(token, merged)
        return merged
      })
    })()
    return () => {
      isCurrent = false
    }
  }, [])

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
   * 아이템을 조작하고 결과를 화면에 반영한다.
   *
   * 실패 사유를 그대로 띄운다 — 요구조건 미달이면 서버가 실측값을 담아 보낸다.
   *
   * @param path `/equip` 같은 경로.
   * @param body 보낼 절.
   */
  function applyItem(path: string, body: Record<string, unknown>): void {
    if (account === undefined) {
      return
    }
    setItemDetail('')
    void applyItemAction(account, path, body).then((outcome) => {
      if (outcome.inventory !== undefined) {
        setInventory(outcome.inventory)
        return
      }
      if (outcome.detail !== '') {
        setItemDetail(outcome.detail)
        return
      }
      void readInventory(account).then(setInventory)
    })
  }

  /**
   * 세계를 다시 읽는다. 성장·순위·경매장이 함께 바뀌는 일이 많다.
   */
  function refreshWorld(): void {
    if (account === undefined) {
      return
    }
    void readProgress(account).then(setProgress)
    void readLeaderboard(account).then(setLeaderboard)
    void readAuction(account).then(setAuction)
    void readInventory(account).then(setInventory)
    // **관리자가 아니면 undefined 로 남는다.** 서버가 404 로 답하므로 관리자 경로가
    // 있다는 사실 자체가 일반 계정 화면에 드러나지 않는다.
    void readAdminOverview(account).then(setAdmin)
    void readAdminCatalog(account).then(setCatalog)
  }

  /**
   * 경매장을 조작하고 결과를 반영한다.
   *
   * @param path `/auction/buy` 같은 경로.
   * @param body 보낼 절.
   */
  function applyAuction(path: string, body: Record<string, unknown>): void {
    if (account === undefined) {
      return
    }
    setWorldDetail('')
    void applyAuctionAction(account, path, body).then((outcome) => {
      if (outcome.auction !== undefined) {
        setAuction(outcome.auction)
        void readInventory(account).then(setInventory)
        return
      }
      setWorldDetail(outcome.detail)
    })
  }

  /**
   * 가입한다. 지금 토큰을 함께 보내므로 **익명 계정이 승격된다** — 계정 id 가 그대로라
   * 지금까지의 기록이 전부 따라온다.
   *
   * @param loginId 아이디.
   * @param password 비밀번호.
   * @returns 실패 사유. 성공이면 빈 문자열.
   */
  async function applyRegister(loginId: string, password: string): Promise<string> {
    const outcome = await registerAccount(loginId, password, account)
    if (outcome.account === undefined) {
      return outcome.detail
    }
    if (outcome.token !== undefined && outcome.token !== account) {
      writeToken(getLocalStorage(), outcome.token)
      setAccount(outcome.token)
    }
    // 승격은 계정 id 를 바꾸지 않지만 **토큰은 바뀔 수 있다.** 그 뒤의 조회가 옛 토큰을
    // 쓰면 서버가 거절하고, 화면은 조용히 낡은 값을 들고 있게 된다.
    await loadAccountState(outcome.token ?? account ?? '')
    return ''
  }

  /**
   * 이 토큰의 계정 상태를 전부 읽어 화면에 앉힌다.
   *
   * **로그인·승격·첫 접속이 같은 함수를 쓴다.** 예전에는 첫 접속에서만 읽어서, 다른
   * 기기에서 로그인하면 화면이 **익명 계정의 값을 계속 보고 있었다** — 레벨과 CPU 가
   * 사라진 것처럼 보였다. 서버에는 그대로 있었고 화면만 갱신되지 않은 것이다.
   *
   * @param token 기기 토큰.
   */
  async function loadAccountState(token: string): Promise<void> {
    setProfile(await readAccount(token))
    setInventory(await readInventory(token))
    setBestiary(await readBestiary(token))
    setDiscovery(await readDiscovery(token))
    setProgress(await readProgress(token))
    setLeaderboard(await readLeaderboard(token))
    setAuction(await readAuction(token))
    // 관리자가 아니면 undefined 로 남는다 — 서버가 404 로 답한다.
    setAdmin(await readAdminOverview(token))
    setCatalog(await readAdminCatalog(token))
  }

  /**
   * 로그인해서 그 계정의 기록을 불러온다.
   *
   * **이 기기의 익명 기록은 따라오지 않는다.** 서버 세이브로 갈아 끼우며, 화면이 그것을
   * 먼저 경고한다. 합치면 남의 계정에 이 기기의 진행이 섞이므로 그렇게 하지 않는다.
   *
   * @param loginId 아이디.
   * @param password 비밀번호.
   * @returns 실패 사유. 성공이면 빈 문자열.
   */
  async function applyLogin(loginId: string, password: string): Promise<string> {
    const outcome = await createLogin(loginId, password)
    if (outcome.account === undefined || outcome.token === undefined) {
      return outcome.detail
    }
    const storage = getLocalStorage()
    writeToken(storage, outcome.token)
    setAccount(outcome.token)
    setProfile(outcome.account)
    const server = await readServerMeta(outcome.token)
    const next = server.meta ?? createEmptyMeta()
    writeMeta(storage, next)
    setMeta(next)
    // **계정이 통째로 바뀐다.** 레벨·CPU·가방·권한이 전부 다른 사람의 것이 되므로
    // 하나라도 안 읽으면 화면이 앞 계정의 값을 계속 보여준다.
    await loadAccountState(outcome.token)
    return ''
  }

  /**
   * 지금 규칙표로 판을 시작한다. 방·시드·규칙표를 이 순간의 값으로 얼린다.
   */
  function startRun(): void {
    // 시드는 티켓을 거쳐서만 전투로 들어간다. 서버가 있으면 서버가 발급하고, 없으면
    // 로컬 연습 티켓으로 계속한다 — **서버가 없다고 게임이 멈추지 않는다.** 다만 로컬
    // 티켓으로 돈 판은 서버에 남지 않으므로 G1 계측에서도 빠진다.
    setVerdict(undefined)
    setOutcome(OUTCOME_ONGOING)
    setPostState('auto')
    const local = createLocalTicket(session.seed, session.roomId, coreVersion)
    setRun({
      // 로컬 티켓에는 스냅샷이 없다 — 지속 몬스터는 서버가 아는 것이다.
      setup: {
        roomId: local.roomId,
        rulesetId: ruleset.rulesetId,
        seed: local.seed,
        chain: buildChainPosition(session.roomId),
      },
      rulesets: new Map([[ruleset.rulesetId, ruleset]]),
      ticket: local,
    })
    if (account === undefined) {
      return
    }
    void requestTicket(account, session.roomId, session.seed).then((issued) => {
      if (issued === undefined) {
        return
      }
      // 서버가 준 시드로 판을 다시 건다. 연습 모드라 제안한 시드가 그대로 오지만,
      // 순위 모드가 생기면 여기서 값이 갈리고 그때는 서버 것이 정본이다.
      setRun({
        setup: buildRunSetup(issued, ruleset.rulesetId),
        rulesets: new Map([[ruleset.rulesetId, ruleset]]),
        ticket: {
          ticketId: issued.ticketId,
          seed: issued.seed,
          roomId: issued.roomId,
          floor: issued.floor,
          mode: 'PRACTICE',
          coreVersion: issued.coreVersion,
        },
      })
    })
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
    // 서버에 제출한다. **결과는 보내지 않는다** — 서버가 티켓의 시드로 다시 계산한다.
    // 실패는 무시한다: 제출이 안 됐다고 판이 무효가 되면 네트워크가 끊긴 사람은
    // 게임을 할 수 없다.
    const ticket = run?.ticket
    if (account !== undefined && ticket !== undefined && !ticket.ticketId.startsWith('local:')) {
      void submitRun(
        account,
        ticket.ticketId,
        buildRuleSetPayload(finishedRun.ruleset),
        ticket.coreVersion,
      ).then((result) => {
        setVerdict(result)
        // 전리품과 화폐가 여기서 들어온다. 다시 읽어야 화면이 그것을 안다.
        void readInventory(account).then(setInventory)
        // 판이 끝나면 몬스터가 컸거나 내 장비를 가져갔을 수 있다.
        void readBestiary(account).then(setBestiary)
        // 전리품이 들어왔으면 도감이 열린다 — 그 순간 안 읽으면 다음 접속까지 잠겨 보인다.
        void readDiscovery(account).then(setDiscovery)
        // 판이 끝나면 경험치와 순위가 올랐다.
        void readProgress(account).then(setProgress)
        void readLeaderboard(account).then(setLeaderboard)
        // **서버가 확정한 성취를 받아 온다.** 아래에서 기기가 낙관적으로 먼저 반영하지만
        // 정본은 서버의 재시뮬이다 — 둘이 갈리면 화면에 뜬 해금이 다음 접속에 사라진다.
        void readServerMeta(account).then((outcome) => {
          const server = outcome.meta
          if (server === undefined) {
            return
          }
          setMeta((current) => {
            const adopted = adoptServerMeta(server, current)
            writeMeta(getLocalStorage(), adopted)
            return adopted
          })
        })
      })
    }

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
      // 서버에도 민다. 실패는 무시한다 — 기기에는 이미 남았고, 다음 접속에 합쳐진다.
      if (account !== undefined) {
        void writeServerMeta(account, next)
      }
      return next
    })
  }

  /**
   * 이긴 방 다음으로 넘어간다.
   *
   * **규칙 편집은 방 사이에서만 가능하다** (GDD §2.2). 그래서 여기서 규칙표를 다시 읽지
   * 않고 시작할 때 얼린 것을 그대로 쓴다 — 방 중간에 규칙이 바뀌면 관전한 판과 서버가
   * 재시뮬한 판이 갈린다.
   */
  function goToNextRoom(): void {
    if (run === undefined) {
      return
    }
    const next = buildNextRoomSetup(run.setup, outcome)
    if (next === undefined) {
      return
    }
    setOutcome(OUTCOME_ONGOING)
    setPostState('auto')
    setRun({ ...run, setup: next })
  }

  /**
   * 끝난 판이 지금 튜토리얼 단계를 통과시켰는지 반영한다.
   *
   * @param outcome 판정.
   * @param playerHp 남은 체력.
   */
  function applyTutorialResult(outcome: string, playerHp: number): void {
    const stage = TUTORIAL_STAGES.find((item) => item.stageId === tutorialId)
    if (!checkTutorialCleared(stage, outcome, playerHp) || stage === undefined) {
      return
    }
    setTutorialCleared((current) => {
      if (current.includes(stage.stageId)) {
        return current
      }
      const next = [...current, stage.stageId]
      getLocalStorage()?.setItem(TUTORIAL_PROGRESS_KEY, JSON.stringify(next))
      return next
    })
  }

  /**
   * 에디터로 돌아간다. 판을 버리고 결과만 들고 나온다.
   */
  function goToEditor(): void {
    if (recording !== undefined) {
      applyTutorialResult(recording.outcome, recording.playerHp)
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
  // 서버 판정이 다르면 그것을 숨기지 않는다. mismatch 는 치트의 증거가 아니라
  // 두 코어가 갈렸다는 신호이고, 대개 우리 쪽 버그다 (docs/설계/7_변조방지 §8).
  const verdictText =
    verdict === undefined || verdict.verdict === 'verified'
      ? ''
      : `서버 판정 ${verdict.verdict}${verdict.detail === '' ? '' : ` — ${verdict.detail}`}`

  const launchControls = (
    <div className="launch">
      {resultText === '' ? null : <ValueExpr text={resultText} size="sm" dim />}
      {verdictText === '' ? null : <ValueExpr text={verdictText} size="sm" />}
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
            <DrawerPanel tabs={buildDrawerTabs()} />
          }
        />
      </div>
    )
  }

  /**
   * 서랍 탭을 만든다.
   *
   * **묶음은 "무엇에 대한 것인가" 로 가른다.** 화면 수를 줄이려고 아무거나 합치면 탭
   * 이름이 설명을 못 하고, 그러면 탭이 있으나 마나다.
   *
   * 관리자 탭은 관리자에게만 생긴다 — 빈 탭이라도 있으면 관리자 경로의 존재가 드러난다.
   *
   * @returns 탭 목록.
   */
  function buildDrawerTabs(): DrawerTab[] {
    const tabs: DrawerTab[] = [
      {
        id: 'me',
        label: '나',
        body: (
          <>
              <AccountPanel
                account={profile}
                isOnline={isOnline}
                hasLocalProgress={meta.bestFloor > 0 || meta.bestiary.length > 0}
                onRegister={applyRegister}
                onLogin={applyLogin}
              />
              <CharacterPanel
                progress={progress}
                baseStats={BALANCE.player as Record<string, number>}
                allSkills={ALL_SKILL_IDS}
                allItems={ALL_ITEM_TAGS}
                isOnline={isOnline}
              />
          </>
        ),
      },
      {
        id: 'bag',
        label: '가방',
        body: (
          <>
              <InventoryPanel
                inventory={inventory}
                isOnline={isOnline}
                detail={itemDetail}
                onEquip={(itemId, slot) => {
                  applyItem('/equip', { item_id: itemId, slot })
                }}
                onUnequip={(slot) => {
                  applyItem('/unequip', { item_id: 0, slot })
                }}
                onDiscard={(itemId) => {
                  applyItem('/item/discard', { item_id: itemId })
                }}
                onRepair={(itemId) => {
                  applyItem('/item/repair', { item_id: itemId })
                }}
              />
          </>
        ),
      },
      {
        id: 'world',
        label: '세계',
        body: (
          <>
              <WorldPanel
                progress={progress}
                leaderboard={leaderboard}
                auction={auction}
                accountId={profile?.accountId}
                isOnline={isOnline}
                detail={worldDetail}
                onAllocate={(stats) => {
                  if (account === undefined) {
                    return
                  }
                  setWorldDetail('')
                  void fetch('/api/progress/stats', {
                    method: 'PUT',
                    headers: { 'X-Game-Token': account, 'Content-Type': 'application/json' },
                    body: JSON.stringify({ stats }),
                  }).then(() => {
                    refreshWorld()
                  })
                }}
                onBuy={(listingId) => {
                  applyAuction('/auction/buy', { listing_id: listingId })
                }}
                onCancel={(listingId) => {
                  applyAuction('/auction/cancel', { listing_id: listingId })
                }}
                onDaily={() => {
                  if (account === undefined) {
                    return
                  }
                  void fetch('/api/daily', {
                    method: 'POST',
                    headers: { 'X-Game-Token': account },
                  }).then(() => {
                    setWorldDetail('오늘의 도전 티켓을 받았다 — 출격하면 그 판이 돈다')
                  })
                }}
              />
              <BestiaryPanel entries={bestiary} isOnline={isOnline} />
              <DiscoveryPanel discovery={discovery} isOnline={isOnline} />
          </>
        ),
      },
      {
        id: 'learn',
        label: '배움',
        body: (
          <>
              <TutorialPanel
                stages={TUTORIAL_STAGES}
                cleared={tutorialCleared}
                activeId={tutorialId}
                onOpen={(stage) => {
                  // **틀린 규칙표를 싣는다.** 실패한 판을 한 번 보고 나서 고치는 것이
                  // 이 게임의 학습 방식이다 (P1).
                  setTutorialId(stage.stageId)
                  setSession((current) => applyTutorialStage(current, stage, stage.startRules))
                }}
                onHint={(stage) => {
                  // 막히면 답을 준다. 벽에 부딪힌 사람을 세워 두면 G1 이 재는 것이
                  // "재미" 가 아니라 "인내" 가 된다.
                  setSession((current) => applyTutorialStage(current, stage, stage.solutionRules))
                }}
                onClose={() => {
                  setTutorialId(undefined)
                }}
              />
              <MetaPanel meta={meta} baseSlots={limits.ruleSlots} />
          </>
        ),
      },
      {
        id: 'library',
        label: '서고',
        body: (
          <>
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
        ),
      },
    ]
    if (admin !== undefined) {
      tabs.push({
        id: 'admin',
        label: '관리',
        body: (
          <>
              <AdminPanel
                overview={admin}
                detail={adminDetail}
                onIntervene={(path, targetId, reason) => {
                  if (account === undefined) {
                    return
                  }
                  setAdminDetail('')
                  void applyAdminAction(account, path, targetId, reason).then((outcome) => {
                    setAdminDetail(outcome.detail)
                    if (outcome.overview !== undefined) {
                      setAdmin(outcome.overview)
                    }
                  })
                }}
                onSetMonsterLevel={(recordId, level) => {
                  if (account === undefined) {
                    return
                  }
                  setAdminDetail('')
                  void applyMonsterLevel(account, recordId, level).then((outcome) => {
                    setAdminDetail(outcome.detail)
                    if (outcome.overview !== undefined) {
                      setAdmin(outcome.overview)
                    }
                  })
                }}
              />
            <CatalogPanel catalog={catalog} />
          </>
        ),
      })
    }
    return tabs
  }

  const nextRoom = run === undefined ? undefined : buildNextRoomSetup(run.setup, outcome)
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
      {nextRoom === undefined ? null : (
        <Button
          size="sm"
          variant="primary"
          glyph="→"
          title="체력과 포션을 그대로 들고 다음 방으로 넘어간다"
          onClick={goToNextRoom}
        >
          다음 방 {String((run.setup.chain?.index ?? 0) + 2)}/
          {String(run.setup.chain?.roomIds.length ?? 1)}
        </Button>
      )}
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
