/**
 * Button — design/README.md 컴포넌트 계약.
 *
 * 선언 props 는 variant·size·active·disabled·glyph·block 이다. 여기에 `onClick`·`children`·
 * `title` 셋을 더했다. 계약표가 이들을 적지 않은 것은 표가 **표현 상태**만 열거하기
 * 때문이다. 셋 다 표현이 아니라 네이티브 `<button>` 의 기능이고, 빼면 대체 수단이 더
 * 나쁘다 — 핸들러가 없으면 소비자가 `<div onClick>` 으로 감싸 키보드 조작을 잃고,
 * `title` 이 없으면 글리프만 있는 버튼에 이름이 남지 않는다. 표현 prop 은 늘리지 마라.
 *
 * 황동 예산: `variant="primary"` 만 `--brass` 를 쓴다. 한 화면에 primary 는 하나로 둔다.
 */
import type { ReactNode } from 'react'

/** 시각적 무게. primary 만 황동을 쓴다. */
export type ButtonVariant = 'primary' | 'secondary' | 'ghost'

/** 크기 단계. 두 단계뿐이며 그 사이 값은 없다(4px 모듈). */
export type ButtonSize = 'md' | 'sm'

/** Button 이 받는 props. 계약에 없는 표현 prop 을 늘리지 마라. */
export interface ButtonProps {
  readonly variant?: ButtonVariant
  readonly size?: ButtonSize
  /** 토글로 켜진 상태. `aria-pressed` 로도 나가므로 색이 유일한 채널이 아니다. */
  readonly active?: boolean
  readonly disabled?: boolean
  /** 라벨 앞에 붙는 유니코드 도형 하나. 이모지 금지. */
  readonly glyph?: string
  /** 열 폭 전체를 채운다. */
  readonly block?: boolean
  readonly onClick?: () => void
  readonly children?: ReactNode
  /** 네이티브 툴팁. 글리프만 있는 버튼의 이름 역할을 한다. */
  readonly title?: string
}

/**
 * 버튼 하나를 그린다.
 *
 * @param props 표현 상태와 클릭 핸들러.
 * @returns 렌더 트리.
 */
export function Button(props: ButtonProps): React.JSX.Element {
  const variant = props.variant ?? 'secondary'
  const size = props.size ?? 'md'
  const classNames = [
    'ds-button',
    `ds-button--${variant}`,
    `ds-button--${size}`,
    props.active === true ? 'ds-button--active' : '',
    props.block === true ? 'ds-button--block' : '',
  ].filter((name) => name !== '')

  return (
    <button
      type="button"
      className={classNames.join(' ')}
      disabled={props.disabled === true}
      aria-pressed={props.active === undefined ? undefined : props.active}
      title={props.title}
      onClick={props.onClick}
    >
      {props.glyph === undefined ? null : (
        <span className="ds-button__glyph" aria-hidden="true">
          {props.glyph}
        </span>
      )}
      {props.children}
    </button>
  )
}
