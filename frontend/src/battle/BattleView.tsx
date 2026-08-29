/**
 * 전투 화면 (W13, GDD §2.1·§8).
 *
 * 골격은 디자인이 정한 그대로다 — 상단 56px / 좌 320px 규칙표 / 가운데 가변 도면 /
 * 우 300px 로그 / 하단 48px, 열 사이는 1px 괘선 하나. 규칙 에디터(W11)와 같은 치수라
 * 두 화면을 오갈 때 눈이 자리를 다시 잡지 않는다.
 *
 * **플레이어는 아무것도 조종하지 않는다.** 이 화면의 유일한 입력은 배속이며, 그래서
 * 화면의 일이 "무엇을 누를까" 가 아니라 "무엇이 왜 일어났는가" 로 간다. 세 열이 같은
 * 한 틱의 세 얼굴이다 — 규칙표는 판단, 도면은 결과, 로그는 이력.
 *
 * 황동 예산 셋 (design/README.md):
 *   1) 도면 위 플레이어 말        2) 발동한 규칙 줄의 좌측 세로바
 *   3) 그 줄에서 말로 잇는 지시선
 * 그래서 상단의 버튼들은 primary 를 쓰지 않는다.
 */
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'

import { Button, LogPanel, Panel, RuleRow, RuleTable, StatusBar, TopBar } from '../ds'
import { BLOCK_CATALOG } from '../core/resources'
import { PLAYER_ENTITY_ID } from '../core/services/runBattle'
import {
  SPEED_INSTANT,
  type TickBatch,
  getStepTicks,
  runTickBatch,
} from '../core/services/runSteppedBattle'
import { OUTCOME_ONGOING } from '../core/sim/phases'
import { buildThreatNotice, getForesightTicks } from '../core/sim/telegraph'
import type { RuleSet } from '../core/schemas'
import { readBatchIntervalMs, useBattleClock } from './battleClock'
import { buildBattleSession, checkOngoing, type BattleSetup } from './battleSession'
import { formatActionText, formatPendingCondition } from './ruleTrace'
import { LeaderLine, buildLeaderPath, type LeaderPath } from './leaderLine'
import { PlanCanvas } from './PlanCanvas'
import { buildPlanScene } from './planScene'
import { createTokenReader, readPlanTheme, type PlanTheme } from './planTheme'

/** 로그 열에 남기는 줄 수. 전량을 DOM 에 두면 400틱짜리 판에서 수천 노드가 된다. */
const LOG_TAIL = 200

/** 4px 모듈. 지시선의 어깨 길이를 이 배수로 잡는다. */
const MODULE_TOKEN = '--sp-1'

/** 발동한 규칙 줄을 찾는 선택자. ds 가 그 상태에만 붙이는 클래스다. */
const ARMED_ROW_SELECTOR = '.ds-rule-row--armed'

/**
 * 로그 열의 스크롤 영역. Panel 이 `scroll` 일 때만 붙는 클래스다.
 *
 * 관전 중에는 마지막 줄이 화면의 기본값이어야 한다. 매 틱 손으로 내려야 한다면 로그는
 * 사실상 없는 것과 같다 (P1).
 */
const LOG_SCROLL_SELECTOR = '.ds-panel__body--scroll'

/** 판정 이름에서 화면 문구로. */
const OUTCOME_LABELS: ReadonlyMap<string, string> = new Map([
  ['PLAYER_WIN', '승리'],
  ['PLAYER_LOSS', '패배'],
  ['TIMEOUT', '시간 초과'],
])

/** 처음 열었을 때의 배속. 정지로 두면 화면이 죽은 것처럼 보인다. */
const INITIAL_SPEED = 1

/** 정지 단계. 즉시 실행을 누르면 시계를 세운다 — 이미 끝까지 돌렸기 때문이다. */
const SPEED_PAUSED = 0

/** 셀 한가운데를 가리키는 비율. */
const HALF = 0.5

