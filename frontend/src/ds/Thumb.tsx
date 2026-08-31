/**
 * Thumb — 아이템·몬스터 한 칸의 그림 자리.
 *
 * **그림이 오기 전에 자리를 먼저 만든다.** 나중에 SVG 를 넣을 때 배치가 흔들리지
 * 않아야 하고, 지금은 그림이 없어도 화면이 텍스트 목록으로만 보이지 않아야 한다.
 *
 * 그림이 없을 때 그리는 것은 **분류 코드**다. 기계 도면이 부품에 번호를 적는 것과 같은
 * 자리이며, `WM`(주무기)·`HD`(투구)처럼 두 글자다. 개체마다 다른 무늬를 만들지 않는
 * 이유는 그것이 거짓말이기 때문이다 — 무늬가 다르면 다른 물건으로 읽히는데, 실제로는
 * 이름만이 그것을 가른다.
 *
 * 이모지를 쓰지 않는다(design/README.md). 코드는 어느 기기에서도 같은 폭으로 그려진다.
 */

/** 아직 안 밝힌 것. 도감의 미해금 칸이 이것을 쓴다. */
export type ThumbState = 'known' | 'locked'

/** 분류에서 두 글자 코드로. 없는 분류는 `··` 로 떨어진다. */
export const THUMB_CODES: ReadonlyMap<string, string> = new Map([
  ['WEAPON_MAIN', 'WM'],
  ['WEAPON_OFF', 'WO'],
  ['HEAD', 'HD'],
  ['BODY', 'BD'],
  ['FEET', 'FT'],
  ['HANDS', 'HN'],
  ['CONSUMABLE', 'CS'],
  ['EQUIPMENT', 'EQ'],
  ['NORMAL', 'N'],
  ['ELITE', 'E'],
  ['BOSS', 'B'],
])

/** Thumb 가 받는 props. */
export interface ThumbProps {
  /**
   * 분류. 슬롯(`HEAD`)이거나 종류(`ELITE`)다. 코드를 여기서 고른다.
   */
  readonly kind: string
  /** 보조 기술이 읽을 이름. 그림 자리는 장식이고 이름이 정보다. */
  readonly label: string
  /**
   * 그림 주소. 아직 없으면 생략한다 — 코드가 그려진다.
   *
   * 외부 호스트를 가리키지 않는다. 아티팩트와 같은 이유이며, 자산은 번들에 들어온다.
   */
  readonly art?: string
  readonly size?: 'md' | 'sm'
  readonly state?: ThumbState
}

/**
 * 한 칸의 그림 자리를 그린다.
 *
 * @param props 분류·이름·그림·크기·상태.
 * @returns 렌더 트리.
 */
export function Thumb(props: ThumbProps): React.JSX.Element {
  const size = props.size ?? 'md'
  const state = props.state ?? 'known'
  const code = THUMB_CODES.get(props.kind) ?? '··'

  return (
    <span
      className={`ds-thumb ds-thumb--${size} ds-thumb--${state}`}
      role="img"
      aria-label={state === 'locked' ? `${props.label} · 아직 안 밝힘` : props.label}
    >
      {props.art !== undefined && state === 'known' ? (
        <img className="ds-thumb__art" src={props.art} alt="" />
      ) : (
        <span className="ds-thumb__code" aria-hidden="true">
          {state === 'locked' ? '⧅' : code}
        </span>
      )}
    </span>
  )
}
