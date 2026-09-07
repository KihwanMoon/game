/**
 * 도면 격자 판 — **칸을 고르고 아래에서 조작한다** (가방·소모품·경매·스킬).
 *
 * 네 화면이 같은 모양을 각자 그리고 있었다. 제목 한 줄, 칸 격자, 「칸을 고르면 …」 안내,
 * 고른 칸의 상세. 같은 것이 네 벌이면 한 곳을 고쳐도 나머지 셋은 옛 모양으로 남고,
 * 그때부터 사람은 같은 질문에 네 모양의 답을 받는다 — 봇 가방이 유저 가방과 다른
 * 목록이던 것이 정확히 그 병이었다 (`gridCell` 머리말).
 *
 * **칸은 상태만, 조작은 상세에.** 칸마다 버튼을 펴면 좁은 화면에서 칸 하나가 서너 줄로
 * 꺾인다. 이 규율이 부품에 박혀 있어야 새 화면이 그것을 다시 깨지 않는다.
 *
 * 알맹이는 모른다. 겉면(`CellFace`)만 받고, 그것이 무엇을 가리키는지는 부르는 쪽이 안다.
 */
import { useCallback, useState } from 'react'
import type { ReactNode } from 'react'

import { ValueExpr } from '../ds'

import { renderCell } from './GridCellView'
import type { CellFace } from './gridCell'

/**
 * 칸을 어떻게 늘어놓는가.
 *
 * - `equip` 3열 — 슬롯 순서가 줄을 맞춘다(주무기·보조·머리 / 갑옷·신발·장갑).
 * - `bag` 5열 — 스무 칸이 **고정**이라 열 수를 박는다.
 * - `free` 폭이 채우는 만큼 — 칸 수가 정해져 있지 않은 것들(소모품 칸·경매 매물).
 *   열 수를 박으면 칸이 셋일 때 두 자리가 빈 채로 남아 「빈 칸이 있다」로 읽힌다.
 */
export type SlotShape = 'equip' | 'bag' | 'free'

/** SlotGrid 가 받는 props. */
export interface SlotGridProps<T extends CellFace> {
  /** 격자 위 한 줄. 무엇이 몇 개인지가 여기 선다. */
  readonly title: string
  readonly shape: SlotShape
  readonly cells: readonly T[]
  /** 지금 고른 칸의 key. 없으면 빈 문자열. */
  readonly pickedKey: string
  readonly onPick: (cell: T) => void
  /**
   * 칸이 하나도 없을 때 적을 말.
   *
   * **빈 격자만 두면 「불러오는 중」과 구별되지 않는다.** 생략하면 빈 격자를 그대로
   * 그린다 — 가방처럼 칸 수가 고정이라 빈 칸이 곧 뜻인 자리가 그 경우다.
   */
  readonly emptyText?: string
}

/**
 * 제목 한 줄과 칸 격자를 그린다.
 *
 * @param props 제목·모양·칸들과 고른 칸.
 * @returns 격자 요소.
 */
export function SlotGrid<T extends CellFace>(props: SlotGridProps<T>): React.JSX.Element {
  const isEmpty = props.cells.length === 0 && props.emptyText !== undefined
  return (
    <>
      <div className="inv__head">{props.title}</div>
      {isEmpty ? (
        <ValueExpr text={props.emptyText ?? ''} size="sm" dim />
      ) : (
        <div className={`invg invg--${props.shape}`}>
          {props.cells.map((cell) => renderCell(cell, cell.key === props.pickedKey, props.onPick))}
        </div>
      )}
    </>
  )
}

/** SlotBoard 가 받는 props. */
export interface SlotBoardProps {
  /** 격자들. `SlotGrid` 를 하나 이상 넣는다. */
  readonly children: ReactNode
  /** 고른 칸의 상세. 아무 칸도 안 골랐으면 undefined 다. */
  readonly detail?: ReactNode
  /** 아무것도 안 골랐을 때 적을 말. 상세 자리가 비어 보이면 누를 것이 있는 줄 모른다. */
  readonly hint: string
  /** 격자 앞에 붙일 것. 연결 경고·런 진행 안내가 여기 온다. */
  readonly notice?: ReactNode
}

/**
 * 격자들과 고른 칸의 상세를 한 판으로 그린다.
 *
 * @param props 격자·상세·안내.
 * @returns 판 요소.
 */
export function SlotBoard(props: SlotBoardProps): React.JSX.Element {
  return (
    <>
      {props.notice}
      {props.children}
      {props.detail === undefined ? (
        <ValueExpr text={props.hint} size="sm" dim />
      ) : (
        props.detail
      )}
    </>
  )
}

/**
 * 고른 칸 하나를 든다.
 *
 * **같은 칸을 다시 누르면 놓는다.** 네 화면이 이 토글을 각자 적고 있었는데, 하나만
 * 빠뜨려도 그 화면에서는 고른 것을 놓을 방법이 없어진다.
 *
 * @returns 고른 key 와 토글 함수.
 */
export function usePickedKey(): [string, (cell: CellFace) => void] {
  const [pickedKey, setPickedKey] = useState('')
  const togglePick = useCallback((cell: CellFace) => {
    setPickedKey((current) => (current === cell.key ? '' : cell.key))
  }, [])
  return [pickedKey, togglePick]
}
