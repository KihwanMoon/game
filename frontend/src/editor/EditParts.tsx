/**
 * 모바일 편집 화면의 낱개 부품 — 카드 껍데기와 선택 칸 (명세 C).
 *
 * **디자인 시스템에 넣지 않고 여기 둔 이유.** `ds/` 의 계약표(design/README.md)는 정본이
 * 정한 부품 열여섯을 담고 있고, 선언되지 않은 부품을 늘리는 것은 그 표를 우리가 고치는
 * 일이다. 여기 있는 것들은 편집 화면 하나가 쓰는 **표현**이므로 화면 폴더에 둔다 — 다른
 * 화면이 같은 모양을 원하게 되면 그때 정본에 올린다.
 *
 * 칸은 전부 네이티브 `select`·`input` 이다. 직접 만든 드롭다운은 키보드·보조 기술 보장을
 * 처음부터 다시 짜야 하고, 모바일에서는 그 위에 OS 의
 * 선택 UI 까지 잃는다. `▽` 는 그 위에 얹은 표시일 뿐이라 클릭을 가로채지 않는다.
 *
 * 훅을 쓰지 않는다. 상태는 화면 하나(`RuleEditor`)가 들고 여기로는 값과 콜백만 내려온다 —
 * 그래서 테스트가 이 함수들을 직접 불러 반환된 트리에서 핸들러를 눌러 볼 수 있다.
 */
import type { ReactNode } from 'react'

/** 선택 칸의 항목 하나. */
export interface EditOption {
  readonly value: string
  readonly label: string
}

/** 항목 묶음. 인지 변수·행동처럼 카테고리가 있는 목록이 이것으로 온다. */
export interface EditOptionGroup {
  readonly label: string
  readonly options: readonly EditOption[]
}

/** EditCard 가 받는 props. */
export interface EditCardProps {
  readonly title: string
  /** 헤더 오른쪽에 적는 한 줄. 조건 카드는 여기에 값의 출처를 적는다. */
  readonly meta?: string
  readonly children: ReactNode
}

/**
 * 편집 카드 한 장을 그린다. 1px 괘선 테두리와 32px 헤더가 카드의 전부다 — 그림자는
 * 시스템에 없다.
 *
 * @param props 제목·부제와 본문.
 * @returns 렌더 트리.
 */
export function EditCard(props: EditCardProps): React.JSX.Element {
  return (
    <section className="edit-card">
      <header className="edit-card__head">
        <h2 className="edit-card__title">{props.title}</h2>
        {props.meta === undefined ? null : <span className="edit-card__meta">{props.meta}</span>}
      </header>
      <div className="edit-card__body">{props.children}</div>
    </section>
  )
}

/** EditField 가 받는 props. */
export interface EditFieldProps {
  /** 보조 기술이 읽는 이름. 칸에는 값만 보이므로 이것이 유일한 이름이다. */
  readonly label: string
  readonly value: string
  readonly options?: readonly EditOption[]
  readonly groups?: readonly EditOptionGroup[]
  readonly onChange: (value: string) => void
  /** 격자의 한 칸이 아니라 줄 전체를 쓴다. 인자 선택칸이 이것을 쓴다. */
  readonly wide?: boolean
}

/** 목록에 없는 값에 붙이는 꼬리표. 지금 든 것이 고를 수 없는 것임을 말한다. */
export const ORPHAN_SUFFIX = ' (목록에 없음)'

/** 아무것도 안 고른 자리에 적는 말. 빈 칸은 「목록이 덜 실렸다」로 읽힌다. */
export const UNSET_LABEL = '— 안 골랐다'

