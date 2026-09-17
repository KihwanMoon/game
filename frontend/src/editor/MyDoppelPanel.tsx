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

import { DataList } from './DataList'
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

/** 아직 아무것도 안 끝났을 때. **「없다」가 아니라 「아직」이다.** */
const NO_RETIRED_HINT = '아직 물러난 둔갑이 없다 — 목숨 셋을 다 쓰면 그때 셈이 끝난다'

/** 전적을 한 번에 보일 줄 수. 예전에 서버가 주던 만큼이라 첫 화면이 안 바뀐다. */
const PAGE_SIZE = 10

/**
 * 물러난 둔갑 한 줄을 사람이 읽는 말로.
 *
 * **활자를 함께 적는다.** 승수와 같은 수지만, 그 둘이 같다는 사실 자체가 화면에
 * 없으면 「몇을 이겼는지」와 「무엇을 받았는지」를 사람이 속으로 이어야 한다.
 *
 * @param one 물러난 둔갑.
 * @returns 한 줄.
 */
export function formatRetired(one: { floor: number; won: number; lost: number }): string {
  const tail = one.won === 0 ? '활자 없음' : `활자 +${String(one.won)}`
  return `${String(one.floor)}장 · ${String(one.won)}승 ${String(one.lost)}패 → ${tail}`
}

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
          {/* **세 목록이 같은 틀을 쓴다** (2026-09-17). 손으로 짠 `ul` 이 셋이었고, 빈
              경우를 저마다 바깥에서 갈라 적고 있었다 — 한 곳을 고쳐도 나머지 둘은 옛
              모양으로 남는 자리다.

              **서 있는 둔갑에는 찾기를 안 켠다.** 둘까지다(`DOPPELS_PER_SOURCE`) —
              두 줄짜리에 찾기 칸이 서면 뒤에 뭔가 더 있다는 거짓말이 된다.

              **전적에는 켠다.** 한 계정이 236판을 치른 것을 재고(2026-09-17) 서버 상한을
              10 → 100 으로 올렸다. 그 전에는 열 줄만 와서 나머지가 아예 안 보였다 —
              찾기를 붙여도 볼 것이 없었던 셈이다. 기본 한 장은 여전히 열 줄이다. */}
          <DataList
            items={view.standing}
            rowKey={(one) => String(one.recordId)}
            listClass="doppel-mine__list"
            rowClass="doppel-mine__row"
            emptyText="지금 서 있는 둔갑이 없다 — 깊은 장에서 죽으면 선다"
            renderRow={(one) => (
              <>
                <span className="doppel-mine__floor">{String(one.floor)}장</span>
                <ValueExpr
                  text={`lv ${String(one.level)} · 목숨 ${String(one.lives)}`}
                  size="sm"
                  dim
                />
              </>
            )}
          />
          <div className="doppel-mine__head">물러난 둔갑</div>
          <DataList
            items={view.retired}
            rowKey={(one) => String(one.recordId)}
            listClass="doppel-mine__list"
            rowClass="doppel-mine__row"
            emptyText={NO_RETIRED_HINT}
            pageSize={PAGE_SIZE}
            filterText={(one) => formatRetired(one)}
            filterLabel="장·전적으로 찾기"
            unit="줄"
            renderRow={(one) => (
              <GlyphState
                state={one.won > 0 ? 'armed' : 'false'}
                size="sm"
                label={formatRetired(one)}
              />
            )}
          />
          <div className="doppel-mine__head">최근 만난 판</div>
          <DataList
            items={view.recent}
            // **값이 겹칠 수 있어 자리를 함께 쓴다.** 같은 시각에 두 판이 끝나면 키가
            // 같아지고, React 가 같은 줄로 보고 하나를 지운다.
            rowKey={(bout, at) => `${bout.at}-${String(at)}`}
            listClass="doppel-mine__list"
            rowClass="doppel-mine__row"
            emptyText={EMPTY_HINT}
            pageSize={PAGE_SIZE}
            // 상대 이름과 층이 한 줄에 있다 — 「누구에게 졌더라」가 이 목록의 질문이다.
            filterText={(bout) => formatBout(bout)}
            filterLabel="상대·장으로 찾기"
            unit="판"
            renderRow={(bout) => (
              <GlyphState
                state={bout.isDoppelWin ? 'true' : 'false'}
                size="sm"
                label={formatBout(bout)}
              />
            )}
          />
        </div>
      )}
    </Panel>
  )
}
