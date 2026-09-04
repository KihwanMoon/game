/**
 * 세계 패널 — 순위와 오늘의 도전 (F단계).
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
 * **경매장도 여기 있지 않다.** 세계 탭은 「나 밖의 일」인데 경매는 내 가방을 바꾸는
 * 일이다 — 사면 돈이 나가고 아이템이 들어오며 되돌릴 수 없다(귀속된다, 결정 #07).
 * 순위표 아래에 있으면 그만한 무게로 안 보였고, 매물 열둘이면 순위표가 화면 밖으로
 * 밀려나기도 했다. `AuctionPanel` 로 나갔다.
 */
import { Button, GlyphState, Panel, ValueExpr } from "../ds";
import type { LeaderboardView, ProgressView } from "../storage";

import { LinkNoticeLine } from './LinkNoticeLine'
import { checkLinked, type LinkState } from './linkState'

export interface WorldPanelProps {
  readonly progress: ProgressView | undefined;
  readonly leaderboard: LeaderboardView | undefined;
  readonly accountId: number | undefined;
  readonly link: LinkState;
  readonly detail: string;
  readonly onDaily: () => void;
}

/** 못 닿았을 때 무엇을 못 보는가. 앞머리(`서버에 닿지 못했다`)는 linkState 가 든다. */
const MISSING_HINT = '순위는 서버가 안다'


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
 * @param props 성장·순위와 처리기.
 * @returns 패널 요소.
 */

export function WorldPanel(props: WorldPanelProps): React.JSX.Element {
  const { progress, leaderboard, link } = props;
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