/** BattleView 가 받는 props. */
export interface BattleViewProps {
  readonly setup: BattleSetup
  readonly rulesets: ReadonlyMap<string, RuleSet>
  /** 상단 바에 적을 위치 표기. */
  readonly location: string
  /** 상단 바 오른쪽에 덧붙일 조작부. 확인용 페이지가 방 선택을 여기에 끼운다. */
  readonly controls?: ReactNode
  /**
   * 판정이 바뀔 때마다 부른다. 마운트 직후 한 번(진행 중)과 판이 끝날 때 한 번 온다.
   *
   * 화면 밖에서 "판이 끝났다" 를 알아야 하는 쪽이 있기 때문이다 — 앱은 이 신호를 받아
   * 사후 분석을 띄운다. 매 틱이 아니라 판정이 바뀔 때만 부르므로, 받는 쪽이 상태를
   * 들어도 관전 중에 다시 그려지지 않는다.
   */
  readonly onOutcome?: (outcome: string) => void
}

/**
 * 전투 화면을 그린다.
 *
 * @param props 전투 설정·규칙표 대응표·위치 표기·덧붙일 조작부.
 * @returns 렌더 트리.
 */
export function BattleView(props: BattleViewProps): React.JSX.Element {
  const session = useMemo(
    () => buildBattleSession(props.setup, props.rulesets),
    [props.setup, props.rulesets],
  )
  const [speed, setSpeed] = useState(INITIAL_SPEED)
  const [outcome, setOutcome] = useState(OUTCOME_ONGOING)
  const [frame, setFrame] = useState(0)
  const [theme, setTheme] = useState<PlanTheme | undefined>(undefined)
  const [module, setModule] = useState(0)
  const [intervalMs, setIntervalMs] = useState(0)
  const [leader, setLeader] = useState<LeaderPath | undefined>(undefined)
  const containerRef = useRef<HTMLDivElement>(null)
  const planRef = useRef<HTMLDivElement>(null)
  const logRef = useRef<HTMLDivElement>(null)
  const rulesRef = useRef<HTMLDivElement>(null)

  // 판이 바뀌면 시계와 판정을 처음으로 되돌린다. 되돌리지 않으면 새 판이 끝난 판정을
  // 물려받아 첫 틱도 돌지 않는다.
  useEffect(() => {
    setOutcome(OUTCOME_ONGOING)
    setSpeed(INITIAL_SPEED)
    setFrame(0)
  }, [session])

  // 토큰은 :root 에 있다. 렌더 중에 읽으면 서버 렌더에서 document 가 없어 터진다.
  useEffect(() => {
    const read = createTokenReader(document.documentElement)
    setTheme(readPlanTheme(read))
    setModule(Number.parseFloat(read(MODULE_TOKEN)))
    setIntervalMs(readBatchIntervalMs(read))
  }, [])

  // 판정이 바뀔 때만 알린다. `handleBatch` 안에서 부르면 배치마다(즉 매 틱) 밖이 흔들린다.
  const { onOutcome } = props
  useEffect(() => {
    onOutcome?.(outcome)
  }, [outcome, onOutcome])

  const handleBatch = useCallback((batch: TickBatch) => {
    setOutcome(batch.outcome)
    setFrame((value) => value + 1)
  }, [])

  useBattleClock({
    engine: session.engine,
    step: speed,
    intervalMs,
    isFinished: !checkOngoing(outcome) || intervalMs <= 0,
    onBatch: handleBatch,
  })

  const runInstant = useCallback(() => {
    setSpeed(SPEED_PAUSED)
    if (!checkOngoing(outcome)) {
      return
    }
    handleBatch(runTickBatch(session.engine, getStepTicks(SPEED_INSTANT)))
  }, [session, handleBatch, outcome])

  const scene = useMemo(() => buildPlanScene(session.engine), [session, frame])
  const player = session.engine.state.entities.get(PLAYER_ENTITY_ID)
  const trace = session.tracer.trace

  // 지시선은 실제로 그려진 두 요소의 자리를 재서 잇는다. 규칙 줄의 높이는 조건문의 길이에
  // 따라 달라지므로 계산으로 맞출 수 없다.
  useLayoutEffect(() => {
    const container = containerRef.current
    const plan = planRef.current
    const rules = rulesRef.current
    if (container === null || plan === null || rules === null || theme === undefined) {
      setLeader(undefined)
      return
    }
    const row = rules.querySelector(ARMED_ROW_SELECTOR)
    const self = scene.actors.find((actor) => actor.isSelf)
    if (row === null || self === undefined) {
      setLeader(undefined)
      return
    }
    const base = container.getBoundingClientRect()
    const rowRect = row.getBoundingClientRect()
    const planRect = plan.getBoundingClientRect()
    // 규칙표가 길어 그 줄이 스크롤 밖으로 나가면 선을 긋지 않는다. 보이지 않는 줄에서
    // 나오는 선은 어느 규칙이 발동했는지 알려 주는 대신 엉뚱한 줄을 가리킨다.
    const rulesRect = rules.getBoundingClientRect()
    const anchorY = rowRect.top + rowRect.height * HALF
    if (anchorY < rulesRect.top || anchorY > rulesRect.bottom) {
      setLeader(undefined)
      return
    }
    setLeader(
      buildLeaderPath({
        from: {
          x: rowRect.right - base.left,
          y: anchorY - base.top,
        },
        to: {
          x: planRect.left - base.left + (self.x + HALF) * theme.cell,
          y: planRect.top - base.top + (self.y + HALF) * theme.cell,
        },
        cell: theme.cell,
        module,
      }),
    )
  }, [scene, trace, theme, module])

  // 로그는 늘 마지막 줄을 보고 있어야 한다.
  useEffect(() => {
    const body = logRef.current?.querySelector(LOG_SCROLL_SELECTOR)
    if (body !== null && body !== undefined) {
      body.scrollTop = body.scrollHeight
    }
  }, [scene])

  const armedRow = trace?.rows.find((row) => row.armed)
  const cpuBudget = player?.cpuBudget ?? 0
  const cpuUsed = session.ruleset.rules.reduce((sum, rule) => sum + rule.cpuCost, 0)
  const foresight = player === undefined ? 0 : getForesightTicks(player)
  const threat =
    player === undefined
      ? undefined
      : buildThreatNotice(session.engine.telegraphs, player.position, foresight)
  const outcomeLabel = OUTCOME_LABELS.get(outcome)

  return (
    <div className="battle" ref={containerRef}>
      <div className="battle__top">
        <TopBar
          location={props.location}
          tick={scene.tick}
          speed={speed}
          onSpeedChange={setSpeed}
        />
        <Button size="sm" variant="secondary" glyph="≫" onClick={runInstant}>
          즉시
        </Button>
        {props.controls}
      </div>

      <div className="battle__body">
        <div className="battle__col" ref={rulesRef}>
          <Panel
            title="규칙표"
            meta={`cpu ${String(cpuUsed)} / ${String(cpuBudget)}`}
            tone="panel"
            scroll
          >
            <RuleTable>
              {session.ruleset.rules.map((rule) => {
                const row = trace?.rows.find((one) => one.priority === rule.priority)
                return (
                  <RuleRow
                    key={rule.priority}
                    index={rule.priority}
                    state={row?.state ?? 'pending'}
                    condition={row?.condition ?? formatPendingCondition(rule, BLOCK_CATALOG)}
                    action={row?.action ?? formatActionText(rule, BLOCK_CATALOG)}
                    cpu={{ used: row?.cpuUsed ?? rule.cpuCost, budget: cpuBudget }}
                    armed={row?.armed ?? false}
                  />
                )
              })}
            </RuleTable>
          </Panel>
        </div>

        <div className="battle__rule-line" />

        <div className="battle__col battle__col--plan">
          <div className="battle__frame" ref={planRef}>
            {theme === undefined ? null : <PlanCanvas scene={scene} theme={theme} />}
          </div>
          <div className="battle__plan-foot">
            <span className="ds-label">{session.template.templateId}</span>
            {outcomeLabel === undefined ? null : (
              <span className="battle__outcome">{outcomeLabel}</span>
            )}
          </div>
        </div>

        <div className="battle__rule-line" />

        <div className="battle__col" ref={logRef}>
          <Panel title="이벤트 로그" meta={`${String(session.engine.log.count())}줄`} scroll>
            <LogPanel entries={session.engine.log.entries.slice(-LOG_TAIL)} />
          </Panel>
        </div>
      </div>

      <StatusBar
        hp={player?.hp ?? 0}
        hpMax={player?.hpMax ?? 1}
        potions={player?.potions ?? 0}
        potionsMax={session.balance.player.potions}
        {...(threat === undefined ? {} : { threat: `${threat.glyph} ${threat.text}` })}
      />

      <LeaderLine
        path={leader}
        label={
          armedRow === undefined
            ? '발동한 규칙 없음'
            : `규칙 ${String(armedRow.priority)} 이 플레이어를 움직였다`
        }
      />
    </div>
  )
}
