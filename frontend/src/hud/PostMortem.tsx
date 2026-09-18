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
import { readRoomTitle } from '../core/schemas/room'
import type { PlanTheme } from '../battle'
import { Button, Panel } from '../ds'

import { buildDamageHeatmap, buildRuleStats } from './analysis'
import { formatOutcome, formatTickLabel } from './analysisText'
import type { BattleRecording, RecordedFrame } from './battleRecorder'
import { DamageHeatmap } from './DamageHeatmap'
import { DEATH_REPLAY_TICKS, useLogAnchor } from './logWindow'
import { buildVitalRows } from '../battle'
import { buildReplayTrace, buildSheetRows, findDecision } from './replayTrace'
import { RuleStatsTable } from './RuleStatsTable'
import { AdSlot } from '../battle/AdSlot'
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

  // **최대치를 함께 적는다.** `체력 0` 만으로는 그 판이 어디서 끝났는지 읽히지 않는다.
  // 기록에는 판 전체의 최대치 칸이 없고 프레임마다 들고 있으므로, 마지막 프레임에서
  // 읽는다 — 머리에 적는 현재 값(`recording.playerHp`)과 같은 시점이다.
  const playerHpMax = recording.frames.at(-1)?.playerHpMax ?? recording.playerHp

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
          {readRoomTitle(recording.template)} · {formatTickLabel(recording.ticks)} · 체력{' '}
          {recording.playerHp} / {playerHpMax}
        </span>
        <Button size="sm" variant="secondary" glyph="✕" onClick={props.onClose}>
          닫기
        </Button>
      </header>

      {/* **여기는 상단이 된다** (2026-09-17 확인 요청). 전투 화면에서 상단을 못 쓴 이유는
          도면까지 52px 밖에 없어 구글의 「게임 가장자리에서 150px」에 걸리기 때문인데,
          **사후 분석은 게임 창이 아니라 읽는 화면이다.** 판은 이미 끝났고 여기 있는 것은
          성적표·히트맵·되감기다 — 그 규칙이 재는 대상 자체가 아니다.

          바닥에서 올렸다. 아래에 두면 세 열을 다 지나야 닿는데, 스크롤해야 보이는 배너는
          없는 것과 같다. 판이 끝나고 잠깐 멈추는 자리라 위가 제자리다.

          **광고 탭에서는 물러난다** — 전투 화면과 같은 이유다. 탭이 이미 광고 면이라
          겹쳐 세우면 같은 배너가 한 화면에 두 번 보인다.

          전투 진입 화면은 안 골랐다. 티켓을 기다리는 1.3초뿐이라 광고 자리로는 약하고,
          그 1.3초를 위해 화면을 하나 더 만들어 유지해야 한다. */}
      <div className="hud-post__ad">{tab === 'ads' ? null : <AdSlot inline />}</div>

      <div className="hud-post__body">
        <div className="hud-post__col">
          <Panel title="규칙별 발동" meta={recording.ruleset.rulesetId} padded={false} scroll>
            <RuleStatsTable stats={stats} />
          </Panel>
          <Panel title="피해 히트맵" meta="플레이어 피격">
            <DamageHeatmap grid={heatmap} caption="플레이어가 받은 피해" />
          </Panel>
        </div>

        <div className="hud-post__col">
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
                vitals={buildVitalRows({
                  hp: frame.playerHp,
                  hpMax: frame.playerHpMax,
                  potions: frame.potions,
                  potionsMax: recording.potionsMax,
                  scrolls: frame.scrolls,
                  scrollsMax: recording.potionsMax,
                  cpuUsed: trace.at(-1)?.cpuUsed ?? 0,
                  cpuBudget: recording.cpuBudget,
                })}
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
                      label="틱"
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
