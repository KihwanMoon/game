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

import {
  BattleView,
  checkOngoing,
  resolveRoomFloor,
  type BattleSetup,
  type ChainPosition,
} from './battle'
import {
  G0_RULESETS,
  ALL_ITEM_TAGS,
  ALL_SKILL_IDS,
  RULE_TEMPLATES,
  TUTORIAL_STAGES,
} from './core/resources'
// 지금 도는 자산은 팩에서 읽는다 (설계/4_아이템 §18). 번들은 폴백이고, 서버가
// 발행하면 이 값들이 그쪽을 가리킨다. 예시 규칙표·튜토리얼·태그는 화면의 것이라
// 번들에 남는다 — 발행 대상이 아니다.
import { readActivePack } from './content/pack'

const ACTIVE = readActivePack()
const BLOCK_CATALOG = ACTIVE.catalog
const ROOM_TEMPLATES = ACTIVE.rooms
const ENEMY_RULESETS = ACTIVE.enemies
const BALANCE = ACTIVE.balance
import type { RawBalanceFile } from './core/resources'
import { validateRuleSet } from './core/rules/validator'
import type { RuleSet } from './core/schemas'
import { OUTCOME_ONGOING, OUTCOME_PLAYER_WIN } from './core/sim/phases'
import { Button, GlyphState, Panel, ValueExpr } from './ds'
import {
  RuleEditor,
  AccountPanel,
  AdminPanel,
  BestiaryPanel,
  DiscoveryPanel,
  DrawerPanel,
  EvictionNotice,
  FloorRewardNotice,
  AUTO_ADVANCE_SECONDS,
  AutoAdvanceNotice,
  checkShouldAutoAdvance,
  readAutoAdvance,
  writeAutoAdvance,
  type DrawerTab,
  CharacterPanel,
  TemplatePanel,
  TutorialPanel,
  WorldPanel,
  ConsumablePanel,
  findFreeConsumableSlot,
  InventoryPanel,
  MaintenancePanel,
  SkillPanel,
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
  adoptAccount,
  adoptDraft,
  adoptPresets,
  applyRuleSetEdit,
  applySessionToMeta,
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
  applyLogout,
  createLogin,
  listenEviction,
  TOKEN_STORAGE_KEY,
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
  readAdminOverview,
  readProgress,
  readServerMeta,
  applyAuctionAction,
  applyConsumableAction,
  applyItemAction,
  buildRuleSetPayload,
  readBagState,
  readMaintenance,
  readSkillPrefs,
  saveMaintenance,
  saveSkillPrefs,
  readItemContext,
  registerAccount,
  requestTicket,
  submitRun,
  writeMeta,
  writeServerMeta,
  writeToken,
  type AccountState,
  type AuctionView,
  type BestiaryEntry,
  type SaveOutcome,
  type DiscoveryView,
  type LeaderboardView,
  type ProgressView,
  type BagState,
  type MaintenanceView,
  type SkillPrefView,
  type ConsumableView,
  type InventoryView,
  type RunResult,
  type RunVerdict,
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
import { MAX_SEED, createLocalTicket, type RunTicket } from './core/schemas'
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

/**
 * 서버로 메타를 올리기까지 미루는 시간(ms).
 *
 * 로컬 저장(400ms)보다 길다 — 네트워크를 타므로, 키를 칠 때마다 보내면 규칙 한 줄을
 * 고치는 동안 수십 번이 나간다.
 */
const META_PUSH_DELAY_MS = 1500

/** 1초. 자동 진행 카운트다운이 쓴다. */
const SECOND_MS = 1000

const PLAYER_SECTION = 'player'
const CPU_BUDGET_KEY = 'cpu_budget'
const RULE_SLOTS_KEY = 'rule_slots'

/** 상단 바의 층 표기. 층 진행(Phase 4)이 붙기 전까지는 1층 하나뿐이다. */
/**
 * 전투 화면 최상단의 층·실 표기.
 *
 * **층이 박혀 있었다.** 하강이 층을 넘어가는데 머리글은 늘 `1층` 이라고 적었다 — 화면에서
 * 가장 크게 적히는 자리가 거짓말을 하고 있었다.
 *
 * @param floor 지금 층.
 * @param roomId 지금 방.
 * @returns 「4층 · pillars」.
 */
export function formatLocation(floor: number, roomId: string): string {
  return `${String(floor)}층 · ${roomId}`
}

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
 * 출격 버튼을 잠글지 정한다.
 *
 * **기다리는 동안 잠근다.** 눌렀는데 아무 일도 없으면 사람은 다시 누르고, 그러면 티켓이
 * 둘 발급된다 — 하나는 안 쓴 채로 남아 티켓 상한만 먹는다.
 *
 * @param blocker 출격을 막는 사유. 빈 문자열이면 막는 것이 없다.
 * @param isLaunching 티켓을 기다리는 중인가.
 * @returns 잠가야 하면 true.
 */
export function checkLaunchLocked(blocker: string, isLaunching: boolean): boolean {
  return blocker !== '' || isLaunching
}

/**
 * 출격 버튼에 적을 글자를 고른다.
 *
 * @param isLaunching 티켓을 기다리는 중인가.
 * @returns 버튼 글자.
 */
export function formatLaunchLabel(isLaunching: boolean): string {
  return isLaunching ? '티켓 받는 중' : '출격'
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
    // **층도 서버가 정한다.** 기기가 정하면 1층으로 적어 보내 쉬운 판으로 검증받을 수
    // 있고, 반대로 안 받으면 화면만 1층으로 싸워 이긴 판이 진 것으로 확정된다.
    floor: issued.floor,
    // 층 하나에 드는 방 수. 방 순번에서 층을 파생한다 — 서버와 같은 값을 써야 한다.
    roomsPerFloor: issued.roomsPerFloor,
    ...(issued.loadout === undefined ? {} : { loadout: issued.loadout }),
    // 장비·레벨이 확정한 플레이어 전투 입력 (결정 #13).
  }
}

