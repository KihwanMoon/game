/**
 * 서랍 — 곁다리 패널을 탭으로 갈라 **한 번에 하나만** 세운다.
 *
 * 예전에는 팔레트 열에 패널을 세로로 쌓았다. 둘일 때는 됐지만 아홉이 되자 두 가지가
 * 한꺼번에 깨졌다.
 *
 * 1. **높이가 안 나온다.** 쌓인 패널마다 `max-height: 50%` 에 `flex: 0 0 auto` 라,
 *    아홉이면 열 높이의 450% 를 요구하고 줄지도 않는다 — 아래쪽 패널이 하단 바를 뚫고
 *    나간다.
 * 2. **찾을 수가 없다.** 규칙 에디터에 닿기 전에 스크롤을 아홉 번 지나야 한다.
 *
 * 탭 하나만 세우면 높이 계산이 「팔레트 + 서랍 하나」로 돌아가고, 세로 배치에서도 같은
 * 구조를 그대로 쓴다.
 *
 * **묶음은 "무엇에 대한 것인가" 로 가른다.** 화면 수를 줄이려고 아무거나 합치면 탭
 * 이름이 설명을 못 하고, 그러면 탭이 있으나 마나다.
 */
import { useState } from 'react'

import { Button, Panel } from '../ds'

/** 서랍 한 칸. */
export interface DrawerTab {
  readonly id: string
  readonly label: string
  readonly body: React.ReactNode
}

export interface DrawerPanelProps {
  readonly tabs: readonly DrawerTab[]
  /** 처음 열려 있을 탭. 없으면 첫 칸. */
  readonly initialId?: string
}

/**
 * 서랍을 그린다.
 *
 * @param props 탭 목록.
 * @returns 패널 요소. 탭이 없으면 null.
 */
export function DrawerPanel(props: DrawerPanelProps): React.JSX.Element | null {
  const { tabs } = props
  const [openId, setOpenId] = useState(props.initialId ?? tabs[0]?.id ?? '')
  if (tabs.length === 0) {
    return null
  }
  // 열려 있던 탭이 사라질 수 있다 — 관리자 권한을 잃으면 그 탭이 목록에서 빠진다.
  const open = tabs.find((tab) => tab.id === openId) ?? tabs[0]

  return (
    <Panel title="서랍" meta={open?.label ?? ''} tone="panel" padded={false} scroll={false}>
      <div className="drw">
        <div className="drw__tabs" role="tablist">
          {tabs.map((tab) => (
            <Button
              key={tab.id}
              size="sm"
              variant={tab.id === open?.id ? 'primary' : 'ghost'}
              onClick={() => {
                setOpenId(tab.id)
              }}
            >
              {tab.label}
            </Button>
          ))}
        </div>
        <div className="drw__body">{open?.body}</div>
      </div>
    </Panel>
  )
}
