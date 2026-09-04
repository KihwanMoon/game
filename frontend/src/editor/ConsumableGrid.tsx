/**
 * 소모품 칸·재고 격자 (도면 그리드).
 *
 * **가방과 같은 격자다.** 칸은 상태만 그리고, 조작은 고른 칸의 상세 한 곳에 모인다 —
 * 예전에는 칸마다 카드가 펴져 머리·눈금·옵션 줄들·도구줄로 네 덩이였고, 칸 넷이면
 * 화면 한 장을 넘겼다.
 *
 * 훅을 안 쓴다. 고른 칸은 밖에서 든다.
 */
import { ValueExpr } from '../ds'

import type { ConsumableView } from '../storage'

import {
  buildConsumableSlotCells,
  buildConsumableStockCells,
  type ConsumableCell,
} from './consumableCells'
import { renderCell } from './GridCellView'

export interface ConsumableGridProps {
  readonly view: ConsumableView | undefined
  /** 지금 고른 칸의 key. 없으면 빈 문자열. */
  readonly pickedKey: string
  readonly onPick: (cell: ConsumableCell) => void
}

/** 재고가 없을 때 적을 말. 빈 격자만 두면 「불러오는 중」과 구별되지 않는다. */
const EMPTY_STOCK = '가방에 소모품이 없다 — 판을 돌면 나온다'

/**
 * 끼운 칸들과 가방 재고를 두 격자로 그린다.
 *
 * @param props 소모품 화면과 고른 칸.
 * @returns 격자 요소.
 */
export function ConsumableGrid(props: ConsumableGridProps): React.JSX.Element {
  const slotCells = buildConsumableSlotCells(props.view)
  const stockCells = buildConsumableStockCells(props.view)
  const filled = slotCells.filter((cell) => cell.label !== '').length
  return (
    <>
      {/* **「들고 갈 것」과 「가진 것」을 가른다.** 이 구분이 이 화면의 존재 이유다 —
          합치면 예전처럼 주운 만큼이 답이 된다. */}
      <div className="inv__head">
        {`들고 갈 것 — 칸 ${String(filled)} / ${String(slotCells.length)}`}
      </div>
      <div className="invg invg--cns">
        {slotCells.map((cell) => renderCell(cell, cell.key === props.pickedKey, props.onPick))}
      </div>
      <div className="inv__head">가진 것 — 가방 재고</div>
      {stockCells.length === 0 ? (
        <ValueExpr text={EMPTY_STOCK} size="sm" dim />
      ) : (
        <div className="invg invg--cns">
          {stockCells.map((cell) => renderCell(cell, cell.key === props.pickedKey, props.onPick))}
        </div>
      )}
    </>
  )
}