/** 한 층이 도는 방 수 (로드맵 W3). 하강은 층마다 이만큼씩 잇는다. */
export const CHAIN_LENGTH = 5

/**
 * 서버 없이 도는 판의 마지막 층.
 *
 * **서버가 정본이다.** 이 값은 티켓을 못 받았을 때만 쓴다 — `balance.json` 의
 * `floor_scale.max_floor` 와 같아야 하며, 갈리면 오프라인 판만 다른 깊이를 돈다.
 */
export const LOCAL_FLOOR_CAP = 10

/**
 * 이 판으로 런이 끝났는가.
 *
 * **끝나야만 정산한다.** 하강은 서른 방이고, 규칙을 고치러 갈 때마다 정산하면 티켓이
 * 소비되어 남은 층을 못 돈다 — 그것이 「방 3개까지만 진행하고 끝난다」의 반대편 실수다.
 *
 * @param outcome 방금 방의 판정.
 * @param nextRoom 다음 방의 setup. 없으면 하강이 끝났다.
 * @returns 끝났으면 true. 졌거나 더 갈 방이 없을 때다.
 */
export function checkRunOver(outcome: string, nextRoom: BattleSetup | undefined): boolean {
  return outcome !== OUTCOME_PLAYER_WIN || nextRoom === undefined
}

/**
 * 방금 끝낸 방이 그 층의 마지막인가 (로드맵 W14).
 *
 * **층을 깬 순간 보상을 준다.** 하강으로 바꾸면서 한 런이 방 30개가 됐는데, 정산이 런
 * 끝에 한 번뿐이면 죽거나 다 깨야만 보상을 받는다 — 주기가 열 배로 늘어난 셈이다.
 *
 * @param index 방금 끝낸 방의 순번. 0 부터 센다.
 * @param roomsPerFloor 층 하나에 드는 방 수. 0 이면 층 개념이 없다.
 * @returns 층을 깼으면 true.
 */
