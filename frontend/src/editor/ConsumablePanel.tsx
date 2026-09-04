/**
 * 소모품 칸 패널 (설계/4_아이템 §5).
 *
 * **가방과 다른 화면이되 같은 형식이다.** 가방은 「가진 것」, 여기는 「들고 갈 것」이다 —
 * 그 구분은 지키고, 그리는 모양은 가방과 맞춘다. 예전에는 여기만 카드 목록이었다: 칸
 * 하나가 머리·눈금·옵션 줄들·도구줄로 네 덩이라 칸 넷이면 화면 한 장을 넘겼고, 「어느
 * 물약이 더 좋은가」는 위아래로 오가며 읽어야 했다. **같은 질문에 두 화면이 다른 모양으로
 * 답하고 있었다.**
 *
 * **빈 칸도 그린다.** 안 그리면 「칸이 없다」와 「비었다」를 구분할 수 없고, 빈 칸이
 * 출격할 때 공짜로 한 개를 받는다는 사실이 어디에도 안 적힌다.
 *
 * 훅은 고른 칸 하나뿐이다. 나머지는 전부 props 로 받는다 — 가방과 같다.
 */
import { useState } from 'react'

import { GlyphState, Panel, ValueExpr } from '../ds'
import type { ConsumableView } from '../storage'

import {
  buildConsumableSlotCells,
  buildConsumableStockCells,
  findFreeConsumableSlot,
  formatCharges,
  formatClearLabel,
  formatRefillLabel,
  formatSlotName,
} from './consumableCells'
import { ConsumableDetail } from './ConsumableDetail'
import { ConsumableGrid } from './ConsumableGrid'
import { LinkNoticeLine } from './LinkNoticeLine'
import { checkLinked, type LinkState } from './linkState'

export {
  findFreeConsumableSlot,
  formatCharges,
  formatClearLabel,
  formatRefillLabel,
  formatSlotName,
}

/** 못 닿았을 때 무엇을 못 보는가. 앞머리(`서버에 닿지 못했다`)는 linkState 가 든다. */
const MISSING_HINT = '소모품 칸은 서버가 안다'

export interface ConsumablePanelProps {
  readonly view: ConsumableView | undefined
  readonly link: LinkState
  readonly detail: string
  /** 칸을 비운다. 남은 충전은 안 돌아온다. */
  readonly onClear: (useTag: string, slotIndex: number) => void
  /** 돈을 내고 빈 충전을 채운다. */
  readonly onRefill: (useTag: string, slotIndex: number) => void
  /** 남는 것을 판다. */
  readonly onSell: (catalogId: string) => void
  /**
   * 보유 재고 하나를 **빈 칸부터** 끼운다.
   *
   * 가방 격자에서 소모품 조작을 뺐으므로(두 집 금지) 여기가 유일한 끼우기 자리다.
   */
  readonly onLoadStock: (catalogId: string) => void
}

/**
 * 소모품 칸을 도면 격자로 그린다.
 *
 * 끼운 칸 + 가방 재고. 칸을 고르면 아래 상세에 그 소모품의 전부(충전·옵션·견줌·조작)가
 * 모인다.
 *
 * @param props 칸 화면과 조작들.
 * @returns 렌더 트리.
 */
export function ConsumablePanel(props: ConsumablePanelProps): React.JSX.Element {
  const { view, link } = props
  const [pickedKey, setPickedKey] = useState('')

  const cells = [...buildConsumableSlotCells(view), ...buildConsumableStockCells(view)]
  const picked = cells.find((cell) => cell.key === pickedKey)

  return (
    <Panel
      title="소모품 칸"
      meta={view === undefined ? '' : `잔액 ${String(view.balance)}`}
      tone="panel"
      padded
      scroll
    >
      <div className="inv">
        {!checkLinked(link) || view === undefined ? (
          <LinkNoticeLine link={link} missing={MISSING_HINT} />
        ) : (
          <>
            {view.isRunOpen ? (
              <GlyphState
                state="pending"
                size="sm"
                label="런이 도는 중 — 지금 채운 것은 다음 런부터 실린다"
              />
            ) : null}
            <ConsumableGrid
              view={view}
              pickedKey={pickedKey}
              onPick={(target) => {
                setPickedKey((current) => (current === target.key ? '' : target.key))
              }}
            />
            {picked === undefined ? (
              <ValueExpr text="칸을 고르면 여기에 상세와 조작이 뜬다" size="sm" dim />
            ) : (
              <ConsumableDetail
                cell={picked}
                view={view}
                link={link}
                onClear={props.onClear}
                onRefill={props.onRefill}
                onSell={props.onSell}
                onLoadStock={props.onLoadStock}
              />
            )}
            {props.detail === '' ? null : <ValueExpr text={props.detail} size="sm" />}
          </>
        )}
      </div>
    </Panel>
  )
}
