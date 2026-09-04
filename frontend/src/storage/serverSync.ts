/**
 * 검증 서버와의 동기화 (B단계).
 *
 * **서버가 없어도 게임은 돈다.** 코어가 브라우저 안에서 직접 도는 구조이므로 서버는
 * 보관과 검증을 맡을 뿐이고, 여기서 나는 오류는 전부 무시된다 — 네트워크가 끊겼다고
 * 규칙 편집이 막히면 사람은 서버가 아니라 게임을 잃는다.
 *
 * 계정은 익명이다. 첫 접속에 계정이 생기고 토큰이 기기에 저장된다. **토큰을 잃으면
 * 계정을 잃는다** — 승격 경로(이메일·OAuth)가 아이템과 거래 전에 필요하다.
 */
import type {
  RawRuleSet,
  RuleSet,
  MetaSave,
  MonsterSnapshot,
  PlayerLoadout,
  RawMonsterSnapshot,
  RawPlayerLoadout,
} from '../core/schemas'
import { parseRuleSet, parseLoadout, parseSnapshot, sortSnapshots } from '../core/schemas'
import { buildMetaPayload, parseMetaPayload, removeMeta } from './metaSave'
import { removeSave, type StorageLike } from './saveStore'

/** 기기 토큰을 담는 localStorage 열쇠. */
export const TOKEN_STORAGE_KEY = 'game.account-token'

/** 토큰이 안 통할 때의 상태 코드. */
const HTTP_UNAUTHORIZED = 401

/** 인증 헤더 이름. 서버의 `TOKEN_HEADER` 와 같아야 한다. */
export const TOKEN_HEADER = 'X-Game-Token'

/** API 뿌리. 프런트 nginx 가 같은 출처의 `/api/` 를 백엔드로 넘긴다. */
export const API_ROOT = '/api'

/** 요청 제한 시간. 서버가 느리다고 화면이 멈추면 안 된다. */
export const REQUEST_TIMEOUT_MS = 5000

/** 계정 상태. `loginId` 가 undefined 면 익명이다. */
export interface AccountState {
  readonly accountId: number
  readonly handle: string
  readonly loginId: string | undefined
}

/** 가입·로그인 결과. 실패 사유를 그대로 화면에 띄운다. */
export interface AuthOutcome {
  readonly account: AccountState | undefined
  readonly token: string | undefined
  readonly detail: string
}

/** 동기화 결과. 화면이 상태를 말해 줄 수 있게 사유를 함께 낸다. */
export interface SyncOutcome {
  readonly meta: MetaSave | undefined
  readonly isOnline: boolean
  readonly detail: string
}

/**
 * 토큰이 더 이상 안 통할 때 부를 곳.
 *
 * **다른 기기에서 로그인하면 이 기기의 토큰이 지워진다** (한 계정은 한 기기). 그때 이
 * 기기는 401 을 받는데, 그것을 조용히 넘기면 화면이 오프라인처럼 보인다 — 서버가 죽은
 * 것과 내가 튕긴 것은 사람이 해야 할 일이 다르다.
 */
let evictionWatcher: (() => void) | undefined = undefined

/**
 * 토큰이 막혔을 때 들을 곳을 정한다.
 *
 * @param watcher 들을 함수.
 */
export function listenEviction(watcher: () => void): void {
  evictionWatcher = watcher
}

/**
 * 이 요청이 토큰을 들고 갔는지 본다.
 *
 * **로그인 실패도 401 이다.** 토큰 없이 간 요청의 401 은 "자격증명이 틀렸다" 이지
 * "튕겼다" 가 아니다 — 가르지 않으면 비밀번호를 한 번 틀릴 때마다 튕겼다고 뜬다.
 *
 * @param init fetch 설정.
 * @returns 토큰 헤더가 있으면 true.
 */
function checkHasToken(init: RequestInit): boolean {
  const headers = init.headers as Record<string, string> | undefined
  return headers !== undefined && headers[TOKEN_HEADER] !== undefined
}

/**
 * 제한 시간이 붙은 요청을 보낸다.
 *
 * @param path `/api` 뒤의 경로.
 * @param init fetch 설정.
 * @returns 응답. 실패하면 undefined.
 */
export async function sendRequest(
  path: string,
  init: RequestInit,
): Promise<Response | undefined> {
  const controller = new AbortController()
  const timer = setTimeout(() => {
    controller.abort()
  }, REQUEST_TIMEOUT_MS)
  try {
    const response = await fetch(`${API_ROOT}${path}`, { ...init, signal: controller.signal })
    if (response.status === HTTP_UNAUTHORIZED && checkHasToken(init)) {
      evictionWatcher?.()
    }
    return response
  } catch {
    return undefined
  } finally {
    clearTimeout(timer)
  }
}

/**
 * 저장된 기기 토큰을 읽는다.
 *
 * @param storage 저장소.
 * @returns 토큰. 없으면 undefined.
 */
export function readToken(storage: StorageLike | undefined): string | undefined {
  try {
    return storage?.getItem(TOKEN_STORAGE_KEY) ?? undefined
  } catch {
    return undefined
  }
}

/**
 * 기기 토큰을 확보한다. 없으면 익명 계정을 새로 만든다.
 *
 * **토큰은 만들 때 한 번만 나온다.** 저장에 실패하면 그 계정은 영영 다시 못 쓰므로,
 * 저장이 실패하면 토큰을 돌려주지 않는다 — 쓸 수 없는 토큰으로 요청을 보내는 것보다
 * 오프라인으로 두는 편이 낫다.
 *
 * @param storage 저장소.
 * @returns 토큰. 서버에 닿지 못했거나 저장하지 못하면 undefined.
 */
export async function ensureToken(storage: StorageLike | undefined): Promise<string | undefined> {
  const existing = readToken(storage)
  if (existing !== undefined && existing !== '') {
    return existing
  }
  const response = await sendRequest('/account', { method: 'POST' })
  if (response === undefined || !response.ok) {
    return undefined
  }
  const body = (await response.json()) as { token?: string }
  const token = body.token
  if (typeof token !== 'string' || token === '') {
    return undefined
  }
  try {
    storage?.setItem(TOKEN_STORAGE_KEY, token)
  } catch {
    return undefined
  }
  return token
}

/**
 * 서버에 있는 메타 세이브를 읽는다.
 *
 * @param token 기기 토큰.
 * @returns 읽어 낸 세이브와 접속 상태.
 */
export async function readServerMeta(token: string): Promise<SyncOutcome> {
  const response = await sendRequest('/meta', { headers: { [TOKEN_HEADER]: token } })
  if (response === undefined) {
    return { meta: undefined, isOnline: false, detail: '서버에 닿지 못했다' }
  }
  if (!response.ok) {
    return { meta: undefined, isOnline: true, detail: `서버가 거절했다 (${response.status})` }
  }
  const body = (await response.json()) as { payload?: unknown }
  if (body.payload === null || body.payload === undefined) {
    return { meta: undefined, isOnline: true, detail: '서버에 세이브가 없다' }
  }
  try {
    return { meta: parseMetaPayload(body.payload), isOnline: true, detail: '' }
  } catch {
    // 읽지 못하는 세이브는 없는 것과 같이 다룬다. 여기서 던지면 화면이 뜨지 않는다.
    return { meta: undefined, isOnline: true, detail: '서버 세이브를 읽지 못했다' }
  }
}

/**
 * 메타 세이브를 서버에 쓴다.
 *
 * @param token 기기 토큰.
 * @param meta 저장할 세이브.
 * @returns 실제로 저장됐으면 true.
 */
export async function writeServerMeta(token: string, meta: MetaSave): Promise<boolean> {
  const response = await sendRequest('/meta', {
    method: 'PUT',
    headers: { [TOKEN_HEADER]: token, 'Content-Type': 'application/json' },
    body: JSON.stringify({ payload: buildMetaPayload(meta) }),
  })
  return response !== undefined && response.ok
}

/**
 * 응답 절에서 계정 상태를 읽는다.
 *
 * @param body 서버가 준 절.
 * @returns 계정 상태.
 */
function readAccountState(body: {
  account_id: number
  handle: string
  login_id?: string | null
}): AccountState {
  return {
    accountId: body.account_id,
    handle: body.handle,
    loginId: body.login_id ?? undefined,
  }
}

