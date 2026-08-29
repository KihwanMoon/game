/**
 * 화면 하나를 감싸는 오류 경계.
 *
 * 왜 필요한가. 이 게임에서 실행되는 코드의 상당 부분을 **플레이어가 쓴다** — 규칙표가
 * 그것이다. 검증기가 대부분을 막지만, 막지 못한 조합 하나가 렌더 도중에 터지면 React 는
 * 트리 전체를 버린다. 그러면 화면이 하얗게 비고 플레이어는 자기가 무엇을 했는지 알 수
 * 없다. 실패는 정보여야 한다(P1) — 그래서 무엇이 터졌는지 적고, 고치러 갈 문을 남긴다.
 *
 * 훅으로는 만들 수 없다. `getDerivedStateFromError` 에 대응하는 훅이 아직 없어서 오류
 * 경계는 클래스 컴포넌트가 유일한 수단이다.
 */
import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'

import { Button, Panel } from './ds'

/** ErrorBoundary 가 받는 props. */
export interface ErrorBoundaryProps {
  /** 되돌아갈 곳. 여기서는 규칙 에디터다. */
  readonly onReset: () => void
  readonly children: ReactNode
}

/** 잡은 오류. 아직 없으면 undefined 다 — 빈 문자열로 접지 마라. */
export interface ErrorBoundaryState {
  readonly message: string | undefined
}

/**
 * 알 수 없는 던짐을 사람이 읽을 문구로 바꾼다.
 *
 * @param error 잡힌 값. Error 가 아닐 수도 있다.
 * @returns 화면에 적을 문구.
 */
export function formatCrash(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

/** 자식이 렌더 중에 터지면 대신 사유를 그린다. */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  /**
   * @param props 되돌아갈 콜백과 감쌀 화면.
   */
  public constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { message: undefined }
  }

  /**
   * 오류를 상태로 옮긴다.
   *
   * @param error 잡힌 값.
   * @returns 다음 상태.
   */
  public static getDerivedStateFromError(error: unknown): ErrorBoundaryState {
    return { message: formatCrash(error) }
  }

  /**
   * 콘솔에 스택을 남긴다. 화면에는 문구만 적고 스택은 개발자 도구에 둔다.
   *
   * @param error 잡힌 값.
   * @param info 컴포넌트 스택.
   */
  public override componentDidCatch(error: unknown, info: ErrorInfo): void {
    console.error('화면이 중단됐다', error, info.componentStack)
  }

  /**
   * 자식이나 사유 패널을 그린다.
   *
   * @returns 렌더 트리.
   */
  public override render(): ReactNode {
    const { message } = this.state
    if (message === undefined) {
      return this.props.children
    }
    return (
      <div className="app-crash">
        <Panel title="판이 중단됐다" meta="규칙표를 고쳐 다시 시도한다" tone="raised">
          <p className="app-crash__text">{message}</p>
          <Button
            variant="secondary"
            size="sm"
            glyph="↰"
            onClick={() => {
              this.setState({ message: undefined })
              this.props.onReset()
            }}
          >
            규칙 에디터로
          </Button>
        </Panel>
      </div>
    )
  }
}
