/**
 * PostMortem — 사망 시 자동으로 뜨는 사후 분석 (GDD §8.3).
 *
 * 죽은 뒤에 답해야 하는 질문은 둘이다. **어느 규칙이 틀렸는가**(규칙 성적표)와 **어디에
 * 서 있었던 것이 틀렸는가**(피해 히트맵). 그 둘을 먼저 보고, 미심쩍은 구간을 직전 15틱
 * 리플레이에서 되감아 확인한다 — 로그 수백 줄을 처음부터 읽는 것이 아니라 짚은 곳만
 * 본다. 그것이 P1(실패는 정보다)이 요구하는 순서다.
 *
 * 되감기는 세계를 되돌리지 않는다. 판이 시작될 때 이미 다 돌려 둔 프레임 배열의 첨자를
 * 옮길 뿐이다(`battleSession.ts`). 결정론 덕에 몇 번을 오가도 같은 화면이 나온다 (R5).
 *
 * 황동 예산: 이 화면은 전투 화면을 덮으므로 예산을 새로 센다. 도면의 플레이어 말 하나와
 * 로그의 현재 틱 세로바, 슬라이더 손잡이까지 셋이다. primary 버튼을 쓰지 않는 이유다.
 */
import { useMemo, useState } from 'react'

import { PlanCanvas } from '../battle'
import type { PlanTheme } from '../battle'
import { Button, Panel } from '../ds'

import { buildDamageHeatmap, buildRuleStats } from './analysis'
import { formatOutcome, formatTickLabel } from './analysisText'
import type { BattleRecording, RecordedFrame } from './battleRecorder'
import { DamageHeatmap } from './DamageHeatmap'
import { LogStream } from './LogStream'
import { DEATH_REPLAY_TICKS, findTickIndex } from './logWindow'
import { RuleStatsTable } from './RuleStatsTable'
import { TickScrubber } from './TickScrubber'

/** 리플레이 로그에 한 번에 그릴 줄 수. 15틱이면 이 안에 들어온다. */
const REPLAY_LOG_ROWS = 120

/** PostMortem 이 받는 props. */
export interface PostMortemProps {
  readonly recording: BattleRecording
  /** 도면 테마. 아직 토큰을 읽지 못했으면 undefined 이고 그동안 도면을 그리지 않는다. */
  readonly theme: PlanTheme | undefined
  readonly onClose: () => void
}

/**
 * 되감기가 오갈 수 있는 첫 틱.
 *
 * @param ticks 판이 끝난 틱.
 * @returns 마지막 틱에서 DEATH_REPLAY_TICKS 만큼 거슬러 올라간 틱. 1 아래로는 가지 않는다.
 */
export function getReplayStartTick(ticks: number): number {
  return Math.max(1, ticks - DEATH_REPLAY_TICKS + 1)
}

/**
 * 사후 분석 화면을 그린다.
 *
 * @param props 기록·도면 테마·닫기 콜백.
 * @returns 렌더 트리.
 */
export function PostMortem(props: PostMortemProps): React.JSX.Element {
  const { recording } = props
  const startTick = getReplayStartTick(recording.ticks)
  const [tick, setTick] = useState(recording.ticks)

  const stats = useMemo(
    () => buildRuleStats(recording.entries, recording.playerId),
    [recording.entries, recording.playerId],
  )
  const heatmap = useMemo(
    () =>
      buildDamageHeatmap(
        recording.hits,
        recording.template.width,
        recording.template.height,
        recording.playerId,
      ),
    [recording.hits, recording.template, recording.playerId],
  )

  const frame: RecordedFrame | undefined = recording.frames[tick]
  const anchorIndex = findTickIndex(recording.entries, tick)

  return (
    <div className="hud-post" role="dialog" aria-label="사후 분석">
      <header className="hud-post__head">
        <h2 className="hud-post__title">사후 분석 — {formatOutcome(recording.outcome)}</h2>
        <span className="hud-post__meta">
          {recording.template.templateId} · {formatTickLabel(recording.ticks)} · HP{' '}
          {recording.playerHp}
        </span>
        <Button size="sm" variant="secondary" glyph="✕" onClick={props.onClose}>
          닫기
        </Button>
      </header>

      <div className="hud-post__body">
        <div className="hud-post__col">
          <Panel title="규칙별 발동" meta={recording.ruleset.rulesetId} padded={false} scroll>
            <RuleStatsTable stats={stats} />
          </Panel>
          <Panel title="피해 히트맵" meta="플레이어 피격">
            <DamageHeatmap grid={heatmap} caption="플레이어가 받은 피해" />
          </Panel>
        </div>

        <div className="hud-post__col hud-post__col--wide">
          <Panel
            title={`직전 ${DEATH_REPLAY_TICKS}틱 리플레이`}
            meta={formatTickLabel(tick)}
            padded={false}
          >
            <div className="hud-post__replay">
              <div className="hud-post__plan">
                {frame === undefined || props.theme === undefined ? (
                  <p className="hud-log__cut">그 틱의 화면이 없다</p>
                ) : (
                  <PlanCanvas scene={frame.scene} theme={props.theme} />
                )}
              </div>
              <div className="hud-post__log">
                <LogStream
                  entries={recording.entries}
                  follow={false}
                  onFollowChange={() => undefined}
                  currentTick={tick}
                  maxRows={REPLAY_LOG_ROWS}
                  {...(anchorIndex === undefined ? {} : { anchorIndex })}
                />
              </div>
            </div>
            <div className="hud-post__scrub">
              <TickScrubber
                min={startTick}
                max={recording.ticks}
                value={tick}
                onChange={setTick}
                label="되감기"
              />
            </div>
          </Panel>
        </div>
      </div>
    </div>
  )
}
