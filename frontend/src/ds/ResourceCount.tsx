/**
 * ResourceCount — 물약처럼 낱개로 세는 자원.
 *
 * 남은 수를 글리프 개수로 그리고 숫자도 함께 적는다. 개수는 색과 무관한 채널이라
 * 흑백에서도 읽힌다.
 */

/** 남아 있는 칸의 기본 글리프. */
const FILLED_GLYPH = '●'

/** 빈 칸의 글리프. 채워진 글리프를 바꿔도 빈 칸은 이것으로 둔다. */
const EMPTY_GLYPH = '○'

/** 그릴 낱개 글리프의 상한. 넘으면 숫자로만 읽는다. */
export const PIP_LIMIT = 12

/** ResourceCount 가 받는 props. */
export interface ResourceCountProps {
  readonly label: string
  readonly count: number
  readonly max: number
  /** 채워진 칸의 글리프. 유니코드 도형만 — 이모지 금지. */
  readonly glyph?: string
}

/**
 * 자원 낱개 표시를 그린다.
 *
 * @param props 라벨·현재 수·최대 수·글리프.
 * @returns 렌더 트리.
 */
export function ResourceCount(props: ResourceCountProps): React.JSX.Element {
  const filledGlyph = props.glyph ?? FILLED_GLYPH
  const total = Math.max(0, Math.trunc(props.max))
  const held = Math.max(0, Math.min(Math.trunc(props.count), total))
  const pips = total <= PIP_LIMIT ? Array.from({ length: total }, (_unused, index) => index) : []

  return (
    <span className="ds-resource">
      <span className="ds-label">{props.label}</span>
      {pips.length === 0 ? null : (
        <span className="ds-resource__pips" aria-hidden="true">
          {pips.map((index) => (
            <span
              className={index < held ? 'ds-resource__pip' : 'ds-resource__pip--empty'}
              key={index}
            >
              {index < held ? filledGlyph : EMPTY_GLYPH}
            </span>
          ))}
        </span>
      )}
      <span className="ds-readout">
        {props.count} / {props.max}
      </span>
    </span>
  )
}
