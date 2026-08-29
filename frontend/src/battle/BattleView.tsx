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
 *
 * **모바일 세로는 이 골격의 축소가 아니라 재배치다** (design/README.md 「반응형」).
 * 도면이 위에 고정되고 규칙표와 로그가 아래 시트 하나를 탭으로 나눠 쓴다. 그래서 폭을
 * 가르는 수단이 CSS 가 아니라 스크립트다 — 컨테이너 쿼리로는 로그 열을 DOM 에서 **빼는**
 * 일도, 탭 줄을 새로 만드는 일도 못 하고, 화면 CSS 에는 미디어쿼리를 적지 않기로 했다
 * (그 경계는 토큰 한 곳에만 둔다). `useViewportMode()` 가 `--layout-mode` 를 읽으므로
 * 경계는 여전히 토큰 하나다.
 *
 * **가르는 자리는 이 컴포넌트 안이다.** 배치별로 다른 화면 컴포넌트를 App 이 고르게 하면
 * 기기를 돌릴 때 컴포넌트가 갈아 끼워지면서 엔진이 새로 조립되고, 보고 있던 판이 처음으로
 * 돌아간다. 세션·시계·판정은 여기 한 곳에 두고 그리는 트리만 가른다.
 *
 * **가로 모바일은 세 번째 배치다** (명세 B). 세로가 여섯 줄로 쌓는 것을 가로는 2열로
 * 세운다 — 도면(가변) + 우측 340px 시트. 세 배치가 같은 값 묶음을 받으므로, 기기를
 * 돌리면 트리만 바뀌고 판은 그대로 이어진다.
 */
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'

import {
  Button,
  LogPanel,
  Panel,
  RuleRow,
  RuleTable,
  StatusBar,
  TopBar,
  useViewportMode,
  watchViewport,
} from '../ds'
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
import { BattleLandscape } from './BattleLandscape'
import { BattlePortrait } from './BattlePortrait'
import { buildBattleSession, checkOngoing, type BattleSetup } from './battleSession'
import { buildRunRulesets, toggleRulePriority, type SheetTab } from './portraitSheet'
import { buildRuleRows } from './ruleRows'
import { LeaderLine, buildLeaderPath, type LeaderPath } from './leaderLine'
import { formatOutcome } from './outcomeText'
import { PlanCanvas } from './PlanCanvas'
import { buildPlanScene } from './planScene'
import {
  checkPlanThemeSame,
  createTokenReader,
  readPlanTheme,
  type PlanTheme,
} from './planTheme'

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

/** 처음 열었을 때의 배속. 정지로 두면 화면이 죽은 것처럼 보인다. */
const INITIAL_SPEED = 1

/** 정지 단계. 즉시 실행을 누르면 시계를 세운다 — 이미 끝까지 돌렸기 때문이다. */
const SPEED_PAUSED = 0

/** 셀 한가운데를 가리키는 비율. */
const HALF = 0.5

/** `한 틱` 버튼이 돌리는 틱 수. */
const ONE_TICK = 1