/**
 * 서버가 준 오류 사유를 꺼낸다.
 *
 * @param response 실패한 응답.
 * @returns 사람이 읽을 사유.
 */
export async function readErrorDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown }
    return typeof body.detail === 'string' ? body.detail : `서버가 거절했다 (${response.status})`
  } catch {
    return `서버가 거절했다 (${response.status})`
  }
}

/**
 * 지금 토큰이 가리키는 계정을 읽는다.
 *
 * @param token 기기 토큰.
 * @returns 계정 상태. 읽지 못하면 undefined.
 */
export async function readAccount(token: string): Promise<AccountState | undefined> {
  const response = await sendRequest('/account', { headers: { [TOKEN_HEADER]: token } })
  if (response === undefined || !response.ok) {
    return undefined
  }
  return readAccountState(
    (await response.json()) as { account_id: number; handle: string; login_id?: string | null },
  )
}

/**
 * 가입한다. 토큰을 함께 보내면 그 익명 계정이 **승격**된다.
 *
 * 승격이면 계정 id 가 바뀌지 않으므로 지금까지의 진행이 전부 따라온다. 그래서 화면은
 * "가입하면 잃지 않는다" 를 약속할 수 있다.
 *
 * @param loginId 아이디.
 * @param password 비밀번호.
 * @param token 지금 쓰는 기기 토큰. 없으면 새 계정이 생긴다.
 * @returns 계정과 토큰, 또는 실패 사유.
 */
export async function registerAccount(
  loginId: string,
  password: string,
  token: string | undefined,
): Promise<AuthOutcome> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token !== undefined) {
    headers[TOKEN_HEADER] = token
  }
  const response = await sendRequest('/register', {
    method: 'POST',
    headers,
    body: JSON.stringify({ login_id: loginId, password }),
  })
  if (response === undefined) {
    return { account: undefined, token: undefined, detail: '서버에 닿지 못했다' }
  }
  if (!response.ok) {
    return { account: undefined, token: undefined, detail: await readErrorDetail(response) }
  }
  const body = (await response.json()) as {
    account_id: number
    handle: string
    login_id?: string | null
    token?: string
  }
  return { account: readAccountState(body), token: body.token, detail: '' }
}

/**
 * 로그인해서 이 기기용 토큰을 받는다.
 *
 * **기존 기기는 튕기지 않는다.** 서버가 토큰을 지우지 않고 새로 하나 더 붙인다.
 *
 * @param loginId 아이디.
 * @param password 비밀번호.
 * @returns 계정과 새 토큰, 또는 실패 사유.
 */
export async function createLogin(loginId: string, password: string): Promise<AuthOutcome> {
  const response = await sendRequest('/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ login_id: loginId, password }),
  })
  if (response === undefined) {
    return { account: undefined, token: undefined, detail: '서버에 닿지 못했다' }
  }
  if (!response.ok) {
    return { account: undefined, token: undefined, detail: await readErrorDetail(response) }
  }
  const body = (await response.json()) as {
    account_id: number
    handle: string
    login_id?: string | null
    token?: string
  }
  return { account: readAccountState(body), token: body.token, detail: '' }
}

/**
 * 기기 토큰을 갈아 끼운다. 로그인 뒤에 부른다.
 *
 * @param storage 저장소.
 * @param token 새 토큰.
 * @returns 실제로 저장했으면 true.
 */
export function writeToken(storage: StorageLike | undefined, token: string): boolean {
  try {
    storage?.setItem(TOKEN_STORAGE_KEY, token)
    return true
  } catch {
    return false
  }
}

/** 서버가 발급한 티켓. 로컬 연습 티켓과 같은 모양이다. */
export interface ServerTicket {
  readonly ticketId: string
  readonly seed: number
  readonly roomId: string
  readonly floor: number
  /** 층 하나에 드는 방 수. 방 순번에서 층을 파생하는 데 쓴다. */
  readonly roomsPerFloor: number
  readonly mode: string
  readonly coreVersion: string
  /**
   * 이 런이 만날 지속 몬스터의 얼어붙은 상태.
   *
   * **전투에 반드시 넘겨야 한다.** 서버는 이것으로 재시뮬하므로, 넘기지 않으면 화면과
   * 서버가 다른 판을 돈다 (docs/설계/6_몬스터 §5).
   */
  readonly snapshots: readonly MonsterSnapshot[]
  /**
   * 장비·레벨이 확정한 전투 입력 (결정 #13).
   *
   * **전투에 반드시 넘겨야 한다.** 서버는 이것으로 재시뮬하므로, 넘기지 않으면 화면은
   * 맨몸으로 싸우고 서버는 장비를 낀 채로 계산한다.
   */
  readonly loadout: PlayerLoadout | undefined
  /**
   * 이 런이 도는 방들 (로드맵 W3).
   *
   * **서버가 이 목록대로 재시뮬한다.** 비면 브라우저는 세 방을 도는데 서버는 한 방만
   * 계산해, 이긴 판이 진 것으로 확정된다.
   */
  readonly roomIds: readonly string[]
}

/**
 * 서버에 티켓을 청한다.
 *
 * 연습 모드라 시드를 제안할 수 있다 — "이 시드 다시" 가 성립해야 하기 때문이며,
 * 순위에 반영되는 판이 생기면 그때는 서버가 정한 시드만 쓴다.
 *
 * @param token 기기 토큰.
 * @param roomId 방 id.
 * @param seed 제안할 시드. **없으면 서버가 굴린다** — 그것이 기본이고, 값이 있는
 *   경우는 사람이 「시드 고정」을 켠 때뿐이다. 서버는 연습 모드에서만 받아들인다.
 * @returns 발급된 티켓. 서버에 닿지 못했으면 undefined.
 */
export async function requestTicket(
  token: string,
  roomId: string,
  seed?: number,
): Promise<ServerTicket | undefined> {
  // **칸을 아예 만들지 않는다.** `seed: undefined` 를 넘겨도 JSON 에서는 사라지지만,
  // 그것에 기대면 다음 사람이 `null` 로 고쳤을 때 조용히 0번 시드가 된다.
  const wanted = seed === undefined ? {} : { seed }
  const response = await sendRequest('/ticket', {
    method: 'POST',
    headers: { [TOKEN_HEADER]: token, 'Content-Type': 'application/json' },
    body: JSON.stringify({ room_id: roomId, ...wanted }),
  })
  if (response === undefined || !response.ok) {
    return undefined
  }
  const body = (await response.json()) as {
    ticket_id: string
    seed: number
    room_id: string
    floor: number
    rooms_per_floor?: number
    mode: string
    core_version: string
    monster_snapshot?: RawMonsterSnapshot[]
    loadout?: RawPlayerLoadout | null
    room_ids?: string[]
  }
  return {
    ticketId: body.ticket_id,
    seed: body.seed,
    roomId: body.room_id,
    floor: body.floor,
    mode: body.mode,
    coreVersion: body.core_version,
    snapshots: sortSnapshots((body.monster_snapshot ?? []).map(parseSnapshot)),
    loadout: body.loadout ? parseLoadout(body.loadout) : undefined,
    // 구버전 서버는 목록을 주지 않는다. 그때는 방 하나짜리다 — 없는 것을 길이 3으로
    // 채우면 서버가 계산하지 않은 방을 브라우저가 돈다.
    roomIds: body.room_ids ?? [body.room_id],
    roomsPerFloor: body.rooms_per_floor ?? 0,
  }
}

/** 서버가 확정한 판정. 브라우저가 낸 결과와 다르면 두 코어가 갈린 것이다. */
export interface RunVerdict {
  readonly verdict: string
  readonly outcome: string
  readonly ticks: number
  readonly playerHp: number
  readonly detail: string
  /**
   * 이 판으로 무엇을 얻었는가 — 화폐·아이템·경험치·몬스터 변화.
   *
   * **서버가 처음부터 보내고 있었는데 이 계층이 버리고 있었다.** 아이템은 이겨도 60%
   * 로만 나오므로, 나왔다는 말이 없으면 안 나온 것과 구별되지 않는다. 가방을 열어
   * 20칸에서 새 것을 찾아내는 사람은 없다.
   */
  readonly reward: string
}

