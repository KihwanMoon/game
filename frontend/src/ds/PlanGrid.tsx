/**
 * PlanGrid — 가운데 열의 도면. 12x9 격자.
 *
 * 격자 크기는 토큰(`--plan-cols`·`--plan-rows`)이 정하고, 셀 크기의 **기본값**도 토큰
 * (`--plan-cell`)이 정한다. 화면 폭에 따른 값은 미디어쿼리가 토큰 쪽에서 바꾼다
 * (design/tokens/spacing.css — 데스크톱 64 / 가로 모바일 32 / 세로 모바일 30).
 *
 * `cell` 은 그 토큰을 **이 격자 안에서만** 덮어쓰는 선택적 탈출구다. 모바일 도면이
 * `cell={30}`·`cell={32}` 로 넘기는 계약이 있어 열어 두었다. 값을 주면 격자 엘리먼트에
 * `--plan-cell` 을 인라인으로 얹으므로, 자식 `PlanActor` 들이 쓰는
 * `calc(var(--plan-cell) * x)` 도 그대로 따라온다 — 좌표 계산이 두 벌이 되지 않는다.
 * 주지 않으면 토큰 값을 그대로 쓴다.
 *
 * 값을 주는 쪽이 화면 크기를 스스로 판단해야 하므로, **일반적인 반응형은 토큰(미디어
 * 쿼리)으로 하고 `cell` 은 한 도면만 다른 배율로 그려야 할 때 쓴다.**
 *
 * 격자 괘선은 배경 그라디언트로 그린다. 셀마다 DOM 을 두면 108개 노드가 매 틱 다시
 * 그려지고, 도면은 움직이지 않는 배경이라 그럴 이유가 없다.
 */
import type { CSSProperties, ReactNode } from 'react'

/** 셀 한 변을 정하는 토큰 이름. `cell` prop 이 덮어쓰는 대상이다. */
export const PLAN_CELL_TOKEN = '--plan-cell'

/** PlanGrid 가 받는 props. */
export interface PlanGridProps {
  /** 셀 한 변(px). 주지 않으면 `--plan-cell` 토큰을 쓴다. */
  readonly cell?: number
  /** PlanActor 들. 좌표로 절대 배치된다. */
  readonly children?: ReactNode
}

/**
 * 셀 크기를 덮어쓰는 인라인 스타일을 만든다.
 *
 * @param cell 셀 한 변(px). undefined 면 덮어쓰지 않는다.
 * @returns 인라인 스타일. 덮어쓸 것이 없으면 undefined.
 */
export function buildCellStyle(cell: number | undefined): CSSProperties | undefined {
  if (cell === undefined) {
    return undefined
  }
  // 커스텀 속성은 CSSProperties 의 키가 아니라 단언이 한 번 필요하다.
  return { [PLAN_CELL_TOKEN]: `${String(cell)}px` } as CSSProperties
}

/**
 * 도면 격자를 그린다.
 *
 * @param props 셀 크기와 격자 위에 얹을 말들.
 * @returns 렌더 트리.
 */
export function PlanGrid(props: PlanGridProps): React.JSX.Element {
  return (
    <div className="ds-plan" role="img" aria-label="전투 도면" style={buildCellStyle(props.cell)}>
      {props.children}
    </div>
  )
}
