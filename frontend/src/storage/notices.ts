/**
 * 알림함 (2026-09-25) — 판이 끝난 결과와 없는 동안 생긴 일이 쌓이는 곳.
 *
 * **판이 끝나면 결과가 출격 줄에 끼어들었다가 다음 판에 덮였다.** 한 줄짜리 알림이 화면을
 * 밀어낸 일도 있다(`battle/settlement.ts`). 알림은 화면 위에 떠서 밀지 않고(토스트), 읽을
 * 때까지 안 읽은 수로 남는다.
 *
 * **문구는 서버가 확정한 것이다.** 여기서는 `·` 로 끊기만 한다 — 다시 짜면 실제로 들어온
 * 것과 다른 말을 하게 된다.
 */
import { splitRewardNotes } from '../battle/settlement'
import { TOKEN_HEADER, sendRequest } from './serverSync'

/** 알림 종류. 글리프와 색을 고르는 열쇠이고 문구에는 안 쓴다. */
export type NoticeKind = 'run' | 'floor' | 'record' | 'rejected' | 'doppel' | 'auction' | 'other'

/** 알림 한 건. */
export interface NoticeView {
  readonly id: number
  readonly kind: NoticeKind
  readonly title: string
  /** 서버 본문을 항목별로 끊은 것. */
  readonly lines: readonly string[]
  /** ISO 시각. */
  readonly createdAt: string
  readonly isRead: boolean
}

/** 한 쪽의 알림 수 (2026-09-25 요청: 「10개 단위로」). 서버의 `NOTICE_PAGE` 와 같은 값이다. */
export const NOTICE_PAGE_SIZE = 10

/** 알림함 한 쪽. */
export interface NoticeBoardView {
  /** 안 읽은 수. **이 쪽 밖의 것도 센다.** */
  readonly unread: number
  /** 전체 건수. 쪽 수를 이것으로 센다. */
  readonly total: number
  /** 이 쪽이 건너뛴 건수. */
  readonly offset: number
  /** 새것부터. */
  readonly notices: readonly NoticeView[]
}

const KNOWN_KINDS: ReadonlySet<string> = new Set(['run', 'floor', 'record', 'rejected', 'doppel', 'auction'])

interface RawNotice {
  id: number
  kind: string
  title: string
  body: string
  created_at: string
  is_read: boolean
}

interface RawBoard {
  unread: number
  total?: number
  offset?: number
  notices: RawNotice[]
}

function parseBoard(body: RawBoard): NoticeBoardView {
  return {
    unread: body.unread,
    // 구버전 서버는 전체 수를 안 준다 — 그때는 받은 만큼이 전부다.
    total: body.total ?? body.notices.length,
    offset: body.offset ?? 0,
    notices: body.notices.map((raw) => ({
      id: raw.id,
      // **모르는 종류는 「기타」로 받는다.** 서버가 먼저 새 종류를 보내도 화면이 죽지 않는다.
      kind: (KNOWN_KINDS.has(raw.kind) ? raw.kind : 'other') as NoticeKind,
      title: raw.title,
      lines: splitRewardNotes(raw.body),
      createdAt: raw.created_at,
      isRead: raw.is_read,
    })),
  }
}

/**
 * 알림함 한 쪽을 읽는다. **읽기만으로는 읽음이 안 된다.**
 *
 * @param token 기기 토큰.
 * @param page 쪽 번호. 0 이 가장 새 쪽이다.
 * @returns 그 쪽. 서버에 못 닿으면 undefined.
 */
export async function readNotices(token: string, page = 0): Promise<NoticeBoardView | undefined> {
  const query = new URLSearchParams({
    offset: String(Math.max(0, page) * NOTICE_PAGE_SIZE),
    limit: String(NOTICE_PAGE_SIZE),
  })
  const response = await sendRequest(`/notices?${query.toString()}`, {
    headers: { [TOKEN_HEADER]: token },
  })
  if (response === undefined || !response.ok) {
    return undefined
  }
  return parseBoard((await response.json()) as RawBoard)
}

/**
 * 쪽 수. **알림이 없어도 한 쪽이다** — 「0 / 0」은 읽을 수 없는 말이다.
 *
 * @param total 전체 건수.
 * @returns 쪽 수.
 */
export function countNoticePages(total: number): number {
  return Math.max(1, Math.ceil(total / NOTICE_PAGE_SIZE))
}

/**
 * 화면이 본 가장 새 알림까지 읽음으로 적는다.
 *
 * **id 로 끊는다.** 「전부 읽음」이면 알림함을 여는 사이 도착한 것까지 읽음이 된다.
 *
 * @param token 기기 토큰.
 * @param upToId 화면이 본 가장 새 id.
 * @returns 적은 뒤의 알림함. 못 닿으면 undefined.
 */
export async function markNoticesRead(
  token: string,
  upToId: number,
): Promise<NoticeBoardView | undefined> {
  const response = await sendRequest('/notices/read', {
    method: 'POST',
    headers: { [TOKEN_HEADER]: token, 'Content-Type': 'application/json' },
    body: JSON.stringify({ up_to_id: upToId }),
  })
  if (response === undefined || !response.ok) {
    return undefined
  }
  return parseBoard((await response.json()) as RawBoard)
}

/**
 * 토스트로 띄울 새것을 고른다 — 지난번에 본 가장 새 id 보다 새 것.
 *
 * **처음 읽을 때는 아무것도 안 띄운다**(`seenId` 가 undefined). 들어오자마자 지난 알림
 * 쉰 장이 쏟아지면 토스트가 아니라 벽이다 — 처음에는 안 읽은 수만 적는다.
 *
 * @param board 방금 읽은 알림함.
 * @param seenId 지난번에 본 가장 새 id. 처음이면 undefined.
 * @returns 띄울 것(오래된 것부터)과 다음 기준 id.
 */
export function pickFreshNotices(
  board: NoticeBoardView,
  seenId: number | undefined,
): { readonly fresh: readonly NoticeView[]; readonly seenId: number } {
  const newest = board.notices.reduce((top, one) => Math.max(top, one.id), seenId ?? 0)
  if (seenId === undefined) {
    return { fresh: [], seenId: newest }
  }
  const fresh = board.notices.filter((one) => one.id > seenId && !one.isRead)
  return { fresh: [...fresh].sort((left, right) => left.id - right.id), seenId: newest }
}

/**
 * 안 읽은 수를 배지에 적을 글자로. **아홉을 넘으면 접는다** — 자리 폭이 늘면 줄이 밀린다.
 *
 * @param unread 안 읽은 수.
 * @returns 빈 문자열이면 배지를 안 그린다.
 */
export function formatUnreadBadge(unread: number): string {
  if (unread <= 0) {
    return ''
  }
  return unread > 9 ? '9+' : String(unread)
}
