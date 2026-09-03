/**
 * 서버 연결 상태 — **셋이다.** 「확인 중」과 「못 닿았다」는 다르다.
 *
 * 예전에는 불리언 하나였다. 첫 페인트에서 그 값이 `false` 라, 앱이 서버에 붙어 보기도
 * 전에 **「서버에 닿지 못했다」를 ◈ 위험으로 띄우고 가입·로그인 버튼을 잠갔다.**
 * 매번 뜨는 경보는 곧 아무도 안 읽는 경보가 되고, 진짜로 서버가 죽은 날 그 줄은
 * 배경이 된다.
 *
 * 규칙 상태를 넷으로 가른 것과 같은 이유다 — 「거짓」과 「아직 평가 안 함」을 한 값으로
 * 적으면 화면이 모르는 것을 아는 척한다.
 *
 * 문구도 여기 하나뿐이다. 예전에는 같은 문장이 여덟 패널에 복사돼 있었고, 그러면
 * 고칠 때 일곱 개가 남는다.
 */
import type { GlyphStateKind } from '../ds'

/** 서버에 붙었는가. `probing` 은 아직 물어보는 중이다. */
export type LinkState = 'probing' | 'online' | 'offline'

/** 물어보는 중임을 알리는 말. 경보가 아니라 상태다. */
export const PROBING_TEXT = '서버에 연결하는 중이다'

/** 붙었는데 아직 안 온 것. 빈 화면으로 두면 「없다」로 읽힌다. */
export const LOADING_TEXT = '불러오는 중이다'

/** 못 닿았을 때의 앞머리. 뒤에 「무엇을 못 보는가」가 붙는다. */
export const OFFLINE_PREFIX = '서버에 닿지 못했다'

/** 한 줄이 말할 것. */
export interface LinkNotice {
  readonly state: GlyphStateKind
  readonly text: string
}

/**
 * 아직 보여 줄 수 없는 이유를 화면 한 줄로 옮긴다.
 *
 * **넷을 갈라야 한다.** 셋은 연결 상태이고 하나는 그 뒤의 일이다.
 *
 *   probing  아직 물어보는 중 — 아무것도 실패하지 않았으므로 위험을 쓰지 않는다
 *   offline  못 닿았다 — 여기서만 ◈ 다
 *   online   붙었는데 아직 안 왔다 — 빈 화면으로 두면 「없다」로 읽힌다
 *
 * 예전에는 첫째와 둘째를 한 값으로 적어, 앱이 서버에 붙어 보기도 전에 ◈ 를 띄웠다.
 * 셋째는 아예 아무 말도 안 해서 「가방이 비었다」와 「아직 안 왔다」가 같아 보였다.
 *
 * @param link 연결 상태.
 * @param missing 못 닿았을 때 무엇을 못 보는지. `아이템은 서버가 발급한다` 처럼 적는다.
 * @returns 글리프 상태와 문구.
 */
export function describeLink(link: LinkState, missing: string): LinkNotice {
  if (link === 'probing') {
    return { state: 'pending', text: PROBING_TEXT }
  }
  if (link === 'online') {
    return { state: 'pending', text: LOADING_TEXT }
  }
  return { state: 'danger', text: `${OFFLINE_PREFIX} — ${missing}` }
}

/**
 * 서버가 있어야 하는 것을 지금 보여 줄 수 있는가.
 *
 * @param link 연결 상태.
 * @returns 붙었으면 참.
 */
export function checkLinked(link: LinkState): boolean {
  return link === 'online'
}
