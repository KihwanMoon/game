/**
 * RuleStatsTable — 규칙별 발동·성공·헛돔 (GDD §8.3).
 *
 * `sniper` 가 "후퇴 36회 · 사격 2회" 로 졌다는 한 줄이면 로그를 처음부터 읽지 않아도
 * 고칠 곳이 특정된다. 그것이 P1(실패는 정보다)이 요구하는 것이고 이 표가 있는 이유다.
 *
 * 숫자 열은 모노 + tabular-nums 로 **컬럼 정렬**한다. design/README.md 가 적었듯 컬럼
 * 정렬은 미관이 아니라 디버깅 기능이다 — 자리가 맞아야 눈이 세로로 훑는다.
 *
 * 집계는 `analysis.ts`, 진단 문구는 `analysisText.ts` 에 있다. 이 파일에는 계산이 없다.
 */

import { GlyphState } from '../ds'

import { SUSPICIOUS_WASTE_PCT, getWastePercent } from './analysis'
import type { RuleStat } from './analysis'
import { describeRuleStat } from './analysisText'

/** RuleStatsTable 이 받는 props. */
export interface RuleStatsTableProps {
  readonly stats: readonly RuleStat[]
}

/**
 * 성적표를 그린다.
 *
 * @param props 규칙별 성적.
 * @returns 렌더 트리.
 */
export function RuleStatsTable(props: RuleStatsTableProps): React.JSX.Element {
  if (props.stats.length === 0) {
    return <p className="hud-stats__empty ds-label">기록 없음</p>
  }

  return (
    <table className="hud-stats">
      <thead>
        <tr>
          <th scope="col">규칙</th>
          <th scope="col">발동</th>
          <th scope="col">성공</th>
          <th scope="col">헛돔</th>
          <th scope="col">진단</th>
        </tr>
      </thead>
      <tbody>
        {props.stats.map((stat) => {
          const wastePct = getWastePercent(stat)
          const suspicious = wastePct >= SUSPICIOUS_WASTE_PCT
          return (
            <tr key={stat.label} className={suspicious ? 'hud-stats__row--warn' : undefined}>
              <th scope="row">{stat.label}</th>
              <td>{stat.fired}</td>
              <td>{stat.acted}</td>
              <td>{stat.wasted}</td>
              <td className="hud-stats__note">
                {describeRuleStat(stat) === '' ? null : (
                  <GlyphState
                    state={suspicious ? 'danger' : 'pending'}
                    size="sm"
                    label={describeRuleStat(stat)}
                  />
                )}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
