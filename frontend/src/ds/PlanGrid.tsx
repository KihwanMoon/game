/**
 * PlanGrid — 가운데 열의 도면. 12x9 격자, 셀 64px.
 *
 * 격자 크기와 셀 크기는 토큰(`--plan-cols`·`--plan-rows`·`--plan-cell`)이 정한다. 여기서
 * 숫자를 받지 않는 이유는 기준 해상도에서 가운데 열 가용 폭이 818px 이고 64px 셀로는
 * 12열이 상한이기 때문이다 — 방을 더 키우려면 토큰과 셀 크기 정책을 먼저 정해야 한다
 * (design/README.md D-2).
 *
 * 격자 괘선은 배경 그라디언트로 그린다. 셀마다 DOM 을 두면 108개 노드가 매 틱 다시
 * 그려지고, 도면은 움직이지 않는 배경이라 그럴 이유가 없다.
 */
import type { ReactNode } from 'react'

/** PlanGrid 가 받는 props. */
export interface PlanGridProps {
  /** PlanActor 들. 좌표로 절대 배치된다. */
  readonly children?: ReactNode
}

/**
 * 도면 격자를 그린다.
 *
 * @param props 격자 위에 얹을 말들.
 * @returns 렌더 트리.
 */
export function PlanGrid(props: PlanGridProps): React.JSX.Element {
  return (
    <div className="ds-plan" role="img" aria-label="전투 도면">
      {props.children}
    </div>
  )
}
