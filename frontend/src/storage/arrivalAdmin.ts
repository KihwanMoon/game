/**
 * 새로 들어온 계정을 읽는다 (U1).
 *
 * **여기 뜨는 줄은 「앱을 연 사람」이 아니다.** 계정은 출격에서만 생기므로
 * (`requireAccount`: "여는 것만으로는 안 만든다"), 이 목록은 **판을 내려 한 사람**이다.
 * 그냥 들렀다 간 사람은 명부의 트래픽 줄이 센다 — 둘을 나란히 놓아야 유입이 읽힌다.
 */
import { TOKEN_HEADER, sendRequest } from './serverSync'

/** 새로 들어온 계정 한 줄. */
export interface ArrivalView {
  readonly accountId: number
  readonly name: string
  /** 자격증명을 붙였는가. 익명으로 시작해 가입으로 승격되는 구조라 이것이 머무름의 신호다. */
  readonly isJoined: boolean
  readonly isBot: boolean
  readonly createdAt: string
  /** 서버에 남은 판 수. **0 이면 출격은 눌렀는데 서버에 아무것도 안 남았다는 뜻이다.** */
  readonly runs: number
  readonly bestFloor: number
}

/** 유입 목록과 요약. */
export interface ArrivalList {
  readonly days: number
  readonly arrived: number
  readonly joined: number
  readonly played: number
  readonly rows: readonly ArrivalView[]
}

interface RawArrival {
  account_id: number
  name: string
  is_joined: boolean
  is_bot: boolean
  created_at: string
  runs: number
  best_floor: number
}

interface RawArrivalList {
  days: number
  arrived: number
  joined: number
  played: number
  rows: RawArrival[]
}

/**
 * 유입 목록을 읽는다.
 *
 * @param token 기기 토큰.
 * @param days 며칠치를 볼 것인가.
 * @returns 목록과 요약. 못 읽으면 undefined — 화면이 그 자리를 비운다.
 */
export async function readArrivals(
  token: string,
  days = 14,
): Promise<ArrivalList | undefined> {
  const response = await sendRequest(`/admin/arrivals?days=${String(days)}`, {
    headers: { [TOKEN_HEADER]: token },
  })
  if (response === undefined || !response.ok) {
    return undefined
  }
  const body = (await response.json()) as RawArrivalList
  return {
    days: body.days,
    arrived: body.arrived,
    joined: body.joined,
    played: body.played,
    rows: body.rows.map((row) => ({
      accountId: row.account_id,
      name: row.name,
      isJoined: row.is_joined,
      isBot: row.is_bot,
      createdAt: row.created_at,
      runs: row.runs,
      bestFloor: row.best_floor,
    })),
  }
}
