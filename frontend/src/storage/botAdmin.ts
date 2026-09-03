/**
 * 봇·도플갱어 관리 조회 (관리 화면).
 *
 * **성격보다 결과를 본다.** 규칙표와 실력은 우리가 정해 준 값이라 화면에 적어도 새
 * 사실이 없다. 알아야 할 것은 몇 판을 돌았고 몇 번 이겼고 어디까지 내려갔는가다 —
 * 승리가 0이면 그 봇은 세계에 아무것도 안 남긴다.
 */
import { TOKEN_HEADER, readInventoryPayload, sendRequest } from './serverSync'
import type { InventoryView } from './serverSync'

/** 봇 한 줄. */
export interface BotView {
  readonly accountId: number
  readonly handle: string
  readonly label: string
  readonly rulesetId: string
  readonly cadenceSec: number
  readonly skillPct: number
  readonly isActive: boolean
  /** 다음 출격까지 남은 초. 음수면 이미 차례다. */
  readonly dueInSec: number
  readonly runs: number
  readonly wins: number
  readonly bestFloor: number
  readonly balance: number
  readonly items: number
}

/** 도플갱어 한 줄. */
export interface DoppelView {
  readonly recordId: number
  readonly zoneFloor: number
  readonly level: number
  readonly alive: boolean
  readonly entitySlot: string
  readonly originHandle: string
}

/** 봇 현황 전체. */
export interface BotOverview {
  readonly maxRunsPerHour: number
  readonly minCadenceSec: number
  readonly bots: readonly BotView[]
  readonly doppels: readonly DoppelView[]
}

/** 서버가 주는 봇 절. */
interface RawBot {
  account_id: number
  handle: string
  label: string
  ruleset_id: string
  cadence_sec: number
  skill_pct: number
  is_active: boolean
  due_in_sec: number
  runs: number
  wins: number
  best_floor: number
  balance: number
  items: number
}

/** 서버가 주는 도플갱어 절. */
interface RawDoppel {
  record_id: number
  zone_floor: number
  level: number
  alive: boolean
  entity_slot: string
  origin_handle: string
}

/**
 * 응답 절을 화면 모양으로 옮긴다.
 *
 * @param raw 서버 응답.
 * @returns 현황.
 */
export function parseBotOverview(raw: {
  max_runs_per_hour: number
  min_cadence_sec: number
  bots: RawBot[]
  doppels: RawDoppel[]
}): BotOverview {
  return {
    maxRunsPerHour: raw.max_runs_per_hour,
    minCadenceSec: raw.min_cadence_sec,
    bots: raw.bots.map((item) => ({
      accountId: item.account_id,
      handle: item.handle,
      label: item.label,
      rulesetId: item.ruleset_id,
      cadenceSec: item.cadence_sec,
      skillPct: item.skill_pct,
      isActive: item.is_active,
      dueInSec: item.due_in_sec,
      runs: item.runs,
      wins: item.wins,
      bestFloor: item.best_floor,
      balance: item.balance,
      items: item.items,
    })),
    doppels: raw.doppels.map((item) => ({
      recordId: item.record_id,
      zoneFloor: item.zone_floor,
      level: item.level,
      alive: item.alive,
      entitySlot: item.entity_slot,
      originHandle: item.origin_handle,
    })),
  }
}

/**
 * 봇·도플갱어 현황을 읽는다.
 *
 * @param token 기기 토큰.
 * @returns 현황. 서버에 닿지 못했거나 관리자가 아니면 undefined.
 */
export async function readBotAdmin(token: string): Promise<BotOverview | undefined> {
  const response = await sendRequest('/admin/bots', { headers: { [TOKEN_HEADER]: token } })
  if (response === undefined || !response.ok) {
    return undefined
  }
  return parseBotOverview((await response.json()) as Parameters<typeof parseBotOverview>[0])
}

/**
 * 봇 하나의 성격을 고친다.
 *
 * @param token 기기 토큰.
 * @param bot 고칠 값들.
 * @returns 고친 뒤의 현황. 실패하면 undefined.
 */
export async function applyBotSettings(
  token: string,
  bot: {
    accountId: number
    rulesetId: string
    skillPct: number
    cadenceSec: number
    isActive: boolean
  },
): Promise<BotOverview | undefined> {
  const response = await sendRequest('/admin/bot', {
    method: 'PUT',
    headers: { [TOKEN_HEADER]: token, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      account_id: bot.accountId,
      ruleset_id: bot.rulesetId,
      skill_pct: bot.skillPct,
      cadence_sec: bot.cadenceSec,
      is_active: bot.isActive,
    }),
  })
  if (response === undefined || !response.ok) {
    return undefined
  }
  return parseBotOverview((await response.json()) as Parameters<typeof parseBotOverview>[0])
}

/**
 * 내 가방의 아이템 하나를 봇에게 넘긴다.
 *
 * **한 방향이다.** 도착하는 순간 귀속되고(결정 #07), 귀속된 물건은 경매에 못 걸린다 —
 * 한 번 봇에게 간 것은 어떤 경로로도 사람에게 돌아오지 않는다. 되받는 함수를 여기에
 * 만들지 않는 이유가 그것이다.
 *
 * @param token 기기 토큰.
 * @param accountId 받을 봇.
 * @param itemId 넘길 아이템.
 * @returns 넘긴 뒤의 현황. 실패하면 undefined.
 */
export async function applyBotGift(
  token: string,
  accountId: number,
  itemId: number,
): Promise<BotOverview | undefined> {
  const response = await sendRequest('/admin/bot/gift', {
    method: 'POST',
    headers: { [TOKEN_HEADER]: token, 'Content-Type': 'application/json' },
    body: JSON.stringify({ account_id: accountId, item_id: itemId }),
  })
  if (response === undefined || !response.ok) {
    return undefined
  }
  return parseBotOverview((await response.json()) as Parameters<typeof parseBotOverview>[0])
}

/**
 * 봇 하나의 가방을 읽는다.
 *
 * **사람 화면과 같은 모양이다** — 서버가 같은 빌더로 만든다. 여기서 따로 만들면 두
 * 화면이 다른 것을 그리고, 「봇에게 뭐가 있지」를 답하려던 화면이 답을 틀리게 한다.
 *
 * @param token 기기 토큰.
 * @param accountId 볼 봇.
 * @returns 그 봇의 가방. 봇이 아니거나 못 닿으면 undefined.
 */
export async function readBotBag(
  token: string,
  accountId: number,
): Promise<InventoryView | undefined> {
  const response = await sendRequest(`/admin/bot/bag?account_id=${String(accountId)}`, {
    headers: { [TOKEN_HEADER]: token },
  })
  if (response === undefined || !response.ok) {
    return undefined
  }
  return readInventoryPayload((await response.json()) as Record<string, unknown>)
}
