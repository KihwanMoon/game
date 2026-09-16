/**
 * 경매장 화면 검사 — **가방과 같은 격자, 같은 견줌.**
 *
 * 세계 탭의 줄 목록에서 갈라 나왔다. 여기서 지키는 것은 여섯이다.
 *
 * 1. **매물이 격자 칸이다.** 줄 목록이면 매물 열둘에 화면이 넘어간다.
 * 2. **칸은 자리 코드와 대표 접사를 적는다** — 격자를 봐서 어느 게 나은지 짐작이 가야
 *    칸을 하나씩 눌러 보지 않는다.
 * 3. **조작은 상세에만 있다.** 칸 안에 버튼이 생기면 되돌아간 것이다.
 * 4. **사기 전에 내 것과 견준다.** 사면 귀속돼 되돌릴 수 없다 (결정 #07).
 * 5. **못 사는 이유를 실측값과 함께 적는다** — 「구매할 수 없습니다」만으로는 얼마가
 *    모자란지 모른다 (GDD §8.2, P1).
 * 6. **상세에도 그림이 서되 이름이 남는다** (2026-09-16). 상세는 칸이 든 그림을 그대로
 *    쓴다 — 따로 고르면 한 매물이 격자와 상세에서 두 그림으로 뜬다.
 *
 * **3번이 죽어 있었다** (2026-09-16). 격자를 `slice(markup.indexOf('invg--lot'), …)` 로
 * 떼어 내고 있었는데, `invg--lot` 은 이 저장소에 없는 이름이다 — 경매 격자는 칸 수가
 * 정해져 있지 않아 `shape="free"` 를 쓴다(`SlotBoard`). `indexOf` 가 `-1` 을 돌려주고
 * `slice(-1, -1)` 은 **빈 문자열**이라, 그 위의 `not.toContain` 은 칸 안에 무엇이 들어
 * 있든 통과했다.
 *
 * 그래서 이 파일은 두 가지를 지킨다.
 *
 * - **`slice(indexOf(…))` 를 안 쓴다.** 못 찾은 것과 찾았는데 비어 있는 것이 구별되지
 *   않는 잘라내기다. 떼어 낼 때는 몇 개를 떼었는지 먼저 센다(`sliceCells`).
 * - **부정 검사를 혼자 두지 않는다.** 찾는 글자가 실제로 나오는 렌더를 짝으로 붙여,
 *   이름이 썩으면 짝이 먼저 빨개지게 한다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { AuctionView, ItemView } from '../storage'

import { AuctionDetail, AuctionPanel } from './AuctionPanel'
import { buildListingCells, findBuyBlocker, MINE_MARK } from './auctionCells'

const noop = () => undefined

/**
 * 상세에만 있어야 하는 조작의 라벨. 한 곳에서 꺼내 쓴다.
 *
 * 흩어 놓으면 라벨을 고칠 때 「칸에 없다」 쪽만 옛 글자로 남고, 그 검사는 없는 말을
 * 찾으며 조용히 통과한다 — 이 파일이 실제로 앓던 병이다.
 */
const BUY_TEXT = '구매'
const PULL_TEXT = '내리기'

/**
 * 격자 칸 마크업을 칸 단위로 떼어 낸다.
 *
 * 칸(`invg__cell`)은 그 자체가 버튼 하나라 닫는 태그까지가 한 칸이다. 안에 또 버튼이
 * 있으면 그 버튼의 닫는 태그에서 끊기므로, 끊긴 조각에 조작 라벨이 그대로 남는다.
 *
 * @param markup 패널 마크업.
 * @returns 칸 하나당 문자열 하나. 하나도 못 찾으면 빈 배열이다 — 부르는 쪽이 센다.
 */
function sliceCells(markup: string): readonly string[] {
  return [...markup.matchAll(/<button[^>]*class="invg__cell[^"]*"[\s\S]*?<\/button>/g)].map(
    (found) => found[0],
  )
}

