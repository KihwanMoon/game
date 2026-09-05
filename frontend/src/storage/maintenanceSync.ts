/**
 * 정비 규칙을 서버와 주고받는다 (설계/4_아이템 §5).
 *
 * 실행은 서버가 티켓이 닫힐 때 한다 — 여기는 행 목록의 읽기·저장뿐이다.
 */
import { TOKEN_HEADER, readErrorDetail, sendRequest } from './serverSync'

/** 정비 규칙 한 행. 순서가 실행 순서다. */
export interface MaintenanceRowView {
  readonly action: string
  /** DISCARD 의 인자. 다른 행동은 빈 문자열이다. */
  readonly grade: string
}

/** 정비 규칙 전체. */
export interface MaintenanceView {
  readonly rows: readonly MaintenanceRowView[]
}

interface RawBody {
  rows: { action: string; grade: string }[]
}

function buildView(body: RawBody): MaintenanceView {
  return { rows: body.rows.map((row) => ({ action: row.action, grade: row.grade })) }
}

/**
 * 정비 행들을 읽는다.
 *
 * @param token 기기 토큰.
 * @returns 행들. 서버에 닿지 못했으면 undefined.
 */
export async function readMaintenance(token: string): Promise<MaintenanceView | undefined> {
  const response = await sendRequest('/maintenance', { headers: { [TOKEN_HEADER]: token } })
  if (response === undefined || !response.ok) {
    return undefined
  }
  return buildView((await response.json()) as RawBody)
}

/**
 * 정비 행들을 저장한다. 순서 그대로다.
 *
 * @param token 기기 토큰.
 * @param view 저장할 행들.
 * @returns 저장된 행들과 실패 사유. 실패하면 행들이 undefined 다.
 */
export async function saveMaintenance(
  token: string,
  view: MaintenanceView,
): Promise<{ view: MaintenanceView | undefined; detail: string }> {
  const response = await sendRequest('/maintenance', {
    method: 'PUT',
    headers: { [TOKEN_HEADER]: token, 'Content-Type': 'application/json' },
    body: JSON.stringify({ rows: view.rows }),
  })
  if (response === undefined) {
    return { view: undefined, detail: '서버에 닿지 못했다' }
  }
  if (!response.ok) {
    return { view: undefined, detail: await readErrorDetail(response) }
  }
  return { view: buildView((await response.json()) as RawBody), detail: '' }
}

/**
 * 지금 정비를 한 번 돌린다.
 *
 * **저장된 행 그대로 돈다.** 무엇을 할지 여기서 고르지 않는다 — 화면이 보여주는 순서와
 * 실제로 도는 순서가 갈리는 순간 미리보기가 거짓말이 된다.
 *
 * @param token 기기 토큰.
 * @returns 무슨 일이 있었는지 한 줄과, 못 닿았는지 여부. 한 일이 없으면 detail 이 빈
 *   문자열이다 — 그것도 답이라 화면이 「할 일이 없었다」로 적는다.
 */
export async function applyMaintenanceNow(
  token: string,
): Promise<{ detail: string; isDone: boolean }> {
  const response = await sendRequest('/maintenance/run', {
    method: 'POST',
    headers: { [TOKEN_HEADER]: token },
  })
  if (response === undefined) {
    return { detail: '서버에 닿지 못했다', isDone: false }
  }
  if (!response.ok) {
    return { detail: await readErrorDetail(response), isDone: false }
  }
  const body = (await response.json()) as { detail?: string }
  return { detail: String(body.detail ?? ''), isDone: true }
}
