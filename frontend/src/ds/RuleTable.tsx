/**
 * RuleTable — 좌측 320px 열의 규칙표. RuleRow 를 우선순위 순으로 담는다.
 *
 * 표가 아니라 목록으로 짠 것은 각 줄이 클릭 가능한 편집 대상이고, 목록 항목 안의
 * 버튼이 표 셀 안의 버튼보다 키보드 이동이 단순하기 때문이다.
 */
import type { ReactNode } from 'react'

/** RuleTable 이 받는 props. */
export interface RuleTableProps {
  readonly children?: ReactNode
}

/**
 * 규칙표를 그린다.
 *
 * @param props RuleRow 들.
 * @returns 렌더 트리.
 */
export function RuleTable(props: RuleTableProps): React.JSX.Element {
  return (
    <ul className="ds-rule-table" aria-label="규칙표">
      {props.children}
    </ul>
  )
}
