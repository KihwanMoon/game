/**
 * 세계 패널 — 순위와 경매장 (F단계).
 *
 * **레벨과 능력치는 여기 있지 않다.** 그것은 세계에 대한 사실이 아니라 나에 대한
 * 사실이라 `GrowthPanel` 로 나갔다 — 「내 캐릭터가 지금 뭘 찍을 수 있나」를 보려고
 * 세계를 여는 것이 이상했다. 여기 남은 것은 **나 밖의 일**뿐이다.
 *
 * **순위표의 점수는 누적 경험치다.** 한 판의 성적이 아니라 얼마나 멀리 왔는가를 잰다 —
 * 이 게임은 로그라이크가 아니라 던전 RPG 이고, 캐릭터가 이어지는 것이 전제다.
 *
 * **시즌 이름이 코어 버전이다** (결정 #06). 밸런스나 블록 목록이 바뀌면 과거 기록이
 * 재현되지 않으므로 순위표가 새로 시작한다 — 화면이 그 이유를 적어 둔다.
 *
 * 경매장은 **수수료율을 먼저 보여준다.** 걸기 전에 얼마가 나가는지 알아야 한다.
 */
import { Button, GlyphState, Panel, ValueExpr } from "../ds";
import { formatAffix } from "./InventoryPanel";
import type { AuctionView, ItemView, LeaderboardView, ListingView, ProgressView } from "../storage";

import { compareToWorn, formatDelta } from "./compareItems";

import { LinkNoticeLine } from './LinkNoticeLine'
import { checkLinked, type LinkState } from './linkState'

export interface WorldPanelProps {
  readonly progress: ProgressView | undefined;
  readonly leaderboard: LeaderboardView | undefined;
  readonly auction: AuctionView | undefined;
  readonly accountId: number | undefined;
  readonly link: LinkState;
  readonly detail: string;
  /**
   * 자리에서 지금 낀 것으로. 매물을 「내 것보다 나은가」로 읽는 데 쓴다.
   *
   * 서버가 매물의 자리를 이제 보내므로 견줄 상대를 찾을 수 있다 — 예전에는 그 필드가
   * 없어서 접사만 늘어놓고 판단을 통째로 사람에게 넘겼다.
   */
  readonly worn: ReadonlyMap<string, ItemView>;
  readonly onBuy: (listingId: number) => void;
  readonly onCancel: (listingId: number) => void;
  readonly onDaily: () => void;
}

/** 못 닿았을 때 무엇을 못 보는가. 앞머리(`서버에 닿지 못했다`)는 linkState 가 든다. */
const MISSING_HINT = '순위와 경매는 서버가 안다'


/**
 * 매물을 지금 낀 것과 견준다.
 *
 * **가방의 견줌과 같은 규칙이다** — 점수 하나가 아니라 스탯별 차이까지만 낸다. 같은
 * 질문에 두 화면이 다른 방식으로 답하면 어느 쪽을 믿을지가 또 문제가 된다.
 *
 * 자리를 모르는 매물(소모품 등)은 견주지 않는다. 견줄 자리가 없다.
 *
 * @param listing 볼 매물.
 * @param worn 자리에서 지금 낀 것으로의 대응표.
 * @returns 견줌 줄들. 견줄 것이 없으면 null.
 */
function renderListingCompare(
  listing: ListingView,
  worn: ReadonlyMap<string, ItemView>,
): React.JSX.Element | null {
  if (listing.slot === '') {
    return null
  }
  const held = worn.get(listing.slot)
  const rows = compareToWorn(listing.affixes, held?.affixes ?? [])
  if (rows.length === 0) {
    const same = held === undefined ? '빈 자리라 그대로 이득이다' : '지금 낀 것과 같다'
    return <ValueExpr text={same} size="sm" dim />
  }
  return (
    <ul className="invd__compare">
      {rows.map((row) => {
        const gain = row.flatDelta + row.percentDelta
        const tone = gain > 0 ? ' invd__delta--up' : gain < 0 ? ' invd__delta--down' : ''
        return (
          <li className="invd__compare-row" key={row.stat}>
            <span className="invd__compare-name">
              {held === undefined ? `${row.label} · 빈 자리` : row.label}
            </span>
            <span className={`invd__delta${tone}`}>{formatDelta(row)}</span>
          </li>
        )
      })}
    </ul>
  )
}

/** 격차 막대의 칸 수. 여덟이면 한 칸이 12.5%라 눈이 그 단위로 읽는다. */
export const BAR_SEGMENTS = 8

/**
 * 1등 대비 격차를 칸으로 나눈다.
 *
 * **색이 아니라 칸 수가 정보다.** 그리고 칸 옆에 점수가 그대로 적혀 있으므로, 칸을
 * 못 읽어도 잃는 것이 없다 — 색이 유일한 채널이 되지 않게 하는 규율과 같다.
 *
 * @param score 이 줄의 점수.
 * @param top 1등의 점수. 0 이면 아무도 점수가 없다.
 * @returns 칸마다 켜짐 여부. 언제나 BAR_SEGMENTS 개다.
 */
export function buildBarSegments(score: number, top: number): boolean[] {
  const filled = top <= 0 ? 0 : Math.round((Math.max(0, score) * BAR_SEGMENTS) / top)
  return Array.from({ length: BAR_SEGMENTS }, (_, index) => index < filled)
}

/**
 * 세계 패널을 그린다.
 *
 * @param props 성장·순위·경매장과 처리기.
 * @returns 패널 요소.
 */

