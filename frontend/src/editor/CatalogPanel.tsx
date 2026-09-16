/**
 * 콘텐츠 카탈로그 — 무엇이 들어 있는가 (관리자, 읽기 전용).
 *
 * **여기서 고칠 수 없다.** 아이템·적·레벨 곡선은 `resources/*.json` 과 코어 상수이고
 * `core_version` 에 묶여 있다 — 런타임에 바꾸면 이미 발급된 티켓이 다른 게임을 가리키고,
 * 브라우저와 서버가 다른 값을 본다 (결정 #06, R5). 고치는 길은 파일을 고쳐 배포하는
 * 것뿐이며, 이 화면은 **게임이 읽는 그대로** 보여 준다.
 *
 * **레벨 곡선은 실제 인원과 겹쳐 그린다.** 곡선만 보면 튜닝할 수 없다 — 사람들이 실제로
 * 어디서 멈추는지가 보여야 "이 구간이 너무 긴가" 를 물을 수 있다.
 *
 * **격자는 가방과 같은 것을 쓴다** (2026-09-16). 예전에는 `ds/CellGrid` 였고, 상세가
 * 두 벌로 적혀 있었다 — 갈라 둔 `ItemDetail`·`EnemyDetail` 이 있는데 패널 안에 같은
 * 줄들이 또 있었고, 그쪽에는 사거리가 빠져 있었다. 사본은 늘 한쪽만 늙는다.
 * `ds/CellGrid` 는 **지우지 않는다** — `tests/test_design_contract.py` 가 `ds/*.tsx`
 * 전량을 정본 계약과 대조하므로 파일이 사라지거나 prop 이 하나 늘면 게이트가 깨진다.
 */
import { useState } from 'react'

import { Button, Panel, ValueExpr } from '../ds'
import type { AdminCatalog, CatalogEnemyRow, CatalogItemRow } from '../storage'

import { buildCatalogEnemyCells, buildCatalogItemCells } from './catalogCells'
import { SlotBoard, SlotGrid, usePickedKey } from './SlotBoard'

export interface CatalogPanelProps {
  readonly catalog: AdminCatalog | undefined
}

type View = 'items' | 'enemies' | 'curve'

const VIEWS: readonly { readonly id: View; readonly label: string }[] = [
  { id: 'items', label: '아이템' },
  { id: 'enemies', label: '적' },
  { id: 'curve', label: '레벨 곡선' },
]

/** 인원 막대의 최대 칸 수. 좁은 열에서도 한 줄에 들어와야 표가 흐트러지지 않는다. */
const BAR_MAX = 12

/**
 * 인원 수를 막대로 만든다.
 *
 * **숫자만으로는 분포가 안 보인다.** 이 화면의 목적이 "어디에 몰려 있는가" 이므로
 * 눈이 한 번에 읽는 형태가 필요하다. 색을 쓰지 않는 이유는 의미색 셋이 이미 배정됐고,
 * 이것은 참/거짓이 아니라 양이기 때문이다.
 *
 * @param count 인원.
 * @param peak 가장 많은 레벨의 인원.
 * @returns 막대 문자열. 0명이면 빈 문자열.
 */
export function formatPeopleBar(count: number, peak: number): string {
  if (count <= 0 || peak <= 0) {
    return ''
  }
  return '▮'.repeat(Math.max(1, Math.round((count * BAR_MAX) / peak)))
}

/**
 * 고른 아이템 하나의 상세.
 *
 * 격자에서 갈라 둔 이유는 검사 때문만이 아니다 — 칸마다 이 내용을 펼치면 격자가 다시
 * 목록이 되고, 격자로 바꾼 이유가 사라진다.
 *
 * @param props 아이템 한 줄.
 * @returns 렌더 트리.
 */
export function ItemDetail(props: { readonly row: CatalogItemRow }): React.JSX.Element {
  const { row } = props
  return (
    <div className="cat__detail">
      <span className="cat__name">{row.labelKo}</span>
      <ValueExpr
        text={`${row.kind}${row.slot === '' ? '' : ` · ${row.slot}`}${row.hands === '' ? '' : ` · ${row.hands}`}${row.attackRange === 0 ? '' : ` · 사거리 ${String(row.attackRange)}`}`}
        size="sm"
        dim
      />
      {row.affixes.length === 0 ? null : <ValueExpr text={row.affixes.join(' · ')} size="sm" />}
      {row.requirements.length === 0 ? null : (
        <ValueExpr text={`요구 ${row.requirements.join(' · ')}`} size="sm" dim />
      )}
      {row.grantsSkill === '' ? null : (
        // 장비가 여는 스킬 (결정 #13). 장비 교체가 규칙 재설계로 이어지는 지점.
        <ValueExpr text={`스킬 ${row.grantsSkill}`} size="sm" />
      )}
    </div>
  )
}

