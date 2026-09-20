/**
 * 오늘의 도전 판 — 같은 판을 다 같이 돈다는 사실을 화면에 들인다.
 *
 * **데일리는 이미 돌고 있었다** (2026-09-20). 티켓을 하루 한 번 내주고 시드를 날짜로
 * 고정하는 것까지 서버가 하고 있었는데, 그 결과를 아무도 못 봤다 — 화면에는 「티켓을
 * 받았다」 한 줄이 전부였다. 그러면 데일리는 그냥 「어제와 다른 한 판」이고, 내일 다시
 * 올 이유가 되지 못한다.
 *
 * **순위표와 갈라 둔다.** 저쪽은 시즌(`core_version`)으로 갈리고 점수를 누적하는 표다.
 * 오늘의 도전은 하루가 곧 판이라 그날 어디까지 갔는지만 본다.
 */
import { TOKEN_HEADER, sendRequest } from './serverSync'

/** 오늘의 순위 한 줄. */
export interface DailyRow {
  readonly rank: number
  readonly handle: string
  readonly floor: number
  readonly accountId: number
}

/** 오늘의 도전 상태. */
export interface DailyBoardView {
  /** `YYYY-MM-DD`. 화면이 「오늘」이 언제인지 서버 기준으로 적는다. */
  readonly day: string
  /** 이 판을 잡은 사람 수. 윗자리만 보면 혼자인지 백 명인지 모른다. */
  readonly players: number
  readonly rows: readonly DailyRow[]
  /** 내가 오늘 티켓을 받았는가. */
  readonly hasEntry: boolean
  readonly myFloor: number
  /** 윗자리 안에서의 내 순위. 밖이면 0 이다. */
  readonly myRank: number
}

/**
 * 오늘의 도전 판을 읽는다.
 *
 * @param token 기기 토큰.
 * @returns 오늘의 판. 서버에 닿지 못했으면 undefined — 그때는 줄을 안 그린다.
 */
export async function readDailyBoard(token: string): Promise<DailyBoardView | undefined> {
  const response = await sendRequest('/daily', { headers: { [TOKEN_HEADER]: token } })
  if (response === undefined || !response.ok) {
    return undefined
  }
  const body = (await response.json()) as {
    day: string
    players: number
    rows: { rank: number; handle: string; floor: number; account_id: number }[]
    has_entry: boolean
    my_floor: number
    my_rank: number
  }
  return {
    day: body.day,
    players: body.players,
    rows: body.rows.map((item) => ({
      rank: item.rank,
      handle: item.handle,
      floor: item.floor,
      accountId: item.account_id,
    })),
    hasEntry: body.has_entry,
    myFloor: body.my_floor,
    myRank: body.my_rank,
  }
}

/**
 * 오늘의 도전을 한 줄로 요약한다.
 *
 * **아직 안 돈 사람에게도 할 말이 있어야 한다.** 「0층」이라고 적으면 못한 것처럼
 * 읽히므로, 받았는지 돌았는지 아예 안 잡았는지를 가른다.
 *
 * @param board 오늘의 판. 없으면 서버에 못 닿은 것이다.
 * @returns 화면에 적을 한 줄.
 */
export function formatDailySummary(board: DailyBoardView | undefined): string {
  if (board === undefined) {
    return ''
  }
  const crowd = board.players === 0 ? '아직 아무도 안 잡았다' : `${String(board.players)}명이 잡았다`
  if (!board.hasEntry) {
    return `오늘 같은 판을 ${crowd} — 받으면 그 판이 돈다`
  }
  if (board.myFloor === 0) {
    return `오늘 판을 받아 뒀다 · ${crowd}`
  }
  const place = board.myRank === 0 ? '' : ` · ${String(board.myRank)}위`
  return `오늘 ${String(board.myFloor)}장까지${place} · ${crowd}`
}
