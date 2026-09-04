/**
 * 경매장 화면 검사 — **가방과 같은 격자, 같은 견줌.**
 *
 * 세계 탭의 줄 목록에서 갈라 나왔다. 여기서 지키는 것은 다섯이다.
 *
 * 1. **매물이 격자 칸이다.** 줄 목록이면 매물 열둘에 화면이 넘어간다.
 * 2. **칸은 자리 코드와 대표 접사를 적는다** — 격자를 봐서 어느 게 나은지 짐작이 가야
 *    칸을 하나씩 눌러 보지 않는다.
 * 3. **조작은 상세에만 있다.** 칸 안에 버튼이 생기면 되돌아간 것이다.
 * 4. **사기 전에 내 것과 견준다.** 사면 귀속돼 되돌릴 수 없다 (결정 #07).
 * 5. **못 사는 이유를 실측값과 함께 적는다** — 「구매할 수 없습니다」만으로는 얼마가
 *    모자란지 모른다 (GDD §8.2, P1).
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { AuctionView, ItemView } from '../storage'

import { AuctionDetail, AuctionPanel } from './AuctionPanel'
import { buildListingCells, findBuyBlocker, MINE_MARK } from './auctionCells'

const noop = () => undefined

const AUCTION: AuctionView = {
  listings: [
    {
      listingId: 1,
      itemId: 11,
      labelKo: '철 투구',
      price: 300,
      isMine: false,
      affixes: [{ stat: 'hp_max', flat: 8, percent: 0, labelKo: '튼튼함', statLabel: '최대체력' }],
      expiresInMinutes: 42,
      fee: 15,
      slot: 'HEAD',
      grade: 'COMMON',
      attackRange: 0,
    },
    {
      listingId: 2,
      itemId: 12,
      labelKo: '대검',
      price: 900,
      isMine: true,
      affixes: [],
      expiresInMinutes: 10,
      fee: 45,
      slot: 'WEAPON_MAIN',
      grade: 'FINE',
      attackRange: 0,
    },
  ],
  balance: 500,
  feePercent: 5,
}

const WORN_HELM: ItemView = {
  itemId: 99,
  catalogId: 'helm_old',
  labelKo: '낡은 투구',
  kind: 'EQUIPMENT',
  slot: 'HEAD',
  hands: null,
  equippedSlot: 'HEAD',
  isBroken: false,
  isBound: false,
  isRecovered: false,
  sealedSlots: 0,
  unsealCost: 0,
  grade: 'COMMON',
  attackRange: 0,
  affixes: [{ stat: 'hp_max', flat: 3, percent: 0, labelKo: '', statLabel: '최대체력' }],
  requirements: [],
  canEquip: true,
}

const WORN = new Map([['HEAD', WORN_HELM]])

describe('매물 셀 모델', () => {
  const cells = buildListingCells(AUCTION)

  it('★ 칸이 자리 코드를 단다 — 어디에 끼는 물건인지가 칸에서 보인다', () => {
    expect(cells[0]?.code).toBe('HD')
    expect(cells[1]?.code).toBe('WM')
  })

  it('★ 칸이 대표 접사를 적는다 — 없으면 어느 게 나은지 짐작조차 못 한다', () => {
    expect(cells[0]?.fact).toBe('체+8')
  })

  it('접사가 없으면 빈 줄이다 — 없는 것을 지어내지 않는다', () => {
    expect(cells[1]?.fact).toBe('')
  })

  it('★ 내 매물은 칸에서 보인다 — 모르고 누르면 살 수 없는 것에 손이 간다', () => {
    expect(cells[1]?.marks).toContain(MINE_MARK)
    expect(cells[0]?.marks).toHaveLength(0)
  })

  it('빈 칸을 덧대지 않는다 — 경매장에는 정해진 자리 수가 없다', () => {
    expect(cells).toHaveLength(2)
  })

  it('등급을 싣는다 — 이름의 등급색이 매물에서만 죽으면 안 된다', () => {
    expect(cells[1]?.grade).toBe('FINE')
  })
})

describe('★ 못 사는 이유를 실측값과 함께 적는다', () => {
  it('잔액이 모자라면 얼마가 모자란지 적는다', () => {
    const blocker = findBuyBlocker(AUCTION.listings[0]!, 100)
    expect(blocker).toContain('300 필요')
    expect(blocker).toContain('100 있음')
  })

  it('내 매물은 못 산다고 적는다', () => {
    expect(findBuyBlocker(AUCTION.listings[1]!, 5000)).toContain('내 매물')
  })

  it('살 수 있으면 아무 말도 안 한다 — 없는 사유를 지어내지 않는다', () => {
    expect(findBuyBlocker(AUCTION.listings[0]!, 500)).toBe('')
  })
})

describe('경매 격자', () => {
  const markup = renderToStaticMarkup(
    <AuctionPanel auction={AUCTION} link="online" detail="" worn={WORN} onBuy={noop} onCancel={noop} />,
  )

  it('★ 가방과 같은 격자를 쓴다 — 같은 질문에 두 모양으로 답하지 않는다', () => {
    expect(markup).toContain('invg')
    expect(markup).toContain('invg__cell')
  })

  it('★ 조작이 칸 안에 없다 — 칸은 상태만 그린다', () => {
    const grid = markup.slice(markup.indexOf('invg--lot'), markup.indexOf('</div>', markup.indexOf('invg--lot')))
    expect(grid).not.toContain('구매')
    expect(grid).not.toContain('내리기')
  })

  it('수수료와 잔액을 머리에 적는다 — 걸기 전에 얼마가 나가는지 알아야 한다', () => {
    expect(markup).toContain('수수료 5%')
    expect(markup).toContain('잔액 500')
  })

  it('★ 거는 곳이 가방임을 말한다 — 두 집에 두면 어느 쪽이 진짜인지 모른다', () => {
    expect(markup).toContain('거는 것은 가방에서 한다')
  })

  it('내 매물 수를 센다', () => {
    expect(markup).toContain('내 것 1')
  })
})

describe('경매 상세 — 사기 전에 알아야 할 것', () => {
  const cells = buildListingCells(AUCTION)
  const markup = renderToStaticMarkup(
    <AuctionDetail
      cell={cells[0]!}
      balance={500}
      worn={WORN}
      disabled={false}
      onBuy={noop}
      onCancel={noop}
    />,
  )

  it('★ 접사가 보인다 — 이름과 값만 보고 사면 저주를 돈 주고 산다', () => {
    expect(markup).toContain('튼튼함 · 최대체력 +8')
  })

  it('★ 언제 사라지는지 보인다', () => {
    expect(markup).toContain('42분 뒤 사라진다')
  })

  it('★ 사면 귀속된다는 사실이 사기 전에 있다 (결정 #07)', () => {
    expect(markup).toContain('귀속된다')
  })

  it('★ 매물이 내 것보다 얼마나 나은지 적는다', () => {
    // 철 투구는 체력 +8, 낡은 투구는 +3 이므로 차이는 +5 다.
    expect(markup).toContain('invd__compare')
    expect(markup).toContain('+5')
  })

  it('★ 스탯별로 낸다 — 한 숫자로 접으면 기준을 코드가 정하게 된다', () => {
    expect(markup).toContain('invd__compare-name')
    expect(markup).toContain('최대체력')
    // 「이게 낫다」 같은 한 줄 판정을 내리지 않는다.
    expect(markup).not.toContain('추천')
    expect(markup).not.toContain('더 좋다')
  })

  it('부위를 적는다 — 어느 자리와 견준 것인지가 보여야 한다', () => {
    expect(markup).toContain('머리')
  })
})

describe('경매 상세 — 빈 자리와 내 매물', () => {
  const cells = buildListingCells(AUCTION)

  it('★ 빈 자리는 그렇게 말한다 — 견줄 상대가 없는 것과 같은 것은 다르다', () => {
    // 대검 자리(WEAPON_MAIN)에는 아무것도 안 꼈다.
    const markup = renderToStaticMarkup(
      <AuctionDetail
        cell={cells[1]!}
        balance={500}
        worn={WORN}
        disabled={false}
        onBuy={noop}
        onCancel={noop}
      />,
    )
    expect(markup).toContain('빈 자리')
  })

  it('내 매물은 사는 대신 내리는 버튼이 뜬다', () => {
    const markup = renderToStaticMarkup(
      <AuctionDetail
        cell={cells[1]!}
        balance={500}
        worn={WORN}
        disabled={false}
        onBuy={noop}
        onCancel={noop}
      />,
    )
    expect(markup).toContain('내리기')
    expect(markup).toContain('수수료 45')
    expect(markup).not.toContain('구매')
  })

  it('★ 잔액이 모자라면 사유가 화면에 선다', () => {
    const markup = renderToStaticMarkup(
      <AuctionDetail
        cell={cells[0]!}
        balance={100}
        worn={WORN}
        disabled={false}
        onBuy={noop}
        onCancel={noop}
      />,
    )
    expect(markup).toContain('300 필요')
    expect(markup).toContain('100 있음')
  })
})

describe('경매 — 서버 없음', () => {
  it('경매가 서버의 것임을 말한다', () => {
    const markup = renderToStaticMarkup(
      <AuctionPanel
        auction={undefined}
        link="offline"
        detail=""
        worn={new Map()}
        onBuy={noop}
        onCancel={noop}
      />,
    )
    expect(markup).toContain('서버에 닿지 못했다')
    expect(markup).toContain('경매는 서버가 안다')
  })
})