/**
 * 고른 적 하나의 상세.
 *
 * @param props 적 한 줄.
 * @returns 렌더 트리.
 */
export function EnemyDetail(props: { readonly row: CatalogEnemyRow }): React.JSX.Element {
  const { row } = props
  return (
    <div className="cat__detail">
      <span className="cat__name">{row.labelKo}</span>
      <ValueExpr text={row.type} size="sm" dim />
      <ValueExpr
        text={`hp ${String(row.hpMax)} · 공 ${String(row.attack)} · 방 ${String(row.defense)} · 사거리 ${String(row.attackRange)}`}
        size="sm"
      />
      {/* 몬스터의 정체는 스탯이 아니라 규칙표다 (설계/6_몬스터 §2). */}
      <ValueExpr text={`내력 ${row.rulesetId}`} size="sm" dim />
    </div>
  )
}

/**
 * 카탈로그 화면을 그린다.
 *
 * @param props 카탈로그. 관리자가 아니면 undefined 다.
 * @returns 패널 요소. 관리자가 아니면 null.
 */
export function CatalogPanel(props: CatalogPanelProps): React.JSX.Element | null {
  const { catalog } = props
  const [view, setView] = useState<View>('items')
  // 격자는 이름과 자리까지만 담는다. 상세를 칸마다 펼치면 격자가 다시 목록이 되므로,
  // 고른 것 하나만 아래에 편다 — 좁은 화면에서 특히 그렇다. 칸 key 에 계열
  // (`cat:item:`·`cat:enemy:`)이 들어 있어 탭을 옮겨도 엉뚱한 칸이 열리지 않는다.
  const [pickedKey, togglePick] = usePickedKey()
  // 훅은 조기 반환보다 앞에 와야 한다(React 규칙). 카탈로그가 없으면 뒤에서 null 을 낸다.
  if (catalog === undefined) {
    return null
  }
  const itemCells = buildCatalogItemCells(catalog.items)
  const enemyCells = buildCatalogEnemyCells(catalog.enemies)
  const pickedItem = itemCells.find((cell) => cell.key === pickedKey)
  const pickedEnemy = enemyCells.find((cell) => cell.key === pickedKey)
  const peak = Math.max(0, ...catalog.levelCurve.map((row) => row.players))

  return (
    <Panel title="카탈로그" meta={`${catalog.coreVersion} · 읽기 전용`} tone="panel" padded scroll>
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

        <ValueExpr
          text="여기서 고칠 수 없다 — resources 파일을 고쳐 배포한다"
          size="sm"
          dim
        />

        {view === 'items' ? (
          <SlotBoard
            hint="칸을 고르면 접사·요구조건·여는 재주가 뜬다"
            detail={pickedItem === undefined ? undefined : <ItemDetail row={pickedItem.row} />}
          >
            <SlotGrid
              title={`아이템 ${String(itemCells.length)}`}
              shape="free"
              cells={itemCells}
              pickedKey={pickedKey}
              onPick={togglePick}
              emptyText="등록된 아이템이 없다"
            />
          </SlotBoard>
        ) : null}

        {view === 'enemies' ? (
          <SlotBoard
            hint="칸을 고르면 스탯과 내력이 뜬다"
            detail={pickedEnemy === undefined ? undefined : <EnemyDetail row={pickedEnemy.row} />}
          >
            <SlotGrid
              title={`적 ${String(enemyCells.length)}`}
              shape="free"
              cells={enemyCells}
              pickedKey={pickedKey}
              onPick={togglePick}
              emptyText="등록된 적이 없다"
            />
          </SlotBoard>
        ) : null}

        {view === 'curve' ? (
          <>
            <ValueExpr
              text={`표현력 상한 — 슬롯 +${String(catalog.caps.maxBonusRuleSlots)} · CPU +${String(catalog.caps.maxBonusCpu)} · 플래그 +${String(catalog.caps.maxBonusFlags)}`}
              size="sm"
              dim
            />
            <ul className="cat__list">
              {catalog.levelCurve.map((row) => (
                <li className="cat__row" key={row.level}>
                  <span className="cat__name">lv {row.level}</span>
                  <ValueExpr
                    text={`누적 ${String(row.totalXp)} · 슬롯+${String(row.bonusRuleSlots)} · CPU+${String(row.bonusCpu)} · 포인트 ${String(row.statPoints)}`}
                    size="sm"
                    dim
                  />
                  <ValueExpr
                    text={
                      row.players === 0
                        ? '·'
                        : `${formatPeopleBar(row.players, peak)} ${String(row.players)}`
                    }
                    size="sm"
                  />
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </div>
    </Panel>
  )
}
