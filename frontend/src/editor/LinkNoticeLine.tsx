/**
 * 연결 상태 한 줄 — 「확인 중」과 「못 닿았다」를 갈라 적는다.
 *
 * 여덟 패널이 같은 문장을 각자 들고 있었다. 그러면 고칠 때 일곱 개가 남고, 실제로
 * 첫 페인트마다 여덟 곳이 한꺼번에 거짓말을 했다 — 서버에 붙어 보기도 전에 「닿지
 * 못했다」라고 적혀 있었다.
 */
import { GlyphState } from '../ds'

import { describeLink, type LinkState } from './linkState'

export interface LinkNoticeLineProps {
  readonly link: LinkState
  /** 못 닿았을 때 무엇을 못 보는가. `아이템은 서버가 발급한다` 처럼 적는다. */
  readonly missing: string
}

/**
 * 아직 보여 줄 수 없는 이유를 한 줄로 그린다.
 *
 * **부르는 쪽은 이미 「보여 줄 수 없다」를 안다.** 그래서 `online` 이면 그것은 붙었는데
 * 아직 안 온 것이고, 그때도 한 줄이 필요하다 — 빈 화면은 「없다」로 읽힌다.
 *
 * @param props 연결 상태와 못 보는 것.
 * @returns 렌더 트리.
 */
export function LinkNoticeLine(props: LinkNoticeLineProps): React.JSX.Element {
  const notice = describeLink(props.link, props.missing)
  return <GlyphState state={notice.state} size="sm" label={notice.text} />
}
