/**
 * HudScreen — 기록된 판을 되감아 보는 관전·진단 화면 (GDD §8).
 *
 * `battle/BattleView` 와 무엇이 다른가. 그쪽은 엔진을 **앞으로** 밀며 지금을 보여 주고,
 * 이쪽은 이미 끝난 판의 프레임 배열 위를 **앞뒤로** 걷는다. 죽은 뒤에 "무엇이 나를
 * 죽였는가" 를 묻는 자리라서, 되감기와 사후 분석이 이 화면에만 있다. 판 조립·도면
 * 렌더러·규칙표 서식은 그쪽 것을 그대로 쓴다 — 화면이 둘이어도 판은 하나여야 한다.
 *
 * 골격은 디자인이 정한 그대로다: 상단 56 / 좌 320 규칙표 / 가운데 도면 / 우 300 로그 /
 * 하단 48, 열 사이는 1px 괘선 하나.
 *
 * 로그는 **현재 프레임까지만** 보여 준다. 앞선 틱의 줄이 보이면 관전자가 미래를 보고
 * 판단하게 되어 "지금 이 규칙이 왜 이렇게 결정했는가" 를 되짚는 훈련이 되지 않는다.
 *
 * 황동 예산 셋: armed 규칙 한 줄 · 도면의 플레이어 말 · 현재 틱의 발동 로그 세로바.
 * 그래서 이 화면의 버튼은 전부 ghost·secondary 다.
 */
import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { PlanCanvas } from '../battle'
import { BLOCK_CATALOG } from '../core/resources'
import { OUTCOME_PLAYER_LOSS } from '../core/sim/phases'
import { Button, Panel, RuleRow, RuleTable, StatusBar, ThreatNotice, TopBar } from '../ds'

import { formatOutcome, formatTickLabel } from './analysisText'
import type { BattleRecording } from './battleRecorder'
import { LogStream } from './LogStream'
import { findTickIndex } from './logWindow'
import { PostMortem } from './PostMortem'
import { buildReplayTrace, findDecision } from './replayTrace'
import { TickScrubber } from './TickScrubber'
import { usePlanTheme } from './usePlanTheme'

/** 처음 열었을 때의 배속. 정지로 두면 화면이 죽은 것처럼 보인다. */
const INITIAL_SPEED = 1

/** 사후 분석 패널의 표시 상태. auto 는 "사망하면 저절로 뜬다" 다. */
type PostState = 'auto' | 'open' | 'closed'

/** HudScreen 이 받는 props. */
export interface HudScreenProps {
  readonly recording: BattleRecording
  /** 상단 바의 층·실 표기. */
  readonly location: string
  /** 상단 바 오른쪽에 덧붙일 조작부. 확인용 페이지가 조합 선택을 여기에 끼운다. */
  readonly controls?: ReactNode
}

/**
 * 관전 화면을 그린다.
 *
 * @param props 기록·위치 표기·덧붙일 조작부.
 * @returns 렌더 트리.
 * @throws 프레임이 하나도 없는 기록인 경우. 조립이 잘못된 것이다.
 */
