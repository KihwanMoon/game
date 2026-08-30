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
 */
import { useState } from 'react'

import { Button, Panel, ValueExpr } from '../ds'
import type { AdminCatalog } from '../storage'

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
 * 카탈로그 화면을 그린다.
 *
 * @param props 카탈로그. 관리자가 아니면 undefined 다.
 * @returns 패널 요소. 관리자가 아니면 null.
 */
export function CatalogPanel(props: CatalogPanelProps): React.JSX.Element | null {
  const { catalog } = props
  const [view, setView] = useState<View>('items')
  if (catalog === undefined) {
    return null
  }
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
          <ul className="cat__list">
            {catalog.items.map((row) => (
              <li className="cat__entry" key={row.catalogId}>
                <div className="cat__row">
                  <span className="cat__name">{row.labelKo}</span>
                  <ValueExpr
                    text={`${row.kind}${row.slot === '' ? '' : ` · ${row.slot}`}${row.hands === '' ? '' : ` · ${row.hands}`}`}
                    size="sm"
                    dim
                  />
                </div>
                {row.affixes.length === 0 ? null : (
                  <ValueExpr text={row.affixes.join(' · ')} size="sm" />
                )}
                {row.requirements.length === 0 ? null : (
                  <ValueExpr text={`요구 ${row.requirements.join(' · ')}`} size="sm" dim />
                )}
                {row.grantsSkill === '' ? null : (
                  // 장비가 여는 스킬 (결정 #13). 장비 교체가 규칙 재설계로 이어지는 지점.
                  <ValueExpr text={`스킬 ${row.grantsSkill}`} size="sm" />
                )}
              </li>
            ))}
          </ul>
        ) : null}

        {view === 'enemies' ? (
          <ul className="cat__list">
            {catalog.enemies.map((row) => (
              <li className="cat__entry" key={row.kindId}>
                <div className="cat__row">
                  <span className="cat__name">{row.labelKo}</span>
                  <ValueExpr text={row.type} size="sm" dim />
                </div>
                <ValueExpr
                  text={`hp ${String(row.hpMax)} · 공 ${String(row.attack)} · 방 ${String(row.defense)} · 사거리 ${String(row.attackRange)}`}
                  size="sm"
                />
                {/* 몬스터의 정체는 스탯이 아니라 규칙표다 (설계/6_몬스터 §2). */}
                <ValueExpr text={`규칙표 ${row.rulesetId}`} size="sm" dim />
              </li>
            ))}
          </ul>
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
