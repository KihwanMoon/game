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
import type { MetaSave } from '../core/schemas'
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
