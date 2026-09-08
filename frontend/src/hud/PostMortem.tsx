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
import { useMemo, useRef, useState } from 'react'

import { BattleFrame, PlanCanvas, buildLookOf } from '../battle'
import type { SheetTab } from '../battle'
import { BLOCK_CATALOG } from '../core/resources'
import type { PlanTheme } from '../battle'
import { Button, Panel } from '../ds'

import { buildDamageHeatmap, buildRuleStats } from './analysis'
import { formatOutcome, formatTickLabel } from './analysisText'
import type { BattleRecording, RecordedFrame } from './battleRecorder'
import { DamageHeatmap } from './DamageHeatmap'
import { DEATH_REPLAY_TICKS, useLogAnchor } from './logWindow'
import { buildReplayTrace, buildSheetRows, findDecision } from './replayTrace'
import { RuleStatsTable } from './RuleStatsTable'
import { TickScrubber } from './TickScrubber'

/** PostMortem 이 받는 props. */
export interface PostMortemProps {
  readonly recording: BattleRecording
  /** 도면 테마. 아직 토큰을 읽지 못했으면 undefined 이고 그동안 도면을 그리지 않는다. */
  readonly theme: PlanTheme | undefined
  /**
   * 그 판에서 낀 무기. 되감기의 칼자국이 이것으로 갈린다 (설계/10_외형과_모션 C1).
   *
   * **안 받던 때는 리플레이만 기본 자국 하나로 돌았다**(실제 신고). 관전에서 도끼로
   * 찍던 것이 되감기에서 직검이 되면, 방금 본 판과 다른 판을 보는 것이 된다.
   */
  readonly weaponCatalogId?: string
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
  // 시트가 처음 여는 탭. 관전·되감기와 같다 — 규칙표가 이 게임의 주어다.
  const [tab, setTab] = useState<SheetTab>('rules')
  const sheetRef = useRef<HTMLDivElement>(null)

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

  const lookOf = useMemo(() => buildLookOf(props.weaponCatalogId ?? ''), [props.weaponCatalogId])

  // 강조만 있고 그 줄이 화면 밖이면 강조가 아무것도 못 한다.
  useLogAnchor(sheetRef, tick, tab)

  const frame: RecordedFrame | undefined = recording.frames[tick]
  const trace = buildReplayTrace(
    recording.ruleset,
    BLOCK_CATALOG,
    findDecision(recording.entries, tick, recording.playerId),
  )

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
            {/* **관전·되감기와 같은 속이다.** 짚은 틱에서 무엇이 있었는지를 묻는 자리라
                그리는 것이 전투 화면과 다를 이유가 없다 — 다른 모양으로 그리면 방금
                본 판과 다른 판을 보는 것이 된다. 바는 이 다이얼로그가 이미 들었다. */}
            {frame === undefined ? (
              <p className="hud-log__cut">그 틱의 화면이 없다</p>
            ) : (
              <BattleFrame
                isPanel
                {...(props.theme === undefined
                  ? {}
                  : {
                      plan: (
                        <PlanCanvas scene={frame.scene} theme={props.theme} lookOf={lookOf} />
                      ),
                    })}
                outcome={frame.outcome}
                {...(frame.threat === undefined ? {} : { threat: frame.threat.text })}
                rows={buildSheetRows(trace, recording.cpuBudget)}
                onToggleRule={() => undefined}
                entries={recording.entries.slice(0, frame.logEnd)}
                tick={tick}
                hp={frame.playerHp}
                hpMax={frame.playerHpMax}
                cpuUsed={trace.at(-1)?.cpuUsed ?? 0}
                cpuBudget={recording.cpuBudget}
                potions={frame.potions}
                potionsMax={recording.potionsMax}
                scrolls={frame.scrolls}
                scrollsMax={recording.potionsMax}
                tab={tab}
                onTabChange={setTab}
                bodyRef={sheetRef}
                foot={
                  <div className="hud__rewind-foot">
                    <TickScrubber
                      min={startTick}
                      max={recording.ticks}
                      value={tick}
                      onChange={setTick}
                      label="되감기"
                    />
                  </div>
                }
              />
            )}
          </Panel>
        </div>
      </div>
    </div>
  )
}
