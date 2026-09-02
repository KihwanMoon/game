/**
 * 스킬 세팅을 서버와 주고받는다 (결정 #13 확장).
 *
 * **빼기만 한다.** 스킬은 장비가 열고, 여기서는 연 것 중 안 들고 갈 것을 끈다.
 */
import { TOKEN_HEADER, readErrorDetail, sendRequest } from './serverSync'

/** 스킬 한 줄. */
export interface SkillRowView {
  readonly skillId: string
  readonly isOn: boolean
  /** 기본 공격은 끌 수 없다 — 폴백이 기댄다. */
  readonly isLocked: boolean
}

/** 스킬 세팅 전체. */
export interface SkillPrefView {
  readonly rows: readonly SkillRowView[]
}

interface RawBody {
  rows: { skill_id: string; is_on: boolean; is_locked: boolean }[]
}

function buildView(body: RawBody): SkillPrefView {
  return {
    rows: body.rows.map((row) => ({
      skillId: row.skill_id,
      isOn: row.is_on,
      isLocked: row.is_locked,
    })),
  }
}

/**
 * 스킬 세팅을 읽는다.
 *
 * @param token 기기 토큰.
 * @returns 세팅. 서버에 닿지 못했으면 undefined.
 */
export async function readSkillPrefs(token: string): Promise<SkillPrefView | undefined> {
  const response = await sendRequest('/skills', { headers: { [TOKEN_HEADER]: token } })
  if (response === undefined || !response.ok) {
    return undefined
  }
  return buildView((await response.json()) as RawBody)
}

/**
 * 스킬 세팅을 저장한다. 다음 티켓부터 실린다.
 *
 * @param token 기기 토큰.
 * @param view 저장할 세팅.
 * @returns 저장 뒤 세팅과 실패 사유.
 */
export async function saveSkillPrefs(
  token: string,
  view: SkillPrefView,
): Promise<{ view: SkillPrefView | undefined; detail: string }> {
  const response = await sendRequest('/skills', {
    method: 'PUT',
    headers: { [TOKEN_HEADER]: token, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      rows: view.rows.map((row) => ({
        skill_id: row.skillId,
        is_on: row.isOn,
        is_locked: row.isLocked,
      })),
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
