/**
 * 관리자 화면 — 세계에 무슨 일이 벌어지는지 보고, 필요하면 손댄다.
 *
 * **지금까지 세계 상태를 볼 방법이 아예 없었다.** 지속 몬스터가 몇이고 누가 남의 장비를
 * 들고 있는지, 화폐가 얼마나 풀렸는지 확인하려면 매번 임시 스크립트를 써야 했다 — 그
 * 상태로는 "세계가 건강한가" 를 아무도 답할 수 없다.
 *
 * **콘텐츠는 여기서 고치지 않는다.** 아이템 카탈로그·레벨 곡선·방 구성은
 * `resources/*.json` 이고 그것은 `core_version` 에 묶여 있다 — 런타임에 바꾸면 이미
 * 발급된 티켓이 다른 게임을 가리키고, 브라우저(빌드에 박힌 JSON)와 서버가 다른 값을 본다.
 * 그래서 카탈로그 수치는 **읽기 전용**으로 적고, 고치는 길은 파일을 고쳐 배포하는 것이다.
 *
 * 관리자가 아니면 서버가 404 로 답하므로 이 패널은 아무것도 그리지 않는다.
 */
import { useState } from 'react'

import { Button, GlyphState, Panel, ValueExpr } from '../ds'
import type { AdminOverview } from '../storage'

export interface AdminPanelProps {
  readonly overview: AdminOverview | undefined
  readonly detail: string
  readonly onSetMonsterLevel: (recordId: number, level: number) => void
}

/** 요약에 적을 항목. 순서가 곧 화면 순서다. */
const SUMMARY_ROWS: readonly { readonly key: keyof AdminOverview; readonly label: string }[] = [
  { key: 'accounts', label: '계정' },
  { key: 'registered', label: '가입' },
  { key: 'monstersAlive', label: '지속 몬스터' },
  { key: 'items', label: '아이템' },
  { key: 'itemsBound', label: '귀속' },
  { key: 'itemsHeldByMonsters', label: '몬스터 보유' },
  { key: 'listingsOpen', label: '열린 매물' },
  { key: 'currencyTotal', label: '풀린 화폐' },
  { key: 'verifiedRuns', label: '검증된 런' },
]

/**
 * 관리자 화면을 그린다.
 *
 * @param props 현황과 처리기.
 * @returns 패널 요소. 관리자가 아니면 null.
 */
export function AdminPanel(props: AdminPanelProps): React.JSX.Element | null {
  const { overview, detail } = props
  const [draft, setDraft] = useState<Record<number, string>>({})
  if (overview === undefined) {
    return null
  }

  return (
    <Panel title="관리자" meta={overview.coreVersion} tone="panel" padded scroll>
      <div className="adm">
        <div className="adm__head">세계 현황</div>
        <ul className="adm__list">
          {SUMMARY_ROWS.map((row) => (
            <li className="adm__row" key={String(row.key)}>
              <span className="adm__label">{row.label}</span>
              <ValueExpr text={String(overview[row.key])} size="sm" />
            </li>
          ))}
        </ul>

        <div className="adm__head">
          콘텐츠 · 읽기 전용 — 고치려면 resources 파일을 고쳐 배포한다
        </div>
        <ul className="adm__list">
          <li className="adm__row">
            <span className="adm__label">아이템 카탈로그</span>
            <ValueExpr text={`${String(overview.catalogItems)}종`} size="sm" dim />
          </li>
          <li className="adm__row">
            <span className="adm__label">적 종류</span>
            <ValueExpr text={`${String(overview.enemyKinds)}종`} size="sm" dim />
          </li>
        </ul>

        <div className="adm__head">플레이어 레벨 분포</div>
        {overview.levelCounts.length === 0 ? (
          <ValueExpr text="아직 없다" size="sm" dim />
        ) : (
          <ul className="adm__list">
            {overview.levelCounts.map((row) => (
              <li className="adm__row" key={row.level}>
                <span className="adm__label">레벨 {row.level}</span>
                <ValueExpr text={`${String(row.count)}명`} size="sm" />
              </li>
            ))}
          </ul>
        )}

        <div className="adm__head">지속 몬스터 · 층 / 레벨 / 보유</div>
        {overview.monsters.length === 0 ? (
          <ValueExpr text="아직 세계에 지속 몬스터가 없다" size="sm" dim />
        ) : (
          <ul className="adm__list">
            {overview.monsters.map((row) => (
              <li className="adm__monster" key={row.recordId}>
                <div className="adm__row">
                  <GlyphState
                    state={row.alive ? 'true' : 'blocked'}
                    size="sm"
                    label={`${row.catalogId} · ${row.tier}`}
                  />
                  <ValueExpr
                    text={`층${String(row.zoneFloor)} · lv ${String(row.level)}/${String(row.levelCap)}`}
                    size="sm"
                  />
                  {row.heldItems === 0 ? null : (
                    // 남의 장비를 들고 있는 것이 되찾으러 가는 동기다 (§5).
                    <ValueExpr text={`아이템 ${String(row.heldItems)}`} size="sm" dim />
                  )}
                </div>
                <div className="adm__row">
                  <input
                    className="adm__field"
                    type="number"
                    min={1}
                    max={row.levelCap}
                    placeholder={String(row.level)}
                    value={draft[row.recordId] ?? ''}
                    onChange={(event) => {
                      setDraft((current) => ({ ...current, [row.recordId]: event.target.value }))
                    }}
                  />
                  <Button
                    size="sm"
                    variant="secondary"
                    glyph="✎"
                    title={`1 이상 ${String(row.levelCap)} 이하. 넘기면 폭주 방지가 뚫린다`}
                    onClick={() => {
                      const next = Number(draft[row.recordId])
                      if (Number.isFinite(next) && next > 0) {
                        props.onSetMonsterLevel(row.recordId, next)
                      }
                    }}
                  >
                    레벨 고침
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}

        {detail === '' ? null : <ValueExpr text={detail} size="sm" dim />}

        <div className="adm__head">최근 개입 · 손댄 것은 반드시 남는다</div>
        {overview.recentActions.length === 0 ? (
          <ValueExpr text="아직 손댄 기록이 없다" size="sm" dim />
        ) : (
          <ul className="adm__list">
            {overview.recentActions.map((item) => (
              <li className="adm__row" key={`${item.createdAt}:${item.target}`}>
                <span className="adm__label">{item.handle}</span>
                <ValueExpr text={`${item.action} ${item.target} ${item.detail}`} size="sm" dim />
              </li>
            ))}
          </ul>
        )}
      </div>
    </Panel>
  )
}
