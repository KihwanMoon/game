/**
 * 도감 — 세계에 무엇이 있고, 그중 무엇을 밝혔는가.
 *
 * **미해금도 자리를 보여준다.** 안 밝힌 것을 목록에서 빼면 도감이 "내가 가진 것 목록"
 * 이 되고, 무엇을 더 찾아야 하는지가 화면에서 사라진다 — 몬스터 도감이 표적 목록인
 * 것과 같은 이유다 (docs/설계/6_몬스터 §8).
 *
 * **이름은 가리지 않는다.** 실루엣만 남기고 이름까지 지우면 목표가 안 보이고, 그러면
 * 찾아갈 이유도 안 생긴다. 가리는 것은 접사·계수 같은 속살이며, 그 판단은 서버가 한다
 * — 화면이 가리면 응답에 답이 실려 오므로 가린 것이 아니다.
 *
 * 미해금 표기는 「불가」와 같은 해칭이다. 새 표기를 만들지 않는다 — 뜻이 같다(해당 없음).
 */
import { useState } from 'react'

import { Button, CellGrid, Panel, Thumb, ValueExpr } from '../ds'
import type { DiscoveryRow, DiscoveryView } from '../storage'

import { LinkNoticeLine } from './LinkNoticeLine'
import { checkLinked, type LinkState } from './linkState'

export interface DiscoveryPanelProps {
  readonly discovery: DiscoveryView | undefined
  readonly link: LinkState
}

type View = 'items' | 'skills'

const VIEWS: readonly { readonly id: View; readonly label: string }[] = [
  { id: 'items', label: '아이템' },
  { id: 'skills', label: '스킬' },
]

/** 못 닿았을 때 무엇을 못 보는가. 앞머리(`서버에 닿지 못했다`)는 linkState 가 든다. */
const MISSING_HINT = '도감은 서버가 안다'

/**
 * 도감 줄들을 칸으로 바꾼다.
 *
 * @param rows 도감 줄들.
 * @param picked 고른 것의 id.
 * @returns 격자에 넣을 칸들.
 */
export function buildDiscoveryCells(rows: readonly DiscoveryRow[], picked: string) {
  return rows.map((row) => ({
    id: row.refId,
    thumb: (
      <Thumb
        kind={row.category}
        label={row.labelKo}
        state={row.isFound ? 'known' : 'locked'}
      />
    ),
    name: row.labelKo,
    meta: [row.isFound ? row.category : '아직 못 얻었다'],
    isSelected: row.refId === picked,
  }))
}

/**
 * 도감 패널을 그린다.
 *
 * @param props 도감과 접속 상태.
 * @returns 패널 요소.
 */
export function DiscoveryPanel(props: DiscoveryPanelProps): React.JSX.Element {
  const { discovery, link } = props
  const [view, setView] = useState<View>('items')
  const [picked, setPicked] = useState('')

  if (!checkLinked(link) || discovery === undefined) {
    return (
      <Panel title="수집" tone="panel" padded>
        <LinkNoticeLine link={link} missing={MISSING_HINT} />
      </Panel>
    )
  }

  const rows = view === 'items' ? discovery.items : discovery.skills
  const pickedRow = rows.find((row) => row.refId === picked)

  return (
    <Panel
      title="수집"
      meta={`${String(discovery.found)} / ${String(discovery.total)}`}
      tone="panel"
      padded
      scroll
    >
      <div className="cat">
        <div className="cat__tabs">
          {VIEWS.map((item) => (
            <Button
              key={item.id}
              size="sm"
              variant={item.id === view ? 'primary' : 'ghost'}
              onClick={() => {
                setView(item.id)
                setPicked('')
              }}
            >
              {item.label}
            </Button>
          ))}
        </div>

        <CellGrid
          cells={buildDiscoveryCells(rows, picked)}
          onSelect={setPicked}
          emptyText="세계에 아직 아무것도 없다"
        />

        {pickedRow === undefined ? null : (
          <div className="cat__detail">
            <span className="cat__name">{pickedRow.labelKo}</span>
            <ValueExpr text={pickedRow.category} size="sm" dim />
            {pickedRow.isFound ? (
              <ValueExpr text={pickedRow.detail} size="sm" />
            ) : (
              // 안 밝힌 것의 성능은 서버가 안 보낸다. 화면이 가리는 것이 아니라
              // 응답에 없다 — 개발자 도구를 열어도 답이 없어야 가린 것이다.
              <ValueExpr text="얻으면 밝혀진다" size="sm" dim />
            )}
          </div>
        )}
      </div>
    </Panel>
  )
}
