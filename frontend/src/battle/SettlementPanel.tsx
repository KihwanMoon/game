/**
 * 정산 탭 본문 — 층별로 무엇을 벌었는지 한 줄에 하나씩 적는다.
 *
 * **한 줄에 정보 하나다** (실제 요청). 서버는 `화폐 +80 · 경험치 +160 · 사슬 갑옷 획득`
 * 처럼 한 줄로 잇는데, 그것을 그대로 적으면 가로로 길어져 무엇이 들어왔는지 훑을 수
 * 없다. 끊기만 하고 문구는 서버가 만든 것을 그대로 쓴다.
 *
 * 훅을 안 쓴다. 훅 안에 있으면 렌더 검사가 문구를 못 본다 — 이 저장소의 검사는 jsdom
 * 없이 돈다.
 */
import { ValueExpr } from '../ds/ValueExpr'
import type { FloorSettlement } from './settlement'

/** 아직 정산한 층이 없을 때 적는 말. 빈 화면은 고장으로 읽힌다. */
const EMPTY_HINT = '아직 정산한 층이 없다 — 한 층을 깨면 여기에 쌓인다'

/** 항목 줄 앞에 붙는 도형. 색은 --chalk-dim 이며 황동 예산에 들지 않는다. */
const ITEM_GLYPH = '·'

/** SettlementPanel 이 받는 props. */
export interface SettlementPanelProps {
  readonly settlements: readonly FloorSettlement[]
}

/**
 * 층별 정산을 그린다.
 *
 * @param props 정산 목록.
 * @returns 렌더 트리.
 */
export function SettlementPanel(props: SettlementPanelProps): React.JSX.Element {
  if (props.settlements.length === 0) {
    return (
      <div className="settle">
        <ValueExpr text={EMPTY_HINT} size="sm" dim />
      </div>
    )
  }
  return (
    <div className="settle">
      {props.settlements.map((item) => (
        <div className="settle__floor" key={item.floor}>
          <div className="settle__head">{`${String(item.floor)}층 정산`}</div>
          {item.lines.map((line, index) => (
            <div className="settle__row" key={`${String(item.floor)}:${String(index)}`}>
              <span className="settle__glyph" aria-hidden="true">
                {ITEM_GLYPH}
              </span>
              <span className="settle__text">{line}</span>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}
