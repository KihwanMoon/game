/**
 * 도면 렌더러가 쓰는 값들을 **토큰에서** 읽어 온다.
 *
 * 캔버스는 CSS 를 상속하지 않는다. `ctx.fillStyle` 에 넣을 색은 결국 문자열이라, 그냥
 * 짜면 생 hex 가 이 파일에 쌓이고 `design/` 을 다시 가져와도 도면만 옛 색으로 남는다.
 * 그래서 그리기 직전에 `getComputedStyle` 로 커스텀 속성을 읽어 값을 만든다 — 정본은
 * 여전히 토큰 CSS 한 곳이다.
 *
 * **없는 토큰은 조용히 넘기지 않고 던진다.** 빈 문자열을 fillStyle 에 넣으면 캔버스는
 * 직전 색을 그대로 쓰므로, 오타 하나가 "어딘가 색이 이상한데 원인을 모르겠는" 화면이
 * 된다. 이름을 달고 즉시 실패하는 편이 싸다.
 */

/** 렌더러가 쓰는 색 토큰. 키가 곧 `PlanTheme` 의 필드 이름이다. */
export const PLAN_COLOR_TOKENS: ReadonlyMap<string, string> = new Map([
  ['surface', '--surface-plan'],
  ['grid', '--line-grid'],
  ['wall', '--plan-wall'],
  ['floorDot', '--plan-floor-dot'],
  ['door', '--plan-door'],
  ['coverFill', '--surface-raised'],
  ['coverEdge', '--line-strong'],
  ['spring', '--state-heal'],
  ['hazard', '--plan-hazard'],
  ['actorSelf', '--plan-actor-self'],
  ['actorEnemy', '--plan-actor-enemy'],
  ['dim', '--text-dim'],
])

/** 렌더러가 쓰는 치수 토큰. 값은 `12px` 형태의 길이이며 px 단위로 읽는다. */
export const PLAN_LENGTH_TOKENS: ReadonlyMap<string, string> = new Map([
  ['cell', '--plan-cell'],
  ['hatchGap', '--hatch-gap'],
  ['lineWidth', '--bw'],
  ['glyphSize', '--fs-num-l'],
  ['labelSize', '--fs-label'],
])

/** 활자 계열 토큰. 캔버스의 `ctx.font` 에 그대로 붙는다. */
export const PLAN_FONT_TOKEN = '--font-mono'

/** 도면 한 장을 그리는 데 필요한 값 전부. 전부 토큰에서 왔다. */
export interface PlanTheme {
  /** 셀 한 변의 길이(px). */
  readonly cell: number
  /** 45도 해칭 간격(px). */
  readonly hatchGap: number
  /** 괘선 두께(px). */
  readonly lineWidth: number
  /** 말 글리프의 활자 크기(px). */
  readonly glyphSize: number
  /** 말 표기와 남은 틱의 활자 크기(px). */
  readonly labelSize: number
  /** 모노 활자 계열. */
  readonly font: string
  /** 도면 바탕. */
  readonly surface: string
  /** 격자 괘선. */
  readonly grid: string
  /** 벽 해칭. */
  readonly wall: string
  /** 바닥 점. */
  readonly floorDot: string
  /** 문·계단. */
  readonly door: string
  /** 엄폐물 면. */
  readonly coverFill: string
  /** 엄폐물 테두리. */
  readonly coverEdge: string
  /** 생명의 샘. */
  readonly spring: string
  /** 용암·함정·예고 타일. */
  readonly hazard: string
  /** 플레이어 말. 화면의 황동 예산 한 자리를 쓴다. */
  readonly actorSelf: string
  /** 적 말. */
  readonly actorEnemy: string
  /** 보조 표기. */
  readonly dim: string
}

/** 토큰 이름 하나를 값으로 바꾸는 함수. 테스트가 이 자리에 가짜를 끼운다. */
export type TokenReader = (name: string) => string

/**
 * 엘리먼트에 걸린 커스텀 속성을 읽는 함수를 만든다.
 *
 * @param element 계산된 스타일을 볼 엘리먼트. 보통 캔버스 자신이다.
 * @returns 토큰 이름을 값으로 바꾸는 함수.
 */
