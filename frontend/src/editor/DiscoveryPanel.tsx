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
 *
 * **격자는 가방과 같은 것을 쓴다** (2026-09-16). 예전에는 `ds/CellGrid` 였다 — 얇아서
 * 그림과 이름까지만 그렸고, 등급·상태 글리프·「무엇을 해 주는가」 한 줄이 들어갈 자리가
 * 없었다. 도면 격자(`SlotBoard`)로 옮기면서 그 넷을 공짜로 얻었고, 조작과 상세가 한
 * 곳에 모이는 규율도 가방과 같아졌다. `ds/CellGrid` 는 **지우지 않는다** —
 * `tests/test_design_contract.py` 가 `ds/*.tsx` 전량을 정본 계약과 대조하므로 파일이
 * 사라지거나 prop 이 하나 늘면 그 게이트가 깨진다.
 */
import { useState } from 'react'

import { Button, Panel, ValueExpr } from '../ds'
import type { DiscoveryRow, DiscoveryView } from '../storage'

import { buildDiscoveryCells } from './discoveryCells'
import { LinkNoticeLine } from './LinkNoticeLine'
import { checkLinked, type LinkState } from './linkState'
import { SlotBoard, SlotGrid, usePickedKey } from './SlotBoard'

// `editor/index` 가 이 이름을 이 파일에서 내보내고 있다. 어댑터로 옮겼지만 자리는
// 남긴다 — 배럴은 다른 손이 같이 쥔 파일이라 이 단계에서 안 건드린다.
export { buildDiscoveryCells } from './discoveryCells'

export interface DiscoveryPanelProps {
  readonly discovery: DiscoveryView | undefined
  readonly link: LinkState
}

type View = 'items' | 'skills'

const VIEWS: readonly { readonly id: View; readonly label: string }[] = [
  { id: 'items', label: '아이템' },
  { id: 'skills', label: '재주' },
]

/** 못 닿았을 때 무엇을 못 보는가. 앞머리(`서버에 닿지 못했다`)는 linkState 가 든다. */
const MISSING_HINT = '이문록은 서버가 안다'

/** 아무 칸도 안 골랐을 때. 상세 자리가 비어 보이면 누를 것이 있는 줄 모른다. */
const PICK_HINT = '칸을 고르면 여기에 속살이 뜬다'

/**
 * 고른 줄 하나의 상세.
 *
 * 격자에서 갈라 둔 이유는 검사 때문만이 아니다 — 칸마다 이 내용을 펼치면 격자가 다시
 * 목록이 되고, 격자로 바꾼 이유가 사라진다.
 *
 * @param props 도감 한 줄.
 * @returns 렌더 트리.
 */
export function DiscoveryDetail(props: { readonly row: DiscoveryRow }): React.JSX.Element {
  const { row } = props
  return (
    <div className="cat__detail">
      <span className="cat__name">{row.labelKo}</span>
      <ValueExpr text={row.category} size="sm" dim />
      {row.isFound ? (
        <ValueExpr text={row.detail} size="sm" />
      ) : (
        // 안 밝힌 것의 성능은 서버가 안 보낸다. 화면이 가리는 것이 아니라
        // 응답에 없다 — 개발자 도구를 열어도 답이 없어야 가린 것이다.
        <ValueExpr text="아직 못 얻었다 — 얻으면 밝혀진다" size="sm" dim />
      )}
    </div>
  )
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
  // 탭을 옮길 때 고른 것을 지우지 않는다. 칸 key 에 계열(`ITEM`·`SKILL`)이 들어 있어
  // 다른 탭의 key 와 절대 안 맞으므로, 돌아오면 보던 자리가 그대로 남는다.
  const [pickedKey, togglePick] = usePickedKey()

  if (!checkLinked(link) || discovery === undefined) {
    return (
      <Panel title="이문록 · 물건과 재주" tone="panel" padded>
        <LinkNoticeLine link={link} missing={MISSING_HINT} />
      </Panel>
    )
  }

  const rows = view === 'items' ? discovery.items : discovery.skills
  const cells = buildDiscoveryCells(rows)
  const picked = cells.find((cell) => cell.key === pickedKey)
  const found = rows.filter((row) => row.isFound).length
  const title = view === 'items' ? '물건' : '재주'

  return (
    <Panel
      title="이문록 · 물건과 재주"
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
              }}
            >
              {item.label}
            </Button>
          ))}
        </div>

        <SlotBoard
          hint={PICK_HINT}
          detail={picked === undefined ? undefined : <DiscoveryDetail row={picked.row} />}
        >
          <SlotGrid
            title={`${title} ${String(found)} / ${String(rows.length)}`}
            shape="free"
            cells={cells}
            pickedKey={pickedKey}
            onPick={togglePick}
            emptyText="비각에 아직 아무것도 없다"
          />
        </SlotBoard>
      </div>
    </Panel>
  )
}