/** 세로 시트가 처음 여는 탭. 규칙표가 이 화면의 주어다. */
const INITIAL_TAB: SheetTab = 'rules'

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
  const mode = useViewportMode()
  const [speed, setSpeed] = useState(INITIAL_SPEED)
  const [outcome, setOutcome] = useState(OUTCOME_ONGOING)
  const [tab, setTab] = useState<SheetTab>(INITIAL_TAB)
  const [disabled, setDisabled] = useState<readonly number[]>([])
  const [runKey, setRunKey] = useState(0)
  const [frame, setFrame] = useState(0)
  const [theme, setTheme] = useState<PlanTheme | undefined>(undefined)
  const [module, setModule] = useState(0)
  const [intervalMs, setIntervalMs] = useState(0)
  const [leader, setLeader] = useState<LeaderPath | undefined>(undefined)
  const containerRef = useRef<HTMLDivElement>(null)
  const planRef = useRef<HTMLDivElement>(null)
  const logRef = useRef<HTMLDivElement>(null)
  const rulesRef = useRef<HTMLDivElement>(null)
  const sheetRef = useRef<HTMLDivElement>(null)

  // 꺼진 규칙을 뺀 대응표로 판을 조립한다. 아무것도 끄지 않았으면 받은 대응표가 그대로
  // 나오므로 참조가 흔들리지 않고, 데스크톱은 전과 같은 판을 얻는다.
  const runRulesets = useMemo(
    () => buildRunRulesets(props.rulesets, props.setup.rulesetId, disabled),
    [props.rulesets, props.setup.rulesetId, disabled],
  )
  // `runKey` 는 「처음부터」다. 규칙을 켜고 끄면 대응표가 바뀌어 저절로 재조립되지만,
  // 같은 규칙표로 다시 돌리는 데에는 바뀌는 값이 없다.
  const session = useMemo(
    () => buildBattleSession(props.setup, runRulesets),
    [props.setup, runRulesets, runKey],
  )

  // 판이 바뀌면 시계와 판정을 처음으로 되돌린다. 되돌리지 않으면 새 판이 끝난 판정을
  // 물려받아 첫 틱도 돌지 않는다.
  useEffect(() => {
    setOutcome(OUTCOME_ONGOING)
    setSpeed(INITIAL_SPEED)
    setFrame(0)
  }, [session])

  // 토큰은 :root 에 있다. 렌더 중에 읽으면 서버 렌더에서 document 가 없어 터진다.
  // 창이 바뀌면 다시 읽는다 — `--plan-cell` 이 브레이크포인트마다 달라졌으므로 한 번만
  // 읽으면 기기를 돌렸을 때 캔버스가 옛 셀 크기의 백버퍼로 남아 도면이 흐려진다.
  useEffect(() => {
    const update = (): void => {
      const read = createTokenReader(document.documentElement)
      const next = readPlanTheme(read)
      // 값이 같으면 상태를 그대로 둔다. 새 객체를 넣으면 창을 1px 끌 때마다 도면을
      // 다시 그린다.
      setTheme((prev) => (checkPlanThemeSame(prev, next) ? prev : next))
      setModule(Number.parseFloat(read(MODULE_TOKEN)))
      setIntervalMs(readBatchIntervalMs(read))
    }
    update()
    return watchViewport(update)
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
    // 세로 배치에는 지시선이 없다. 규칙 줄과 도면이 위아래로 떨어져 있어 선을 그으면
    // 시트를 가로지르고, 황동 예산 셋도 그쪽에서는 다른 자리가 가져간다.
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

  // 세로 시트도 같다. 로그 탭일 때만 내린다 — 규칙표 탭에서 내리면 방금 누른 줄이
  // 화면 밖으로 밀려난다.
  useEffect(() => {
    const body = sheetRef.current
    if (body !== null && tab === 'log') {
      body.scrollTop = body.scrollHeight
    }
  }, [scene, tab])

  // 한 틱만 민다. 배속을 세우는 이유는 이 버튼을 누른 사람이 틱 하나를 들여다보려는
  // 것이기 때문이다 — 누르자마자 시계가 다음 틱을 덮어쓰면 아무것도 못 본다.
  const runStep = useCallback(() => {
    setSpeed(SPEED_PAUSED)
    if (!checkOngoing(outcome)) {
      return
    }
    handleBatch(runTickBatch(session.engine, ONE_TICK))
  }, [session, handleBatch, outcome])

  // 같은 방·같은 시드·지금 켜져 있는 규칙표로 판을 다시 조립한다 (R5 — 같은 입력은
  // 같은 판을 낸다).
  const runRestart = useCallback(() => {
    setRunKey((value) => value + 1)
  }, [])

  // 규칙 줄을 눌러 켜고 끈다. 끈 줄은 판에 실리지 않으므로 판이 새로 조립되고 처음부터
  // 다시 돈다 — 도는 판의 규칙표를 중간에 갈아 끼우면 시드가 결과를 특정하지 못한다.
  const toggleRule = useCallback((priority: number) => {
    setDisabled((current) => toggleRulePriority(current, priority))
  }, [])

  const armedRow = trace?.rows.find((row) => row.armed)
  const cpuBudget = player?.cpuBudget ?? 0
  // 누적 CPU 는 **판에 실린** 규칙만 센다. 끈 줄은 비용을 쓰지 않는다.
  const cpuUsed = session.ruleset.rules.reduce((sum, rule) => sum + rule.cpuCost, 0)
  // 화면이 그리는 것은 규칙표 **전량**이다. 끈 줄까지 보여야 다시 켤 수 있다.
  const allRules = props.rulesets.get(props.setup.rulesetId)?.rules ?? session.ruleset.rules
  const rows = buildRuleRows({
    rules: allRules,
    trace,
    catalog: BLOCK_CATALOG,
    cpuBudget,
    disabled,
  })
  const foresight = player === undefined ? 0 : getForesightTicks(player)
  const threat =
    player === undefined
      ? undefined
      : buildThreatNotice(session.engine.telegraphs, player.position, foresight)
  // 진행 중에는 판정을 적지 않는다. 라벨표는 `outcomeText` 한 곳이며 사후 분석과 같은
  // 말을 쓴다 — 사후 분석이 이 화면을 덮으므로 두 말이 한 화면에 보이면 안 된다.
  const outcomeLabel = checkOngoing(outcome) ? undefined : formatOutcome(outcome)
  const threatText = threat === undefined ? undefined : `${threat.glyph} ${threat.text}`
  const plan = theme === undefined ? null : <PlanCanvas scene={scene} theme={theme} />

  // 세로 모바일은 같은 값들을 다른 배열로 그린다. 세션·시계·판정은 위에서 이미 다 나왔고
  // 여기서 갈리는 것은 트리뿐이라, 기기를 돌려도 보고 있던 판이 그대로 이어진다.
  if (mode === 'portrait') {
    return (
      <BattlePortrait
        location={props.location}
        controls={props.controls}
        tick={scene.tick}
        speed={speed}
        onSpeedChange={setSpeed}
        onInstant={runInstant}
        onStep={runStep}
        onRestart={runRestart}
        outcome={outcome}
        threat={threatText}
        plan={plan}
        rows={rows}
        onToggleRule={toggleRule}
        cpuUsed={cpuUsed}
        cpuBudget={cpuBudget}
        entries={session.engine.log.entries.slice(-LOG_TAIL)}
        hp={player?.hp ?? 0}
        hpMax={player?.hpMax ?? 1}
        potions={player?.potions ?? 0}
        potionsMax={session.balance.player.potions}
        tab={tab}
        onTabChange={setTab}
        bodyRef={sheetRef}
      />
    )
  }

  // 가로 모바일은 2열이다 — 도면과 시트. 세로와 같은 값 묶음을 받고 배열만 다르다.
  // 앱의 조작부(사후 분석·규칙 고치기)는 상단 바 안으로 들어간다. 세로와 달리 자리가
  // 있고, 없으면 가로에서는 에디터로 돌아갈 길이 사라진다.
  if (mode === 'landscape') {
    return (
      <BattleLandscape
        location={props.location}
        tick={scene.tick}
        speed={speed}
        onSpeedChange={setSpeed}
        onInstant={runInstant}
        onStep={runStep}
        onRestart={runRestart}
        controls={props.controls}
        outcome={outcome}
        threat={threatText}
        plan={plan}
        rows={rows}
        onToggleRule={toggleRule}
        cpuUsed={cpuUsed}
        cpuBudget={cpuBudget}
        entries={session.engine.log.entries.slice(-LOG_TAIL)}
        hp={player?.hp ?? 0}
        hpMax={player?.hpMax ?? 1}
        potions={player?.potions ?? 0}
        potionsMax={session.balance.player.potions}
        tab={tab}
        onTabChange={setTab}
        bodyRef={sheetRef}
      />
    )
  }

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
              {rows.map((row) => (
                <RuleRow
                  key={row.priority}
                  index={row.priority}
                  state={row.state}
                  condition={row.condition}
                  action={row.action}
                  cpu={row.cpu}
                  armed={row.armed}
                />
              ))}
            </RuleTable>
          </Panel>
        </div>

        <div className="battle__rule-line" />

        <div className="battle__col battle__col--plan">
          <div className="battle__frame" ref={planRef}>
            {plan}
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
        {...(threatText === undefined ? {} : { threat: threatText })}
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
