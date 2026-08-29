/**
 * Panel — 제목 괘선 하나와 본문을 가진 면.
 *
 * 층위는 그림자가 아니라 배경 명도차 + 1px 괘선으로만 만든다. `tone` 셋은 명도 세 단이며
 * plan 은 화면에서 가장 어두운 면(도면 바탕)이다.
 */
import type { ReactNode } from 'react'

/** 면의 명도 단계. */
export type PanelTone = 'panel' | 'raised' | 'plan'

/** Panel 이 받는 props. */
export interface PanelProps {
  /** 머리 괘선 왼쪽에 오는 라벨. 대문자·자간 확장으로 괘선처럼 읽힌다. */
  readonly title?: string
  /**
   * 머리 괘선 오른쪽 슬롯. 문자열을 주면 모노·저명도 보조 수치로 그린다.
   *
   * 노드도 받는다. 계약표의 뜻은 "보조 수치" 지만, 타입을 문자열로 좁히면 헤더에 작은
   * 버튼 하나가 필요한 화면이 Panel 을 버리고 헤더를 직접 짜게 된다 — 그 순간 여백과
   * 괘선이 화면마다 갈린다. 시스템 밖으로 나가게 만드는 것보다 슬롯을 여는 편이 낫다.
   * 다만 여기에 본문을 넣지 마라. 한 줄 높이의 보조 정보 자리다.
   */
  readonly meta?: ReactNode
  readonly tone?: PanelTone
  /** 본문에 패널 여백을 준다. 표·로그처럼 행이 괘선까지 닿아야 하면 false. */
  readonly padded?: boolean
  /** 본문을 세로 스크롤 영역으로 만든다. 높이는 바깥에서 정해 준다. */
  readonly scroll?: boolean
  readonly children?: ReactNode
}

/**
 * 패널 하나를 그린다.
 *
 * @param props 제목·보조 수치·명도·여백·스크롤 여부.
 * @returns 렌더 트리.
 */
export function Panel(props: PanelProps): React.JSX.Element {
  const tone = props.tone ?? 'panel'
  const hasHead = props.title !== undefined || props.meta !== undefined
  const bodyNames = [
    'ds-panel__body',
    props.padded === false ? '' : 'ds-panel__body--padded',
    props.scroll === true ? 'ds-panel__body--scroll' : '',
  ].filter((name) => name !== '')

  return (
    <section className={`ds-panel ds-panel--${tone}`}>
      {hasHead ? (
        <header className="ds-panel__head">
          <span className="ds-label">{props.title}</span>
          {props.meta === undefined ? null : <span className="ds-panel__meta">{props.meta}</span>}
        </header>
      ) : null}
      <div className={bodyNames.join(' ')}>{props.children}</div>
    </section>
  )
}
