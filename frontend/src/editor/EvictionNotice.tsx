/**
 * 튕김 안내 — 다른 기기에서 로그인해 이 기기의 연결이 끊겼다.
 *
 * **서버가 죽은 것과 내가 튕긴 것은 사람이 해야 할 일이 다르다.** 앞엣것은 기다리면
 * 되고 뒤엣것은 다시 로그인해야 한다. 둘 다 "오프라인" 으로 보이면 사람은 기다린다.
 *
 * **이 기기의 저장은 안 지운다고 말한다.** 튕긴 것은 내가 고른 일이 아니고, 여기서
 * 지우면 잃는 것이 하나 더 는다 — 로그아웃은 내가 고른 일이라 지운다.
 */
import { GlyphState } from '../ds'

export interface EvictionNoticeProps {
  readonly isEvicted: boolean
}

export const EVICTION_TEXT =
  '다른 기기에서 로그인했다 — 이 기기는 연결이 끊겼다. 이 기기의 규칙표는 그대로 있고,' +
  ' 다시 로그인하면 계정이 돌아온다'

/**
 * 튕김 안내를 그린다.
 *
 * @param props 튕겼는지.
 * @returns 렌더 트리. 안 튕겼으면 null.
 */
export function EvictionNotice(props: EvictionNoticeProps): React.JSX.Element | null {
  if (!props.isEvicted) {
    return null
  }
  return <GlyphState state="danger" size="sm" label={EVICTION_TEXT} />
}