export function checkFloorCleared(index: number, roomsPerFloor: number): boolean {
  if (roomsPerFloor <= 0) {
    return false
  }
  return (index + 1) % roomsPerFloor === 0
}

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
export function buildChainPosition(roomId: string, floorCap = LOCAL_FLOOR_CAP): ChainPosition {
  // 층마다 방 셋. 로컬은 방을 굴려 고를 근거(서버 난수)가 없으므로 고른 방을 잇는다 —
  // **다만 길이는 하강과 같아야 한다.** 셋으로 끊으면 화면이 계속 1층이라고 말한다.
  const total = CHAIN_LENGTH * Math.max(1, floorCap)
  return { roomIds: Array.from({ length: total }, () => roomId), index: 0 }
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
  // 자동 진행. 남은 초가 `undefined` 면 안 돌고 있는 것이다.
  // **런을 살린 채 편집기를 본다.** 하강이 서른 방이라, 고치러 갈 때마다 런이 끝나면
  // 편집이 사실상 불가능해진다 — 방 사이에서 고칠 수 있다는 것이 이 게임의 고리다.
  const [isEditing, setEditing] = useState(false)
  // 티켓을 기다리는 중. **판을 미리 걸지 않는다** — 걸었다가 갈아 끼우면 첫 방이
  // 스킵된 것처럼 보인다.
  const [isLaunching, setLaunching] = useState(false)
  // 방금 정산한 층과 그 벌이. **전투 화면이 말한다** — 편집기로 나가야 보이면
  // 플레이 중에는 무엇을 벌었는지 알 수 없다.
  const [floorReward, setFloorReward] = useState({ floor: 0, reward: '' })
  const [autoLeft, setAutoLeft] = useState<number | undefined>(undefined)
  // **이번 방에서만 멈춘다.** 설정을 끄는 것과 다르다 — 한 번 멈추려고 기능을 끄게 하면
  // 다음 방부터도 안 넘어간다.
  const [isAutoStopped, setAutoStopped] = useState(false)
  const [isAutoOn, setAutoOn] = useState<boolean>(() => readAutoAdvance(getLocalStorage()))
  // 서버 연결 상태. 오프라인이어도 게임은 돈다 — 코어가 브라우저 안에서 직접 돌기
  // 때문이며, 서버는 보관과 검증을 맡을 뿐이다.
  const [account, setAccount] = useState<string | undefined>(undefined)
  const [profile, setProfile] = useState<AccountState | undefined>(undefined)
  const [isOnline, setOnline] = useState(false)
  // 서버가 확정한 판정. 브라우저가 낸 결과와 다르면 두 코어가 갈린 것이다 (G3).
  const [verdict, setVerdict] = useState<RunVerdict | undefined>(undefined)
  // 아이템은 **서버가 발급한다** (결정 #02). 화면은 받아서 보여줄 뿐이다.
  const [inventory, setInventory] = useState<InventoryView | undefined>(undefined)
  const [consumables, setConsumables] = useState<ConsumableView | undefined>(undefined)
  const [consumableDetail, setConsumableDetail] = useState('')
  const [upkeep, setUpkeep] = useState<MaintenanceView | undefined>(undefined)
  const [upkeepDetail, setUpkeepDetail] = useState('')
  const [skillPrefs, setSkillPrefs] = useState<SkillPrefView | undefined>(undefined)
  const [skillDetail, setSkillDetail] = useState('')
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
  // 서버가 준 코어 버전을 그대로 쓴다. 브라우저가 다시 조립하면 두 곳이 갈리고,
  // 갈린 티켓은 제출에서 거절된다. 번들로 돌 때는 팩이 스스로 조립한 값이다.
  const coreVersion = useMemo(() => ACTIVE.coreVersion, [])
  const problems = useMemo(
    () => validateRuleSet(ruleset, BLOCK_CATALOG, limits.cpuBudget, limits.ruleSlots),
    [ruleset, limits],
  )

  // 저장기는 앱이 사는 동안 하나다. 렌더마다 새로 만들면 앞선 예약이 사라져 디바운스가
  // "마지막 것 하나" 가 아니라 "아무것도 안 씀" 이 된다.
  const scheduler = useMemo(() => createSaveScheduler(getLocalStorage()), [])
  // **저장 실패가 조용하면 저장이 없는 것과 같다.** 지금까지 writeSave 의 결과를 아무도
  // 읽지 않아, 사파리 프라이빗 창처럼 저장소가 막힌 브라우저에서는 편집이 매번 사라지는데
  // 화면은 아무 말도 하지 않았다.
  const [saveState, setSaveState] = useState<SaveOutcome>('saved')
  // 저장을 몇 번 눌렀는지. 값 자체는 안 쓰고, **눌린 적이 있는가**만 본다 — 누른 적이
  // 없는데 "저장됨" 이 떠 있으면 그 표시는 아무 말도 하지 않는 것과 같다.
  const [savedAt, setSavedAt] = useState(0)
  // **튕겼다는 사실.** 다른 기기에서 로그인하면 이 기기의 토큰이 막히는데, 그것을
  // 조용히 넘기면 화면이 오프라인처럼 보인다 — 서버가 죽은 것과 내가 튕긴 것은 사람이
  // 해야 할 일이 다르다.
  const [isEvicted, setEvicted] = useState(false)

  useEffect(() => {
    scheduler.listen(setSaveState)
  }, [scheduler])

  // 토큰이 막히면 계정 연결만 끊는다. **이 기기의 저장은 안 지운다** — 튕긴 것은 내가
  // 고른 일이 아니고, 여기서 지우면 잃는 것이 하나 더 는다. 로그아웃은 내가 고른
  // 일이라 지운다.
  useEffect(() => {
    listenEviction(() => {
      setEvicted(true)
      setAccount(undefined)
      setProfile(undefined)
      setOnline(false)
      setAdmin(undefined)
      try {
        getLocalStorage()?.removeItem(TOKEN_STORAGE_KEY)
      } catch {
        // 지우기 실패도 화면을 막지 않는다.
      }
    })
  }, [])

  // 세션이 바뀔 때마다 예약한다. 화면을 떠날 때는 예약을 버리지 않고 즉시 쓴다 — 마지막
  // 편집이 400ms 안에 있었다는 이유로 사라지면 저장이 없는 것과 다르지 않다.
  useEffect(() => {
    scheduler.schedule(buildSessionSave(session))
  }, [scheduler, session])

  // **코드 라이브러리와 편집 중인 규칙표가 계정을 따라온다.**
  //
  // 예전에는 이 효과가 `session.presets` 만 보고 있었다. 초안은 규칙을 고칠 때마다
  // 바뀌는데 슬롯은 안 바뀌므로, **초안이 한 번도 서버로 안 올라갔다** — 기기를 바꾸면
  // 규칙이 사라진 것처럼 보인 진짜 이유가 이것이다.
  //
  // 네트워크를 타므로 로컬 저장보다 길게 미룬다. 키를 칠 때마다 보내면 규칙 한 줄을
  // 고치는 동안 수십 번이 나간다.
  useEffect(() => {
    if (account === undefined) {
      return undefined
    }
    const timer = setTimeout(() => {
      setMeta((current) => {
        const merged = applySessionToMeta(session, current)
        if (merged === current) {
          return current
        }
        writeMeta(getLocalStorage(), merged)
        void writeServerMeta(account, merged)
        return merged
      })
    }, META_PUSH_DELAY_MS)
    return () => {
      clearTimeout(timer)
    }
  }, [session, account])

  // 계정을 확보하고 서버 세이브를 합친다. **실패해도 아무 일도 일어나지 않는다** —
  // 서버가 없어도 게임은 돌아야 한다. 합치기는 최대값·합집합이라 몇 번을 해도 같은
  // 결과가 나온다(멱등).
  useEffect(() => {
    let isCurrent = true
    void (async () => {
      const storage = getLocalStorage()
      // **저장이 있었는지를 먼저 본다.** 새 기기는 저장이 없고, 그때만 서버의 초안을
      // 받는다 — 이미 짜던 것이 있으면 덮어쓰지 않는다.
      const hasSave = readSave(storage) !== undefined
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
        // 받은 슬롯과 초안을 편집기에도 싣는다. 이 기기에 있으면 손대지 않는다 —
        // 덮어쓰면 방금 만든 것이 사라지고 그 손실은 되돌릴 수 없다.
        setSession((live) => adoptDraft(adoptPresets(live, merged.presets), merged.draft, hasSave))
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
      if (outcome.detail !== '' && outcome.inventory === undefined) {
        setItemDetail(outcome.detail)
        return
      }
      // **가방만 다시 읽으면 「내 정보」가 옛 값으로 남는다.** 장착·해제·복구·봉인 해제는
      // 전부 캐릭터 시트의 숫자를 바꾸는데, 그 숫자는 `progress.loadout` 에서 온다 —
      // 응답이 실어 주는 것은 가방뿐이다.
      void readBagState(account).then((bag) => {
        if (bag.consumables !== undefined) {
          setConsumables(bag.consumables)
        }
      })
      void readItemContext(account).then((context) => {
        if (context.inventory !== undefined) {
          setInventory(context.inventory)
        }
        if (context.progress !== undefined) {
          setProgress(context.progress)
        }
      })
      if (outcome.detail !== '') {
        setItemDetail(outcome.detail)
      }
    })
  }

  /**
   * 소모품 칸을 조작한다.
   *
   * **로드아웃이 함께 바뀐다.** 칸이 실어 보내는 충전 수가 곧 이번 런에 들고 가는 것이라,
   * 「내 정보」의 소모품 줄이 여기서 갈린다.
   *
   * @param path `/consumable/load` 같은 경로.
   * @param body 보낼 절.
   */
  function applyConsumable(path: string, body: Record<string, unknown>): void {
    if (account === undefined) {
      return
    }
    setConsumableDetail('')
    void applyConsumableAction(account, path, body).then((outcome) => {
      if (outcome.view === undefined) {
        setConsumableDetail(outcome.detail)
        return
      }
      setConsumables(outcome.view)
      // 끼우면 가방에서 하나 빠지고, 팔면 지갑이 는다 — 가방 화면도 옛 값으로 두면 안 된다.
      refreshBag(account)
    })
  }

  /**
   * 가방과 소모품 칸을 함께 다시 읽는다.
   *
   * **둘은 한 몸이다.** 끼우면 가방에서 빠지고 칸이 차며, 팔면 가방이 줄고 지갑이 는다 —
   * 한쪽만 읽으면 다른 쪽이 옛 값으로 남는다. 마운트에서 칸을 안 읽어 패널이 「서버에
   * 닿지 못했다」로 굳어 있던 자리이기도 하다.
   *
   * @param token 기기 토큰.
   */
  function refreshBag(token: string): void {
    void readBagState(token).then(applyBagState)
  }

  /**
   * 읽어 온 가방 상태를 화면에 붙인다.
   *
   * @param bag 가방과 소모품 칸.
   */
  function applyBagState(bag: BagState): void {
    setInventory(bag.inventory)
    setConsumables(bag.consumables)
  }

  /**
   * 가방의 소모품 하나를 **빈 칸부터** 끼운다.
   *
   * **가방 행에서 바로 끼운다.** 칸을 고르라고 하면 어느 칸이 비었는지 사람이 세어야
   * 하고, 그 전에 소모품 칸 패널을 먼저 찾아야 한다 — 실제로 못 찾았다.
   *
   * @param catalogId 끼울 소모품.
   */
  function loadConsumableStack(catalogId: string): void {
    const target = findFreeConsumableSlot(consumables, catalogId)
    if (target === undefined) {
      setItemDetail('끼울 칸이 없다 — 소모품 칸에서 하나를 비워야 한다')
      return
    }
    applyConsumable('/consumable/load', {
      use_tag: target.useTag,
      slot_index: target.slotIndex,
      catalog_id: catalogId,
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
    refreshBag(account)
    // **관리자가 아니면 undefined 로 남는다.** 서버가 404 로 답하므로 관리자 경로가
    // 있다는 사실 자체가 일반 계정 화면에 드러나지 않는다.
    void readAdminOverview(account).then(setAdmin)
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
        refreshBag(account)
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
    // **가방과 칸을 함께 읽는다.** 여기서 가방만 읽어 소모품 칸이 영원히 「서버에
    // 닿지 못했다」로 굳어 있었다 — 칸은 뜨는데 아무것도 끼울 수 없었다.
    applyBagState(await readBagState(token))
    setBestiary(await readBestiary(token))
    setDiscovery(await readDiscovery(token))
    setProgress(await readProgress(token))
    setLeaderboard(await readLeaderboard(token))
    setAuction(await readAuction(token))
    // 관리자가 아니면 undefined 로 남는다 — 서버가 404 로 답한다.
    setAdmin(await readAdminOverview(token))
    setUpkeep(await readMaintenance(token))
    setSkillPrefs(await readSkillPrefs(token))
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
    // **로그인은 서버가 이긴다.** 이 기기에 있던 초안·슬롯은 다른 계정의 것이거나 옛
    // 것이고, 로그인은 "이 기기를 그 계정으로 만든다" 는 명시적 행동이다 — 여기서
    // 로컬을 지키면 모바일에서 짠 규칙이 컴퓨터에 안 보인다. 실제로 그렇게 보고됐다.
    setSession((live) => adoptAccount(live, next))
    // **계정이 통째로 바뀐다.** 레벨·CPU·가방·권한이 전부 다른 사람의 것이 되므로
    // 하나라도 안 읽으면 화면이 앞 계정의 값을 계속 보여준다.
    await loadAccountState(outcome.token)
    return ''
  }

  /**
   * 이 기기에서 로그아웃한다.
   *
   * **이 기기의 저장을 함께 지우고 화면을 처음 상태로 되돌린다.** 토큰만 지우면 다음
   * 사람이 이 기기를 열었을 때 앞사람의 규칙표를 보게 되고, 화면에도 그 값이 남는다.
   */
  function applyLogoutHere(): void {
    const storage = getLocalStorage()
    const held = account
    setAccount(undefined)
    setProfile(undefined)
    setOnline(false)
    setMeta(createEmptyMeta())
    setSession(
      createSession(undefined, {
        ruleset: buildInitialRuleSet(),
        roomId: INITIAL_ROOM_ID,
        seed: INITIAL_SEED,
      }),
    )
    setInventory(undefined)
    setProgress(undefined)
    setAdmin(undefined)
    if (held !== undefined) {
      void applyLogout(held, storage)
    }
  }

  /**
   * 지금 규칙표로 판을 시작한다. 방·시드·규칙표를 이 순간의 값으로 얼린다.
   */
  function startRun(): void {
    // **서버 티켓을 기다렸다 건다.** 예전에는 로컬 티켓으로 판을 먼저 걸고 서버 티켓이
    // 오면 갈아 끼웠는데, 그 순간 방과 시드가 바뀌어 **첫 방이 스킵된 것처럼** 보였다 —
    // 실제로 그렇게 신고됐다. 서버가 정본이면 정본이 올 때까지 판을 안 건다.
    setVerdict(undefined)
    setOutcome(OUTCOME_ONGOING)
    setPostState('auto')
    setEditing(false)
    setFloorReward({ floor: 0, reward: '' })
    if (account === undefined) {
      applyLocalRun()
      return
    }
    setLaunching(true)
    void requestTicket(account, session.roomId, session.seed).then((issued) => {
      setLaunching(false)
      if (issued === undefined) {
        // **서버가 없다고 게임이 멈추지 않는다.** 다만 로컬로 돈 판은 서버에 안 남으므로
        // G1 계측에서도 빠진다.
        applyLocalRun()
        return
      }
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
   * 서버 없이 도는 판을 건다.
   *
   * 로컬 티켓에는 스냅샷이 없다 — 지속 몬스터는 서버가 아는 것이다.
   */
  function applyLocalRun(): void {
    const local = createLocalTicket(session.seed, session.roomId, coreVersion)
    setRun({
      setup: {
        roomId: local.roomId,
        rulesetId: ruleset.rulesetId,
        seed: local.seed,
        // **로컬도 하강이다.** 여기만 방 셋짜리 한 층으로 두면 다른 게임이 돈다.
        chain: buildChainPosition(session.roomId),
        floor: local.floor,
        roomsPerFloor: CHAIN_LENGTH,
      },
      rulesets: new Map([[ruleset.rulesetId, ruleset]]),
      ticket: local,
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
        // **여기서도 층을 청구한다.** 0(전체)으로 보내면 서버가 하강 전체의 보상을 다시
        // 주고, 층마다 이미 받은 것이 두 번 나간다.
        resolveRoomFloor(
          run?.setup.floor ?? 1,
          run?.setup.chain?.index ?? 0,
          run?.setup.roomsPerFloor ?? 0,
        ),
      ).then((result) => {
        setVerdict(result)
        // 전리품과 화폐가 여기서 들어온다. 다시 읽어야 화면이 그것을 안다.
        refreshBag(account)
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
    // **층을 넘기 전에 그 층을 청구한다.** 넘고 나서 하면 순번이 이미 다음 층이라
    // 앞 층의 보상을 다음 층 것으로 적게 된다.
    if (
      recording !== undefined &&
      checkFloorCleared(run.setup.chain?.index ?? 0, run.setup.roomsPerFloor ?? 0)
    ) {
      applyFloorSettlement(recording)
    }
    setOutcome(OUTCOME_ONGOING)
    setPostState('auto')
    setAutoLeft(undefined)
    setEditing(false)
    // 멈춤은 **그 방에서만** 이다. 안 풀면 한 번 멈춘 뒤로 영영 안 넘어간다.
    setAutoStopped(false)
    setRun({ ...run, setup: next })
  }

  // **방을 비우면 저절로 넘어간다.** 다만 곧장은 아니다 — 방 사이는 규칙을 고치는 유일한
  // 창이고(GDD §2.2), 곧장 넘기면 "고치려고 했는데 이미 넘어가 있다" 가 된다. 몇 초를
  // 세어 보여 주고, 그동안 멈출 수 있다.
  //
  // 진 판에서는 안 넘어간다. `buildNextRoomSetup` 이 이긴 판에만 다음 방을 주므로
  // 여기서 판정을 다시 안 봐도 된다.
  useEffect(() => {
    const isEligible = checkShouldAutoAdvance({
      // **편집 중에는 안 넘어간다.** 규칙을 고치는 동안 뒤에서 방이 넘어가면, 돌아왔을 때
      // 내가 고친 규칙이 이미 지나간 방에 쓰인 것인지 알 수 없다.
      isFinished: !isEditing && !checkOngoing(outcome),
      hasNext: run !== undefined && buildNextRoomSetup(run.setup, outcome) !== undefined,
      isEnabled: isAutoOn,
      isStopped: isAutoStopped,
    })
    if (!isEligible) {
      setAutoLeft(undefined)
      return undefined
    }
    setAutoLeft(AUTO_ADVANCE_SECONDS)
    const timer = setInterval(() => {
      setAutoLeft((left) => (left === undefined ? undefined : left - 1))
    }, SECOND_MS)
    return () => {
      clearInterval(timer)
    }
  }, [outcome, run, isAutoOn, isAutoStopped, isEditing])

  // 세다가 0 이 되면 넘어간다. **세는 것과 넘어가는 것을 갈라 둔다** — 한 효과에 두면
  // 넘어가면서 상태가 바뀌고 그 바뀜이 다시 타이머를 세워, 방 하나를 건너뛴다.
  useEffect(() => {
    if (autoLeft !== undefined && autoLeft <= 0) {
      goToNextRoom()
    }
  })

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
  /**
   * 층을 깬 순간 그 층을 청구한다 (로드맵 W14).
   *
   * **정산이 런 끝까지 미뤄지던 자리다.** 하강으로 바꾸면서 한 런이 방 30개가 됐고, 보상
   * 주기가 3방에서 30방으로 늘어났다 — 죽거나 다 깨야만 받게 됐다.
   *
   * 결과를 보내는 것이 아니다. **서버가 그 층까지 처음부터 다시 돌려 확정한다** (T9).
   */
  function applyFloorSettlement(finishedRun: BattleRecording): void {
    const ticket = run?.ticket
    const setup = run?.setup
    if (account === undefined || ticket === undefined || setup === undefined) {
      return
    }
    if (ticket.ticketId.startsWith('local:')) {
      return
    }
    void submitRun(
      account,
      ticket.ticketId,
      buildRuleSetPayload(finishedRun.ruleset),
      ticket.coreVersion,
      resolveRoomFloor(setup.floor ?? 1, setup.chain?.index ?? 0, setup.roomsPerFloor ?? 0),
    ).then((result) => {
      if (result === undefined) {
        return
      }
      setVerdict(result)
      setFloorReward({
        floor: resolveRoomFloor(setup.floor ?? 1, setup.chain?.index ?? 0, setup.roomsPerFloor ?? 0),
        reward: result.reward,
      })
      // 층마다 들어오는 것이 있으므로 가방·성장·도감을 그때그때 다시 읽는다.
      void readBagState(account).then((bag) => {
        if (bag.consumables !== undefined) {
          setConsumables(bag.consumables)
        }
      })
      void readItemContext(account).then((context) => {
        if (context.inventory !== undefined) {
          setInventory(context.inventory)
        }
        if (context.progress !== undefined) {
          setProgress(context.progress)
        }
      })
      void readDiscovery(account).then(setDiscovery)
    })
  }

  function goToEditor(): void {
    // **런이 살아 있으면 정산하지 않는다.** 하강은 서른 방이라, 규칙을 고치러 갈 때마다
    // 런이 끝나면 편집이 사실상 불가능해진다 — 방 사이에서 고칠 수 있다는 것이 이 게임의
    // 고리다 (GDD §2.2). 티켓은 그대로 살아 있고 돌아오면 이어서 돈다.
    if (recording !== undefined && checkRunOver(recording.outcome, nextRoom)) {
      applyTutorialResult(recording.outcome, recording.playerHp)
      const result = {
        outcome: recording.outcome,
        ticks: recording.ticks,
        playerHp: recording.playerHp,
      }
      setSession((current) => applyRunResult(current, result))
      applyRunSettlement(recording)
      setRun(undefined)
    }
    setOutcome(OUTCOME_ONGOING)
    setEditing(true)
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
  // **얻은 것을 말한다.** 서버는 처음부터 보내고 있었는데 화면이 버리고 있었다. 아이템은
  // 이겨도 60% 로만 나오므로, 나왔다는 말이 없으면 안 나온 것과 구별되지 않는다 — 가방
  // 20칸에서 새 것을 찾아내는 사람은 없다.
  const rewardText = verdict?.reward ?? ''

  const launchControls = (
    <div className="launch">
      <EvictionNotice isEvicted={isEvicted} />
      {/* **돌던 판으로 돌아가는 문.** 규칙을 고치러 오면 런은 살아 있는데, 돌아갈 길이
          없으면 그 런은 버려진다 — 하강은 서른 방이라 잃는 것이 크다. */}
      {run === undefined || !isEditing ? null : (
        <Button
          size="sm"
          variant="primary"
          glyph="▶"
          title="고친 규칙으로 돌던 판을 이어서 본다"
          onClick={() => {
            setEditing(false)
          }}
        >
          이어서
        </Button>
      )}
      {/* **저장 버튼.** 편집은 400ms 뒤에 자동으로 저장되지만, 자동은 눈에 안 보이고
          안 보이는 것은 안 일어난 것과 구별되지 않는다. 눌러서 지금 쓰고, 그 결과를
          바로 옆에 적는다. */}
      <Button
        size="sm"
        variant="primary"
        glyph="▣"
        title="지금 저장한다 (편집은 자동으로도 저장된다)"
        onClick={() => {
          scheduler.flush()
          setSavedAt((count) => count + 1)
        }}
      >
        저장
      </Button>
      {saveState !== 'saved' || savedAt === 0 ? null : (
        <ValueExpr text="저장됨" size="sm" dim />
      )}
      {saveState === 'saved' ? null : (
        <GlyphState
          state="danger"
          size="sm"
          label={
            saveState === 'blocked'
              ? '저장 안 됨 — 이 브라우저가 저장을 막고 있다 (프라이빗 창?)'
              : '저장 안 됨 — 이 규칙표를 저장 형식으로 못 만든다'
          }
        />
      )}
      {resultText === '' ? null : <ValueExpr text={resultText} size="sm" dim />}
      {verdictText === '' ? null : <ValueExpr text={verdictText} size="sm" />}
      {rewardText === '' ? null : <GlyphState state="true" size="sm" label={rewardText} />}
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
        disabled={checkLaunchLocked(blocker, isLaunching)}
        title={blocker === '' ? '이 규칙표로 던전에 내보낸다' : blocker}
        onClick={startRun}
      >
        {/* **기다리는 중임을 말한다.** 눌렀는데 아무 일도 없으면 사람은 다시 누른다. */}
        {formatLaunchLabel(isLaunching)}
      </Button>
    </div>
  )

  // **이른 return 앞에서 구한다.** 뒤에 두면 편집기 가지에서 `goToEditor` 가 이 값을
  // 읽을 때 아직 초기화되지 않아 터진다.
  const nextRoom = run === undefined ? undefined : buildNextRoomSetup(run.setup, outcome)
  const roomFloor =
    run === undefined
      ? 1
      : resolveRoomFloor(
          run.setup.floor ?? 1,
          run.setup.chain?.index ?? 0,
          run.setup.roomsPerFloor ?? 0,
        )

  if (run === undefined || isEditing) {
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
                onLogout={() => {
                  applyLogoutHere()
                }}
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
                feePercent={auction?.feePercent ?? 0}
                onUnseal={(itemId) => {
                  applyItem('/item/unseal', { item_id: itemId })
                }}
                onList={(itemId, price) => {
                  // **경매에 걸면 가방과 지갑이 함께 바뀐다.** 아이템이 빠지고 수수료가
                  // 나가므로 둘 다 다시 읽어야 화면이 그것을 안다.
                  applyAuction('/auction/list', { item_id: itemId, price })
                  if (account !== undefined) {
                    refreshBag(account)
                  }
                }}
              />
              <SkillPanel
                view={skillPrefs}
                isOnline={isOnline}
                detail={skillDetail}
                onChange={(next) => {
                  if (account === undefined) {
                    return
                  }
                  // 낙관하지 않는다 — 서버가 확정한 값을 앉힌다 (정비 규칙과 같은 규율).
                  setSkillDetail('')
                  void saveSkillPrefs(account, next).then((outcome) => {
                    if (outcome.view === undefined) {
                      setSkillDetail(outcome.detail)
                      return
                    }
                    setSkillPrefs(outcome.view)
                  })
                }}
              />
              <MaintenancePanel
                view={upkeep}
                isOnline={isOnline}
                detail={upkeepDetail}
                onChange={(next) => {
                  if (account === undefined) {
                    return
                  }
                  // **낙관하지 않는다.** 서버가 저장한 값을 화면에 앉힌다 — 저장이
                  // 실패했는데 켜진 것으로 보이면, 껐다고 믿은 정비가 돈을 쓴다.
                  setUpkeepDetail('')
                  void saveMaintenance(account, next).then((outcome) => {
                    if (outcome.view === undefined) {
                      setUpkeepDetail(outcome.detail)
                      return
                    }
                    setUpkeep(outcome.view)
                  })
                }}
              />
              <ConsumablePanel
                view={consumables}
                isOnline={isOnline}
                detail={consumableDetail}
                onClear={(useTag, slotIndex) => {
                  applyConsumable('/consumable/clear', {
                    use_tag: useTag,
                    slot_index: slotIndex,
                  })
                }}
                onRefill={(useTag, slotIndex) => {
                  applyConsumable('/consumable/refill', {
                    use_tag: useTag,
                    slot_index: slotIndex,
                  })
                }}
                onSell={(catalogId) => {
                  applyConsumable('/consumable/sell', { catalog_id: catalogId, count: 1 })
                }}
                onLoadStock={(catalogId) => {
                  loadConsumableStack(catalogId)
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
              <TemplatePanel
                templates={RULE_TEMPLATES}
                catalog={BLOCK_CATALOG}
                cpuBudget={limits.cpuBudget}
                ruleSlots={limits.ruleSlots}
                onLoad={(next) => {
                  // 편집 한 단계로 쌓는다 — 되돌리기로 돌아간다. 공유 코드 불러오기와
                  // 같은 방식이라 "눌렀다가 내 것이 사라졌다" 가 되지 않는다.
                  setSession((current) => applyRuleSetEdit(current, next))
                }}
              />
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
            {/* **관리는 별도 페이지다** (`/admin.html`). 표와 격자가 폭을 다 써야 하는데
                서랍은 좁은 열이라 게임 UI 와 공간을 다퉜다. 여기엔 세계 현황과 개입만
                남긴다 — 판을 돌다 급히 볼 것들이다. */}
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
            <Panel title="콘텐츠·아이템 관리" tone="panel" padded>
              <ValueExpr text="별도 페이지에서 연다 — 표와 격자가 폭을 다 써야 한다" size="sm" dim />
              <a className="adm__link" href="/admin.html">
                관리 페이지 열기
              </a>
            </Panel>
          </>
        ),
      })
    }
    return tabs
  }

  const battleControls = (
    <div className="launch">
      {/* **지금 몇 층인지 말한다.** 하강은 층을 넘어가며 적이 세지는데, 그 사실을
          말하는 자리가 없으면 갑자기 어려워진 이유를 알 수 없다. */}
      <ValueExpr
        text={`${String(roomFloor)}층 · 방 ${String((run.setup.chain?.index ?? 0) % Math.max(1, run.setup.roomsPerFloor ?? CHAIN_LENGTH) + 1)}/${String(run.setup.roomsPerFloor ?? CHAIN_LENGTH)}`}
        size="sm"
      />
      <FloorRewardNotice floor={floorReward.floor} reward={floorReward.reward} />
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
        <>
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
          <AutoAdvanceNotice
            secondsLeft={autoLeft}
            roomNumber={(run.setup.chain?.index ?? 0) + 2}
            roomTotal={run.setup.chain?.roomIds.length ?? 1}
            onStop={() => {
              setAutoStopped(true)
            }}
          />
          {/* **끄기는 안내와 다른 일이다.** 멈춤은 이번 방만이고, 이것은 앞으로 계속이다.
              둘을 한 버튼에 두면 한 번 멈추려다 기능을 꺼 버린다. */}
          <Button
            size="sm"
            variant="ghost"
            glyph={isAutoOn ? '⏩' : '⏸'}
            title={
              isAutoOn
                ? '자동 진행을 끈다 — 방마다 눌러서 넘어간다'
                : '자동 진행을 켠다 — 이기면 몇 초 뒤 저절로 넘어간다'
            }
            onClick={() => {
              const next = !isAutoOn
              setAutoOn(next)
              writeAutoAdvance(getLocalStorage(), next)
            }}
          >
            자동 진행 {isAutoOn ? '켬' : '끔'}
          </Button>
        </>
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
          location={formatLocation(roomFloor, run.setup.roomId)}
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
