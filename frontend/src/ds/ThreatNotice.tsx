/**
 * ThreatNotice — 예고(텔레그래프)가 몇 틱 남았는지 알린다.
 *
 * 텔레그래프는 "지금 피하면 산다" 를 읽을 수 있게 하는 장치라 **남은 틱 수가 본문**이다
 * (design/README.md §4). 위험은 색·글리프·좌측 세로바 세 채널로 적는다.
 */

/** 예고 표시의 기본 글리프. */
const DEFAULT_GLYPH = '◈'

/** ThreatNotice 가 받는 props. */
export interface ThreatNoticeProps {
  readonly text: string
  /** 남은 틱. 생략하면 틱 표시를 그리지 않는다. */
  readonly ticks?: number
  readonly glyph?: string
  readonly tone?: 'danger' | 'neutral'
}

/**
 * 예고 알림 한 줄을 그린다.
 *
 * @param props 문구·남은 틱·글리프·색 계열.
 * @returns 렌더 트리.
 */
export function ThreatNotice(props: ThreatNoticeProps): React.JSX.Element {
  const tone = props.tone ?? 'danger'
  const glyph = props.glyph ?? DEFAULT_GLYPH

  return (
    <div className={`ds-threat ds-threat--${tone}`} role="status">
      <span className="ds-threat__glyph" aria-hidden="true">
        {glyph}
      </span>
      <span className="ds-threat__text">{props.text}</span>
      {props.ticks === undefined ? null : (
        <span className="ds-threat__ticks">{props.ticks}틱</span>
      )}
    </div>
  )
}
