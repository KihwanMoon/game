/**
 * 내가 돈 판들 — **다시 볼 수 있다** (결정 #09).
 *
 * **기록을 트는 것이 아니라 다시 돌리는 것이다.** 이벤트 로그는 저장하지 않는다 — 남는
 * 것은 제출(규칙표)과 판정(결과)뿐이다. 그런데 코어가 결정론이라(R5·G3) 같은 입력이면
 * 같은 판이 나오므로, 시드·방·층·로드아웃·스냅샷을 그대로 넣고 다시 돌리면 그때 그
 * 판이 눈앞에 다시 선다.
 *
 * **그때의 결과를 함께 적는다.** 재생이 같은 답을 내는지 사람이 눈으로 대조할 수 있어야
 * 한다 — 어긋나면 그것은 재생의 버그가 아니라 **두 코어가 갈렸다는 신호**다.
 */
import { Button, GlyphState, Panel, ValueExpr } from '../ds'
import type { RunHistoryRow } from '../storage'

import { LinkNoticeLine } from './LinkNoticeLine'
import { checkLinked, type LinkState } from './linkState'

/** 못 닿았을 때 무엇을 못 보는가. 앞머리는 linkState 가 든다. */
const MISSING_HINT = '지나간 판은 서버가 안다'

/** 한 판도 없을 때. 빈 화면은 고장으로 읽힌다. */
const EMPTY_TEXT = '아직 돈 판이 없다 — 출격하면 여기에 쌓인다'

export interface RunHistoryPanelProps {
  readonly runs: readonly RunHistoryRow[]
  readonly link: LinkState
  /** 그 판을 다시 돌린다. */
  readonly onReplay: (submissionId: number) => void
}

/**
 * 결과를 사람이 읽는 말로.
 *
 * **판정 전과 패배를 가른다** — 서버가 밀렸을 뿐인데 진 것으로 읽히면 안 된다.
 *
 * @param outcome 서버가 확정한 결과.
 * @returns 화면에 적을 말.
 */
export function formatRunOutcome(outcome: string): string {
  if (outcome === 'PLAYER_WIN') {
    return '승리'
  }
  if (outcome === '') {
    return '판정 전'
  }
  if (outcome === 'TIMEOUT') {
    return '시간 초과'
  }
  return '패배'
}

/**
 * 내가 돈 판 목록을 그린다.
 *
 * @param props 판들과 처리기.
 * @returns 렌더 트리.
 */
export function RunHistoryPanel(props: RunHistoryPanelProps): React.JSX.Element {
  const isLinked = checkLinked(props.link)
  return (
    <Panel title="지나간 판" meta={`${String(props.runs.length)}`} tone="panel" padded scroll>
      <LinkNoticeLine link={props.link} missing={MISSING_HINT} />
      {!isLinked ? null : props.runs.length === 0 ? (
        <ValueExpr text={EMPTY_TEXT} size="sm" dim />
      ) : (
        <ul className="runs">
          {props.runs.map((run) => (
            <li className="runs__row" key={run.submissionId}>
              <span className="runs__cell">{`${run.roomId} · ${String(run.floor)}층`}</span>
              <GlyphState
                state={run.outcome === 'PLAYER_WIN' ? 'true' : 'false'}
                size="sm"
                label={formatRunOutcome(run.outcome)}
              />
              <ValueExpr
                text={`${String(run.ticks)}틱 · HP ${String(run.playerHp)}`}
                size="sm"
                dim
              />
              {/* **시드를 적는다.** 재생이 같은 판을 도는 근거가 이것이고, 같은 시드로
                  다시 돌려 보고 싶은 사람에게도 필요하다. */}
              <ValueExpr text={`시드 ${String(run.seed)}`} size="sm" dim />
              <Button
                size="sm"
                variant="secondary"
                glyph="▶"
                onClick={() => {
                  props.onReplay(run.submissionId)
                }}
              >
                다시 보기
              </Button>
            </li>
          ))}
        </ul>
      )}
      {props.runs.length === 0 ? null : (
        <ValueExpr
          text="기록을 트는 것이 아니라 같은 입력으로 다시 돌린다 — 그때의 결과를 옆에 적어 둔다"
          size="sm"
          dim
        />
      )}
    </Panel>
  )
}