export function HudScreen(props: HudScreenProps): React.JSX.Element {
  const { recording } = props
  const lastIndex = recording.frames.length - 1
  const [frameIndex, setFrameIndex] = useState(0)
  const [speed, setSpeed] = useState(INITIAL_SPEED)
  const [follow, setFollow] = useState(true)
  const [postState, setPostState] = useState<PostState>('auto')
  const { theme, intervalMs } = usePlanTheme()

  // 배속만큼 프레임을 건너뛴다. 끝에 닿으면 첨자가 더 늘지 않으므로 저절로 멈춘다.
  useEffect(() => {
    if (speed <= 0 || intervalMs <= 0) {
      return undefined
    }
    const timer = setInterval(() => {
      setFrameIndex((index) => Math.min(lastIndex, index + speed))
    }, intervalMs)
    return () => {
      clearInterval(timer)
    }
  }, [speed, intervalMs, lastIndex])

  // 훅은 전부 이 지점 위에서 부른다. 프레임이 없는 기록은 아래에서 막지만, 그 검사가
  // 훅보다 앞에 오면 렌더마다 훅 수가 달라진다.
  const current = recording.frames[Math.min(frameIndex, lastIndex)]
  const logEnd = current?.logEnd ?? 0
  const visible = useMemo(() => recording.entries.slice(0, logEnd), [recording.entries, logEnd])

  if (current === undefined) {
    throw new Error('프레임이 없는 기록이다')
  }
  const frame = current

  const decision = findDecision(recording.entries, frame.tick, recording.playerId)
  const trace = buildReplayTrace(recording.ruleset, BLOCK_CATALOG, decision)
  const cpuTotal = trace.at(-1)?.cpuUsed ?? 0
  const anchorIndex = findTickIndex(visible, frame.tick)

  const atEnd = frameIndex >= lastIndex
  const isDefeat = recording.outcome === OUTCOME_PLAYER_LOSS
  const showPost = postState === 'open' || (postState === 'auto' && atEnd && isDefeat)

  /**
   * 되감기·앞감기. 손으로 옮기는 동안에는 재생과 추적을 멈춘다.
   *
   * @param next 옮겨 갈 프레임 첨자.
   */
  const moveTo = (next: number): void => {
    setFrameIndex(next)
    setSpeed(0)
    setFollow(false)
  }

  return (
    <div className="hud">
      <div className="hud__top">
        <TopBar
          location={props.location}
          tick={frame.tick}
          speed={speed}
          onSpeedChange={(value) => {
            setSpeed(value)
            if (value > 0) {
              setFollow(true)
            }
          }}
        />
        {props.controls}
      </div>

      <div className="hud__cols">
        <div className="hud__col">
          <Panel
            title="규칙표"
            meta={`cpu ${String(cpuTotal)} / ${String(recording.cpuBudget)}`}
            padded={false}
            scroll
          >
            <RuleTable>
              {trace.map((row) => (
                <RuleRow
                  key={row.priority}
                  index={row.priority}
                  state={row.state}
                  armed={row.armed}
                  condition={row.condition}
                  action={row.action}
                  cpu={{ used: row.cpuUsed, budget: recording.cpuBudget }}
                />
              ))}
            </RuleTable>
            {decision === undefined ? (
              <p className="hud-log__cut">이 틱에는 플레이어의 결정이 없다</p>
            ) : null}
          </Panel>
        </div>

        <div className="hud__gap" />

        <div className="hud__plan">
          <div className="hud__plan-head">
            {frame.threat === undefined ? (
              <span className="ds-label">예고 없음</span>
            ) : (
              <ThreatNotice
                text={frame.threat.text}
                ticks={frame.threat.ticks}
                glyph={frame.threat.glyph}
                tone={frame.threat.tone === 'danger' ? 'danger' : 'neutral'}
              />
            )}
          </div>
          {theme === undefined ? null : <PlanCanvas scene={frame.scene} theme={theme} />}
          <div className="hud__plan-foot">
            <TickScrubber
              min={0}
              max={lastIndex}
              value={Math.min(frameIndex, lastIndex)}
              onChange={moveTo}
              label="틱"
            />
            <Button
              size="sm"
              variant="secondary"
              glyph="◱"
              onClick={() => {
                setPostState('open')
              }}
            >
              사후 분석
            </Button>
          </div>
        </div>

        <div className="hud__gap" />

        <div className="hud__col">
          <Panel
            title="실행 로그"
            meta={`${formatTickLabel(frame.tick)} · ${formatOutcome(frame.outcome)}`}
            padded={false}
          >
            <LogStream
              entries={visible}
              follow={follow}
              onFollowChange={setFollow}
              currentTick={frame.tick}
              {...(anchorIndex === undefined ? {} : { anchorIndex })}
            />
          </Panel>
        </div>
      </div>

      <StatusBar
        hp={frame.playerHp}
        hpMax={frame.playerHpMax}
        potions={frame.potions}
        potionsMax={recording.potionsMax}
        {...(frame.threat === undefined ? {} : { threat: frame.threat.text })}
      />

      {showPost ? (
        <PostMortem
          recording={recording}
          theme={theme}
          onClose={() => {
            setPostState('closed')
          }}
        />
      ) : null}
    </div>
  )
}
