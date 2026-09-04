/**
 * 경매장 격자의 셀 모델 (도면 그리드).
 *
 * **가방과 같은 형식이다.** 매물은 결국 「이게 내 것보다 나은가」를 묻는 물건이고, 그것은
 * 가방이 도면 격자로 답한 질문과 같다. 예전에는 세계 탭 안에서 줄 목록으로 그렸다 —
 * 이름·접사·견줌·만료·버튼이 한 매물에 다섯 덩이라, 매물 열둘이면 순위표가 화면 밖으로
 * 밀려났고 훑을 수가 없었다.
 *
 * 순수 값이다. 렌더 검사가 훅 없이 셀 배치를 볼 수 있어야 한다.
 */
import type { AuctionView, ListingView } from '../storage'

import type { CellFace } from './gridCell'
import { clipCellLabel, EQUIP_CELL_CODES, pickHeadlineFromAffixes } from './inventoryCells'

/** 내 매물 표시. 도면의 자기 표시(◉)와 같은 글리프다 — 순위표의 「나」와 한 문법이다. */
export const MINE_MARK = '◉'

/** 경매 격자 칸 하나. */
export interface ListingCell extends CellFace {
  readonly listing: ListingView
}

/**
 * 매물들을 격자 칸으로 만든다.
 *
 * **빈 칸을 덧대지 않는다.** 경매장에는 정해진 자리 수가 없다 — 없는 자리를 그리면
 * 「스무 개까지 걸린다」로 읽힌다.
 *
 * **값을 칸에 적지 않는다.** 칸이 54px 라 네 자리 수가 안 들어가고, 안 들어가는 것을
 * 적으면 잘려서 아무 말도 안 하게 된다 — 칸은 **무엇인가**를 말하고, 값과 만료는 상세가
 * 답한다. 대신 내 매물인지는 칸에서 보여야 한다: 내 것을 모르고 누르면 살 수 없는 것에
 * 손이 간다.
 *
 * @param auction 서버가 준 경매장. 없으면 빈 배열.
 * @returns 서버가 준 순서 그대로의 칸들.
 */
export function buildListingCells(auction: AuctionView | undefined): readonly ListingCell[] {
  return (auction?.listings ?? []).map((listing) => ({
    key: `lot:${String(listing.listingId)}`,
    // **자리 코드다.** 「이게 어디에 끼는 물건인가」가 칸에서 바로 보여야 한다 —
    // 가방 칸이 부위 코드를 다는 것과 같은 규칙이며, 자리를 모르는 매물은 `IT` 다.
    code: EQUIP_CELL_CODES.get(listing.slot) ?? 'IT',
    label: clipCellLabel(listing.labelKo),
    grade: listing.grade,
    marks: listing.isMine ? [MINE_MARK] : [],
    countText: '',
    fact: pickHeadlineFromAffixes(listing.affixes),
    isSealedSlot: false,
    listing,
  }))
}

/**
 * 살 수 없는 이유를 적는다.
 *
 * **누르기 전에 말한다.** 눌러 보고 알게 하면 거절 한 번을 겪은 뒤이고, 그것이 가방이
 * 귀속을 미리 적는 것과 같은 이유다.
 *
 * @param listing 매물.
 * @param balance 지금 잔액.
 * @returns 못 사는 사유. 살 수 있으면 빈 문자열.
 */
export function findBuyBlocker(listing: ListingView, balance: number): string {
  if (listing.isMine) {
    return '내 매물이다 — 내가 걸어 둔 것은 못 산다'
  }
  if (balance < listing.price) {
    return `잔액이 모자란다 (${String(listing.price)} 필요 · ${String(balance)} 있음)`
  }
  return ''
}
