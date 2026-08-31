/**
 * CellGrid — 그림 칸을 격자로 늘어놓는다.
 *
 * 목록을 줄로 쌓으면 한 화면에 열댓 개가 들어가고, 그것이 "텍스트만 있다" 로 보이는
 * 이유다. 격자는 좁은 폭에서 두 칸, 넓은 폭에서 예닐곱 칸으로 **폭이 스스로 정한다**
 * — 화면 크기를 여기서 재지 않는다(브레이크포인트는 토큰 한 곳에만 있다).
 *
 * 칸을 누를 수 있게 하면 칸 전체가 버튼이 된다. 세로 배치에서 칸의 최소 높이는
 * `--tap-min` 이며, 작은 글씨 옆에 작은 버튼을 따로 두지 않는 이유가 그것이다.
 */
import type { ReactNode } from 'react'

/** 칸 하나. */
export interface Cell {
  readonly id: string
  /** 칸 안의 그림 자리. `Thumb` 를 넣는다. */
  readonly thumb: ReactNode
  readonly name: string
  /** 이름 아래 한두 줄. 세 줄을 넘기면 격자가 목록이 된다. */
  readonly meta?: readonly string[]
  /** 눌렸을 때 강조할지. 선택한 칸이 어느 것인지 눈에 남아야 한다. */
  readonly isSelected?: boolean
}

/** CellGrid 가 받는 props. */
export interface CellGridProps {
  readonly cells: readonly Cell[]
  /** 누를 수 있게 한다. 없으면 칸은 그냥 보이는 것이다. */
  readonly onSelect?: (id: string) => void
  /** 빈 목록일 때 적을 한 줄. */
  readonly emptyText?: string
}

/**
 * 칸 격자를 그린다.
 *
 * @param props 칸들·선택 핸들러·빈 문구.
 * @returns 렌더 트리.
 */
export function CellGrid(props: CellGridProps): React.JSX.Element {
  if (props.cells.length === 0) {
    return <p className="ds-cells__empty">{props.emptyText ?? '아직 없다'}</p>
  }
  const onSelect = props.onSelect
  return (
    <ul className="ds-cells">
      {props.cells.map((cell) => {
        const body = (
          <>
            {cell.thumb}
            <span className="ds-cell__name">{cell.name}</span>
            {(cell.meta ?? []).map((line) => (
              <span className="ds-cell__meta" key={line}>
                {line}
              </span>
            ))}
          </>
        )
        return (
          <li
            className={`ds-cell${cell.isSelected === true ? ' ds-cell--on' : ''}`}
            key={cell.id}
          >
            {onSelect === undefined ? (
              body
            ) : (
              <button
                className="ds-cell__hit"
                type="button"
                onClick={() => {
                  onSelect(cell.id)
                }}
              >
                {body}
              </button>
            )}
          </li>
        )
      })}
    </ul>
  )
}
