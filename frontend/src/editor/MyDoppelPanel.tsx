/**
 * 내 둔갑 — **돌아오는 길** (2026-09-15 요청: 「둔갑을 양방향으로」).
 *
 * 이 게임의 축은 거의 다 플레이어를 따라온다. 층 스케일도(×1.2 복리), 둔갑의 레벨도,
 * 선공도(2026-09-15 에 그렇게 만들었다). 그래서 **세져도 체감 난이도가 같고**, 순위는
 * 누적 경험치라 오래 돌린 쪽이 앞선다 — 「내가 잘 적었다」가 쌓이는 자리가 없었다.
 *
 * 내 내력이 남의 장에 서서 **누구를 만나고 몇을 이겼는지는 성장과 무관한 사실**이다.
 * 이 패널이 그것 하나만 적는다.
 *
 * **비어 있는 것과 꺼 둔 것을 가른다.** 그림자를 안 세우기로 한 계정은 전적이 없는 것이
 * 정상이고, 그때 「아직 없다」라고만 적으면 켜면 생긴다는 사실이 어디에도 안 보인다.
 *
 * **셈이 언제 끝나는지를 적는다** (2026-09-15). 이긴 판은 활자가 되는데, 들어오는 것은
 * 이긴 그 순간이 아니라 **그림자가 물러날 때**다 — 안 적으면 「이겼는데 활자가 안 늘었다」
 * 로 보인다. 서 있는 동안 몇을 이겼는지는 여기 줄에 그대로 있다.
 */
import { GlyphState, Panel, ValueExpr } from '../ds'
import type { MyDoppelView } from '../storage'

import { LinkNoticeLine } from './LinkNoticeLine'
import { checkLinked, type LinkState } from './linkState'

export interface MyDoppelPanelProps {
  readonly view: MyDoppelView | undefined
  readonly link: LinkState
}

/** 못 닿았을 때 무엇을 못 보는가. */
const MISSING_HINT = '내 둔갑은 서버가 안다'

/** 그림자를 꺼 둔 계정에 적는 말. */
const OFF_HINT = '둔갑을 안 세우는 중이다 — 계정에서 켜면 내 내력이 남의 장에 선다'

/** 한 번도 안 만났을 때. */
const EMPTY_HINT = '아직 아무도 내 둔갑을 못 만났다'

/** 활자가 언제 들어오는가. **이긴 순간이 아니다** — 안 적으면 셈이 틀린 것으로 보인다. */
const LETTER_HINT = '이긴 판은 그 둔갑이 물러날 때 활자가 되어 들어온다'

/**
 * 전적 한 줄을 사람이 읽는 말로.
 *
 * **이긴 쪽을 주어로 적는다.** 「3장에서 이겼다」는 누가 이겼는지를 안 말한다 — 이
 * 패널에서 주인공은 내 그림자다.
 *
 * @param bout 전적 한 줄.
 * @returns 화면에 적을 문구.
 */
export function formatBout(bout: { floor: number; isDoppelWin: boolean; opponent: string }): string {
  const who = bout.opponent === '' ? '누군가' : bout.opponent
  return bout.isDoppelWin
    ? `${String(bout.floor)}장 · ${who} 를 이겼다`
    : `${String(bout.floor)}장 · ${who} 에게 잡혔다`
}

/**
 * 내 둔갑 패널을 그린다.
 *
 * @param props 전적과 접속 상태.
 * @returns 패널 요소.
 */
export function MyDoppelPanel(props: MyDoppelPanelProps): React.JSX.Element {
  const { view, link } = props
  const isLinked = checkLinked(link)

  return (
    <Panel
      title="내 둔갑"
      meta={view === undefined ? '' : `${String(view.won)} / ${String(view.met)}`}
      tone="panel"
      padded
      scroll
    >
      <LinkNoticeLine link={link} missing={MISSING_HINT} />
      {!isLinked || view === undefined ? null : !view.isOptedIn ? (
        <ValueExpr text={OFF_HINT} size="sm" dim />
      ) : (
        <div className="doppel-mine">
          <ValueExpr
            text={`만난 판 ${String(view.met)} · 이긴 판 ${String(view.won)}`}
            size="sm"
          />
          <ValueExpr text={LETTER_HINT} size="sm" dim />
          {view.standing.length === 0 ? (
            <ValueExpr text="지금 서 있는 둔갑이 없다 — 깊은 장에서 죽으면 선다" size="sm" dim />
          ) : (
            <ul className="doppel-mine__list">
              {view.standing.map((one) => (
                <li className="doppel-mine__row" key={one.recordId}>
                  <span className="doppel-mine__floor">{String(one.floor)}장</span>
                  <ValueExpr
                    text={`lv ${String(one.level)} · 목숨 ${String(one.lives)}`}
                    size="sm"
                    dim
                  />
                </li>
              ))}
            </ul>
          )}
          {view.recent.length === 0 ? (
            <ValueExpr text={EMPTY_HINT} size="sm" dim />
          ) : (
            <ul className="doppel-mine__list">
              {view.recent.map((bout, at) => (
                <li className="doppel-mine__row" key={`${bout.at}-${String(at)}`}>
                  <GlyphState
                    state={bout.isDoppelWin ? 'true' : 'false'}
                    size="sm"
                    label={formatBout(bout)}
                  />
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Panel>
  )
}