/**
 * 지금 든 값이 목록에 없으면 그 값을 항목으로 하나 만들어 낸다.
 *
 * **고르개는 거짓말을 하면 안 된다** (2026-09-19). `<select>` 는 value 와 맞는 option 이
 * 없으면 **첫 항목을 고른 것처럼** 보여 준다. 실측한 것 둘:
 *
 * - 실제로는 `ATTACK`(공격)인 새 규칙이 화면에서 「대상에게 접근」으로 떴다.
 * - 대상을 안 고른 규칙이 셀렉터 목록의 첫 칸을 고른 것처럼 떴다.
 *
 * **막는 자리가 여기인 이유.** 부르는 쪽마다 막으면 다음에 생기는 칸이 또 샌다 — 실제로
 * 행동 칸은 인자 칸의 같은 병을 고친 **바로 그 커밋에서** 새로 샜다. 칸 자체가 못 하게
 * 한다.
 *
 * **값을 지우지 않고 드러낸다.** 옛 규칙표가 팔레트에서 뺀 행동(`SKILL_1` 등)을 쓰고
 * 있을 수 있고 그것은 여전히 읽히고 돌아야 한다 — 열었다는 이유로 조용히 바뀌면 안 된다.
 *
 * @param props 칸의 props.
 * @returns 앞에 붙일 항목 하나. 값이 목록에 있으면 빈 배열.
 */
function buildOrphanOption(props: EditFieldProps): readonly EditOption[] {
  const known = [
    ...(props.options ?? []),
    ...(props.groups ?? []).flatMap((group) => group.options),
  ]
  if (known.some((option) => option.value === props.value)) {
    return []
  }
  return [
    {
      value: props.value,
      label: props.value === '' ? UNSET_LABEL : `${props.value}${ORPHAN_SUFFIX}`,
    },
  ]
}

/**
 * 선택 칸 하나를 그린다.
 *
 * @param props 이름·값·항목과 변경 콜백.
 * @returns 렌더 트리.
 */
export function EditField(props: EditFieldProps): React.JSX.Element {
  const groups = props.groups ?? []
  const options = [...buildOrphanOption(props), ...(props.options ?? [])]
  return (
    <span className={`edit-field${props.wide === true ? ' edit-field--wide' : ''}`}>
      <select
        className="edit-field__input"
        aria-label={props.label}
        value={props.value}
        onChange={(event) => {
          props.onChange(event.target.value)
        }}
      >
        {options.map((option) => (
          <option value={option.value} key={option.value}>
            {option.label}
          </option>
        ))}
        {groups.map((group) => (
          <optgroup label={group.label} key={group.label}>
            {group.options.map((option) => (
              <option value={option.value} key={option.value}>
                {option.label}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
      <span className="edit-field__caret" aria-hidden="true">
        ▽
      </span>
    </span>
  )
}

/** EditNumber 가 받는 props. */
export interface EditNumberProps {
  readonly label: string
  readonly value: number
  readonly onChange: (value: number) => void
}

/** 십진수. 규칙표에 부동소수는 들어오지 않는다. */
const DECIMAL_RADIX = 10

/**
 * 숫자 입력 칸 하나를 그린다. 리터럴 우변이 이것을 쓴다.
 *
 * @param props 이름·값과 변경 콜백.
 * @returns 렌더 트리.
 */
export function EditNumber(props: EditNumberProps): React.JSX.Element {
  return (
    <span className="edit-field edit-field--number">
      <input
        className="edit-field__input"
        type="number"
        inputMode="numeric"
        step={1}
        aria-label={props.label}
        value={props.value}
        onFocus={(event) => {
          event.target.select()
        }}
        onChange={(event) => {
          const parsed = Number.parseInt(event.target.value, DECIMAL_RADIX)
          props.onChange(Number.isNaN(parsed) ? 0 : parsed)
        }}
      />
    </span>
  )
}

/** EditSegments 가 받는 props. */
export interface EditSegmentsProps {
  /** 보조 기술이 읽는 묶음 이름. */
  readonly label: string
  readonly options: readonly EditOption[]
  readonly value: string
  readonly onPick: (value: string) => void
}

/**
 * 세그먼트 한 줄을 그린다. 우선순위 카드가 이것으로 자리를 고른다.
 *
 * **활성은 명도와 굵기로만 적는다.** 편집 화면의 황동 예산 둘은 규칙 번호와 저장 버튼이
 * 가져간다 (모바일 원본).
 *
 * @param props 이름·항목·현재 값과 선택 콜백.
 * @returns 렌더 트리.
 */
export function EditSegments(props: EditSegmentsProps): React.JSX.Element {
  return (
    <div className="edit-seg" role="group" aria-label={props.label}>
      {props.options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={`edit-seg__cell${option.value === props.value ? ' edit-seg__cell--on' : ''}`}
          aria-pressed={option.value === props.value}
          onClick={() => {
            props.onPick(option.value)
          }}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
