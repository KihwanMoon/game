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
import { formatOutcome } from '../battle/outcomeText'
import { Button, GlyphState, Panel, ValueExpr } from '../ds'
import type { RunHistoryRow } from '../storage'

import { LinkNoticeLine } from './LinkNoticeLine'
import { checkLinked, type LinkState } from './linkState'
import { ROOM_TEMPLATES } from '../core/resources'
import { findRoomTitle } from '../core/schemas/room'

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
 * **말은 전투·사후 분석과 같은 표에서 가져온다** (`battle/outcomeText`). 여기에 표를 한 벌
 * 더 두면 같은 `PLAYER_LOSS` 가 이 목록에서는 「패배」, 전투 화면에서는 「쓰러짐」으로
 * 보인다 — `outcomeText.ts` 가 라벨표 두 벌을 한 곳으로 모으며 막으려던 바로 그 결함이다.
 *
 * **판정 전만 여기서 덧붙인다.** 코어는 빈 판정을 내지 않는다 — 빈 값은 「서버가 아직
 * 안 봤다」는 이 화면만의 상태이고, 그것이 진 것으로 읽히면 안 된다.
 *
 * @param outcome 서버가 확정한 결과. 아직 판정 전이면 빈 문자열.
 * @returns 화면에 적을 말.
 */
export function formatRunOutcome(outcome: string): string {
  if (outcome === '') {
    return '판정 전'
  }
  return formatOutcome(outcome)
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
              <span className="runs__cell">{`${findRoomTitle(ROOM_TEMPLATES, run.roomId)} · ${String(run.floor)}장`}</span>
              <GlyphState
                state={run.outcome === 'PLAYER_WIN' ? 'true' : 'false'}
                size="sm"
                label={formatRunOutcome(run.outcome)}
              />
              <ValueExpr
                text={`${String(run.ticks)}틱 · 체력 ${String(run.playerHp)}`}
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