const AUCTION: AuctionView = {
  listings: [
    {
      listingId: 1,
      itemId: 11,
      labelKo: '철 투구',
      price: 300,
      isMine: false,
      sellerName: '하윤',
      catalogId: 'sword_short',
      hands: 'ONE',
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
      sellerName: '하윤',
      catalogId: 'sword_short',
      hands: 'ONE',
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
  recastFrom: 0,
  grade: 'COMMON',
  attackRange: 0,
  affixes: [{ stat: 'hp_max', flat: 3, percent: 0, labelKo: '', statLabel: '최대체력' }],
  requirements: [],
  canEquip: true,
  grantsSkill: '',
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

  it('★ 열 수를 안 박는다 — 매물 수는 정해져 있지 않다', () => {
    // 가방처럼 열을 박으면 매물이 셋일 때 남는 자리가 「빈 칸」으로 읽힌다. 경매장에는
    // 빈 자리라는 것이 없다.
    expect(markup).toContain('invg invg--free')
  })

  it('★ 조작이 칸 안에 없다 — 칸은 상태만 그린다', () => {
    const cells = sliceCells(markup)
    // **떼어 낸 것이 있는지부터 센다.** 0개면 아래 부정 검사가 전부 공짜로 통과한다.
    expect(cells).toHaveLength(AUCTION.listings.length)
    for (const cell of cells) {
      // 칸 자신이 버튼 하나다. 둘이면 칸 안에 조작이 돋아난 것이다.
      expect(cell.match(/<button/g)).toHaveLength(1)
      expect(cell).not.toContain(BUY_TEXT)
      expect(cell).not.toContain(PULL_TEXT)
    }
  })

  it('조작은 상세에 있다 — 위 검사가 없는 말을 찾고 있지 않다는 증거다', () => {
    // 「칸에 없다」만으로는 검사가 산 것인지 알 수 없다. 같은 글자가 상세에서는 실제로
    // 나온다는 사실을 여기 붙들어 둔다.
    const cells = buildListingCells(AUCTION)
    const detail = (at: number): string =>
      renderToStaticMarkup(
        <AuctionDetail
          cell={cells[at]!}
          balance={500}
          worn={WORN}
          disabled={false}
          onBuy={noop}
          onCancel={noop}
        />,
      )
    expect(detail(0)).toContain(BUY_TEXT)
    expect(detail(1)).toContain(PULL_TEXT)
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
    expect(markup).toContain(PULL_TEXT)
    expect(markup).toContain('수수료 45')
    expect(markup).not.toContain(BUY_TEXT)
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
    expect(markup).toContain('저잣거리는 서버가 안다')
  })
})

/**
 * 상세에서 그림 주소를 떼어 낸다.
 *
 * 작은따옴표가 마크업에서 `&#x27;` 로 나오므로 되돌린다 — 그림이 인라인 SVG 라, 안
 * 되돌리면 셀 모델이 든 값과 늘 다르게 읽힌다.
 *
 * @param markup 상세 마크업.
 * @returns 그림 주소. 그림 자리가 없으면 빈 문자열이다 — 부르는 쪽이 그것까지 본다.
 */
function pickArtSrc(markup: string): string {
  const found = /class="ds-thumb__art" src="([^"]*)"/.exec(markup)?.[1] ?? ''
  return found.replaceAll('&#x27;', "'")
}

describe('★ 상세에도 그림이 선다 (2026-09-16)', () => {
  const cells = buildListingCells(AUCTION)
  const detail = (at: number): string =>
    renderToStaticMarkup(
      <AuctionDetail
        cell={cells[at]!}
        balance={500}
        worn={WORN}
        disabled={false}
        onBuy={noop}
        onCancel={noop}
      />,
    )

  it('★ 칸이 든 그림을 그대로 쓴다 — 상세가 따로 고르면 한 매물이 두 그림으로 뜬다', () => {
    expect(cells[0]?.art).not.toBeUndefined()
    expect(pickArtSrc(detail(0))).toBe(cells[0]?.art)
  })

  it('★ 이름이 남는다 — 그림만 두면 한 그림을 나눠 쓰는 셋을 값만 보고 골라야 한다', () => {
    // 저잣거리에서 잘못 고르면 되돌릴 수 없다 — 사면 귀속된다 (결정 #07).
    expect(detail(0)).toContain('철 투구')
  })

  it('안 그린 형태는 분류 코드로 떨어진다 — 자리가 비면 고장 난 것으로 읽힌다', () => {
    const odd = buildListingCells({
      ...AUCTION,
      listings: [{ ...AUCTION.listings[0]!, catalogId: 'flute_bone' }],
    })
    const markup = renderToStaticMarkup(
      <AuctionDetail
        cell={odd[0]!}
        balance={500}
        worn={WORN}
        disabled={false}
        onBuy={noop}
        onCancel={noop}
      />,
    )
    expect(pickArtSrc(markup)).toBe('')
    // 머리 자리 물건이라는 것은 남는다 — 그림이 없다고 분류까지 사라지면 안 된다.
    expect(markup).toContain('HD')
  })
})
