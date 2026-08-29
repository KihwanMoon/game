/**
 * 지시선 — 이번 틱에 발동한 규칙 줄에서 도면 위 그 캐릭터까지 1px 황동 선을 긋는다
 * (규칙 행 상태 시트 04번).
 *
 * 규칙표와 도면은 열이 다르다. 그래서 "이 줄이 저 말을 움직였다" 를 잇는 것은 색이나
 * 깜빡임이 아니라 **선**이어야 한다 — 도면의 인출선(leader line)과 같은 역할이고, 그것이
 * 이 화면에서 황동을 쓰는 세 자리 중 하나다.
 *
 * 캔버스가 아니라 SVG 로 그리는 이유는 선이 캔버스 밖에서 시작하기 때문이다. 오버레이는
 * 클릭을 먹지 않는다(`pointer-events: none`).
 */

/** 화면 위의 한 점. 단위는 CSS px 이며 기준은 전투 화면의 왼쪽 위 모서리다. */
export interface LeaderPoint {
  readonly x: number
  readonly y: number
}

/** 지시선 하나의 기하. */
export interface LeaderPath {
  /** 규칙 줄에서 나오는 지점. */
  readonly start: LeaderPoint
  /** 짧은 수평 어깨. 도면 인출선의 관습이다. */
  readonly shoulder: LeaderPoint
  /** 말을 감싼 고리에 닿는 지점. */
  readonly end: LeaderPoint
  /** 말을 감싼 고리의 중심과 반지름. */
  readonly center: LeaderPoint
  readonly radius: number
}

/** 말을 감싸는 고리의 반지름. 셀 한 변에 대한 비율이다. */
export const RING_RATIO = 0.36

/** 어깨 길이를 4px 모듈의 몇 배로 둘지. */
export const SHOULDER_MODULES = 4

/** `buildLeaderPath` 가 받는 값들. 전부 전투 화면 기준 좌표다. */
export interface LeaderPathInput {
  /** 규칙 줄의 오른쪽 끝. */
  readonly from: LeaderPoint
  /** 말이 선 셀의 중심. */
  readonly to: LeaderPoint
  /** 셀 한 변의 길이. */
  readonly cell: number
  /** 4px 모듈 한 칸. */
  readonly module: number
}

/**
 * 지시선의 기하를 만든다.
 *
 * 선은 고리 **바깥**에서 멈춘다. 중심까지 그으면 글리프를 가로질러 말이 읽히지 않는다.
 *
 * @param input 시작점·도착점·셀 크기·모듈.
 * @returns 지시선 기하. 시작점이 이미 고리 안이면 undefined.
 */
export function buildLeaderPath(input: LeaderPathInput): LeaderPath | undefined {
  const radius = input.cell * RING_RATIO
  const shoulder: LeaderPoint = {
    x: input.from.x + input.module * SHOULDER_MODULES,
    y: input.from.y,
  }
  const dx = input.to.x - shoulder.x
  const dy = input.to.y - shoulder.y
  const distance = Math.hypot(dx, dy)
  if (distance <= radius) {
    return undefined
  }
  const ratio = (distance - radius) / distance
  return {
    start: input.from,
    shoulder,
    end: { x: shoulder.x + dx * ratio, y: shoulder.y + dy * ratio },
    center: input.to,
    radius,
  }
}

/** LeaderLine 이 받는 props. */
export interface LeaderLineProps {
  /** 그릴 지시선. 없으면 아무것도 그리지 않는다. */
  readonly path: LeaderPath | undefined
  /** 보조 기술이 읽을 설명. */
  readonly label: string
}

/**
 * 지시선을 그린다.
 *
 * @param props 지시선 기하와 설명.
 * @returns 렌더 트리. 그릴 것이 없으면 빈 오버레이.
 */
export function LeaderLine(props: LeaderLineProps): React.JSX.Element | null {
  if (props.path === undefined) {
    return null
  }
  const { start, shoulder, end, center, radius } = props.path
  const points = [
    `${String(start.x)},${String(start.y)}`,
    `${String(shoulder.x)},${String(shoulder.y)}`,
    `${String(end.x)},${String(end.y)}`,
  ].join(' ')

  return (
    <svg className="battle__leader" role="img" aria-label={props.label}>
      <polyline className="battle__leader-line" points={points} />
      <circle
        className="battle__leader-ring"
        cx={center.x}
        cy={center.y}
        r={radius}
      />
    </svg>
  )
}