/**
 * 판을 제출한다. **결과를 보내지 않는다** — 서버가 다시 계산한다.
 *
 * 실패는 무시한다. 제출이 안 됐다고 판이 무효가 되면, 네트워크가 끊긴 사람은 게임을
 * 할 수 없다. 다만 그 판은 서버 기록에 남지 않으므로 G1 계측에서도 빠진다.
 *
 * @param token 기기 토큰.
 * @param ticketId 이 판의 티켓.
 * @param ruleset 이 판에 쓴 규칙표 절.
 * @param coreVersion 이 클라이언트의 코어 버전.
 * @returns 서버가 확정한 판정. 닿지 못했으면 undefined.
 */
export async function submitRun(
  token: string,
  ticketId: string,
  ruleset: unknown,
  coreVersion: string,
  floor = 0,
): Promise<RunVerdict | undefined> {
  const response = await sendRequest('/run', {
    method: 'POST',
    headers: { [TOKEN_HEADER]: token, 'Content-Type': 'application/json' },
    // **`floor` 는 「어디까지 확인해 달라」는 주장이다.** 서버가 그 층까지 처음부터 다시
    // 돌려 확정하므로 결과를 보내는 것이 아니다. 0 은 하강 전체다.
    body: JSON.stringify({ ticket_id: ticketId, ruleset, core_version: coreVersion, floor }),
  })
  if (response === undefined || !response.ok) {
    return undefined
  }
  const body = (await response.json()) as {
    verdict: string
    outcome: string
    ticks: number
    player_hp: number
    detail?: string
    reward?: string
  }
  return {
    verdict: body.verdict,
    outcome: body.outcome,
    ticks: body.ticks,
    playerHp: body.player_hp,
    detail: body.detail ?? '',
    reward: body.reward ?? '',
  }
}

/** 요구조건 한 줄. 실측값을 함께 받는다 — 무엇이 얼마나 모자란지가 화면에 있어야 한다. */
export interface RequirementView {
  readonly stat: string
  readonly actual: number
  readonly minimum: number
  readonly isMet: boolean
}

/** 아이템 하나. */
export interface ItemView {
  readonly itemId: number
  readonly catalogId: string
  readonly labelKo: string
  readonly kind: string
  readonly slot: string | null
  readonly hands: string | null
  readonly equippedSlot: string | null
  readonly isBroken: boolean
  /**
   * 거래 후 귀속 (결정 #07). 산 물건은 다시 팔 수 없다.
   *
   * **팔기 전에 보여야 한다** — 모르면 걸다가 거절당하고, 그때는 이미 "왜 안 되지" 를
   * 겪은 뒤다.
   */
  readonly isBound: boolean
  /**
   * 몬스터에게 빼앗겼다가 되찾은 것인가 (`설계/6_몬스터` §5).
   *
   * 잃은 것과 되찾은 것이 가방에서 같아 보이면, 되찾으러 간 런이 아무 흔적도 남기지
   * 않는다. World Loop 의 동기는 그 흔적에서 나온다.
   */
  readonly isRecovered: boolean
  /**
   * 남은 봉인 칸 (설계/4_아이템 §17).
   *
   * **무엇이 들어올지는 안 온다.** 오면 열기 전에 아는 것이 되어 열 이유가 사라진다 —
   * 서버가 열 때 굴린다.
   */
  readonly sealedSlots: number
  /** 다음 칸을 여는 값. 화면이 다시 계산하면 두 곳이 갈린다. */
  readonly unsealCost: number
  /** 굴린 등급. 봉인 칸 수가 여기서 나온다. */
  readonly grade: string
  /**
   * 무기가 정하는 사거리 (§2.2). 0 은 「안 정한다」다.
   *
   * **가방에서 보여야 한다.** 사거리를 접사에서 필드로 올리면서 한 번 안 보이게 됐다 —
   * 접사였을 때는 「먼 사거리 +3」 으로 뜨던 것이 필드가 된 순간 어느 화면에도 안 남았다.
   */
  readonly attackRange: number
  /**
   * 이 아이템이 실제로 주는 것.
   *
   * **끼기 전에 보여야 한다** — 무엇을 주는지 모르고 끼우면 캐릭터 시트를 보고 나서야
   * 알게 되고, 그때는 이미 다른 것을 벗은 뒤다.
   */
  readonly affixes: readonly AffixView[]
  readonly requirements: readonly RequirementView[]
  readonly canEquip: boolean
}

/** 접사 하나. 고정 합계에 붙거나 퍼센트에 붙는다. */
export interface AffixView {
  readonly stat: string
  readonly flat: number
  readonly percent: number
  readonly labelKo: string
  /**
   * 능력치의 한글 이름. **서버가 실어 보낸다.**
   *
   * 화면이 제 목록을 들고 있으면 정본이 둘이 되고, 서버가 아는 이름이 늘어도 화면은 옛
   * 이름으로 그린다 — 접사 stat 목록을 서버가 보내기로 한 것과 같은 자리다.
   */
  readonly statLabel: string
}

/** 인벤토리 한 칸 또는 장비 한 자리. */
export interface SlotView {
  readonly slotIndex: number
  readonly item: ItemView | null
  readonly slot: string | null
  /** 양손무기가 막은 자리. 서버가 계산해서 준다 — 저장된 상태가 아니다. */
  readonly isSealed: boolean
  /**
   * 쌓인 소모품. 아이템 인스턴스가 아니라 **카탈로그 id + 개수**다.
   *
   * 개수를 안 보여주면 물약이 1개인지 9개인지 모르고 규칙표를 짠다 — `USE_ITEM` 이
   * 몇 번 돌 수 있는지가 규칙 설계의 입력이다 (#54).
   */
  readonly stackCatalogId: string | null
  readonly stackCount: number
  /** 쌓인 소모품의 한글 이름. 비어 있으면 소모품 칸이 아니다. */
  readonly stackLabelKo: string
  /** 쌓인 소모품의 등급. 가방에서도 색이 갈려야 한다. */
  readonly stackGrade: string
  /** 쌓인 소모품의 쓰임새. 어느 칸에 끼울 수 있는지가 여기서 나온다. */
  readonly stackUseTag: string
}

/** 인벤토리·장비·지갑. */
export interface InventoryView {
  readonly slots: readonly SlotView[]
  readonly equipment: readonly SlotView[]
  readonly balance: number
  readonly repairCost: number
}

interface RawRequirement {
  stat: string
  actual: number
  minimum: number
  is_met: boolean
}

/** 서버가 보내는 접사 절. `stat_label` 은 능력치의 한글 이름이다. */
export interface RawAffix {
  stat: string
  flat: number
  percent: number
  label_ko: string
  stat_label?: string
}

/**
 * 서버가 보낸 접사 절들을 화면 값으로 만든다.
 *
 * **한 곳에 둔다.** 같은 매핑이 가방·경매·소모품에 흩어져 있었고, 그 상태에서 서버가
 * 필드를 하나 늘리면 **고친 화면에서만** 보인다 — `stat_label` 이 없던 시절 경매장에서만
 * 영어 키가 새던 것이 정확히 그 모양이었다.
 *
 * @param raw 서버가 보낸 절들. 없으면 빈 배열이다.
 * @returns 화면이 읽을 접사들.
 */
export function readAffixRows(raw: readonly RawAffix[] | undefined): readonly AffixView[] {
  return (raw ?? []).map((affix) => ({
    stat: affix.stat,
    flat: affix.flat,
    percent: affix.percent,
    labelKo: affix.label_ko,
    // 서버가 한글 이름을 안 실어 보낸 경로가 남아 있다. 그때는 영어 키가 낫다 —
    // 빈 문자열이면 줄이 통째로 사라져 「접사가 없다」로 읽힌다.
    statLabel: affix.stat_label ?? affix.stat,
  }))
}

interface RawItem {
  item_id: number
  catalog_id: string
  label_ko: string
  kind: string
  slot: string | null
  hands: string | null
  equipped_slot: string | null
  is_broken: boolean
  is_bound?: boolean
  is_recovered?: boolean
  sealed_slots?: number
  unseal_cost?: number
  grade?: string
  affixes?: RawAffix[]
  attack_range?: number
  requirements: RawRequirement[]
  can_equip: boolean
}

