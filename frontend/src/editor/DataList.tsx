/**
 * DataList — 목록 화면이 **매번 다시 짓던 다섯 가지**를 한 틀로 모은 것.
 *
 * 다섯은 컨테이너(ul/ol + 클래스) · 개수 · 페이지 · 거르기 · 줄 앞 그림이다. **행은 이
 * 틀이 그리지 않는다** — 줄 하나가 무엇을 적는지는 화면마다 다르고(매물은 값과 만료,
 * 도감은 규칙표 줄 수), 그것까지 틀이 가져가면 prop 이 화면 수만큼 자란다. 틀은 줄의
 * **바깥**만 진다.
 *
 * **빈 상태를 틀이 지지 않는다.** 이 저장소는 `linkState.describeLink` 가 이미 넷을
 * 가른다 — 확인 중 · 못 닿음 · 불러오는 중 · 빈 것. 그것을 `items: T[] | undefined` 로
 * 접으면 **불러오는 중에 「아직 없다」가 뜨는, 이미 고쳐 둔 버그가 되살아난다**(첫
 * 페인트에서 ◈ 를 띄우던 것과 같은 병이다). 그래서 이 틀은 **빈 목록 문구 하나만**
 * 받고(`emptyText`), 「못 닿았다」는 화면이 지금처럼 `LinkNoticeLine` 으로 밖에서 가른다.
 *
 * 정렬 · 스크롤 · 행 접기는 안 한다. 정렬은 무엇이 값인지 알아야 하고(도메인), 스크롤은
 * `Panel scroll` 이 이미 지며, 행 접기는 행의 일이다.
 */
import { useState } from 'react'
import type { ReactNode } from 'react'

import { Button, Thumb, ValueExpr } from '../ds'
import type { ThumbState } from '../ds'

/** 세는 단위의 기본값. 「5줄」 · 「걸리는 줄이 없다」. */
const DEFAULT_UNIT = '줄'

/** 거르기 칸에 적을 기본 이름. 보조 기술이 읽는 이름이기도 하다. */
const DEFAULT_FILTER_LABEL = '거르기'

/**
 * 줄 앞 그림 한 칸.
 *
 * **`Thumb` 의 props 를 그대로 쓰지 않는다.** `exactOptionalPropertyTypes` 아래에서
 * `Thumb.art` 는 `string` 이라 `string | undefined` 를 그냥 못 넘기는데, 화면이 들고 있는
 * 값은 대개 `ItemView.art` 처럼 `string | undefined` 다. 그 변환을 화면마다 하면 매번
 * 조건부 전개(`{...(art === undefined ? {} : { art })}`)를 복사하게 되므로 여기서 한 번만 한다.
 */
export interface DataListThumb {
  /** 분류. 자리(`HEAD`)이거나 종류(`ELITE`)다. 그림이 없으면 두 글자 코드가 그려진다. */
  readonly kind: string
  /** 보조 기술이 읽을 이름. */
  readonly label: string
  readonly art?: string | undefined
  readonly grade?: string | undefined
  readonly state?: ThumbState | undefined
  /** 줄 앞이라 기본은 `sm` 이다. 칸이 아니라 줄이므로 `md` 는 줄 높이를 밀어낸다. */
  readonly size?: 'md' | 'sm' | undefined
}