export function WorldPanel(props: WorldPanelProps): React.JSX.Element {
  const { progress, leaderboard, auction, link } = props;
  return (
    <Panel
      title="세계"
      meta={leaderboard === undefined ? "" : `시즌 ${leaderboard.coreVersion}`}
      tone="panel"
      padded
      scroll
    >
      <div className="wld">
        {!checkLinked(link) || progress === undefined ? (
          <LinkNoticeLine link={link} missing={MISSING_HINT} />
        ) : (
          <>
            <div className="wld__head">순위 — 점수는 누적 경험치다</div>
            {leaderboard === undefined || leaderboard.entries.length === 0 ? (
              <ValueExpr text="아직 기록이 없다" size="sm" dim />
            ) : (
              <ul className="wld__list">
                {leaderboard.entries.slice(0, 10).map((entry) => (
                  <li
                    className={`wld__rank${entry.accountId === props.accountId ? ' wld__rank--me' : ''}`}
                    key={entry.accountId}
                  >
                    {/* **컬럼 정렬은 미관이 아니라 디버깅 기능이다** — 자리가 맞아야
                        눈이 세로로 훑는다. 예전에는 `lv6 · 900` 한 덩어리라 레벨도
                        점수도 줄마다 시작 자리가 달랐다. */}
                    <span className="wld__rank-no">{String(entry.rank)}</span>
                    <span className="wld__name">{entry.handle}</span>
                    <span className="wld__rank-lv">{`lv${String(entry.level)}`}</span>
                    <span className="wld__rank-score">{String(entry.score)}</span>
                    {/* 1등 대비 격차. **색이 아니라 칸 수가 정보이고, 숫자가 정본이다** —
                        칸은 「얼마나 멀리 있나」를 세지 않고 알게 해 주는 보조다. */}
                    <span className="wld__bar" aria-hidden="true">
                      {buildBarSegments(entry.score, leaderboard.entries[0]?.score ?? 0).map(
                        (isOn, index) => (
                          <i className={isOn ? 'on' : undefined} key={index} />
                        ),
                      )}
                    </span>
                    {/* **「이것이 너다」는 황동이다** (design/README.md). 예전에는
                        `state="true"` 라 참/거짓의 녹청 ✓ 를 정체성 표시로 쓰고 있었다 —
                        의미색을 빌려 쓰면 그 색이 무엇을 뜻하는지가 화면마다 갈린다.
                        글리프도 도면의 자기 표시(◉)와 같은 것을 쓴다. */}
                    {entry.accountId === props.accountId ? (
                      <span className="wld__me">
                        <span aria-hidden="true">◉</span>
                        <span className="ds-sr">이 줄이 나다</span>
                        나
                      </span>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}

            <div className="wld__head">
              경매장 · 수수료 {String(auction?.feePercent ?? 0)}%
            </div>
            {auction === undefined || auction.listings.length === 0 ? (
              <ValueExpr text="걸린 매물이 없다" size="sm" dim />
            ) : (
              <ul className="wld__list">
                {auction.listings.slice(0, 12).map((item) => (
                  // **세로에서는 줄을 쌓는다.** 한 줄에 이름·접사·값·만료·버튼을 다 넣으면
                  // 좁은 폭에서 오른쪽 끝의 버튼이 밀려 나가고, 그것이 가장 중요한 것이다.
                  <li className="wld__listing" key={item.listingId}>
                    <div className="wld__row">
                      <span className="wld__name">{item.labelKo}</span>
                      <ValueExpr text={`${String(item.price)} 화폐`} size="sm" />
                    </div>
                    {item.affixes.length === 0 ? null : (
                      // 저주 접사는 음수다. 모르고 사면 돈을 내고 약해진다.
                      <ValueExpr
                        text={item.affixes.map(formatAffix).join(' · ')}
                        size="sm"
                      />
                    )}
                    {/* **사기 전에 「내 것보다 나은가」에 답한다.** 접사만 보여 주면
                        그 판단을 사람이 머리로 해야 하고, 산 뒤에는 되돌릴 수 없다
                        (귀속된다 — 결정 #07). 가방의 견줌과 같은 규칙으로 낸다:
                        점수 하나가 아니라 스탯별 차이까지만. */}
                    {renderListingCompare(item, props.worn)}
                    <div className="wld__row">
                      <ValueExpr
                        text={
                          item.isMine
                            ? `내 매물 · 수수료 ${String(item.fee)} 는 안 돌아온다`
                            : `${String(item.expiresInMinutes)}분 뒤 사라진다`
                        }
                        size="sm"
                        dim
                      />
                      {item.isMine ? (
                        <Button
                          size="sm"
                          variant="ghost"
                          glyph="↰"
                          title="내린다 (수수료는 안 돌려준다)"
                          onClick={() => {
                            props.onCancel(item.listingId);
                          }}
                        >
                          내리기
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          variant="primary"
                          glyph="↧"
                          disabled={(auction.balance ?? 0) < item.price}
                          onClick={() => {
                            props.onBuy(item.listingId);
                          }}
                        >
                          구매
                        </Button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}

            <div className="wld__actions">
              <Button
                size="sm"
                variant="secondary"
                glyph="◷"
                onClick={props.onDaily}
              >
                오늘의 도전
              </Button>
            </div>
          </>
        )}
        {props.detail === "" ? null : (
          <div className="wld__warn">
            <GlyphState state="danger" size="sm" label={props.detail} />
          </div>
        )}
      </div>
    </Panel>
  );
}
