/**
 * DamageHeatmap — 어느 칸에서 얼마를 맞았는가 (GDD §8.3).
 *
 * "어느 규칙이 틀렸는가" 를 규칙 성적표가 답한다면, 이쪽은 **"어디에 서 있었던 것이
 * 틀렸는가"** 를 답한다. 피해의 절반을 같은 통로 칸에서 받았다는 사실은 로그 수백 줄을
 * 읽어서는 보이지 않고 격자 하나로는 한눈에 보인다.
 *
 * 칸마다 수치를 적는다. 색은 정보의 유일한 채널이 될 수 없으므로(design/README.md)
 * 배경 명도는 보조이고, 숫자가 정보다. 흑백으로 인쇄해도 읽힌다.
 */

import { findHeatmapPeakCell } from './analysis'
import { formatHeatValue, getHeatLevel } from './analysisText'

/** DamageHeatmap 이 받는 props. */
export interface DamageHeatmapProps {
  /** `[y][x]` 순서의 피해 합계 격자. */
  readonly grid: readonly (readonly number[])[]
  /** 무엇을 센 격자인가. 화면에 그대로 적는다. */
  readonly caption: string
}

/**
 * 히트맵을 그린다.
 *
 * @param props 격자와 설명.
 * @returns 렌더 트리.
 */
export function DamageHeatmap(props: DamageHeatmapProps): React.JSX.Element {
  const peak = findHeatmapPeakCell(props.grid)
  const width = props.grid[0]?.length ?? 0

  return (
    <div className="hud-heat">
      <p className="hud-heat__caption">
        {props.caption}
        {peak === undefined ? (
          <span className="hud-heat__peak"> — 피해 없음</span>
        ) : (
          <span className="hud-heat__peak">
            {' '}
            — 최다 ({peak.position.x}, {peak.position.y}) {peak.amount}
          </span>
        )}
      </p>
      <div
        className="hud-heat__grid"
        style={{ gridTemplateColumns: `repeat(${String(width)}, var(--sp-5))` }}
      >
        {props.grid.map((row, y) =>
          row.map((value, x) => (
            <span
              className={`hud-heat__cell hud-heat__cell--l${String(getHeatLevel(value, peak?.amount ?? 0))}`}
              key={`${String(x)},${String(y)}`}
              title={`(${String(x)}, ${String(y)}) ${String(value)}`}
            >
              {formatHeatValue(value)}
            </span>
          )),
        )}
      </div>
    </div>
  )
}
