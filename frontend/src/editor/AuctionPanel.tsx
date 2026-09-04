/**
 * 경매장 패널 (F단계) — **가방과 같은 격자, 같은 견줌.**
 *
 * 세계 탭에서 갈라 나왔다. 두 가지 이유다.
 *
 * 1. **묶음이 틀렸다.** 세계 탭은 「나 밖의 일」(순위·도감·오늘의 도전)이고, 경매는 내
 *    가방을 바꾸는 일이다 — 사면 돈이 나가고 아이템이 들어오며 그것은 되돌릴 수 없다
 *    (귀속된다, 결정 #07). 순위표 아래에 있으면 그만한 무게로 안 보인다.
 * 2. **모양이 틀렸다.** 매물 하나가 이름·접사·견줌·만료·버튼으로 다섯 덩이라, 열둘이면
 *    순위표가 화면 밖으로 밀려났다. 같은 질문(「이게 내 것보다 나은가」)에 가방은 격자로
 *    답하고 여기는 줄 목록으로 답하고 있었다.
 *
 * 훅은 고른 칸 하나뿐이다 — 가방과 같다.
 */
import { useState } from 'react'

import { Button, GlyphState, Panel, ValueExpr } from '../ds'
import type { AuctionView, ItemView } from '../storage'

import { buildListingCells, findBuyBlocker, type ListingCell } from './auctionCells'
import { CompareBlock } from './CompareRows'
import { compareToWorn } from './compareItems'
import { renderCell } from './GridCellView'
import { formatGradeClass, renderGrade } from './gradeBadge'
import { formatAffix } from './InventoryPanel'
import { EQUIP_CELL_LABELS } from './inventoryCells'
import { LinkNoticeLine } from './LinkNoticeLine'
import { checkLinked, type LinkState } from './linkState'

/** 못 닿았을 때 무엇을 못 보는가. 앞머리(`서버에 닿지 못했다`)는 linkState 가 든다. */
const MISSING_HINT = '경매는 서버가 안다'

export interface AuctionPanelProps {
  readonly auction: AuctionView | undefined
  readonly link: LinkState
  readonly detail: string
  /**
   * 자리에서 지금 낀 것으로. 매물을 「내 것보다 나은가」로 읽는 데 쓴다.
   *
   * 서버가 매물의 자리를 실어 보내므로 견줄 상대를 찾을 수 있다 — 예전에는 그 필드가
   * 없어서 접사만 늘어놓고 판단을 통째로 사람에게 넘겼다.
   */
  readonly worn: ReadonlyMap<string, ItemView>
  readonly onBuy: (listingId: number) => void
  readonly onCancel: (listingId: number) => void
}

/**
 * 고른 매물의 상세를 그린다.
 *
 * **조작은 전부 여기에 산다.** 격자 칸은 상태만 그린다 — 가방과 같은 규약이다.
 *
 * @param props 매물과 처리기들.
 * @returns 상세 요소.
 */
