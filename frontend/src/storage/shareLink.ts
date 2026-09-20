/**
 * 규칙표를 짧은 주소로 만든다 — 공유 코드의 다음 걸음.
 *
 * **코드는 있었는데 아무도 안 붙였다.** `v2:H4sIA…` 가 475자라 커뮤니티에 그대로
 * 붙는 링크가 아니고, 단축 주소를 쓰면 그 링크는 우리 것이 아니게 된다. 서버가
 * `/r/<id>` 를 내주고(`api/routes/share.py`) 그 장은 크롤러도 읽는다.
 *
 * **코드를 없애지 않는다.** 서버가 없어도 게임은 돌아야 하고(CLAUDE.md), 그때 남에게
 * 표를 건네는 수단은 코드뿐이다. 링크는 서버가 있을 때 더 나은 길이지 대체가 아니다.
 */
import type { RuleSet } from '../core/schemas'
import { buildRuleSetPayload } from './presetPayload'
import { TOKEN_HEADER, readToken, sendRequest } from './serverSync'
import type { StorageLike } from './saveStore'

/** 서버가 주는 절. */
interface ShareBody {
  readonly share_id: string
  readonly path: string
}

/** 링크 만들기의 결과. */
export interface ShareResult {
  /** 붙여 넣을 주소. 실패하면 빈 문자열. */
  readonly url: string
  /** 실패 사유. 성공이면 빈 문자열 — `onImport` 와 같은 규약이다. */
  readonly problem: string
}

/** 서버가 못 읽을 때 화면에 적는 말. */
export const SHARE_OFFLINE = '서버에 닿지 못했다 — 코드는 그대로 쓸 수 있다'

/**
 * 규칙표를 공유용으로 올리고 주소를 받는다.
 *
 * **주소를 여기서 조립한다.** 서버는 경로(`/r/…`)만 주고 어느 도메인에 서 있는지는
 * 모른다 — 알려면 서버가 자기 주소를 설정으로 들고 있어야 하고, 그러면 개발·운영이
 * 갈릴 때마다 그 설정이 틀린다.
 *
 * @param ruleset 올릴 규칙표.
 * @param name 붙일 이름.
 * @param storage 토큰이 든 저장소.
 * @param origin 이 사이트의 주소. 기본은 지금 열려 있는 곳이다.
 * @returns 주소와 실패 사유.
 */
export async function createShareLink(
  ruleset: RuleSet,
  name: string,
  storage: StorageLike | undefined,
  origin: string,
): Promise<ShareResult> {
  const token = readToken(storage)
  if (token === undefined) {
    return { url: '', problem: SHARE_OFFLINE }
  }
  const response = await sendRequest('/share', {
    method: 'POST',
    headers: { [TOKEN_HEADER]: token, 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, ruleset: buildRuleSetPayload(ruleset) }),
  })
  if (response === undefined) {
    return { url: '', problem: SHARE_OFFLINE }
  }
  if (!response.ok) {
    // 서버가 규칙표를 반려했다. **사유를 그대로 보여 준다** — 「실패했다」만 적으면
    // 고칠 곳을 못 찾는다.
    const detail = await readDetail(response)
    return { url: '', problem: detail === '' ? '서버가 이 표를 받지 않았다' : detail }
  }
  const body = (await response.json()) as ShareBody
  return { url: `${origin}${body.path}`, problem: '' }
}

/**
 * 오류 응답에서 사유를 뽑는다.
 *
 * @param response 서버 응답.
 * @returns 사유. 못 읽으면 빈 문자열.
 */
async function readDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { readonly detail?: unknown }
    return typeof body.detail === 'string' ? body.detail : ''
  } catch {
    return ''
  }
}
