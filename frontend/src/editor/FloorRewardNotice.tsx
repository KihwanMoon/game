/**
 * 층을 깬 자리에서 무엇을 벌었는지 말한다 (로드맵 W14).
 *
 * **서버는 이미 주고 있었다.** 층 경계마다 정산이 돌아 화폐·경험치·전리품이 들어오는데,
 * 그 결과가 뜨는 자리는 편집기뿐이었다 — 플레이 중에는 무엇을 벌었는지 알 수 없었다.
 * 「서버는 아는데 화면이 말하지 않는다」의 또 한 자리다.
 *
 * 훅을 안 쓴다. 훅 안에 있으면 검사가 문구를 못 본다 — 이 저장소의 렌더 검사는 jsdom
 * 없이 돌고, 같은 이유로 이번 세션에서 여러 번 갈랐다.
 */
import { GlyphState } from '../ds/GlyphState'
import { ValueExpr } from '../ds/ValueExpr'

/** 층 보상 안내가 받는 props. */
export interface FloorRewardNoticeProps {
  /** 방금 정산한 층. 0 이면 아직 정산한 층이 없다. */
  readonly floor: number
  /**
   * 서버가 확정한 보상 한 줄.
   *
   * **화면이 다시 만들지 않는다** — 무엇을 줬는지는 서버만 알고, 화면이 짜 맞추면 실제로
   * 들어온 것과 다른 말을 하게 된다.
   */
  readonly reward: string
}

/**
 * 층 보상 한 줄을 적는다.
 *
 * @param floor 방금 정산한 층.
 * @param reward 서버가 확정한 보상 문자열.
 * @returns 화면에 적을 한 줄. 벌어들인 것이 없으면 빈 문자열.
 */
export function formatFloorReward(floor: number, reward: string): string {
  if (floor <= 0 || reward.trim() === '') {
    return ''
  }
  return `${String(floor)}층 정산 — ${reward}`
}

/**
 * 층을 깬 순간의 벌이를 그린다.
 *
 * @param props 층과 보상 문자열.
 * @returns 렌더 트리. 정산한 것이 없으면 아무것도 안 그린다.
 */
export function FloorRewardNotice(props: FloorRewardNoticeProps): React.JSX.Element | null {
  const text = formatFloorReward(props.floor, props.reward)
  if (text === '') {
    return null
  }
  return (
    <span className="launch__reward">
      {/* 참 상태의 글리프를 쓴다 — 벌어들인 것은 「일어난 일」이고, 이 화면에서 그것을
          적는 다른 자리(편집기의 보상 줄)와 같은 표기여야 한다. */}
      <GlyphState state="true" size="sm" label={text} />
      <ValueExpr text="가방에 들어와 있다" size="sm" dim />
    </span>
  )
}