interface RawSlot {
  slot_index: number
  item: RawItem | null
  slot: string | null
  is_sealed: boolean
  stack_catalog_id?: string | null
  stack_count?: number
  stack_label_ko?: string
  stack_grade?: string
  stack_use_tag?: string
}

/**
 * 응답 절을 화면이 쓰는 모양으로 옮긴다.
 *
 * @param raw 서버가 준 칸.
 * @returns 화면용 칸.
 */
function readSlot(raw: RawSlot): SlotView {
  return {
    slotIndex: raw.slot_index,
    slot: raw.slot,
    isSealed: raw.is_sealed,
    stackCatalogId: raw.stack_catalog_id ?? null,
    stackCount: raw.stack_count ?? 0,
    stackLabelKo: raw.stack_label_ko ?? '',
    stackGrade: raw.stack_grade ?? '',
    stackUseTag: raw.stack_use_tag ?? '',
    item:
      raw.item === null
        ? null
        : {
            itemId: raw.item.item_id,
            catalogId: raw.item.catalog_id,
            labelKo: raw.item.label_ko,
            kind: raw.item.kind,
            slot: raw.item.slot,
            hands: raw.item.hands,
            equippedSlot: raw.item.equipped_slot,
            isBroken: raw.item.is_broken,
            isBound: raw.item.is_bound ?? false,
            isRecovered: raw.item.is_recovered ?? false,
            sealedSlots: raw.item.sealed_slots ?? 0,
            unsealCost: raw.item.unseal_cost ?? 0,
            grade: raw.item.grade ?? '',
            attackRange: raw.item.attack_range ?? 0,
            affixes: readAffixRows(raw.item.affixes),
            canEquip: raw.item.can_equip,
            requirements: raw.item.requirements.map((item) => ({
              stat: item.stat,
              actual: item.actual,
              minimum: item.minimum,
              isMet: item.is_met,
            })),
          },
  }
}

/**
 * 인벤토리 응답 절을 화면 모양으로 옮긴다.
 *
 * 라우트에서 떼어 낸 이유는 **관리 화면이 봇의 가방을 같은 모양으로 읽어야** 하기
 * 때문이다. 거기서 따로 옮기면 두 화면이 다른 것을 그린다.
 *
 * @param raw 서버 응답.
 * @returns 인벤토리.
 */
export function readInventoryPayload(raw: Record<string, unknown>): InventoryView {
  const body = raw as unknown as {
    slots: RawSlot[]
    equipment: RawSlot[]
    balance: number
    repair_cost: number
  }
  return {
    slots: body.slots.map(readSlot),
    equipment: body.equipment.map(readSlot),
    balance: body.balance,
    repairCost: body.repair_cost,
  }
}

/**
 * 내 인벤토리를 읽는다.
 *
 * @param token 기기 토큰.
 * @returns 인벤토리. 서버에 닿지 못했으면 undefined.
 */
export async function readInventory(token: string): Promise<InventoryView | undefined> {
  const response = await sendRequest('/inventory', { headers: { [TOKEN_HEADER]: token } })
  if (response === undefined || !response.ok) {
    return undefined
  }
  return readInventoryPayload((await response.json()) as Record<string, unknown>)
}

/**
 * 아이템을 조작한다. 성공하면 갱신된 인벤토리가 돌아온다.
 *
 * @param token 기기 토큰.
 * @param path `/equip` 같은 경로.
 * @param body 보낼 절.
 * @returns 갱신된 인벤토리와 사유. 실패하면 인벤토리가 undefined 다.
 */
