/**
 * 지킴이·배포봇 조회 (관리 화면).
 *
 * **로그에서 죽고 있었다.** 지킴이는 5분마다 정확히 판단해 컨테이너 로그에 뱉었고,
 * 컨테이너 로그를 읽는 사람은 없다 (알려진이슈 Z1).
 *
 * **다시 계산하지 않는다.** 지킴이가 남긴 것을 읽는다 — 화면이 열릴 때마다 새로 재면
 * 5분 주기가 무의미해지고, 「이게 언제부터 이랬나」를 여전히 못 답한다.
 */
import { TOKEN_HEADER, sendRequest } from './serverSync'

/** 지표 하나의 지금 상태. */
export interface WatchRow {
  readonly key: string
  /** `OK` · `살핌` · `틀림`. */
  readonly level: string
  readonly text: string
  readonly detail: string
  /** 이 등급이 된 때. **「어제 낮부터 틀렸다」가 여기서 읽힌다.** */
  readonly changedAt: string
  /** 마지막으로 본 때. 오래됐으면 지킴이 자신이 안 도는 것이다. */
  readonly seenAt: string
}

/** 등급이 바뀐 순간 하나. */
export interface WatchEvent {
  readonly key: string
  readonly level: string
  readonly text: string
  readonly detail: string
  readonly happenedAt: string
}

/** 배포 전에 알아야 하는 것 — 게이트를 뺀 절반. */
export interface DeployBrief {
  readonly changes: readonly string[]
  readonly authors: readonly string[]
  readonly breakage: readonly string[]
  /** 되돌리는 법. **이것이 없으면 컨펌이 아니라 도박이다.** */
  readonly undo: readonly string[]
  /** 화면이 안 돌린다 — 사람이 그대로 옮겨 칠 명령. */
  readonly gateCommands: readonly string[]
  readonly openRuns: number
}

/** 지킴이 화면 한 벌. */
export interface WatchView {
  readonly rows: readonly WatchRow[]
  readonly events: readonly WatchEvent[]
  readonly deploy: DeployBrief
}

/** 서버가 주는 절. */
interface RawWatch {
  rows?: {
    key: string
    level: string
    text: string
    detail: string
    changed_at: string
    seen_at: string
  }[]
  events?: {
    key: string
    level: string
    text: string
    detail: string
    happened_at: string
  }[]
  deploy?: {
    changes?: string[]
    authors?: string[]
    breakage?: string[]
    undo?: string[]
    gate_commands?: string[]
    open_runs?: number
  }
}

/**
 * 서버 절을 화면 모양으로 바꾼다.
 *
 * @param raw 서버가 준 절.
 * @returns 화면이 쓰는 모양.
 */
export function parseWatch(raw: RawWatch): WatchView {
  const deploy = raw.deploy ?? {}
  return {
    rows: (raw.rows ?? []).map((row) => ({
      key: row.key,
      level: row.level,
      text: row.text,
      detail: row.detail,
      changedAt: row.changed_at,
      seenAt: row.seen_at,
    })),
    events: (raw.events ?? []).map((event) => ({
      key: event.key,
      level: event.level,
      text: event.text,
      detail: event.detail,
      happenedAt: event.happened_at,
    })),
    deploy: {
      changes: deploy.changes ?? [],
      authors: deploy.authors ?? [],
      breakage: deploy.breakage ?? [],
      undo: deploy.undo ?? [],
      gateCommands: deploy.gate_commands ?? [],
      openRuns: deploy.open_runs ?? 0,
    },
  }
}

/**
 * 지킴이가 남긴 것과 배포 브리핑을 읽는다.
 *
 * @param token 기기 토큰.
 * @returns 화면 한 벌. 관리자가 아니면 undefined.
 */
export async function readWatch(token: string): Promise<WatchView | undefined> {
  const response = await sendRequest('/admin/watch', { headers: { [TOKEN_HEADER]: token } })
  if (response === undefined || !response.ok) {
    return undefined
  }
  return parseWatch((await response.json()) as RawWatch)
}
