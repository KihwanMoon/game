/**
 * 지나간 판을 다시 돌려 본다 (결정 #09).
 *
 * **기록을 트는 것이 아니라 다시 돌리는 것이다.** 이벤트 로그는 저장하지 않는다 — 남는
 * 것은 제출(규칙표)과 판정(결과)뿐이다. 그런데 코어가 결정론이라(R5·G3) 같은 입력이면
 * 같은 판이 나오므로, 시드·방·층·로드아웃·스냅샷을 그대로 넣고 다시 돌리면 그때 그 판이
 * 눈앞에 다시 선다.
 *
 * **관리자 화면에서 갈라 나왔다.** 절은 같고 라우트만 다르다 — 저쪽은 남의 판을 보고
 * 여기는 내 판만 본다. 파서를 두 벌 두면 한쪽만 고쳐지는 날이 온다.
 */
import { parseLoadout, type PlayerLoadout, type RawPlayerLoadout } from '../core/schemas/loadout'
import {
  parseSnapshot,
  sortSnapshots,
  type MonsterSnapshot,
  type RawMonsterSnapshot,
} from '../core/schemas/monsterSnapshot'
import { parseRuleSet, type RawRuleSet, type RuleSet } from '../core/schemas/ruleset'

import { TOKEN_HEADER, sendRequest } from './serverSync'

export interface ReplayInput {
  readonly submissionId: number
  readonly ruleset: RuleSet | undefined
  readonly roomId: string
  readonly seed: number
  readonly floor: number
  readonly roomsPerFloor: number
  readonly roomIds: readonly string[]
  readonly loadout: PlayerLoadout | undefined
  readonly snapshots: readonly MonsterSnapshot[]
  /** 그때 확정된 결과. 재생이 같은 답을 내는지 눈으로 대조할 수 있어야 한다. */
  readonly outcome: string
  readonly ticks: number
  readonly playerHp: number
}

/**
 * 지나간 판을 다시 돌릴 입력을 읽는다.
 *
 * **경로를 받는다.** 사람의 것과 관리자의 것이 라우트만 다르고 절은 같다 — 파서를 두 벌
 * 두면 한쪽만 고쳐지는 날이 오고, 그때 재생이 다른 판을 돈다.
 *
 * @param path 읽을 라우트.
 * @param token 기기 토큰.
 * @param submissionId 볼 제출.
 * @returns 재현 입력. 없거나 못 닿으면 undefined.
 */
async function readReplayFrom(
  path: string,
  token: string,
  submissionId: number,
): Promise<ReplayInput | undefined> {
  const response = await sendRequest(`${path}?submission_id=${String(submissionId)}`, {
    headers: { [TOKEN_HEADER]: token },
  })
  if (response === undefined || !response.ok) {
    return undefined
  }
  const raw = (await response.json()) as {
    submission_id: number
    ruleset: RawRuleSet | null
    room_id: string
    seed: number
    floor: number
    rooms_per_floor: number
    room_ids: string[]
    loadout: RawPlayerLoadout | null
    snapshots: RawMonsterSnapshot[]
    outcome: string
    ticks: number
    player_hp: number
  }
  return {
    submissionId: raw.submission_id,
    // 규칙표가 안 읽히면 undefined 다 — 빈 규칙표로 돌리면 **다른 판**이 나오고, 그것을
    // 재생이라 부르면 화면이 거짓말을 한다.
    ruleset: raw.ruleset === null ? undefined : parseRuleSet(raw.ruleset),
    roomId: raw.room_id,
    seed: raw.seed,
    floor: raw.floor,
    roomsPerFloor: raw.rooms_per_floor,
    roomIds: raw.room_ids,
    loadout: raw.loadout === null ? undefined : parseLoadout(raw.loadout),
    snapshots: sortSnapshots(raw.snapshots.map(parseSnapshot)),
    outcome: raw.outcome,
    ticks: raw.ticks,
    playerHp: raw.player_hp,
  }
}

/**
 * **내** 판 하나를 다시 돌릴 입력을 읽는다.
 *
 * @param token 기기 토큰.
 * @param submissionId 볼 제출.
 * @returns 재현 입력. 내 것이 아니거나 못 닿으면 undefined.
 */
export async function readOwnReplay(
  token: string,
  submissionId: number,
): Promise<ReplayInput | undefined> {
  return readReplayFrom('/replay', token, submissionId)
}

/**
 * 관리자로서 남의 판을 읽는다.
 *
 * @param token 기기 토큰.
 * @param submissionId 볼 제출.
 * @returns 재현 입력. 없거나 못 닿으면 undefined.
 */
export async function readReplay(
  token: string,
  submissionId: number,
): Promise<ReplayInput | undefined> {
  return readReplayFrom('/admin/replay', token, submissionId)
}

/** 내가 돈 판 한 줄. **결과는 서버가 재시뮬해서 만든 값이다.** */
export interface RunHistoryRow {
  readonly submissionId: number
  readonly roomId: string
  readonly floor: number
  readonly seed: number
  readonly outcome: string
  readonly ticks: number
  readonly playerHp: number
  /** 판정. 빈 문자열은 **검증 전**이고, 그것과 「없다」가 같아 보이면 안 된다. */
  readonly verdict: string
  readonly submittedAt: string
}

/**
 * 내가 최근에 돈 판들을 새것부터 읽는다.
 *
 * @param token 기기 토큰.
 * @returns 최근 판들. 못 닿으면 빈 배열이다 — 화면이 「없다」와 「못 읽었다」를 링크
 *   상태로 가른다.
 */
export async function readRunHistory(token: string): Promise<readonly RunHistoryRow[]> {
  const response = await sendRequest('/runs', { headers: { [TOKEN_HEADER]: token } })
  if (response === undefined || !response.ok) {
    return []
  }
  const raw = (await response.json()) as {
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
  return raw.runs.map((row) => ({
    submissionId: row.submission_id,
    roomId: row.room_id,
    floor: row.floor,
    seed: row.seed,
    outcome: row.outcome,
    ticks: row.ticks,
    playerHp: row.player_hp,
    verdict: row.verdict,
    submittedAt: row.submitted_at,
  }))
}
