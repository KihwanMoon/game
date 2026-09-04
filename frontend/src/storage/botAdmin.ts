/**
 * 봇·도플갱어 관리 조회 (관리 화면).
 *
 * **성격보다 결과를 본다.** 규칙표와 실력은 우리가 정해 준 값이라 화면에 적어도 새
 * 사실이 없다. 알아야 할 것은 몇 판을 돌았고 몇 번 이겼고 어디까지 내려갔는가다 —
 * 승리가 0이면 그 봇은 세계에 아무것도 안 남긴다.
 */
import {
  TOKEN_HEADER,
  readInventoryPayload,
  readProgressPayload,
  sendRequest,
} from './serverSync'
import type { InventoryView, ProgressView } from './serverSync'
import type { MaintenanceView } from './maintenanceSync'
import type { SkillPrefView } from './skillSync'

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

/**
 * 도플갱어가 끼고 있던 장비를 읽는다.
 *
 * **가진 아이템이 아니라 얼려 둔 기록이다.** 그 개체는 어떤 아이템도 소유하지 않는다 —
 * 그래서 칸의 `itemId` 가 0 이고, 조작을 걸 자리가 없다.
 *
 * @param token 기기 토큰.
 * @param recordId 볼 개체.
 * @returns 장비만 채워진 인벤토리. 도플갱어가 아니면 undefined.
 */
export async function readDoppelGear(
  token: string,
  recordId: number,
): Promise<InventoryView | undefined> {
  const response = await sendRequest(`/admin/doppel/gear?record_id=${String(recordId)}`, {
    headers: { [TOKEN_HEADER]: token },
  })
  if (response === undefined || !response.ok) {
    return undefined
  }
  return readInventoryPayload((await response.json()) as Record<string, unknown>)
}

/** 봇이 지나간 판 한 줄. **이벤트 로그는 저장하지 않는다** — 결과까지가 남는 전부다. */
export interface BotRunView {
  readonly submissionId: number
  readonly roomId: string
  readonly floor: number
  /** 시드. 결정론 코어라 이것과 규칙표가 있으면 그 판을 다시 돌릴 수 있다 (R5·G3). */
  readonly seed: number
  readonly outcome: string
  readonly ticks: number
  readonly playerHp: number
  /** 서버가 재시뮬해 확정했는가. 빈 문자열이면 아직 안 본 것이고 「없다」와 다르다. */
  readonly verdict: string
  readonly submittedAt: string
}

/** 봇 하나를 사람 화면과 같은 눈으로 본 것. */
export interface BotDetail {
  readonly accountId: number
  readonly handle: string
  readonly rulesetId: string
  readonly maintenance: MaintenanceView
  readonly progress: ProgressView
  readonly skills: SkillPrefView
  readonly runs: readonly BotRunView[]
}

/**
 * 봇 하나의 규칙표·정비·성장·스킬·지나간 판을 한 번에 읽는다.
 *
 * **한 번에 읽는다.** 탭마다 따로 부르면 탭을 옮길 때마다 화면이 비었다가 찬다 —
 * 가방만 따로인 것은 그것이 이미 사람 화면과 같은 라우트를 쓰고 있어서다.
 *
 * @param token 기기 토큰.
 * @param accountId 볼 봇.
 * @returns 그 봇의 상세. 봇이 아니거나 못 닿으면 undefined.
 */
export async function readBotDetail(
  token: string,
  accountId: number,
): Promise<BotDetail | undefined> {
  const response = await sendRequest(`/admin/bot/detail?account_id=${String(accountId)}`, {
    headers: { [TOKEN_HEADER]: token },
  })
  if (response === undefined || !response.ok) {
    return undefined
  }
  const raw = (await response.json()) as {
    account_id: number
    handle: string
    ruleset_id: string
    maintenance: { rows: { action: string; grade: string }[] }
    progress: Record<string, unknown>
    skills: { rows: { skill_id: string; is_on: boolean; is_locked: boolean }[] }
    runs: {
      submission_id: number
      room_id: string
      floor: number
      seed: number
      outcome: string
      ticks: number
      player_hp: number
      verdict: string
      submitted_at: string
    }[]
  }
  return {
    accountId: raw.account_id,
    handle: raw.handle,
    rulesetId: raw.ruleset_id,
    maintenance: { rows: raw.maintenance.rows.map((row) => ({ ...row })) },
    progress: readProgressPayload(raw.progress),
    skills: {
      rows: raw.skills.rows.map((row) => ({
        skillId: row.skill_id,
        isOn: row.is_on,
        isLocked: row.is_locked,
      })),
    },
    runs: raw.runs.map((row) => ({
      submissionId: row.submission_id,
      roomId: row.room_id,
      floor: row.floor,
      seed: row.seed,
      outcome: row.outcome,
      ticks: row.ticks,
      playerHp: row.player_hp,
      verdict: row.verdict,
      submittedAt: row.submitted_at,
    })),
  }
}
