/**
 * RuleRow — 규칙표 한 줄. 여섯 가지 상태를 가진다 (design/README.md, 원본 시트).
 *
 *   01 기본        편집 가능한 평상 상태
 *   02 참·미발동   글리프만 녹청. 배경은 칠하지 않는다 — 더 높은 우선순위가 먼저 발동했다
 *   03 조건 거짓   본문 명도를 한 단 낮춘다
 *   04 이번 틱 발동 배경 --plate-high, 좌측 2px 황동 세로바
 *   05 CPU 초과    좌측 세로바만 --rust. **본문 명도는 그대로 둔다** — 초과 상태에서도
 *                  편집이 계속돼야 하므로 비활성처럼 보이면 안 된다
 *   06 키보드 포커스 outline 2px 황동. 배경은 변하지 않는다
 *   07 꺼짐        모바일에서 줄을 눌러 끈 상태. 명도를 통째로 낮춘다
 *
 * 02 와 04 의 차이가 이 게임의 핵심 정보다. "조건은 참인데 실행되지 않았다" 를 UI 가
 * 구분해 보여주지 못하면 플레이어는 자기 규칙표의 우선순위를 영영 못 읽는다(P1).
 */
import { GlyphState } from './GlyphState'
import type { GlyphStateKind } from './GlyphState'
import { ValueExpr } from './ValueExpr'

/** 규칙 번호를 0 으로 채울 자릿수. */
const INDEX_PAD_WIDTH = 2

/** 규칙 한 줄의 조건 판정. armed 는 별도 prop 이다. */
export type RuleRowState = 'true' | 'false' | 'pending'

/**
 * 누적 CPU 와 예산. 예산 초과는 오류가 아니라 수치이므로 둘을 함께 싣는다
 * (design/README.md §3 — `cpu 10 / 8`).
 */
export interface CpuReadout {
  /** 이 줄까지의 누적 CPU. */
  readonly used: number
  /** 규칙표 전체 예산. */
  readonly budget: number
}

/** `cpu` prop 이 받는 값. 숫자만 주면 이 줄의 비용만 적고 초과 판정은 하지 않는다. */
export type RuleCpu = number | CpuReadout

/**
 * CPU 표시가 예산을 넘었는지 본다.
 *
 * @param cpu 숫자이거나 누적/예산 쌍. 없으면 거짓.
 * @returns 초과면 참.
 */
export function checkCpuOver(cpu?: RuleCpu): boolean {
  if (cpu === undefined || typeof cpu === 'number') {
    return false
  }
  return cpu.used > cpu.budget
}

/**
 * CPU 표시 문구를 만든다.
 *
 * @param cpu 숫자이거나 누적/예산 쌍.
 * @returns `cpu 2` 또는 `cpu 10 / 8`. 값이 없으면 undefined.
 */
export function formatCpu(cpu?: RuleCpu): string | undefined {
  if (cpu === undefined) {
    return undefined
  }
  if (typeof cpu === 'number') {
    return `cpu ${String(cpu)}`
  }
  return `cpu ${String(cpu.used)} / ${String(cpu.budget)}`
}

/** RuleRow 가 받는 props. */
export interface RuleRowProps {
  /** 우선순위. 1 부터 센다. */
  readonly index: number
  readonly state: RuleRowState
  /** 실측값이 병기된 조건문. `적거리(2) <= 사거리(3)`. */
  readonly condition: string
  /** 조건이 참일 때 할 행동. */
  readonly action: string
  readonly cpu?: RuleCpu
  /** 이번 틱에 실제로 발동했는가. state='true' 인데 armed 가 거짓이면 02 상태다. */
  readonly armed?: boolean
  /**
   * 이 규칙이 켜져 있는가. 생략하면 켜진 것이다.
   *
   * 모바일 원본(`모바일 시뮬레이션.dc.html`)이 정한 상태다 — 세로 화면에서는 규칙 줄을
   * 눌러 끄고 켜며 가설을 시험한다. 끈 줄은 판에 실리지 않으므로 조건도 평가되지 않고,
   * 그래서 `state` 로는 표현할 수 없다("조건 거짓"과 "평가되지 않았다"는 다르다).
   */
  readonly enabled?: boolean
  readonly onClick?: () => void
}

/**
 * 조건 판정과 발동 여부를 글리프 상태 하나로 접는다.
 *
 * @param state 조건 판정.
 * @param armed 이번 틱 발동 여부.
 * @returns GlyphState 에 넘길 상태.
 */
export function resolveGlyphKind(state: RuleRowState, armed: boolean): GlyphStateKind {
  if (state === 'true' && armed) {
    return 'armed'
  }
  return state
}

/**
 * 규칙표 한 줄을 그린다.
 *
 * @param props 우선순위·판정·조건문·행동·CPU·발동 여부·켜짐 여부·클릭 핸들러.
 * @returns 렌더 트리.
 */
export function RuleRow(props: RuleRowProps): React.JSX.Element {
  const armed = props.armed === true
  const isOff = props.enabled === false
  const isOver = checkCpuOver(props.cpu)
  const cpuText = formatCpu(props.cpu)
  const classNames = [
    'ds-rule-row',
    `ds-rule-row--${props.state}`,
    armed ? 'ds-rule-row--armed' : '',
    isOver ? 'ds-rule-row--over' : '',
    isOff ? 'ds-rule-row--off' : '',
  ].filter((name) => name !== '')

  return (
    <li className={classNames.join(' ')}>
      <button
        type="button"
        className="ds-rule-row__hit"
        aria-pressed={props.enabled === undefined ? undefined : props.enabled}
        onClick={props.onClick}
      >
        <span className="ds-rule-row__index">
          {String(props.index).padStart(INDEX_PAD_WIDTH, '0')}
        </span>
        <GlyphState state={resolveGlyphKind(props.state, armed)} size="sm" />
        <span className="ds-rule-row__lines">
          <ValueExpr text={props.condition} size="sm" dim={props.state === 'false'} />
          <span className="ds-rule-row__action">{props.action}</span>
        </span>
        {cpuText === undefined ? (
          <span />
        ) : (
          <span className={`ds-rule-row__cpu${isOver ? ' ds-rule-row__cpu--over' : ''}`}>
            {cpuText}
            {isOver ? <span className="ds-sr"> 예산 초과</span> : null}
          </span>
        )}
      </button>
    </li>
  )
}
