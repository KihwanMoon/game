/**
 * LogRow — 이벤트 로그 한 줄.
 *
 * 받는 필드가 `tick·rule·expr·outcome·delta·fired` 인 것은 디자인이 정한 것이 아니라
 * **코어의 출력 계약**이다(design/README.md §5, src/core/eventLog.ts). 그래서 이 props 는
 * `LogEntry` 를 그대로 받을 수 있게 짜여 있다 — 코어의 `engine.log.entries` 원소를
 * 변환 없이 넘길 수 있고, 변환 계층이 없으면 서식을 고쳐도 값이 어긋나지 않는다.
 *
 * 발동/미발동은 글리프(▸ / ·)와 명도 두 채널로 적는다. 증감은 부호를 반드시 붙이므로
 * 색을 못 봐도 방향이 읽힌다.
 */
import { ValueExpr } from './ValueExpr'

/** 틱 번호를 0 으로 채울 자릿수. 코어 `formatLines` 의 `{tick:03d}` 와 같다. */
const TICK_PAD_WIDTH = 3

/** 발동한 줄의 글리프. */
const FIRED_GLYPH = '▸'

/** 발동하지 않은 줄의 글리프. */
const IDLE_GLYPH = '·'

/**
 * 결마다의 글리프. **색과 같은 것을 가리킨다** — 색을 못 보는 화면에서도 이 한 글자가
 * 남으므로, 색이 정보의 유일한 채널이 되지 않는다 (design/README D-1).
 *
 * **`Map` 인 것은 게이트 때문이다.** `tests/test_design_contract.py` 가 정본과 대조하는
 * 표는 `ReadonlyMap` 리터럴 꼴만 읽는다 — `Record` 로 두면 글리프가 갈려도 검사가 조용히
 * 통과한다(2026-09-03 에 그런 자리가 셋 있었다). 조회에만 쓰므로 순회 불변조건(R5)과는
 * 무관하다.
 */
const TONE_GLYPHS: ReadonlyMap<string, string> = new Map([
  ['damage', '✦'],
  ['heal', '✚'],
  ['death', '✕'],
  ['waste', '⊘'],
  ['world', '◇'],
  ['decide', '·'],
])

/** 결마다의 말. 화면 낭독기가 읽는 것이 이것이다. */
const TONE_WORDS: ReadonlyMap<string, string> = new Map([
  ['damage', '피해'],
  ['heal', '회복'],
  ['death', '쓰러짐'],
  ['waste', '헛돎'],
  ['world', '세계'],
  ['decide', '판단'],
])

/**
 * LogRow 가 받는 props.
 *
 * `rule` 과 `delta` 가 `number | null` 을 받는 것은 코어가 "없음" 을 null 로 내보내기
 * 때문이다. 0 과 구분해야 하므로 기본값 0 으로 접지 마라.
 */
export interface LogRowProps {
  readonly tick: number
  readonly rule?: number | null
  readonly expr: string
  readonly outcome: string
  readonly delta?: number | null
  readonly fired?: boolean
  /**
   * 이 줄을 남긴 개체의 이름. **없으면 누가 한 것인지 알 수 없다** — 한 틱에 여러
   * 개체가 줄을 남기므로, 행위자 칸이 없으면 전부 한 덩어리로 읽힌다 (2026-09-15 신고).
   *
   * 코어 레코드의 `entity_id` 에 대응한다. id 를 그대로 넣지 말고 이름으로 바꿔 넣는다
   * (`battle/logNames`) — 화면이 id 로 말하면 그것은 로그가 아니라 덤프다.
   */
  readonly actor?: string
  /** 그 개체가 내 편인가. 색이 이것을 가른다. */
  readonly isMine?: boolean
  /**
   * 줄의 결 — `damage`·`heal`·`waste`·`death`·`decide`·`world`.
   *
   * **색은 세 채널 중 하나일 뿐이다.** 결마다 글리프와 말이 함께 붙으므로 색을 못 봐도
   * 읽힌다 (design/README D-1).
   */
  readonly tone?: string
  /**
   * 지금 보고 있는 틱의 줄인가.
   *
   * **되감기가 이것 없이는 성립하지 않는다.** 로그는 지나온 틱을 전부 이어 그리므로,
   * 틱 12 로 감았을 때 어느 줄이 12 인지가 안 보이면 무엇을 짚은 것인지 알 수 없다.
   * 관전에서도 이번 틱과 잔상을 가른다.
   */
  readonly isNow?: boolean
}

/**
 * 부호를 반드시 붙여 정수를 적는다. 코어 `formatSigned` 와 같은 서식이다.
 *
 * @param value 적을 정수.
 * @returns `+3` 이나 `-3`.
 */
export function formatDelta(value: number): string {
  return value < 0 ? String(value) : `+${String(value)}`
}

/**
 * 로그 한 줄을 그린다.
 *
 * @param props 코어 로그 레코드의 필드들.
 * @returns 렌더 트리.
 */
export function LogRow(props: LogRowProps): React.JSX.Element {
  const fired = props.fired === true
  const rule = props.rule ?? null
  const delta = props.delta ?? null
  const deltaTone = delta !== null && delta < 0 ? 'down' : 'up'

  const tone = props.tone ?? ''

  return (
    <div
      className={`ds-log-row${fired ? '' : ' ds-log-row--idle'}${
        props.isNow === true ? ' ds-log-row--now' : ''
      }${tone === '' ? '' : ` ds-log-row--${tone}`}`}
    >
      <span className="ds-log-row__tick">T{String(props.tick).padStart(TICK_PAD_WIDTH, '0')}</span>
      <span className="ds-log-row__fired" aria-hidden="true">
        {TONE_GLYPHS.get(tone) ?? (fired ? FIRED_GLYPH : IDLE_GLYPH)}
      </span>
      <span className="ds-sr">{TONE_WORDS.get(tone) ?? (fired ? '발동' : '미발동')}</span>
      {/* **없어도 칸은 그린다** (2026-09-16). 안 그리면 항목 수가 줄마다 달라지고,
          격자는 개수로 칸을 채우므로 **나머지가 한 칸씩 당겨진다** — 행위자가 붙은 줄만
          증감이 둘째 줄로 밀려 줄 높이가 두 배가 됐던 자리다. 빈 칸은 폭 0 이다. */}
      <span
        className={`ds-log-row__actor${props.isMine === true ? ' ds-log-row__actor--mine' : ''}`}
      >
        {props.actor ?? ''}
      </span>
      <span className="ds-log-row__rule">{rule === null ? '' : `[${String(rule)}]`}</span>
      <span className="ds-log-row__body">
        <ValueExpr text={props.expr} size="sm" dim={!fired} />
        <span className="ds-log-row__outcome"> → {props.outcome}</span>
      </span>
      {delta === null ? (
        <span />
      ) : (
        <span className={`ds-log-row__delta--${deltaTone}`}>{formatDelta(delta)}</span>
      )}
    </div>
  )
}