/** DataList 가 받는 것. */
export interface DataListProps<T> {
  /**
   * 그릴 것. **`undefined` 를 받지 않는다** — 「아직 안 왔다」와 「빈 것」이 한 값이 되면
   * 불러오는 중에 「아직 없다」가 뜬다. 그 넷은 화면이 밖에서 가른다.
   */
  readonly items: readonly T[]
  /**
   * 줄의 키. **index 를 함께 준다** — 접사 목록처럼 값이 중복될 수 있는 자리가 있고,
   * 거기서 값만으로 키를 만들면 React 가 같은 줄로 보고 하나를 지운다.
   *
   * index 는 거른 뒤의 자리가 아니라 **원래 `items` 안의 자리**다. 질의가 바뀌어도
   * 남은 줄의 키가 그대로라 다시 그려지지 않는다.
   */
  readonly rowKey: (item: T, index: number) => string
  /** 줄 안쪽. 무엇을 적는지는 화면이 정한다. */
  readonly renderRow: (item: T, index: number) => ReactNode
  /** 하나도 없을 때 적을 말. 「불러오는 중」이 아니라 **정말 빈 것**의 문구다. */
  readonly emptyText: string
  /** `ol` 이면 번호가 뜻인 목록이다. 기본은 `ul`. */
  readonly as?: 'ul' | 'ol'
  /**
   * 목록에 덧붙일 클래스. **틀은 `display` 를 안 정한다** — 격자(`display:grid`)로 세는
   * 화면이 있어서 여기서 flex 를 박으면 그 화면이 못 옮겨 온다.
   */
  readonly listClass?: string
  /** 줄에 덧붙일 클래스. */
  readonly rowClass?: string
  /** 세는 단위. 기본은 「줄」이며 개수·거르기 0건 문구가 함께 쓴다. */
  readonly unit?: string
  /** 개수 한 줄을 그릴까. 목록이 비었을 때는 `emptyText` 와 겹치므로 안 그린다. */
  readonly showCount?: boolean
  /**
   * 한 번에 보일 줄 수. **안 주면 「더 보기」가 서지 않는다** — 길이가 고정인 목록
   * (자리 다섯, 접사 셋)에 「더 보기」가 서면 뒤에 뭔가 더 있다는 거짓말이 된다.
   */
  readonly pageSize?: number
  /** 거를 때 볼 글자. 주면 거르기 칸이 선다. 안 주면 칸도 없다. */
  readonly filterText?: (item: T) => string
  /** 거르기 칸의 이름. 자리글씨와 보조 기술 이름으로 함께 나간다. */
  readonly filterLabel?: string
  /**
   * 첫 질의. 화면이 탭을 되돌아올 때 쓰던 질의를 되살리는 자리이며, DOM 없이 도는
   * 검사가 거른 결과를 볼 수 있는 유일한 문이기도 하다(`defaultValue` 와 같은 뜻).
   */
  readonly defaultQuery?: string
  /** 줄 앞 그림. 돌려주지 않으면(`undefined`) 그 줄에는 그림이 없다. */
  readonly thumb?: (item: T, index: number) => DataListThumb | undefined
}

/** 거르기·페이지를 거치는 동안 원래 자리를 잃지 않게 묶어 둔 한 줄. */
interface NumberedRow<T> {
  readonly item: T
  readonly index: number
}

/**
 * 한글 끝소리로 주격 조사를 고른다.
 *
 * 단위를 밖에서 받으므로 「줄이 없다」와 「자료가 없다」가 섞인다. 조사를 박아 두면
 * 단위를 바꾼 화면에서 문장이 어색해지고, 어색한 문장은 기계가 쓴 티가 난다.
 *
 * @param word 앞말.
 * @returns `이` 또는 `가`. 한글이 아니면 `이`.
 */
export function pickSubjectParticle(word: string): string {
  const last = word.codePointAt(word.length - 1) ?? 0
  if (last < 0xac00 || last > 0xd7a3) {
    return '이'
  }
  return (last - 0xac00) % 28 === 0 ? '가' : '이'
}

/**
 * 거르기가 한 줄도 못 남겼을 때 적을 말.
 *
 * **`emptyText` 를 쓰면 안 된다.** 「아직 아무것도 없다」와 「친 글자에 걸리는 것이
 * 없다」는 다른 사실이고, 앞의 것으로 적으면 가진 것을 질의가 가리고 있다는 사실이
 * 사라진다 — 사람은 목록이 빈 줄 알고 화면을 떠난다. 그래서 **전체가 몇인지 함께** 적는다.
 *
 * @param query 친 글자.
 * @param total 거르기 전 전체 줄 수.
 * @param unit 세는 단위.
 * @returns 화면에 적을 한 줄.
 */
export function describeFilterMiss(query: string, total: number, unit: string): string {
  return `「${query}」에 걸리는 ${unit}${pickSubjectParticle(unit)} 없다 — 전체 ${String(total)}${unit}`
}

/**
 * 개수 한 줄.
 *
 * 세는 것은 **보이는 줄이 아니라 걸린 줄**이다. 페이지가 잘라 낸 것은 없는 것이 아니라
 * 아직 안 그린 것이고, 그 수는 「더 보기」가 따로 적는다.
 *
 * @param matched 거르기를 통과한 줄 수.
 * @param total 거르기 전 전체 줄 수.
 * @param unit 세는 단위.
 * @returns 화면에 적을 한 줄.
 */
export function formatRowCount(matched: number, total: number, unit: string): string {
  if (matched === total) {
    return `${String(matched)}${unit}`
  }
  return `${String(matched)}${unit} — 전체 ${String(total)}${unit}`
}

/**
 * 줄 앞 그림 하나를 그린다.
 *
 * @param spec 그림 자리의 값들.
 * @returns 렌더 트리.
 */