export function createTokenReader(element: Element): TokenReader {
  const styles = getComputedStyle(element)
  return (name: string) => styles.getPropertyValue(name).trim()
}

/**
 * 토큰 하나를 읽는다.
 *
 * @param read 토큰 읽기 함수.
 * @param name 토큰 이름.
 * @returns 토큰 값.
 * @throws 토큰이 비어 있는 경우. 이름을 달고 즉시 실패한다.
 */
function readToken(read: TokenReader, name: string): string {
  const value = read(name)
  if (value === '') {
    throw new Error(`도면 렌더러가 쓰는 토큰이 비어 있다: ${name}`)
  }
  return value
}

/**
 * 길이 토큰 하나를 px 수치로 읽는다.
 *
 * @param read 토큰 읽기 함수.
 * @param name 토큰 이름.
 * @returns px 수치.
 * @throws 토큰이 비었거나 수로 읽히지 않는 경우.
 */
function readLength(read: TokenReader, name: string): number {
  const value = readToken(read, name)
  const length = Number.parseFloat(value)
  if (!Number.isFinite(length)) {
    throw new Error(`길이로 읽을 수 없는 토큰이다: ${name} = ${value}`)
  }
  return length
}

/**
 * 필드 이름에 걸린 토큰 이름을 찾는다.
 *
 * @param tokens 필드에서 토큰 이름으로의 표.
 * @param field 찾을 필드 이름.
 * @returns 토큰 이름.
 * @throws 표에 없는 필드인 경우. 표와 `PlanTheme` 이 어긋난 것이다.
 */
function findToken(tokens: ReadonlyMap<string, string>, field: string): string {
  const name = tokens.get(field)
  if (name === undefined) {
    throw new Error(`토큰 표에 없는 필드다: ${field}`)
  }
  return name
}

/**
 * 두 테마가 같은 값인지 본다.
 *
 * 토큰은 창이 바뀔 때마다 다시 읽는다(`--plan-cell` 이 브레이크포인트마다 다르다).
 * 읽을 때마다 새 객체가 나오므로 그대로 상태에 넣으면 참조가 매번 바뀌고, 그것을
 * 의존성으로 쓰는 캔버스가 창 크기가 1px 흔들릴 때마다 도면을 다시 그린다.
 *
 * @param before 지금 들고 있는 값. 아직 없으면 undefined.
 * @param after 방금 읽은 값.
 * @returns 필드가 전부 같으면 참.
 */
export function checkPlanThemeSame(before: PlanTheme | undefined, after: PlanTheme): boolean {
  if (before === undefined) {
    return false
  }
  const left: Record<string, unknown> = { ...before }
  const right: Record<string, unknown> = { ...after }
  return Object.keys(right).every((key) => left[key] === right[key])
}

/**
 * 토큰을 읽어 렌더러가 쓸 값 묶음을 만든다.
 *
 * @param read 토큰 읽기 함수.
 * @returns 도면 한 장을 그리는 데 필요한 값 전부.
 * @throws 토큰 하나라도 비어 있는 경우.
 */
export function readPlanTheme(read: TokenReader): PlanTheme {
  const color = (field: string): string => readToken(read, findToken(PLAN_COLOR_TOKENS, field))
  const length = (field: string): number => readLength(read, findToken(PLAN_LENGTH_TOKENS, field))
  return {
    cell: length('cell'),
    hatchGap: length('hatchGap'),
    lineWidth: length('lineWidth'),
    glyphSize: length('glyphSize'),
    labelSize: length('labelSize'),
    font: readToken(read, PLAN_FONT_TOKEN),
    surface: color('surface'),
    grid: color('grid'),
    wall: color('wall'),
    floorDot: color('floorDot'),
    door: color('door'),
    coverFill: color('coverFill'),
    coverEdge: color('coverEdge'),
    spring: color('spring'),
    hazard: color('hazard'),
    actorSelf: color('actorSelf'),
    actorEnemy: color('actorEnemy'),
    dim: color('dim'),
  }
}
