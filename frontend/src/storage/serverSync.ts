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
  MetaSave,
  MonsterSnapshot,
  PlayerLoadout,
  RawMonsterSnapshot,
  RawPlayerLoadout,
} from '../core/schemas'
import { parseLoadout, parseSnapshot, sortSnapshots } from '../core/schemas'
import { buildMetaPayload, parseMetaPayload } from './metaSave'
import type { StorageLike } from './saveStore'

/** 기기 토큰을 담는 localStorage 열쇠. */
export const TOKEN_STORAGE_KEY = 'game.account-token'

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
 * 제한 시간이 붙은 요청을 보낸다.
 *
 * @param path `/api` 뒤의 경로.
 * @param init fetch 설정.
 * @returns 응답. 실패하면 undefined.
 */
async function sendRequest(path: string, init: RequestInit): Promise<Response | undefined> {
  const controller = new AbortController()
  const timer = setTimeout(() => {
    controller.abort()
  }, REQUEST_TIMEOUT_MS)
  try {
    return await fetch(`${API_ROOT}${path}`, { ...init, signal: controller.signal })
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
async function readErrorDetail(response: Response): Promise<string> {
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
 * @param seed 제안할 시드. 서버가 연습 모드에서만 받아들인다.
 * @returns 발급된 티켓. 서버에 닿지 못했으면 undefined.
 */
export async function requestTicket(
  token: string,
  roomId: string,
  seed: number,
): Promise<ServerTicket | undefined> {
  const response = await sendRequest('/ticket', {
    method: 'POST',
    headers: { [TOKEN_HEADER]: token, 'Content-Type': 'application/json' },
    body: JSON.stringify({ room_id: roomId, seed }),
  })
  if (response === undefined || !response.ok) {
    return undefined
  }
  const body = (await response.json()) as {
    ticket_id: string
    seed: number
    room_id: string
    floor: number
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
  }
}

/** 서버가 확정한 판정. 브라우저가 낸 결과와 다르면 두 코어가 갈린 것이다. */
export interface RunVerdict {
  readonly verdict: string
  readonly outcome: string
  readonly ticks: number
  readonly playerHp: number
  readonly detail: string
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
): Promise<RunVerdict | undefined> {
  const response = await sendRequest('/run', {
    method: 'POST',
    headers: { [TOKEN_HEADER]: token, 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticket_id: ticketId, ruleset, core_version: coreVersion }),
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
  }
  return {
    verdict: body.verdict,
    outcome: body.outcome,
    ticks: body.ticks,
    playerHp: body.player_hp,
    detail: body.detail ?? '',
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
  readonly requirements: readonly RequirementView[]
  readonly canEquip: boolean
}

/** 인벤토리 한 칸 또는 장비 한 자리. */
export interface SlotView {
  readonly slotIndex: number
  readonly item: ItemView | null
  readonly slot: string | null
  /** 양손무기가 막은 자리. 서버가 계산해서 준다 — 저장된 상태가 아니다. */
  readonly isSealed: boolean
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

interface RawItem {
  item_id: number
  catalog_id: string
  label_ko: string
  kind: string
  slot: string | null
  hands: string | null
  equipped_slot: string | null
  is_broken: boolean
  requirements: RawRequirement[]
  can_equip: boolean
}

interface RawSlot {
  slot_index: number
  item: RawItem | null
  slot: string | null
  is_sealed: boolean
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
 * 인벤토리를 읽는다.
 *
 * @param token 기기 토큰.
 * @returns 인벤토리. 서버에 닿지 못했으면 undefined.
 */
export async function readInventory(token: string): Promise<InventoryView | undefined> {
  const response = await sendRequest('/inventory', { headers: { [TOKEN_HEADER]: token } })
  if (response === undefined || !response.ok) {
    return undefined
  }
  const body = (await response.json()) as {
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
  readonly ruleCount: number
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
  ruleset: { rules?: unknown[] } | null
  affixes: { label_ko: string }[]
  trophies: string[]
  holds_mine: boolean
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
    ruleCount: raw.ruleset?.rules?.length ?? 0,
    affixes: raw.affixes.map((item) => item.label_ko),
    trophies: raw.trophies,
    holdsMine: raw.holds_mine,
  }))
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
export async function readProgress(token: string): Promise<ProgressView | undefined> {
  const response = await sendRequest('/progress', { headers: { [TOKEN_HEADER]: token } })
  if (response === undefined || !response.ok) {
    return undefined
  }
  const body = (await response.json()) as {
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
    loadout?: RawPlayerLoadout | null
  }
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
  listings: { listing_id: number; item_id: number; label_ko: string; price: number; is_mine: boolean }[]
  balance: number
  fee_percent: number
}): AuctionView {
  return {
    listings: raw.listings.map((item) => ({
      listingId: item.listing_id,
      itemId: item.item_id,
      labelKo: item.label_ko,
      price: item.price,
      isMine: item.is_mine,
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
