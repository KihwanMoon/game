/**
 * 스킬 세팅을 서버와 주고받는다 (결정 #13 확장).
 *
 * **빼기만 한다.** 스킬은 장비가 열고, 여기서는 연 것 중 안 들고 갈 것을 끈다.
 */
import { TOKEN_HEADER, readErrorDetail, readItemContext, sendRequest } from './serverSync'
import type { ItemContext } from './serverSync'

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
  rows?: { skill_id: string; is_on: boolean; is_locked: boolean }[]
}

function buildView(body: RawBody): SkillPrefView {
  return {
    // **없으면 빈 목록이다.** `body.rows.map` 은 절이 흔들리면 그대로 터지고, 그러면
    // 스킬 하나 못 읽은 것이 화면 전체를 죽인다 — 이 저장소가 다른 파서에서 이미
    // 쓰는 규율이다 (`raw.is_base ?? true`).
    rows: (body.rows ?? []).map((row) => ({
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


/** 장비를 만진 직후의 화면 상태 — 가방·성장·스킬이 한 사건에서 함께 바뀐다. */
export interface GearState extends ItemContext {
  /** 장비가 여는 스킬들. 서버에 닿지 못했으면 undefined 다. */
  readonly skills: SkillPrefView | undefined
}

/**
 * 장비를 만진 뒤 화면이 다시 읽어야 할 것을 **한 번에** 읽는다.
 *
 * **문을 하나로 둔 이유가 있다** (`readBagState` 와 같은 규율). 셋을 따로 읽으면 어느
 * 한 경로에서 하나를 빠뜨리기 쉽고, 실제로 두 번 빠뜨렸다 — 처음에는 가방만 읽어
 * 「내 정보」의 숫자가 옛 값으로 남았고, 그것을 고친 뒤에도 스킬이 남아 **전도 막대를
 * 껴도 스킬 탭에 연쇄 번개가 안 떴다** (2026-09-10, 실제 신고).
 *
 * 마법만의 문제가 아니었다. 대검(범위공격)·방패(방벽)·연산 장갑(치유)도 같았는데,
 * 스킬을 여는 장비가 마법 무기 셋으로 늘면서 눈에 띈 것이다.
 *
 * **여기 있어야 순환이 안 난다.** 이 모듈이 `serverSync` 를 이미 부르므로, 묶는 일은
 * 부르는 쪽인 여기가 한다.
 *
 * @param token 기기 토큰.
 * @returns 가방·성장·스킬. 서버에 못 닿은 것은 undefined 다.
 */
export async function readGearState(token: string): Promise<GearState> {
  const [context, skills] = await Promise.all([readItemContext(token), readSkillPrefs(token)])
  return { ...context, skills }
}
