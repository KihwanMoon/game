/**
 * 아이템 카탈로그 초안·발행 조회 (설계/9_에이전트_운영 §3.2).
 *
 * **아이템만 문이 열려 있었다.** 스킬·블록·밸런스·룸·적 규칙표는 사람이 발행을 눌러야
 * 반영되는데, 카탈로그는 정본이 서버 DB 라 등록·수정·폐기가 **즉시** 세계를 바꿨다.
 * 아이템 에이전트를 붙이면 그 문으로 검토 없이 세계가 바뀐다.
 *
 * 이제 셋 다 초안으로 간다. 올리는 것과 내는 것이 다른 버튼이다.
 */
import { TOKEN_HEADER, sendRequest } from './serverSync'

/** 쌓여 있는 조작 한 줄. */
export interface CatalogDraftRow {
  readonly catalogId: string
  /** `item` · `edit` · `retire` · `restore`. */
  readonly action: string
  readonly reason: string
  /** 누가 올렸는가. 에이전트와 사람을 화면에서 갈라야 검토가 흐려지지 않는다. */
  readonly handle: string
  readonly updatedAt: string
  /** 지금 카탈로그에 대고 다시 검사한 결과. 통과면 빈 문자열이다. */
  readonly problem: string
}

/** 초안 화면 한 벌. */
export interface CatalogDraftView {
  readonly drafts: readonly CatalogDraftRow[]
  readonly generation: number
  readonly hint: string
}

/** 서버가 주는 줄. */
interface RawDraft {
  catalog_id: string
  action: string
  reason: string
  handle: string
  updated_at: string
  problem: string
}

/** 서버가 주는 화면 한 벌. */
interface RawDraftView {
  drafts?: RawDraft[]
  generation?: number
  hint?: string
}

/**
 * 서버 절을 화면 모양으로 바꾼다.
 *
 * @param raw 서버가 준 절.
 * @returns 화면이 쓰는 모양.
 */
export function parseCatalogDrafts(raw: RawDraftView): CatalogDraftView {
  return {
    drafts: (raw.drafts ?? []).map((row) => ({
      catalogId: row.catalog_id,
      action: row.action,
      reason: row.reason,
      handle: row.handle,
      updatedAt: row.updated_at,
      problem: row.problem,
    })),
    generation: raw.generation ?? 0,
    hint: raw.hint ?? '',
  }
}

/**
 * 조작 하나를 **초안으로** 올린다.
 *
 * 응답은 카탈로그가 아니라 쌓인 초안들이다 — 올린 것은 아직 아이템이 아니다.
 *
 * @param token 기기 토큰.
 * @param path 라우트 경로.
 * @param body 보낼 절.
 * @returns 쌓인 초안들과 사유. 사유는 통과면 빈 문자열이다.
 */
export async function applyCatalogDraft(
  token: string,
  path: string,
  body: unknown,
): Promise<{ view: CatalogDraftView | undefined; detail: string }> {
  const response = await sendRequest(path, {
    method: 'POST',
    headers: { [TOKEN_HEADER]: token, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (response === undefined) {
    return { view: undefined, detail: '서버에 닿지 못했다' }
  }
  const raw = (await response.json()) as Record<string, unknown>
  if (!response.ok) {
    return { view: undefined, detail: String(raw.detail ?? '거절됐다') }
  }
  return { view: parseCatalogDrafts(raw as RawDraftView), detail: '' }
}

/**
 * 쌓여 있는 조작을 읽는다.
 *
 * @param token 기기 토큰.
 * @returns 초안들. 관리자가 아니면 undefined.
 */
export async function readCatalogDrafts(token: string): Promise<CatalogDraftView | undefined> {
  const response = await sendRequest('/admin/catalog/drafts', {
    headers: { [TOKEN_HEADER]: token },
  })
  if (response === undefined || !response.ok) {
    return undefined
  }
  return parseCatalogDrafts((await response.json()) as RawDraftView)
}

/**
 * 초안 하나를 버린다.
 *
 * @param token 기기 토큰.
 * @param catalogId 버릴 아이템.
 * @returns 남은 초안들과 사유. 사유는 통과면 빈 문자열이다.
 */
export async function applyCatalogDiscard(
  token: string,
  catalogId: string,
): Promise<{ view: CatalogDraftView | undefined; detail: string }> {
  const response = await sendRequest('/admin/catalog/draft/discard', {
    method: 'POST',
    headers: { [TOKEN_HEADER]: token, 'Content-Type': 'application/json' },
    body: JSON.stringify({ catalog_id: catalogId }),
  })
  if (response === undefined) {
    return { view: undefined, detail: '서버에 닿지 못했다' }
  }
  const raw = (await response.json()) as Record<string, unknown>
  if (!response.ok) {
    return { view: undefined, detail: String(raw.detail ?? '거절됐다') }
  }
  return { view: parseCatalogDrafts(raw as RawDraftView), detail: '' }
}

/**
 * 쌓인 것을 전부 반영한다. **사람이 누른다.**
 *
 * @param token 기기 토큰.
 * @param generation 지금 세대. 손으로 적어야 눌린다.
 * @param reason 왜 내는가.
 * @returns 사유. 통과하면 빈 문자열이다.
 */
export async function applyCatalogPublish(
  token: string,
  generation: number,
  reason: string,
): Promise<string> {
  const response = await sendRequest('/admin/catalog/publish', {
    method: 'POST',
    headers: { [TOKEN_HEADER]: token, 'Content-Type': 'application/json' },
    body: JSON.stringify({ generation, reason }),
  })
  if (response === undefined) {
    return '서버에 닿지 못했다'
  }
  if (!response.ok) {
    const raw = (await response.json()) as Record<string, unknown>
    return String(raw.detail ?? '거절됐다')
  }
  return ''
}