export function AuctionDetail(props: {
  readonly cell: ListingCell
  readonly balance: number
  readonly worn: ReadonlyMap<string, ItemView>
  readonly disabled: boolean
  readonly onBuy: (listingId: number) => void
  readonly onCancel: (listingId: number) => void
}): React.JSX.Element {
  const listing = props.cell.listing
  const held = listing.slot === '' ? undefined : props.worn.get(listing.slot)
  const blocker = findBuyBlocker(listing, props.balance)
  return (
    <div className="invd">
      <div className="invd__row">
        <span className={`inv__name${formatGradeClass(listing.grade)}`}>{listing.labelKo}</span>
        {renderGrade(listing.grade)}
        {listing.slot === '' ? null : (
          <ValueExpr
            text={`부위 · ${EQUIP_CELL_LABELS.get(listing.slot) ?? listing.slot}`}
            size="sm"
            dim
          />
        )}
        <ValueExpr text={`${String(listing.price)} 화폐`} size="sm" />
      </div>
      {listing.affixes.length === 0 ? null : (
        // 저주 접사는 음수다. 모르고 사면 돈을 내고 약해진다 — 옵션 하나에 한 줄이다.
        <ul className="invd__affixes">
          {listing.affixes.map((affix) => (
            <li className="invd__affix" key={`${affix.stat}-${String(affix.flat)}-${String(affix.percent)}`}>
              <ValueExpr text={formatAffix(affix)} size="sm" />
            </li>
          ))}
        </ul>
      )}
      {/* **사기 전에 「내 것보다 나은가」에 답한다.** 접사만 보여 주면 그 판단을 사람이
          머리로 해야 하고, 산 뒤에는 되돌릴 수 없다 (귀속된다 — 결정 #07). 가방의 견줌과
          같은 규칙으로 낸다: 점수 하나가 아니라 스탯별 차이까지만. */}
      {listing.slot === '' ? (
        <ValueExpr text="자리가 없는 물건이라 견줄 상대가 없다" size="sm" dim />
      ) : (
        <CompareBlock
          heading={held === undefined ? '빈 자리와 견줌' : `${held.labelKo} 와 견줌`}
          rows={compareToWorn(listing.affixes, held?.affixes ?? [])}
          sameText={held === undefined ? '빈 자리라 그대로 이득이다' : '지금 낀 것과 같다'}
          {...(held === undefined ? { nameSuffix: '빈 자리' } : {})}
        />
      )}
      <ValueExpr
        text={
          listing.isMine
            ? `내 매물 · 수수료 ${String(listing.fee)} 는 안 돌아온다`
            : `${String(listing.expiresInMinutes)}분 뒤 사라진다`
        }
        size="sm"
        dim
      />
      {/* **산 것은 귀속된다.** 되팔 수 없다는 사실은 사기 전에 있어야 한다 (결정 #07). */}
      {listing.isMine ? null : (
        <ValueExpr text="사면 귀속된다 — 다시 팔 수 없다" size="sm" dim />
      )}
      <div className="invd__row invd__row--tools">
        {listing.isMine ? (
          <Button
            size="sm"
            variant="ghost"
            glyph="↰"
            disabled={props.disabled}
            title="내린다 (수수료는 안 돌려준다)"
            onClick={() => {
              props.onCancel(listing.listingId)
            }}
          >
            내리기
          </Button>
        ) : (
          <Button
            size="sm"
            variant="primary"
            glyph="↧"
            disabled={props.disabled || blocker !== ''}
            title={blocker === '' ? '산다 — 사면 귀속된다' : blocker}
            onClick={() => {
              props.onBuy(listing.listingId)
            }}
          >
            구매
          </Button>
        )}
        {/* **못 사는 이유를 실측값과 함께 적는다.** 「구매할 수 없습니다」만 띄우면
            얼마가 모자란지 알 수 없다 (GDD §8.2, P1). */}
        {blocker === '' ? null : <GlyphState state="blocked" size="sm" label={blocker} />}
      </div>
    </div>
  )
}

/**
 * 경매장을 도면 격자로 그린다.
 *
 * @param props 경매장과 처리기들.
 * @returns 패널 요소.
 */
export function AuctionPanel(props: AuctionPanelProps): React.JSX.Element {
  const { auction, link } = props
  const [pickedKey, setPickedKey] = useState('')

  const cells = buildListingCells(auction)
  const picked = cells.find((cell) => cell.key === pickedKey)
  const mine = cells.filter((cell) => cell.listing.isMine).length

  return (
    <Panel
      title="경매장"
      meta={auction === undefined ? '' : `수수료 ${String(auction.feePercent)}% · 잔액 ${String(auction.balance)}`}
      tone="panel"
      padded
      scroll
    >
      <div className="inv">
        {!checkLinked(link) || auction === undefined ? (
          <LinkNoticeLine link={link} missing={MISSING_HINT} />
        ) : (
          <>
            {/* **거는 것은 가방에서 한다.** 걸 물건을 고르는 일은 가방을 뒤지는 일이라
                거기 있어야 하고, 두 집에 두면 어느 쪽이 진짜인지 알 수 없다. */}
            <div className="inv__head">
              {`매물 ${String(cells.length)}${mine === 0 ? '' : ` · 내 것 ${String(mine)}`}`}
            </div>
            {cells.length === 0 ? (
              <ValueExpr text="걸린 매물이 없다" size="sm" dim />
            ) : (
              <div className="invg invg--lot">
                {cells.map((cell) => renderCell(cell, cell.key === pickedKey, (target) => {
                  setPickedKey((current) => (current === target.key ? '' : target.key))
                }))}
              </div>
            )}
            {picked === undefined ? (
              <ValueExpr text="칸을 고르면 여기에 상세와 견줌이 뜬다" size="sm" dim />
            ) : (
              <AuctionDetail
                cell={picked}
                balance={auction.balance}
                worn={props.worn}
                disabled={!checkLinked(link)}
                onBuy={props.onBuy}
                onCancel={props.onCancel}
              />
            )}
            <ValueExpr text="거는 것은 가방에서 한다 — 걸 물건을 고르는 자리가 거기다" size="sm" dim />
            {props.detail === '' ? null : (
              <div className="wld__warn">
                <GlyphState state="danger" size="sm" label={props.detail} />
              </div>
            )}
          </>
        )}
      </div>
    </Panel>
  )
}
