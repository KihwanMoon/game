/**
 * GlyphState — 참/거짓을 색·글리프·명도 **세 채널**로 적는다.
 *
 * 색은 정보의 유일한 채널이 될 수 없다(design/README.md). 흑백 인쇄와 색약 조건에서도
 * 다섯 상태가 구분돼야 하므로 상태마다 글리프가 다르고, 거짓·대기는 명도를 한 단
 * 낮춘다. 보조 기술을 위해 상태 이름을 감춘 텍스트로 함께 싣는다 — 네 번째 채널이다.
 *
 * 황동 예산: `armed` 가 `--state-armed`(황동)을 쓴다.
 */

/** 규칙 한 줄이 가질 수 있는 판정 상태. */
export type GlyphStateKind = 'true' | 'false' | 'armed' | 'danger' | 'pending'

/** 상태별 글리프. 전부 유니코드 도형이며 이모지가 아니다. */
export const STATE_GLYPHS: ReadonlyMap<GlyphStateKind, string> = new Map([
  ['true', '✓'],
  ['false', '·'],
  ['armed', '◆'],
  ['danger', '◈'],
  ['pending', '◇'],
])

/** 보조 기술이 읽을 상태 이름. 색을 못 보는 경로의 마지막 채널이다. */
export const STATE_NAMES: ReadonlyMap<GlyphStateKind, string> = new Map([
  ['true', '조건 참'],
  ['false', '조건 거짓'],
  ['armed', '이번 틱 발동'],
  ['danger', '위험'],
  ['pending', '평가 대기'],
])

/** GlyphState 가 받는 props. */
export interface GlyphStateProps {
  readonly state: GlyphStateKind
  /** 글리프 오른쪽 라벨. 없으면 글리프만 그린다. */
  readonly label?: string
  readonly size?: 'md' | 'sm'
}

/**
 * 상태 글리프 하나를 그린다.
 *
 * @param props 상태·라벨·크기.
 * @returns 렌더 트리.
 */
export function GlyphState(props: GlyphStateProps): React.JSX.Element {
  const glyph = STATE_GLYPHS.get(props.state) ?? STATE_GLYPHS.get('pending')
  const name = STATE_NAMES.get(props.state) ?? props.state
  const size = props.size ?? 'md'

  return (
    <span className={`ds-glyph ds-glyph--${props.state} ds-glyph--${size}`}>
      <span className="ds-glyph__mark" aria-hidden="true">
        {glyph}
      </span>
      <span className="ds-sr">{name}</span>
      {props.label === undefined ? null : <span className="ds-glyph__text">{props.label}</span>}
    </span>
  )
}
