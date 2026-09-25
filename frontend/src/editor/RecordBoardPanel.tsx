/**
 * 방별 기록판 (2026-09-25) — **「얼마나 잘 짰는가」를 직접 재는 자리.**
 *
 * 순위표는 누적 경험치라 오래 돈 쪽이 앞선다. 이 판은 같은 방·같은 시드·같은 몸에서
 * 누가 가장 적은 CPU 로 이겼는가만 본다 — 장비로 못 사는 축이라 20장을 다 돈 뒤에도
 * 끝이 없다.
 *
 * **지금 고른 방의 판이다.** 방은 출격 줄에서 고른다 — 여기서 또 고르게 하면 두 곳의
 * 방이 갈려 「이 판은 어느 방인가」가 흐려진다.
 *
 * **줄을 누르면 그 표가 열린다.** 1위의 CPU 만 보면 「어떻게?」가 남는다. 공유 주소가
 * 그 답이다.
 */
import { Button, Panel, ValueExpr } from '../ds'
import type { RoomRecordBoard } from '../storage'
import { formatRecordScore, formatRecordSummary } from '../storage'
import { LinkNoticeLine } from './LinkNoticeLine'
import { checkLinked, type LinkState } from './linkState'

export interface RecordBoardPanelProps {
  readonly board: RoomRecordBoard | undefined
  /** 지금 고른 방의 이름. 판 제목에 적는다. */
  readonly roomLabel: string
  readonly accountId: number | undefined
  readonly link: LinkState
  /** 기록 도전을 건다. 막혀 있으면(빈 내력·출격 중) 부르는 쪽이 `isLocked` 로 알린다. */
  readonly onChallenge: () => void
  readonly isLocked: boolean
}

/** 못 닿았을 때 무엇을 못 보는가. */
const MISSING_HINT = '기록판은 서버가 안다'

/** 판에 싣는 줄 수. 서버가 스물을 주지만 한 화면은 열이면 「어디쯤이 잘한 것인가」가 보인다. */
const SHOWN = 10

export function RecordBoardPanel(props: RecordBoardPanelProps) {
  const { board } = props
  return (
    <Panel title="방 기록" meta={props.roomLabel} tone="panel" padded>
      <div className="wld">
        {!checkLinked(props.link) ? (
          <LinkNoticeLine link={props.link} missing={MISSING_HINT} />
        ) : (
          <>
            {/* **몸과 시드가 같다는 것이 이 판의 전부다.** 안 적으면 「장비가 좋아서」로 읽힌다. */}
            <ValueExpr text="같은 시드 · 1장의 기본 몸 · 보상 없음 — 적게 쓰고 이긴 쪽이 위" size="sm" dim />
            <ValueExpr text={formatRecordSummary(board)} size="sm" dim />
            {board === undefined || board.rows.length === 0 ? null : (
              <ul className="wld__list">
                {board.rows.slice(0, SHOWN).map((row) => (
                  <li
                    className={`wld__rank${row.accountId === props.accountId ? ' wld__rank--me' : ''}`}
                    key={row.accountId}
                  >
                    <span className="wld__rank-no">{String(row.rank)}</span>
                    <a className="wld__name" href={`/r/${row.shareId}`} target="_blank" rel="noreferrer">
                      {row.handle}
                    </a>
                    <span className="wld__rank-score">{formatRecordScore(row)}</span>
                    {row.accountId === props.accountId ? (
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
                glyph="◇"
                disabled={props.isLocked}
                title="지금 내력으로 이 방의 기록에 도전한다 — 푼·경험치는 안 나온다"
                onClick={props.onChallenge}
              >
                기록 도전
              </Button>
            </div>
          </>
        )}
      </div>
    </Panel>
  )
}
