/**
 * 견줌 줄들의 렌더 — **가방·소모품 칸·경매장이 함께 쓴다.**
 *
 * 같은 표가 두 곳에 복사돼 있었다 (`InventoryDetail` 과 `WorldPanel`). 그 상태에서 견줌의
 * 표기를 하나 고치면 **고친 화면에서만** 바뀌고, 사람은 같은 질문에 두 모양의 답을 받는다 —
 * 어느 쪽을 믿을지가 그때부터 또 하나의 문제가 된다.
 *
 * **점수 하나로 접지 않는다.** 「이게 더 좋다」를 한 숫자로 말하려면 어느 스탯이 얼마나
 * 값한지를 코드가 정해야 하고, 그 기준이 틀리면 화면이 **틀린 답을 자신 있게** 말한다.
 * 사람의 취향은 사람이 정한다 — 화면은 스탯별 차이까지만 낸다.
 *
 * 좋고 나쁨은 **색과 부호 둘**로 적는다. 색 하나면 못 가르는 사람에게 사라진다.
 */
import { ValueExpr } from '../ds'

import { formatDelta, type CompareRow } from './compareItems'

export interface CompareRowsProps {
  readonly rows: readonly CompareRow[]
  /**
   * 줄 이름 뒤에 덧붙일 말. 경매가 「빈 자리」를 여기에 적는다.
   *
   * 이름 자체를 바꾸지 않는 이유는, 스탯 이름이 두 화면에서 달라지면 같은 줄을 눈으로
   * 이을 수 없기 때문이다.
   */
  readonly nameSuffix?: string
}

/**
 * 견줌 줄들을 그린다.
 *
 * @param props 견줌 줄들.
 * @returns 줄 목록. 줄이 없으면 null — 「달라지는 것이 없다」는 부르는 쪽이 적는다.
 */
export function CompareRows(props: CompareRowsProps): React.JSX.Element | null {
  if (props.rows.length === 0) {
    return null
  }
  const suffix = props.nameSuffix === undefined ? '' : ` · ${props.nameSuffix}`
  return (
    <ul className="invd__compare">
      {props.rows.map((row) => {
        // 고정값과 퍼센트를 **더해서 방향만 본다.** 크기를 재는 것이 아니라 위/아래를
        // 가르는 데만 쓰므로, 둘의 단위가 달라도 부호는 옳다. 방향이 갈리는 줄
        // (`+3 −5%`)은 색을 안 쓰고 숫자가 그대로 말하게 둔다.
        const gain = row.flatDelta + row.percentDelta
        const tone = gain > 0 ? ' invd__delta--up' : gain < 0 ? ' invd__delta--down' : ''
        return (
          <li className="invd__compare-row" key={row.stat}>
            <span className="invd__compare-name">{`${row.label}${suffix}`}</span>
            <span className={`invd__delta${tone}`}>{formatDelta(row)}</span>
          </li>
        )
      })}
    </ul>
  )
}

/**
 * 견줌 한 묶음을 머리글과 함께 그린다.
 *
 * @param props 머리글과 줄들.
 * @returns 머리글 + 줄들. 차이가 없으면 그렇게 적는다.
 */
export function CompareBlock(props: {
  readonly heading: string
  readonly rows: readonly CompareRow[]
  /** 차이가 없을 때 적을 말. */
  readonly sameText: string
  readonly nameSuffix?: string
}): React.JSX.Element {
  if (props.rows.length === 0) {
    return <ValueExpr text={props.sameText} size="sm" dim />
  }
  return (
    <>
      <ValueExpr text={props.heading} size="sm" dim />
      <CompareRows
        rows={props.rows}
        {...(props.nameSuffix === undefined ? {} : { nameSuffix: props.nameSuffix })}
      />
    </>
  )
}