function renderThumb(spec: DataListThumb): React.JSX.Element {
  // 조건부 전개다. `exactOptionalPropertyTypes` 아래에서 `art={undefined}` 는 「없음」이
  // 아니라 타입 오류이고, 화면이 들고 있는 값은 대개 `string | undefined` 다.
  return (
    <Thumb
      kind={spec.kind}
      label={spec.label}
      size={spec.size ?? 'sm'}
      {...(spec.art === undefined ? {} : { art: spec.art })}
      {...(spec.grade === undefined ? {} : { grade: spec.grade })}
      {...(spec.state === undefined ? {} : { state: spec.state })}
    />
  )
}

/**
 * 목록 하나를 그린다.
 *
 * @param props 줄들과 틀이 질 다섯 가지.
 * @returns 렌더 트리.
 */
export function DataList<T>(props: DataListProps<T>): React.JSX.Element {
  const { items, pageSize, filterText, thumb } = props
  const unit = props.unit ?? DEFAULT_UNIT
  const [query, setQuery] = useState(props.defaultQuery ?? '')
  const [shown, setShown] = useState(pageSize ?? 0)

  // 원래 자리를 붙여 둔 채로 거르고 자른다 — 그래야 거른 뒤에도 `rowKey` 와
  // `renderRow` 가 **`items` 안의 자리**를 본다. 거른 뒤의 자리를 주면 질의가 바뀔
  // 때마다 남은 줄의 키까지 바뀌어 통째로 다시 그려진다.
  const needle = query.trim().toLowerCase()
  const numbered: readonly NumberedRow<T>[] = items.map((item, index) => ({ item, index }))
  const matched =
    filterText === undefined || needle === ''
      ? numbered
      : numbered.filter((row) => filterText(row.item).toLowerCase().includes(needle))

  // 페이지를 안 쓰면 전부 그린다. 「더 보기」도 그때는 서지 않는다.
  const visible = pageSize === undefined ? matched : matched.slice(0, shown)
  const rest = matched.length - visible.length

  const Tag = props.as === 'ol' ? 'ol' : 'ul'
  const listClass = ['dlist__rows', `dlist__rows--${props.as ?? 'ul'}`, props.listClass ?? '']
    .filter((name) => name !== '')
    .join(' ')

  // 하나도 없으면 머리도 없다. 「0줄」과 거르기 칸은 `emptyText` 위에서 소음이고,
  // 아직 아무것도 못 넣은 사람에게 거를 것을 내미는 꼴이 된다.
  const showHead = items.length > 0 && (props.showCount === true || filterText !== undefined)

  return (
    <div className="dlist">
      {!showHead ? null : (
        <div className="dlist__head">
          {props.showCount !== true ? null : (
            <ValueExpr text={formatRowCount(matched.length, items.length, unit)} size="sm" dim />
          )}
          {filterText === undefined ? null : (
            <input
              className="dlist__find"
              type="search"
              value={query}
              placeholder={props.filterLabel ?? DEFAULT_FILTER_LABEL}
              aria-label={props.filterLabel ?? DEFAULT_FILTER_LABEL}
              onChange={(event) => {
                setQuery(event.target.value)
                // **보이는 줄 수를 되돌린다.** 열두 줄까지 펼쳐 둔 채로 질의를 치면
                // 새 결과가 열두 줄로 튀어나오고, 「더 보기」로 한 장씩 보던 약속이
                // 깨진다. 질의는 다른 목록이지 같은 목록의 다음 장이 아니다.
                setShown(pageSize ?? 0)
              }}
            />
          )}
        </div>
      )}

      {items.length === 0 ? (
        <ValueExpr text={props.emptyText} size="sm" dim />
      ) : matched.length === 0 ? (
        <ValueExpr text={describeFilterMiss(query.trim(), items.length, unit)} size="sm" dim />
      ) : (
        <Tag className={listClass}>
          {visible.map((row) => {
            const spec = thumb?.(row.item, row.index)
            return (
              <li className={props.rowClass} key={props.rowKey(row.item, row.index)}>
                {spec === undefined ? null : renderThumb(spec)}
                {props.renderRow(row.item, row.index)}
              </li>
            )
          })}
        </Tag>
      )}

      {pageSize === undefined || rest <= 0 ? null : (
        <Button
          size="sm"
          variant="ghost"
          glyph="▾"
          onClick={() => {
            setShown(shown + pageSize)
          }}
        >
          {`더 보기 · 남은 ${String(rest)}${unit}`}
        </Button>
      )}
    </div>
  )
}
