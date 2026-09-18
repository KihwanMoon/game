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
 * **이름이 「명부」인 이유** (2026-09-15). 예전에는 「비각」이었는데 그것이 게임 이름이
 * 되면서 앱 이름과 탭 이름이 같아졌다. 비각은 **기억이 사는 곳**이고, 이 탭이 펴 보이는
 * 것은 그 안의 **이름들**이다 — 목록에서 빠진 것은 세상에서도 빠진다(`기획/6_1막`).
 *
 * **경매장도 여기 있지 않다.** 세계 탭은 「나 밖의 일」인데 경매는 내 가방을 바꾸는
 * 일이다 — 사면 돈이 나가고 아이템이 들어오며 되돌릴 수 없다(귀속된다, 결정 #07).
 * 순위표 아래에 있으면 그만한 무게로 안 보였고, 매물 열둘이면 순위표가 화면 밖으로
 * 밀려나기도 했다. `AuctionPanel` 로 나갔다.
 */
import { useState } from 'react'

import { Button, GlyphState, Panel, ValueExpr } from "../ds";

import type { LeaderboardView, ProgressView, WorldPulse } from "../storage";

import { LinkNoticeLine } from './LinkNoticeLine'
import { checkLinked, type LinkState } from './linkState'

/** 창이 이레면 「이번 주」라 적는다 — 사람이 세는 단위가 그것이다. */
const WEEK_DAYS = 7

/**
 * 누적 한 줄. **명부는 이름들이 사는 곳이라 「이름」이라 적는다.**
 *
 * 예전에는 이 수를 「다녀간 사람」이라 불렀는데 틀린 말이었다 — 계정 행은 앱을 연
 * 순간이 아니라 출격에서 생기므로, 세고 있던 것은 **판을 낸 사람**이다.
 *
 * @param pulse 서버가 낸 현황.
 * @returns 적을 한 줄.
 */
export function formatPulseTotals(pulse: WorldPulse): string {
  return `이름 ${String(pulse.visitors)} · 오늘 ${String(pulse.freshToday)} · 돈 판 ${String(pulse.runs)}`
}

/**
 * 창 한 줄 — 들름에서 판으로 가는 깔때기.
 *
 * **두 수를 나란히 두지 않고 화살표로 잇는다.** 따로 적으면 관계를 보는 사람이 스스로
 * 계산해야 하고, 「사람이 오는데 안 한다」와 「아예 안 온다」가 안 갈린다.
 *
 * **기간과 출처를 함께 적는다.** 누적 절대값은 계측을 갈아 끼우는 순간 점프해 예전 값과
 * 이어 붙일 수 없다. 기간이 없으면 보는 사람이 그것을 못 알아채고, 출처가 없으면 수가
 * 뛴 날을 「갑자기 대박」으로 읽는다.
 *
 * **들름이 0 이면 깔때기를 안 적는다.** 그 0 은 「아무도 안 왔다」가 아니라 「계측을
 * 아직 못 받았다」일 수 있고, 둘을 같은 줄로 적으면 없는 사실을 단언하게 된다.
 *
 * @param pulse 서버가 낸 현황.
 * @returns 적을 한 줄. 창 자체가 없으면 빈 문자열이고, 부르는 쪽이 그 줄을 안 그린다.
 */
export function formatPulseWindow(pulse: WorldPulse): string {
  if (pulse.windowDays <= 0) {
    return ''
  }
  const span = pulse.windowDays === WEEK_DAYS ? '이번 주' : `${String(pulse.windowDays)}일`
  if (pulse.windowVisits <= 0) {
    return `${span} 판 ${String(pulse.windowPlayed)}`
  }
  const rate = `${String(pulse.conversionPct)}%`
  const source = pulse.trafficSource === '' ? '' : ` · ${pulse.trafficSource} 기준`
  return `${span} 들름 ${String(pulse.windowVisits)} → 판 ${String(pulse.windowPlayed)} (${rate})${source}`
}

export interface WorldPanelProps {
  readonly progress: ProgressView | undefined;
  readonly leaderboard: LeaderboardView | undefined;
  /**
   * 둔갑 승수 판.
   *
   * **판을 따로 두는 이유는 재는 것이 다르기 때문이다.** 누적 경험치는 얼마나 멀리
   * 왔는가라 오래 돌린 쪽이 이기고, 둔갑 승수는 **내가 없는 동안 내 규칙표가 버틴
   * 횟수**다 — 이 게임에서 성장과 무관한 유일한 수치다 (2026-09-15).
   */
  readonly doppelBoard: LeaderboardView | undefined;
  /**
   * 세계에 사람이 얼마나 오는가 (2026-09-17).
   *
   * **제3자 계측이 아니라 우리가 이미 가진 수다.** 처음 들어오면 익명 계정이 생기므로
   * 계정 수가 곧 「앱을 연 사람 수」에 가깝다 — 분석 스크립트를 들이지 않고도 셀 수
   * 있는 것이 있었다. 못 받으면 그 줄을 안 그린다.
   */
  readonly pulse?: WorldPulse | undefined;
  readonly accountId: number | undefined;
  readonly link: LinkState;
  readonly detail: string;
  readonly onDaily: () => void;
}

/** 못 닿았을 때 무엇을 못 보는가. 앞머리(`서버에 닿지 못했다`)는 linkState 가 든다. */
const MISSING_HINT = '순위는 서버가 안다'

/** 판마다 점수가 무엇인지. **안 적으면 두 판의 숫자가 같은 것으로 읽힌다.** */
const BOARD_HEADS = {
  doppel: '순위 — 점수는 내 둔갑이 이긴 판이다',
  xp: '순위 — 점수는 누적 경험치다',
} as const

/** 둔갑 판이 비었을 때. **없는 것이 아니라 아직 아무도 못 이긴 것**이라고 적는다. */
const DOPPEL_EMPTY = '아직 아무 둔갑도 못 이겼다 — 계정에서 둔갑을 켜면 여기 선다'


/** 격차 막대의 칸 수. 여덟이면 한 칸이 12.5%라 눈이 그 단위로 읽는다. */
const BAR_SEGMENTS = 8

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
function buildBarSegments(score: number, top: number): boolean[] {
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
  const { progress, link } = props;
  // **둔갑 판을 먼저 보인다.** 누적 경험치 판은 「오래 돌린 사람이 이긴다」를 공개적으로
  // 말하는 수치라, 그것이 첫 화면이면 이 게임이 무엇을 재는지가 그렇게 읽힌다. 다만
  // 없애지는 않는다 — 둔갑을 안 켠 사람이 순위표에서 통째로 사라지면 안 된다.
  //
  // **줄이 없으면 안 편다.** 빈 판이 첫 화면이면 「순위표가 비었다」로 읽히고, 그 뒤에
  // 사람이 사는 판이 있다는 사실이 안 보인다 — 시즌이 갈린 직후가 늘 그 상태다.
  const [picked, setPicked] = useState<'doppel' | 'xp' | undefined>(undefined)
  const hasDoppel = (props.doppelBoard?.entries.length ?? 0) > 0
  const board = picked ?? (hasDoppel ? 'doppel' : 'xp')
  const leaderboard = board === 'doppel' ? props.doppelBoard : props.leaderboard
  return (
    <Panel
      title="명부"
      meta={leaderboard === undefined ? "" : `시즌 ${leaderboard.coreVersion}`}
      tone="panel"
      padded
      scroll
    >
      <div className="wld">
        {/* **여기 사람이 사는가.** 순위표만 있으면 이름 몇 줄이 전부라, 판이 도는
            세계인지 멈춘 세계인지가 안 보인다. 「오늘」을 함께 적는 이유도 그것이다 —
            누계만 적으면 옛날에 붐볐던 곳과 구별되지 않는다.

            **줄이 둘인 이유.** 위는 누적, 아래는 창이다. 누적만 적으면 계측을 갈아
            끼우는 날 수가 점프하고 예전 값과 이어 붙일 수 없다. */}
        {props.pulse === undefined ? null : (
          <>
            <ValueExpr text={formatPulseTotals(props.pulse)} size="sm" dim />
            {formatPulseWindow(props.pulse) === '' ? null : (
              <ValueExpr text={formatPulseWindow(props.pulse)} size="sm" dim />
            )}
          </>
        )}
        {!checkLinked(link) || progress === undefined ? (
          <LinkNoticeLine link={link} missing={MISSING_HINT} />
        ) : (
          <>
            <div className="wld__boards">
              <Button
                size="sm"
                variant="ghost"
                active={board === 'doppel'}
                onClick={() => {
                  setPicked('doppel')
                }}
              >
                둔갑
              </Button>
              <Button
                size="sm"
                variant="ghost"
                active={board === 'xp'}
                onClick={() => {
                  setPicked('xp')
                }}
              >
                경험치
              </Button>
            </div>
            <div className="wld__head">{BOARD_HEADS[board]}</div>
            {leaderboard === undefined || leaderboard.entries.length === 0 ? (
              <ValueExpr
                text={board === 'doppel' ? DOPPEL_EMPTY : '아직 기록이 없다'}
                size="sm"
                dim
              />
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
                    {/* **판마다 옆에 붙는 수가 다르다.** 둔갑 판에서 레벨은 아무것도
                        안 말하고, 대신 「몇 판 만에 이룬 것인가」가 승수의 뜻을 정한다 —
                        열 번을 스무 판에 이긴 쪽과 쉰 판에 이긴 쪽은 다르다. */}
                    <span className="wld__rank-lv">
                      {entry.met < 0 ? `lv ${String(entry.level)}` : `${String(entry.met)}판`}
                    </span>
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