export async function applyItemAction(
  token: string,
  path: string,
  body: Record<string, unknown>,
): Promise<{ inventory: InventoryView | undefined; detail: string }> {
  const response = await sendRequest(path, {
    method: 'POST',
    headers: { [TOKEN_HEADER]: token, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (response === undefined) {
    return { inventory: undefined, detail: '서버에 닿지 못했다' }
  }
  if (!response.ok) {
    return { inventory: undefined, detail: await readErrorDetail(response) }
  }
  const raw = (await response.json()) as {
    slots?: RawSlot[]
    equipment?: RawSlot[]
    balance?: number
    repair_cost?: number
  }
  if (raw.slots === undefined) {
    return { inventory: undefined, detail: '' }
  }
  return {
    inventory: {
      slots: raw.slots.map(readSlot),
      equipment: (raw.equipment ?? []).map(readSlot),
      balance: raw.balance ?? 0,
      repairCost: raw.repair_cost ?? 0,
    },
    detail: '',
  }
}

/** 도감 한 줄. 규칙표를 **요약 없이** 받는다 — 원문이 카운터 설계의 입력이다. */
export interface BestiaryEntry {
  readonly recordId: number
  readonly labelKo: string
  readonly tier: string
  readonly level: number
  readonly levelCap: number
  readonly zoneFloor: number
  readonly entitySlot: string
  /**
   * 이 개체의 규칙표. **줄 수가 아니라 규칙표 그대로다.**
   *
   * 요약하면 카운터를 설계할 수 없다 (`설계/6_몬스터` §8) — 도감이 표적 목록인 이유가
   * 이것이고, 예전에는 클라이언트가 `rules.length` 로 접어 버려 그 뜻이 사라져 있었다.
   */
  readonly ruleset: RuleSet | undefined
  /** 얼마나 센가. 규칙표만으로는 "어떻게 싸우는가" 만 알 수 있다. */
  readonly hpMax: number
  readonly attack: number
  readonly defense: number
  readonly affixes: readonly string[]
  readonly trophies: readonly string[]
  /** 이 개체가 내 아이템을 들고 있는가. 되찾으러 가는 동기가 여기서 나온다. */
  readonly holdsMine: boolean
}

interface RawBestiaryEntry {
  record_id: number
  label_ko: string
  tier: string
  level: number
  level_cap: number
  zone_floor: number
  entity_slot: string
  ruleset: RawRuleSet | null
  affixes: { label_ko: string }[]
  trophies: string[]
  holds_mine: boolean
  hp_max?: number
  attack?: number
  defense?: number
}

/**
 * 도감을 읽는다.
 *
 * @param token 기기 토큰.
 * @returns 도감 줄들. 서버에 닿지 못했으면 undefined.
 */
export async function readBestiary(token: string): Promise<readonly BestiaryEntry[] | undefined> {
  const response = await sendRequest('/bestiary', { headers: { [TOKEN_HEADER]: token } })
  if (response === undefined || !response.ok) {
    return undefined
  }
  const body = (await response.json()) as { entries: RawBestiaryEntry[] }
  return body.entries.map((raw) => ({
    recordId: raw.record_id,
    labelKo: raw.label_ko,
    tier: raw.tier,
    level: raw.level,
    levelCap: raw.level_cap,
    zoneFloor: raw.zone_floor,
    entitySlot: raw.entity_slot,
    ruleset: raw.ruleset === null ? undefined : parseRuleSet(raw.ruleset),
    hpMax: raw.hp_max ?? 0,
    attack: raw.attack ?? 0,
    defense: raw.defense ?? 0,
    affixes: raw.affixes.map((item) => item.label_ko),
    trophies: raw.trophies,
    holdsMine: raw.holds_mine,
  }))
}

/** 도감 한 줄. 밝혔든 아니든 자리는 있다. */
export interface DiscoveryRow {
  readonly kind: string
  readonly refId: string
  readonly labelKo: string
  readonly category: string
  readonly isFound: boolean
  /**
   * 속살. **밝힌 것만 채워져 온다** — 화면이 가리는 것이 아니라 응답에 없다.
   *
   * 화면에서 가리면 개발자 도구를 열었을 때 답이 그대로 보이고, 그러면 가린 것이 아니다.
   */
  readonly detail: string
}

/** 도감 한 화면. */
export interface DiscoveryView {
  readonly items: readonly DiscoveryRow[]
  readonly skills: readonly DiscoveryRow[]
  readonly found: number
  readonly total: number
}

interface RawDiscoveryRow {
  kind: string
  ref_id: string
  label_ko: string
  category?: string
  is_found?: boolean
  detail?: string
}

/**
 * 도감 한 줄을 옮긴다.
 *
 * @param raw 서버가 보낸 줄.
 * @returns 화면이 읽는 줄.
 */
function readDiscoveryRow(raw: RawDiscoveryRow): DiscoveryRow {
  return {
    kind: raw.kind,
    refId: raw.ref_id,
    labelKo: raw.label_ko,
    category: raw.category ?? '',
    isFound: raw.is_found ?? false,
    detail: raw.detail ?? '',
  }
}

/**
 * 내 도감을 읽는다.
 *
 * @param token 기기 토큰.
 * @returns 도감. 서버에 닿지 못했으면 undefined.
 */
export async function readDiscovery(token: string): Promise<DiscoveryView | undefined> {
  const response = await sendRequest('/discovery', { headers: { [TOKEN_HEADER]: token } })
  if (response === undefined || !response.ok) {
    return undefined
  }
  const body = (await response.json()) as {
    items: RawDiscoveryRow[]
    skills: RawDiscoveryRow[]
    found?: number
    total?: number
  }
  return {
    items: body.items.map(readDiscoveryRow),
    skills: body.skills.map(readDiscoveryRow),
    found: body.found ?? 0,
    total: body.total ?? 0,
  }
}

/** 플레이어 성장. 레벨이 표현력(상한 있음)과 능력치 포인트(상한 없음)를 함께 준다. */
export interface ProgressView {
  readonly level: number
  readonly totalXp: number
  readonly remainingXp: number
  readonly nextXp: number
  readonly stats: Readonly<Record<string, number>>
  readonly statKeys: readonly string[]
  readonly statPoints: number
  readonly spentPoints: number
  readonly bonusRuleSlots: number
  readonly bonusCpu: number
  /**
   * 여기까지 내려가 봤다 (설계/6_몬스터 §3).
   *
   * **서버만 올린다.** 화면이 정하면 1층 캐릭터로 10층 보상을 뽑는다.
   */
  readonly reachedFloor: number
  /** 마지막 층. 「7 / 10」 을 그리려면 끝을 알아야 한다. */
  readonly floorCap: number
  /**
   * 지금 이 캐릭터의 확정 전투 입력.
   *
   * **에디터가 CPU·슬롯 한도를 여기서 읽는다.** 기본값으로 두면 레벨·장비로 늘어난
   * 한도가 화면에 안 보이고, 보이더라도 서버가 기본값으로 검증해 제출이 반려된다 —
   * 규칙 검증은 화면과 서버가 **같은 한도**를 봐야 한다.
   */
  readonly loadout: PlayerLoadout | undefined
}

/** 순위표 한 줄. */
export interface RankEntry {
  readonly rank: number
  readonly handle: string
  readonly score: number
  readonly level: number
  readonly accountId: number
}

/** 순위표. `coreVersion` 이 시즌 이름이다 (결정 #06). */
export interface LeaderboardView {
  readonly coreVersion: string
  readonly entries: readonly RankEntry[]
}

/** 경매 매물 한 건. */
export interface ListingView {
  readonly listingId: number
  readonly itemId: number
  readonly labelKo: string
  readonly price: number
  readonly isMine: boolean
  /**
   * 사기 전에 알아야 하는 것들.
   *
   * 이름과 값만 보고 사면 같은 「장궁」이라도 무엇이 붙어 있는지 모른다 — 저주 접사는
   * 음수이므로 그것을 모르고 사면 돈을 내고 약해진다.
   */
  readonly affixes: readonly AffixView[]
  /** 남은 시간(분). 절대 시각이 아니라 남은 양이라 기기 시계가 어긋나도 같다. */
  readonly expiresInMinutes: number
  readonly fee: number
  /**
   * 어느 자리 물건인가.
   *
   * **이것이 없으면 「지금 낀 것과 견주기」를 할 수 없다** — 견줄 상대를 못 찾는다.
   * 서버는 카탈로그에서 이미 알고 있었고 안 보내고 있었다.
   */
  readonly slot: string
  /** 급. 가방 격자가 이름을 등급색으로 칠하는데 매물만 그 색을 못 쓰고 있었다. */
  readonly grade: string
  /**
   * 무기가 정하는 사거리 (§2.2). 0 은 「안 정한다」다.
   *
   * **접사가 아니라 필드라 견줌에서 빠져 있었다.** 매물의 접사만 견주면 활과 단검을
   * 바꿔도 화면이 「달라지는 것이 없다」라고 적는다 — 사거리는 접사 목록에 없으니까.
   */
  readonly attackRange: number
}

/** 경매장. 수수료율을 함께 받는다 — 걸기 전에 얼마가 나가는지 알아야 한다. */
export interface AuctionView {
  readonly listings: readonly ListingView[]
  readonly balance: number
  readonly feePercent: number
}

/**
 * 내 성장 상태를 읽는다.
 *
 * @param token 기기 토큰.
 * @returns 성장 상태. 서버에 닿지 못했으면 undefined.
 */
/** 아이템을 조작한 직후의 화면 상태. 가방과 성장이 **한 사건에서 함께** 바뀐다. */
export interface ItemContext {
  readonly inventory: InventoryView | undefined
  readonly progress: ProgressView | undefined
}

/**
 * 아이템을 조작한 뒤 화면이 다시 읽어야 할 것을 한꺼번에 읽는다.
 *
 * **둘을 묶어 두는 것이 요점이다.** 장착·해제·복구·봉인 해제는 전부 가방과 **캐릭터 시트**를
 * 동시에 바꾸는데, 예전에는 가방만 다시 읽어서 낀 것을 바꿔도 「내 정보」의 숫자가 옛 값
 * 그대로 남았다 — 따로 읽으면 하나만 읽는 날이 온다.
 *
 * @param token 기기 토큰.
 * @returns 가방과 성장. 서버에 못 닿으면 각각 undefined 다.
 */
export async function readItemContext(token: string): Promise<ItemContext> {
  const [inventory, progress] = await Promise.all([readInventory(token), readProgress(token)])
  return { inventory, progress }
}

export async function readProgress(token: string): Promise<ProgressView | undefined> {
  const response = await sendRequest('/progress', { headers: { [TOKEN_HEADER]: token } })
  if (response === undefined || !response.ok) {
    return undefined
  }
  return readProgressPayload((await response.json()) as Record<string, unknown>)
}

/** 서버가 보내는 성장 절. */
interface RawProgress {
  level: number
  total_xp: number
  remaining_xp: number
  next_xp: number
  stats: Record<string, number>
  stat_keys: string[]
  stat_points: number
  spent_points: number
  bonus_rule_slots: number
  bonus_cpu: number
  reached_floor?: number
  floor_cap?: number
  loadout?: RawPlayerLoadout | null
}

/**
 * 성장 절을 화면 값으로 만든다.
 *
 * **라우트에서 갈라 냈다.** 관리 화면이 봇의 성장을 같은 모양으로 읽어야 하는데, 매핑이
 * 라우트 안에 갇혀 있으면 그쪽이 제 것을 하나 더 만들게 된다 — 봇 가방이 한 번 그렇게
 * 갈렸고, 그때 「봇에게 뭐가 있지」를 답하려던 화면이 답을 틀리게 했다.
 *
 * @param raw 서버가 보낸 절.
 * @returns 화면이 읽을 성장 상태.
 */
export function readProgressPayload(raw: Record<string, unknown>): ProgressView {
  const body = raw as unknown as RawProgress
  return {
    level: body.level,
    totalXp: body.total_xp,
    remainingXp: body.remaining_xp,
    nextXp: body.next_xp,
    stats: body.stats,
    statKeys: body.stat_keys,
    statPoints: body.stat_points,
    spentPoints: body.spent_points,
    bonusRuleSlots: body.bonus_rule_slots,
    bonusCpu: body.bonus_cpu,
    reachedFloor: body.reached_floor ?? 1,
    floorCap: body.floor_cap ?? 1,
    loadout: body.loadout ? parseLoadout(body.loadout) : undefined,
  }
}

/**
 * 순위표를 읽는다. 토큰이 없어도 볼 수 있다 — 순위표는 공개다.
 *
 * @param token 기기 토큰.
 * @returns 순위표. 서버에 닿지 못했으면 undefined.
 */
export async function readLeaderboard(token: string): Promise<LeaderboardView | undefined> {
  const response = await sendRequest('/leaderboard', { headers: { [TOKEN_HEADER]: token } })
  if (response === undefined || !response.ok) {
    return undefined
  }
  const body = (await response.json()) as {
    core_version: string
    entries: { rank: number; handle: string; score: number; level: number; account_id: number }[]
  }
  return {
    coreVersion: body.core_version,
    entries: body.entries.map((item) => ({
      rank: item.rank,
      handle: item.handle,
      score: item.score,
      level: item.level,
      accountId: item.account_id,
    })),
  }
}

/**
 * 응답 절을 경매장 화면 모양으로 옮긴다.
 *
 * @param raw 서버가 준 절.
 * @returns 경매장.
 */
function readAuctionBody(raw: {
  listings: {
    listing_id: number
    item_id: number
    label_ko: string
    price: number
    is_mine: boolean
    affixes?: RawAffix[]
    expires_in_minutes?: number
    fee?: number
    slot?: string
    grade?: string
    attack_range?: number
  }[]
  balance: number
  fee_percent: number
}): AuctionView {
  return {
    listings: raw.listings.map((item) => ({
      listingId: item.listing_id,
      itemId: item.item_id,
      labelKo: item.label_ko,
      price: item.price,
      affixes: readAffixRows(item.affixes),
      expiresInMinutes: item.expires_in_minutes ?? 0,
      fee: item.fee ?? 0,
      isMine: item.is_mine,
      slot: item.slot ?? '',
      grade: item.grade ?? '',
      attackRange: item.attack_range ?? 0,
    })),
    balance: raw.balance,
    feePercent: raw.fee_percent,
  }
}

/**
 * 경매장을 읽는다.
 *
 * @param token 기기 토큰.
 * @returns 매물 목록. 서버에 닿지 못했으면 undefined.
 */
export async function readAuction(token: string): Promise<AuctionView | undefined> {
  const response = await sendRequest('/auction', { headers: { [TOKEN_HEADER]: token } })
  if (response === undefined || !response.ok) {
    return undefined
  }
  return readAuctionBody(await response.json())
}

/**
 * 경매장을 조작한다.
 *
 * @param token 기기 토큰.
 * @param path `/auction/list` 같은 경로.
 * @param body 보낼 절.
 * @returns 갱신된 경매장과 사유.
 */
export async function applyAuctionAction(
  token: string,
  path: string,
  body: Record<string, unknown>,
): Promise<{ auction: AuctionView | undefined; detail: string }> {
  const response = await sendRequest(path, {
    method: 'POST',
    headers: { [TOKEN_HEADER]: token, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (response === undefined) {
    return { auction: undefined, detail: '서버에 닿지 못했다' }
  }
  if (!response.ok) {
    return { auction: undefined, detail: await readErrorDetail(response) }
  }
  return { auction: readAuctionBody(await response.json()), detail: '' }
}

/** 관리자 화면의 몬스터 한 줄. */
export interface AdminMonsterRow {
  readonly recordId: number
  readonly catalogId: string
  readonly tier: string
  readonly zoneFloor: number
  readonly entitySlot: string
  readonly level: number
  readonly levelCap: number
  readonly alive: boolean
  readonly heldItems: number
}

/** 관리자가 세계에 손댄 기록 한 줄. */
export interface AdminActionRow {
  readonly handle: string
  readonly action: string
  readonly target: string
  readonly detail: string
  readonly createdAt: string
}

/** 몬스터가 들고 있는 아이템 한 줄. */
export interface AdminHeldItem {
  readonly itemId: number
  readonly recordId: number
  readonly monsterId: string
  readonly catalogId: string
  /** 누구에게서 빼앗았는가. 되찾으러 갈 동기가 World Loop 의 전부다. */
  readonly takenFromHandle: string
  readonly isBroken: boolean
  readonly isBound: boolean
}

/** 세계 현황 한 화면. */
export interface AdminOverview {
  readonly accounts: number
  readonly registered: number
  readonly monstersAlive: number
  readonly items: number
  readonly itemsBound: number
  readonly itemsHeldByMonsters: number
  readonly listingsOpen: number
  readonly currencyTotal: number
  readonly verifiedRuns: number
  readonly catalogItems: number
  readonly enemyKinds: number
  readonly coreVersion: string
  readonly levelCounts: readonly { readonly level: number; readonly count: number }[]
  readonly monsters: readonly AdminMonsterRow[]
  readonly heldItems: readonly AdminHeldItem[]
  readonly recentActions: readonly AdminActionRow[]
}

/**
 * 서버가 준 절을 관리자 현황으로 읽는다.
 *
 * @param body 응답 절.
 * @returns 현황.
 */
export function parseAdminOverview(body: Record<string, never>): AdminOverview {
  const raw = body as unknown as Record<string, number & string & unknown[]>
  return {
    accounts: Number(raw.accounts),
    registered: Number(raw.registered),
    monstersAlive: Number(raw.monsters_alive),
    items: Number(raw.items),
    itemsBound: Number(raw.items_bound),
    itemsHeldByMonsters: Number(raw.items_held_by_monsters),
    listingsOpen: Number(raw.listings_open),
    currencyTotal: Number(raw.currency_total),
    verifiedRuns: Number(raw.verified_runs),
    catalogItems: Number(raw.catalog_items),
    enemyKinds: Number(raw.enemy_kinds),
    coreVersion: String(raw.core_version),
    levelCounts: (raw.level_counts as unknown as { level: number; count: number }[]).map(
      (row) => ({ level: Number(row.level), count: Number(row.count) }),
    ),
    monsters: (raw.monsters as unknown as Record<string, never>[]).map((row) => {
      const item = row as unknown as Record<string, number & string & boolean>
      return {
        recordId: Number(item.record_id),
        catalogId: String(item.catalog_id),
        tier: String(item.tier),
        zoneFloor: Number(item.zone_floor),
        entitySlot: String(item.entity_slot),
        level: Number(item.level),
        levelCap: Number(item.level_cap),
        alive: Boolean(item.alive),
        heldItems: Number(item.held_items),
      }
    }),
    heldItems: ((raw.held_items ?? []) as unknown as Record<string, never>[]).map((row) => {
      const item = row as unknown as Record<string, number & string & boolean>
      return {
        itemId: Number(item.item_id),
        recordId: Number(item.record_id),
        monsterId: String(item.monster_id),
        catalogId: String(item.catalog_id),
        takenFromHandle: String(item.taken_from_handle),
        isBroken: Boolean(item.is_broken),
        isBound: Boolean(item.is_bound),
      }
    }),
    recentActions: (raw.recent_actions as unknown as Record<string, string>[]).map((row) => ({
      handle: String(row.handle),
      action: String(row.action),
      target: String(row.target),
      detail: String(row.detail),
      createdAt: String(row.created_at),
    })),
  }
}

/**
 * 관리자 현황을 읽는다.
 *
 * **관리자가 아니면 서버가 404 로 답한다** — 403 은 경로의 존재를 알려 주기 때문이다.
 * 그때는 undefined 를 돌려주고 화면은 아무것도 그리지 않는다.
 *
 * @param token 기기 토큰.
 * @returns 현황. 관리자가 아니거나 서버에 못 닿으면 undefined.
 */
export async function readAdminOverview(token: string): Promise<AdminOverview | undefined> {
  const response = await sendRequest('/admin/overview', { headers: { [TOKEN_HEADER]: token } })
  if (response === undefined || !response.ok) {
    return undefined
  }
  return parseAdminOverview((await response.json()) as Record<string, never>)
}

/**
 * 지속 몬스터의 레벨을 고친다.
 *
 * @param token 기기 토큰.
 * @param recordId 대상 개체.
 * @param level 새 레벨.
 * @returns 갱신된 현황과 실패 사유.
 */
export async function applyMonsterLevel(
  token: string,
  recordId: number,
  level: number,
): Promise<{ overview: AdminOverview | undefined; detail: string }> {
  const response = await sendRequest('/admin/monster/level', {
    method: 'PUT',
    headers: { [TOKEN_HEADER]: token, 'content-type': 'application/json' },
    body: JSON.stringify({ record_id: recordId, level }),
  })
  if (response === undefined) {
    return { overview: undefined, detail: '서버에 닿지 못했다' }
  }
  const body = (await response.json()) as Record<string, never> & { detail?: string }
  if (!response.ok) {
    return { overview: undefined, detail: String(body.detail ?? '거절당했다') }
  }
  return { overview: parseAdminOverview(body), detail: '' }
}

/**
 * 되돌릴 수 없는 관리자 개입을 보낸다.
 *
 * **사유를 함께 보낸다.** 서버가 빈 사유를 거절한다 — 무엇을 했는지만 남으면 "왜
 * 그랬지" 를 나중에 아무도 답할 수 없다.
 *
 * @param token 기기 토큰.
 * @param path `/admin/item/recall` 같은 경로.
 * @param targetId 대상 id.
 * @param reason 사유.
 * @returns 갱신된 현황과 실패 사유.
 */
export async function applyAdminAction(
  token: string,
  path: string,
  targetId: number,
  reason: string,
): Promise<{ overview: AdminOverview | undefined; detail: string }> {
  const response = await sendRequest(path, {
    method: 'POST',
    headers: { [TOKEN_HEADER]: token, 'content-type': 'application/json' },
    body: JSON.stringify({ target_id: targetId, reason }),
  })
  if (response === undefined) {
    return { overview: undefined, detail: '서버에 닿지 못했다' }
  }
  const body = (await response.json()) as Record<string, never> & { detail?: string }
  if (!response.ok) {
    return { overview: undefined, detail: String(body.detail ?? '거절당했다') }
  }
  return { overview: parseAdminOverview(body), detail: '' }
}

/** 카탈로그 한 줄 — 아이템. */
export interface CatalogItemRow {
  readonly catalogId: string
  readonly labelKo: string
  readonly kind: string
  readonly slot: string
  readonly hands: string
  readonly grantsSkill: string
  /** 무기가 정하는 사거리 (§2.2). 0 은 「안 정한다」다 — 화면이 「-」 로 그린다. */
  readonly attackRange: number
  readonly affixes: readonly string[]
  readonly requirements: readonly string[]
}

/** 카탈로그 한 줄 — 적. */
export interface CatalogEnemyRow {
  readonly kindId: string
  readonly labelKo: string
  readonly type: string
  readonly rulesetId: string
  readonly hpMax: number
  readonly attack: number
  readonly defense: number
  readonly attackRange: number
}

/** 레벨 곡선 한 줄. **실제 인원이 함께 온다** — 곡선만 보면 튜닝할 수 없다. */
export interface LevelCurveRow {
  readonly level: number
  readonly requiredXp: number
  readonly totalXp: number
  readonly bonusRuleSlots: number
  readonly bonusCpu: number
  readonly bonusFlags: number
  readonly statPoints: number
  readonly attackIfAllStr: number
  readonly players: number
}

/** 콘텐츠 초안 한 줄. 본문은 담지 않는다 — 목록은 목록이다. */
export interface ContentDraftRow {
  readonly asset: string
  readonly note: string
  readonly updatedAt: string
  /** 지금 파일의 세대. 초안의 세대가 이것보다 커야 저장된다. */
  readonly currentVersion: number
}

/** 콘텐츠 편집 화면 하나. */
export interface ContentDraftView {
  readonly drafts: readonly ContentDraftRow[]
  readonly assets: readonly string[]
  readonly problem: string
  /** 발행이 사람 손을 탄다는 사실. 화면이 이것을 말해야 한다. */
  readonly publishHint: string
}

/** 자산 하나의 지금 내용과 초안. */
export interface ContentAssetView {
  readonly asset: string
  readonly current: unknown
  readonly draft: unknown
  readonly note: string
  readonly versionKey: string
}

/**
 * 콘텐츠 편집 응답을 옮긴다.
 *
 * @param raw 서버 응답.
 * @returns 화면이 읽는 절.
 */
function readContentDrafts(raw: Record<string, unknown>): ContentDraftView {
  const rows = (raw.drafts ?? []) as Record<string, unknown>[]
  return {
    drafts: rows.map((row) => ({
      asset: String(row.asset),
      note: String(row.note ?? ''),
      updatedAt: String(row.updated_at ?? ''),
      currentVersion: Number(row.current_version ?? 0),
    })),
    assets: (raw.assets ?? []) as string[],
    problem: String(raw.problem ?? ''),
    publishHint: String(raw.publish_hint ?? ''),
  }
}

/**
 * 콘텐츠 초안 목록을 읽는다.
 *
 * @param token 기기 토큰.
 * @returns 초안 목록. 관리자가 아니면 undefined.
 */
export async function readContentAdmin(token: string): Promise<ContentDraftView | undefined> {
  const response = await sendRequest('/admin/content', { headers: { [TOKEN_HEADER]: token } })
  if (response === undefined || !response.ok) {
    return undefined
  }
  return readContentDrafts((await response.json()) as Record<string, unknown>)
}

/**
 * 자산 하나의 지금 내용과 초안을 읽는다.
 *
 * @param token 기기 토큰.
 * @param asset 자산 이름.
 * @returns 자산 절. 관리자가 아니거나 모르는 자산이면 undefined.
 */
export async function readContentAsset(
  token: string,
  asset: string,
): Promise<ContentAssetView | undefined> {
  const response = await sendRequest(`/admin/content/${asset}`, {
    headers: { [TOKEN_HEADER]: token },
  })
  if (response === undefined || !response.ok) {
    return undefined
  }
  const raw = (await response.json()) as Record<string, unknown>
  return {
    asset: String(raw.asset),
    current: raw.current,
    draft: raw.draft ?? null,
    note: String(raw.note ?? ''),
    versionKey: String(raw.version_key ?? ''),
  }
}

/**
 * 초안을 저장하거나 버린다.
 *
 * @param token 기기 토큰.
 * @param path `/admin/content/draft` 또는 `/admin/content/discard`.
 * @param body 보낼 절.
 * @returns 갱신된 목록과 거절 사유.
 */
export async function applyContentAdmin(
  token: string,
  path: string,
  body: unknown,
): Promise<{ view: ContentDraftView | undefined; detail: string }> {
  const response = await sendRequest(path, {
    method: 'POST',
    headers: { [TOKEN_HEADER]: token, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (response === undefined) {
    return { view: undefined, detail: '서버에 닿지 못했다' }
  }
  const raw = (await response.json()) as Record<string, unknown>
  if (!response.ok) {
    return { view: undefined, detail: String(raw.detail ?? '거절됐다') }
  }
  return { view: readContentDrafts(raw), detail: '' }
}

/** 관리자가 보는 카탈로그 한 줄. 굴림에 걸리는 값까지 함께 온다. */
export interface CatalogAdminRow {
  readonly catalogId: string
  readonly kind: string
  readonly labelKo: string
  readonly slot: string
  readonly hands: string
  readonly grade: string
  readonly minFloor: number
  readonly isRetired: boolean
  readonly affixes: readonly string[]
  readonly requirements: readonly string[]
  readonly grantsSkill: string
  /** 무기가 정하는 사거리 (§2.2). 0 은 「안 정한다」다 — 화면이 안 그린다. */
  readonly attackRange: number
  /**
   * 소모품의 쓰임새 (§4). `USE_ITEM[kind]` 의 파라미터와 같은 값이며 **코드가 읽는
   * 유일한 태그다** — `affixes` 옆의 분류 이름표와 다르다.
   */
  readonly useTag: string
  /** 드롭 표의 가중치. 0 이면 표에 없다 — 굴려도 안 나온다. */
  readonly dropWeight: number
  /**
   * 고치기용 원본 절. `affixes` 는 적어 둔 것이라 능력치 축이 안 담긴다 — 그것만 보고
   * 편집 칸을 채우면 이름만 고치려던 편집이 축까지 바꿔 저장한다.
   */
  readonly affixRows: readonly CatalogAffixSpec[]
}

/** 접사 한 줄의 원본 절. */
export interface CatalogAffixSpec {
  readonly stat: string
  readonly flat: number
  readonly percent: number
  readonly labelKo: string
}

/** 카탈로그 관리 화면 하나. */
export interface CatalogAdminView {
  readonly items: readonly CatalogAdminRow[]
  /** 카탈로그 세대. 코어 버전의 `i` 축이며, 고치면 시즌이 갈린다. */
  readonly generation: number
  readonly grades: readonly string[]
  /**
   * 접사가 붙을 수 있는 능력치. **서버가 정본을 들고 있다.**
   *
   * 화면이 목록을 따로 박아 두면 정본이 둘이 되고, 서버가 아는 이름이 늘어도 화면은 옛
   * 목록을 내보인다 — 사람은 그것이 전부라고 읽는다.
   */
  readonly stats: readonly string[]
}

/**
 * 관리자 카탈로그 응답을 옮긴다.
 *
 * @param raw 서버 응답.
 * @returns 화면이 읽는 절.
 */
function readCatalogAdmin(raw: Record<string, unknown>): CatalogAdminView {
  const rows = (raw.items ?? []) as Record<string, unknown>[]
  return {
    items: rows.map((row) => ({
      catalogId: String(row.catalog_id),
      kind: String(row.kind),
      labelKo: String(row.label_ko),
      slot: String(row.slot ?? ''),
      hands: String(row.hands ?? ''),
      grade: String(row.grade),
      minFloor: Number(row.min_floor ?? 1),
      isRetired: Boolean(row.is_retired),
      affixes: (row.affixes ?? []) as string[],
      requirements: (row.requirements ?? []) as string[],
      grantsSkill: String(row.grants_skill ?? ''),
      attackRange: Number(row.attack_range ?? 0),
      useTag: String(row.use_tag ?? ''),
      dropWeight: Number(row.drop_weight ?? 0),
      affixRows: ((row.affix_rows ?? []) as Record<string, unknown>[]).map((spec) => ({
        stat: String(spec.stat ?? ''),
        flat: Number(spec.flat ?? 0),
        percent: Number(spec.percent ?? 0),
        labelKo: String(spec.label_ko ?? ''),
      })),
    })),
    generation: Number(raw.generation ?? 0),
    grades: (raw.grades ?? []) as string[],
    stats: (raw.stats ?? []) as string[],
  }
}

/**
 * 관리자 카탈로그를 읽는다.
 *
 * @param token 기기 토큰.
 * @returns 카탈로그. 관리자가 아니거나 서버에 닿지 못했으면 undefined.
 */
export async function readAdminItems(token: string): Promise<CatalogAdminView | undefined> {
  const response = await sendRequest('/admin/catalog/items', {
    headers: { [TOKEN_HEADER]: token },
  })
  if (response === undefined || !response.ok) {
    return undefined
  }
  return readCatalogAdmin((await response.json()) as Record<string, unknown>)
}

/**
 * 카탈로그를 고친다. **사유가 반드시 붙는다** — 되돌릴 수 없는 조작이다.
 *
 * @param token 기기 토큰.
 * @param path `/admin/catalog/item` 또는 `/admin/catalog/retire`.
 * @param body 보낼 절.
 * @returns 갱신된 카탈로그와 한 줄 설명.
 */
export async function applyCatalogAdmin(
  token: string,
  path: string,
  body: unknown,
): Promise<{ view: CatalogAdminView | undefined; detail: string }> {
  const response = await sendRequest(path, {
    method: 'POST',
    headers: { [TOKEN_HEADER]: token, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (response === undefined) {
    return { view: undefined, detail: '서버에 닿지 못했다' }
  }
  const raw = (await response.json()) as Record<string, unknown>
  if (!response.ok) {
    return { view: undefined, detail: String(raw.detail ?? '거절됐다') }
  }
  return { view: readCatalogAdmin(raw), detail: '' }
}

/** 콘텐츠 카탈로그. 읽기 전용이다. */
export interface AdminCatalog {
  readonly coreVersion: string
  readonly items: readonly CatalogItemRow[]
  readonly enemies: readonly CatalogEnemyRow[]
  readonly levelCurve: readonly LevelCurveRow[]
  readonly caps: {
    readonly maxBonusRuleSlots: number
    readonly maxBonusCpu: number
    readonly maxBonusFlags: number
  }
}

/**
 * 콘텐츠 카탈로그를 읽는다.
 *
 * **관리자가 아니면 404 다** — 그때는 undefined 를 돌려주고 화면이 아무것도 그리지 않는다.
 *
 * @param token 기기 토큰.
 * @returns 카탈로그. 관리자가 아니거나 서버에 못 닿으면 undefined.
 */
export async function readAdminCatalog(token: string): Promise<AdminCatalog | undefined> {
  const response = await sendRequest('/admin/catalog', { headers: { [TOKEN_HEADER]: token } })
  if (response === undefined || !response.ok) {
    return undefined
  }
  const body = (await response.json()) as {
    core_version: string
    items: Record<string, unknown>[]
    enemies: Record<string, unknown>[]
    level_curve: Record<string, number>[]
    caps: Record<string, number>
  }
  return {
    coreVersion: body.core_version,
    items: body.items.map((row) => {
      const item = row as { affixes: string[]; requirements: string[] } & Record<string, string>
      return {
        catalogId: String(item.catalog_id),
        labelKo: String(item.label_ko),
        kind: String(item.kind),
        slot: String(item.slot),
        hands: String(item.hands),
        grantsSkill: String(item.grants_skill),
        attackRange: Number(item.attack_range ?? 0),
        affixes: [...item.affixes],
        requirements: [...item.requirements],
      }
    }),
    enemies: body.enemies.map((row) => {
      const item = row as Record<string, string & number>
      return {
        kindId: String(item.kind_id),
        labelKo: String(item.label_ko),
        type: String(item.type),
        rulesetId: String(item.ruleset_id),
        hpMax: Number(item.hp_max),
        attack: Number(item.attack),
        defense: Number(item.defense),
        attackRange: Number(item.attack_range),
      }
    }),
    levelCurve: body.level_curve.map((row) => ({
      level: Number(row.level),
      requiredXp: Number(row.required_xp),
      totalXp: Number(row.total_xp),
      bonusRuleSlots: Number(row.bonus_rule_slots),
      bonusCpu: Number(row.bonus_cpu),
      bonusFlags: Number(row.bonus_flags),
      statPoints: Number(row.stat_points),
      attackIfAllStr: Number(row.attack_if_all_str),
      players: Number(row.players),
    })),
    caps: {
      maxBonusRuleSlots: Number(body.caps.max_bonus_rule_slots ?? 0),
      maxBonusCpu: Number(body.caps.max_bonus_cpu ?? 0),
      maxBonusFlags: Number(body.caps.max_bonus_flags ?? 0),
    },
  }
}


/**
 * 쌓인 초안을 발행한다 (설계/4_아이템 §18).
 *
 * **세대를 받아 그대로 보낸다.** 브라우저가 정하면 관리자가 모르는 값으로 시즌이 갈린다.
 *
 * @param token 기기 토큰.
 * @param generation 발행 세대.
 * @param note 사유.
 * @returns 갱신된 초안 목록과 거절 사유.
 */
export async function applyContentPublish(
  token: string,
  generation: number,
  note: string,
): Promise<{ view: ContentDraftView | undefined; detail: string }> {
  const response = await sendRequest('/admin/content/publish', {
    method: 'POST',
    headers: { [TOKEN_HEADER]: token, 'Content-Type': 'application/json' },
    body: JSON.stringify({ generation, note }),
  })
  if (response === undefined) {
    return { view: undefined, detail: '서버에 닿지 못했다' }
  }
  const raw = (await response.json()) as Record<string, unknown>
  if (!response.ok) {
    return { view: undefined, detail: String(raw.detail ?? '거절됐다') }
  }
  // 발행 뒤에는 초안이 비어 있다. 목록을 다시 읽어 화면이 그것을 알게 한다.
  return { view: await readContentAdmin(token), detail: '' }
}


/**
 * 이 기기에서 로그아웃한다.
 *
 * **서버의 토큰을 지우고 이 기기의 저장도 지운다.** 토큰만 지우면 다음 사람이 이 기기를
 * 열었을 때 앞사람의 규칙표를 보게 된다 — 로그아웃은 "이 기기가 그 계정을 그만 본다" 이고,
 * 그 계정의 것이 화면에 남아 있으면 그만 본 것이 아니다.
 *
 * @param token 기기 토큰.
 * @param storage 저장소.
 */
export async function applyLogout(token: string, storage: StorageLike | undefined): Promise<void> {
  await sendRequest('/logout', { method: 'POST', headers: { [TOKEN_HEADER]: token } })
  removeSave(storage)
  removeMeta(storage)
  try {
    storage?.removeItem(TOKEN_STORAGE_KEY)
  } catch {
    // 지우기 실패도 로그아웃을 막지 않는다.
  }
}
