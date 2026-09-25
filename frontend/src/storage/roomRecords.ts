/**
 * 방별 상시 기록판 (2026-09-25) — 같은 방·같은 시드·같은 몸에서 가장 적게 쓰고 이긴 판.
 *
 * **순위표와 재는 것이 다르다.** 순위표는 누적 경험치라 오래 돈 쪽이 앞서고, 장비·레벨이
 * 결과를 가른다. 이 판은 둘을 빼고 「얼마나 잘 짰는가」만 본다 — 장비로 못 사는 축이라
 * 20장을 다 돈 뒤에도 끝이 없다.
 *
 * **값은 전부 서버가 낸다.** CPU·줄 수는 검증기를 지난 규칙표에서, 틱은 재시뮬에서 나온다.
 */
import { TOKEN_HEADER, sendRequest } from './serverSync'

/** 기록판 한 줄. */
export interface RoomRecordRow {
  readonly rank: number
  readonly handle: string
  readonly cpu: number
  readonly ticks: number
  readonly ruleCount: number
  /** 이 기록을 세운 규칙표의 공유 주소. `/r/{shareId}` 로 열린다. */
  readonly shareId: string
  readonly accountId: number
}

/** 한 방의 기록판. */
export interface RoomRecordBoard {
  readonly roomId: string
  readonly players: number
  readonly rows: readonly RoomRecordRow[]
  /** 내 기록. **윗자리 밖이어도 온다.** 없으면 undefined. */
  readonly mine: RoomRecordRow | undefined
}

interface RawRow {
  rank: number
  handle: string
  cpu: number
  ticks: number
  rule_count: number
  share_id: string
  account_id: number
}

function parseRow(raw: RawRow): RoomRecordRow {
  return {
    rank: raw.rank,
    handle: raw.handle,
    cpu: raw.cpu,
    ticks: raw.ticks,
    ruleCount: raw.rule_count,
    shareId: raw.share_id,
    accountId: raw.account_id,
  }
}

/**
 * 한 방의 기록판을 읽는다.
 *
 * @param token 기기 토큰.
 * @param roomId 방 id.
 * @returns 기록판. 서버에 닿지 못했으면 undefined — 그때는 판을 안 그린다.
 */
export async function readRoomRecords(
  token: string,
  roomId: string,
): Promise<RoomRecordBoard | undefined> {
  const query = new URLSearchParams({ room_id: roomId })
  const response = await sendRequest(`/records?${query.toString()}`, {
    headers: { [TOKEN_HEADER]: token },
  })
  if (response === undefined || !response.ok) {
    return undefined
  }
  const body = (await response.json()) as {
    room_id: string
    players: number
    entries: RawRow[]
    mine: RawRow | null
  }
  return {
    roomId: body.room_id,
    players: body.players,
    rows: body.entries.map(parseRow),
    mine: body.mine === null ? undefined : parseRow(body.mine),
  }
}

/**
 * 기록 한 줄을 사람이 읽는 값으로 적는다. **CPU 가 먼저다** — 순위를 가르는 순서 그대로다.
 *
 * @param row 기록 한 줄.
 * @returns `CPU 3 · 41틱 · 2줄`.
 */
export function formatRecordScore(row: RoomRecordRow): string {
  return `CPU ${String(row.cpu)} · ${String(row.ticks)}틱 · ${String(row.ruleCount)}줄`
}

/**
 * 기록판을 한 줄로 요약한다. **아직 아무도 없는 방에도 할 말이 있어야 한다.**
 *
 * @param board 기록판. 없으면 서버에 못 닿은 것이다.
 * @returns 화면에 적을 한 줄.
 */
export function formatRecordSummary(board: RoomRecordBoard | undefined): string {
  if (board === undefined) {
    return ''
  }
  const crowd =
    board.players === 0 ? '아직 아무도 기록을 안 세웠다' : `${String(board.players)}명이 세웠다`
  if (board.mine === undefined) {
    return `이 방 · ${crowd} — 이기면 CPU·틱·줄 수가 남는다`
  }
  return `내 기록 ${formatRecordScore(board.mine)} · ${String(board.mine.rank)}위 · ${crowd}`
}
