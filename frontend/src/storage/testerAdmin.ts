/**
 * 테스터 표시 조회·변경 (관리 화면).
 *
 * **G1 의 분모를 사람이 정하는 자리다.** 게이트는 「테스터 5명 중 3명」을 묻는데 이 게임은
 * 익명으로 시작하므로, 자동으로 세면 한 판 내고 떠난 계정까지 전부 테스터가 된다 —
 * 그것이 평균 재도전을 1.2회로 눌러 놓고 있었다. 누구를 불렀는지는 사람만 알고 있다.
 *
 * 표시는 **통계에만** 걸린다. 표시된 계정에 권한이 생기지 않고 세계 상태도 안 바뀐다.
 */
import { TOKEN_HEADER, sendRequest } from './serverSync'

/** 표시 화면의 한 줄. */
export interface TesterView {
  readonly accountId: number
  readonly handle: string
  /** 가입한 계정의 아이디. 익명이면 빈 문자열이다. */
  readonly loginId: string
  readonly isTester: boolean
  /** 낸 제출 수. 익명 계정은 번호뿐이라, 이것 없이는 누구인지 짚을 단서가 없다. */
  readonly attempts: number
  /** 마지막 접속. 기록이 없으면 빈 문자열이다. */
  readonly lastSeen: string
}

/** 표시 화면 한 벌. */
export interface TesterList {
  readonly rows: readonly TesterView[]
  /** 표시된 계정 수 — 이것이 G1 의 분모다. */
  readonly marked: number
  /** 로드맵이 전제하는 테스터 수. **서버가 준다** — 화면에 박으면 정본이 둘이 된다. */
  readonly minTesters: number
}

/** 서버가 주는 줄. */
interface RawTester {
  account_id: number
  handle: string
  login_id: string
  is_tester: boolean
  attempts: number
  last_seen: string
}

/** 서버가 주는 화면 한 벌. */
interface RawTesterList {
  rows: RawTester[]
  marked: number
  min_testers: number
}

/**
 * 서버 절을 화면 모양으로 바꾼다.
 *
 * @param raw 서버가 준 절.
 * @returns 화면이 쓰는 모양.
 */
function parseTesterList(raw: RawTesterList): TesterList {
  return {
    rows: raw.rows.map((row) => ({
      accountId: row.account_id,
      handle: row.handle,
      loginId: row.login_id,
      isTester: row.is_tester,
      attempts: row.attempts,
      lastSeen: row.last_seen,
    })),
    marked: raw.marked,
    minTesters: raw.min_testers,
  }
}

/**
 * 표시할 수 있는 계정을 읽는다.
 *
 * @param token 기기 토큰.
 * @returns 줄들. 관리자가 아니면 undefined.
 */
export async function readTesters(token: string): Promise<TesterList | undefined> {
  const response = await sendRequest('/admin/testers', { headers: { [TOKEN_HEADER]: token } })
  if (response === undefined || !response.ok) {
    return undefined
  }
  return parseTesterList((await response.json()) as RawTesterList)
}

/**
 * 계정 하나의 테스터 표시를 바꾼다.
 *
 * @param token 기기 토큰.
 * @param accountId 대상 계정.
 * @param isTester 켤지.
 * @returns 바뀐 뒤의 줄들. 실패하면 undefined.
 */
export async function applyTesterMark(
  token: string,
  accountId: number,
  isTester: boolean,
): Promise<TesterList | undefined> {
  const response = await sendRequest('/admin/testers/mark', {
    method: 'POST',
    headers: { [TOKEN_HEADER]: token, 'Content-Type': 'application/json' },
    body: JSON.stringify({ account_id: accountId, is_tester: isTester }),
  })
  if (response === undefined || !response.ok) {
    return undefined
  }
  return parseTesterList((await response.json()) as RawTesterList)
}
