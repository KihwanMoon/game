/**
 * 정비 규칙을 서버와 주고받는다 (설계/4_아이템 §5).
 *
 * 실행은 서버가 티켓이 닫힐 때 한다 — 여기는 스위치의 읽기·저장뿐이다.
 */
import { TOKEN_HEADER, readErrorDetail, sendRequest } from './serverSync'

/** 정비 규칙 화면 값. */
export interface MaintenanceView {
  readonly isRefillOn: boolean
  readonly isRepairOn: boolean
  /** 버릴 등급. 빈 문자열이면 안 버린다. */
  readonly discardGrade: string
}

interface RawBody {
  is_refill_on: boolean
  is_repair_on: boolean
  discard_grade: string
}

function buildView(body: RawBody): MaintenanceView {
  return {
    isRefillOn: body.is_refill_on,
    isRepairOn: body.is_repair_on,
    discardGrade: body.discard_grade,
  }
}

/**
 * 정비 규칙을 읽는다.
 *
 * @param token 기기 토큰.
 * @returns 규칙. 서버에 닿지 못했으면 undefined.
 */
export async function readMaintenance(token: string): Promise<MaintenanceView | undefined> {
  const response = await sendRequest('/maintenance', { headers: { [TOKEN_HEADER]: token } })
  if (response === undefined || !response.ok) {
    return undefined
  }
  return buildView((await response.json()) as RawBody)
}

/**
 * 정비 규칙을 저장한다.
 *
 * @param token 기기 토큰.
 * @param view 저장할 규칙.
 * @returns 저장된 규칙과 실패 사유. 실패하면 규칙이 undefined 다.
 */
export async function saveMaintenance(
  token: string,
  view: MaintenanceView,
): Promise<{ view: MaintenanceView | undefined; detail: string }> {
  const response = await sendRequest('/maintenance', {
    method: 'PUT',
    headers: { [TOKEN_HEADER]: token, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      is_refill_on: view.isRefillOn,
      is_repair_on: view.isRepairOn,
      discard_grade: view.discardGrade,
    }),
  })
  if (response === undefined) {
    return { view: undefined, detail: '서버에 닿지 못했다' }
  }
  if (!response.ok) {
    return { view: undefined, detail: await readErrorDetail(response) }
  }
  return { view: buildView((await response.json()) as RawBody), detail: '' }
}
