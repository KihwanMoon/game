/**
 * 가방·장비 격자 (도면 그리드) — **유저 화면과 관리 화면이 함께 쓴다.**
 *
 * 원래 이 렌더는 `InventoryPanel` 안에 갇혀 있었고, 관리 화면의 봇 가방은 따로 만든
 * 목록이었다. 그래서 같은 것을 두 모양으로 그렸다 — 유저는 도면 격자를, 관리자는 줄
 * 목록을 봤다. **두 화면이 다른 것을 그리면 「봇에게 뭐가 있지」를 답하려던 화면이 답을
 * 틀리게 한다.** 셀 모델(`inventoryCells`)은 이미 순수 값으로 갈라져 있었으므로,
 * 갈라야 했던 것은 렌더뿐이었다.
 *
 * **칸은 상태만 그리고 조작은 밖에 산다.** 칸마다 버튼을 펴면 좁은 화면에서 칸 하나가
 * 서너 줄로 꺾인다 — 고른 칸의 상세를 부르는 쪽이 붙인다.
 *
 * 칸 하나의 렌더는 `GridCellView` 로 또 한 번 나갔다. 소모품 칸과 경매장이 같은 격자를
 * 쓰게 됐고, 안 꺼내면 같은 칸이 세 벌로 복사되기 때문이다 — 아래는 **배치**만 안다.
 *
 * 훅을 안 쓴다. 고른 칸은 밖에서 든다 — 유저 화면은 상세를 열고 관리 화면은 넘기기를
 * 거는데, 그 차이가 이 컴포넌트 안에 들어오면 둘 중 하나가 남의 사정을 알게 된다.
 */
import { renderCell } from './GridCellView'
import {
  BAG_CELL_COUNT,
  buildBagCells,
  buildEquipCells,
  type GridCell,
} from './inventoryCells'
import type { InventoryView } from '../storage'

export { renderCell }

/** InventoryGrid 가 받는 props. */
export interface InventoryGridProps {
  readonly inventory: InventoryView | undefined
  /** 지금 고른 칸의 key. 없으면 빈 문자열. */
  readonly pickedKey: string
  readonly onPick: (cell: GridCell) => void
  /** 격자 앞에 붙일 이름. 관리 화면이 봇 이름을 붙인다. */
  readonly ownerLabel?: string
}

/**
 * 장비 여섯 칸과 가방 스무 칸을 그린다.
 *
 * @param props 인벤토리와 고른 칸.
 * @returns 격자 요소.
 */
export function InventoryGrid(props: InventoryGridProps): React.JSX.Element {
  const equipCells = buildEquipCells(props.inventory)
  const bagCells = buildBagCells(props.inventory)
  const filled = bagCells.filter((cell) => cell.entry !== undefined).length
  const owner = props.ownerLabel === undefined ? '' : `${props.ownerLabel} · `
  return (
    <>
      <div className="inv__head">{`${owner}장비`}</div>
      <div className="invg invg--equip">
        {equipCells.map((cell) => renderCell(cell, cell.key === props.pickedKey, props.onPick))}
      </div>
      <div className="inv__head">
        {`${owner}가방 ${String(filled)} / ${String(BAG_CELL_COUNT)}`}
      </div>
      <div className="invg invg--bag">
        {bagCells.map((cell) => renderCell(cell, cell.key === props.pickedKey, props.onPick))}
      </div>
    </>
  )
}
