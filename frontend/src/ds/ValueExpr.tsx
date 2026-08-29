/**
 * ValueExpr — 실측값이 병기된 조건문을 그린다.
 *
 * 받는 문자열은 `적거리(2) <= 사거리(3)` 형태다. RuleVM 이 참/거짓만이 아니라 **각 항이
 * 실제로 무슨 값이었는지**를 내보내기 때문이며(GDD §8.2), 죽고 나서 어느 항이 틀렸는지
 * 짚을 수 있어야 P1(실패는 정보다)이 성립한다. 그래서 괄호 안 실측값을 한 단 강조한다.
 */

/** 괄호로 감싼 실측값. 중첩 괄호는 규칙 문법에 없다. */
const VALUE_PATTERN = /\([^()]*\)/g

/** 조각 하나. `isValue` 가 참이면 괄호로 감싼 실측값이다. */
export interface ExprSegment {
  readonly text: string
  readonly isValue: boolean
}

/**
 * 조건문을 항 이름과 실측값 조각으로 가른다.
 *
 * @param text `적거리(2) <= 사거리(3)` 형태의 조건문.
 * @returns 원문 순서를 유지한 조각 목록. 이어 붙이면 원문과 같다.
 */
export function splitExprSegments(text: string): readonly ExprSegment[] {
  const segments: ExprSegment[] = []
  let cursor = 0
  for (const match of text.matchAll(VALUE_PATTERN)) {
    const start = match.index
    if (start > cursor) {
      segments.push({ text: text.slice(cursor, start), isValue: false })
    }
    segments.push({ text: match[0], isValue: true })
    cursor = start + match[0].length
  }
  if (cursor < text.length) {
    segments.push({ text: text.slice(cursor), isValue: false })
  }
  return segments
}

/** ValueExpr 가 받는 props. */
export interface ValueExprProps {
  readonly text: string
  readonly size?: 'md' | 'sm'
  /** 명도를 한 단 낮춘다. 거짓으로 떨어진 조건 등. */
  readonly dim?: boolean
}

/**
 * 조건문 한 줄을 그린다.
 *
 * @param props 조건문·크기·명도.
 * @returns 렌더 트리.
 */
export function ValueExpr(props: ValueExprProps): React.JSX.Element {
  const size = props.size ?? 'md'
  const classNames = ['ds-expr', `ds-expr--${size}`, props.dim === true ? 'ds-expr--dim' : '']
    .filter((name) => name !== '')
    .join(' ')

  return (
    <span className={classNames}>
      {splitExprSegments(props.text).map((segment, index) =>
        segment.isValue ? (
          <span className="ds-expr__value" key={`${String(index)}-${segment.text}`}>
            {segment.text}
          </span>
        ) : (
          <span key={`${String(index)}-${segment.text}`}>{segment.text}</span>
        ),
      )}
    </span>
  )
}
