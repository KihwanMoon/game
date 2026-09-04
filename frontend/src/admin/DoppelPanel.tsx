/**
 * 도플갱어 목록 (T11).
 *
 * **봇 탭에서 갈라 나왔다.** 한 탭에 봇 표와 도플갱어 표가 함께 있어서, 봇 하나를 열면
 * 그 상세가 도플갱어 목록 뒤로 밀렸다 — 두 표가 서로의 자리를 다퉜다. 둘은 다른 것이다:
 * 봇은 **계정**이고 도플갱어는 **얼려 둔 개체 기록**이다.
 *
 * **봇과 같은 UI 를 쓴다.** 줄을 고르면 같은 탭 껍데기(`DetailShell`)가 열린다 — 같은
 * 것을 두 모양으로 그리면 답이 갈린다. 다른 것은 **탭 수**뿐이고, 그 차이가 곧 이 개체가
 * 무엇인지를 말한다.
 */
import { useState } from 'react'

import { GlyphState, Panel, ValueExpr } from '../ds'
import type { BotOverview } from '../storage/botAdmin'
import type { DoppelDetail, InventoryView } from '../storage'

import { DoppelDetailPanel } from './BotDetail'

/** 아무것도 없을 때 적는 말. 빈 화면은 고장으로 읽힌다. */
const EMPTY_DOPPELS = '아직 도플갱어가 없다 — 봇이 깊은 층에서 죽으면 그 빌드가 여기 선다'

export interface DoppelPanelProps {
  readonly overview: BotOverview | undefined
  /** 고른 개체의 상세. 줄을 고를 때 밖에서 읽어 넣는다. */
  readonly detail: DoppelDetail | undefined
  /** 고른 개체가 끼고 있던 것. 아이템이 아니라 얼려 둔 기록이다. */
  readonly gear: InventoryView | undefined
  /** 줄을 골랐을 때. 그 개체의 상세와 장비를 읽어 오라는 신호다. */
  readonly onPick?: (recordId: number) => void
}

/**
 * 도플갱어 목록과 고른 하나의 상세를 그린다.
 *
 * @param props 현황과 처리기.
 * @returns 렌더 트리.
 */
export function DoppelPanel(props: DoppelPanelProps): React.JSX.Element {
  const [pickedId, setPickedId] = useState(0)
  const rows = props.overview?.doppels ?? []
  return (
    <div className="bots">
      <Panel title="도플갱어" meta={`${String(rows.length)}`} tone="panel" padded>
        {rows.length === 0 ? (
          <ValueExpr text={EMPTY_DOPPELS} size="sm" dim />
        ) : (
          <div className="bots__grid">
            {rows.map((item) => (
              <button
                type="button"
                className={`botrow${item.recordId === pickedId ? ' botrow--picked' : ''}`}
                key={item.recordId}
                onClick={() => {
                  const next = pickedId === item.recordId ? 0 : item.recordId
                  setPickedId(next)
                  if (next !== 0) {
                    props.onPick?.(next)
                  }
                }}
              >
                <span className="botrow__name">{`#${String(item.recordId)}`}</span>
                <GlyphState
                  state={item.alive ? 'true' : 'false'}
                  size="sm"
                  label={item.alive ? '살아 있다' : '죽었다'}
                />
                <span className="botrow__cell">{`${String(item.zoneFloor)}층`}</span>
                {/* **목숨은 셋에서 줄어든다.** 잡을 때마다 하나 쓰고 레벨이 감쇠하므로,
                    같은 그림자를 세 번 만나되 만날 때마다 약해진다. 남은 수를 안 적으면
                    「왜 아직 서 있지」와 「왜 사라졌지」를 둘 다 설명할 수 없다. */}
                <span className="botrow__cell">{`목숨 ${String(item.lives)}`}</span>
                <span className="botrow__cell">{`레벨 ${String(item.level)}`}</span>
                <span className="botrow__cell">{item.entitySlot}</span>
                <span className="botrow__cell">
                  {item.originHandle === '' ? '주인 없음' : `${item.originHandle} 의 그림자`}
                </span>
              </button>
            ))}
          </div>
        )}
        {rows.length === 0 ? null : (
          <ValueExpr text="줄을 고르면 아래에서 그 개체를 연다" size="sm" dim />
        )}
      </Panel>

      {/* 고른 개체의 상세. **표 바로 다음이다** — 뒤로 밀면 스크롤에 묻힌다. */}
      <DoppelDetailPanel detail={props.detail} gear={props.gear} />
    </div>
  )
}
