/**
 * 관리자 화면 — 세계에 무슨 일이 벌어지는지 보고, 필요하면 손댄다.
 *
 * **지금까지 세계 상태를 볼 방법이 아예 없었다.** 지속 몬스터가 몇이고 누가 남의 장비를
 * 들고 있는지, 푼이 얼마나 풀렸는지 확인하려면 매번 임시 스크립트를 써야 했다 — 그
 * 상태로는 "세계가 건강한가" 를 아무도 답할 수 없다.
 *
 * **콘텐츠는 여기서 고치지 않는다.** 아이템 카탈로그·레벨 곡선·방 구성은
 * `resources/*.json` 이고 그것은 `core_version` 에 묶여 있다 — 런타임에 바꾸면 이미
 * 발급된 티켓이 다른 게임을 가리키고, 브라우저(빌드에 박힌 JSON)와 서버가 다른 값을 본다.
 * 그래서 카탈로그 수치는 **읽기 전용**으로 적고, 고치는 길은 파일을 고쳐 배포하는 것이다.
 *
 * 관리자가 아니면 서버가 404 로 답하므로 이 패널은 아무것도 그리지 않는다.
 *
 * **목록 여섯이 전부 `DataList` 위에 선다.** 예전에는 여섯이 각자 `ul` 과 빈 문구를 들고
 * 있었고, 그래서 서버가 최대 200줄까지 실어 오는 목록에 페이지도 거르기도 없었다 —
 * 200줄이 한 번에 쏟아진 화면에서 몬스터 하나를 찾는 길은 브라우저 찾기뿐이었다.
 */
import { useState } from 'react'

import { findItemArt } from '../content/itemArt'
import { Button, GlyphState, Panel, ValueExpr } from '../ds'
import type { AdminActionRow, AdminHeldItem, AdminMonsterRow, AdminOverview } from '../storage'

import { DataList } from './DataList'
import { LinkNoticeLine } from './LinkNoticeLine'
import type { LinkState } from './linkState'

export interface AdminPanelProps {
  readonly overview: AdminOverview | undefined
  readonly detail: string
  /**
   * 서버 연결 상태. **안 주면 `online` 이다** — 붙어 있는데 현황이 없다는 것은 404 하나뿐,
   * 곧 "관리자가 아니다" 이므로 그때는 지금처럼 아무것도 그리지 않는다.
   */
  readonly link?: LinkState
  readonly onSetMonsterLevel: (recordId: number, level: number) => void
  /** 되돌릴 수 없는 개입. 사유를 함께 넘긴다. */
  readonly onIntervene: (path: string, targetId: number, reason: string) => void
}

/** 못 닿았을 때 무엇을 못 보는가. 세계는 서버 한 곳에만 있다. */
const MISSING_HINT = '세계 현황은 서버가 센다'

/** 요약에 적을 항목. 순서가 곧 화면 순서다. */
const SUMMARY_ROWS: readonly { readonly key: keyof AdminOverview; readonly label: string }[] = [
  { key: 'accounts', label: '계정' },
  { key: 'registered', label: '가입' },
  { key: 'monstersAlive', label: '지속 몬스터' },
  { key: 'items', label: '아이템' },
  { key: 'itemsBound', label: '귀속' },
  { key: 'itemsHeldByMonsters', label: '몬스터 보유' },
  { key: 'listingsOpen', label: '열린 매물' },
  { key: 'currencyTotal', label: '풀린 푼' },
  { key: 'verifiedRuns', label: '검증된 런' },
]

/** 콘텐츠 수치. 읽기 전용이라 값과 이름만 적는다. */
const CONTENT_ROWS: readonly {
  readonly key: 'catalogItems' | 'enemyKinds'
  readonly label: string
}[] = [
  { key: 'catalogItems', label: '아이템 카탈로그' },
  { key: 'enemyKinds', label: '적 종류' },
]

/**
 * 서버가 목록에 건 상한. 정본은 서버 쪽이며(`game/app/store/world_view.py`·`admin.py`),
 * 여기 적어 두는 이유는 **화면이 "이게 전부다" 와 "여기서 잘렸다" 를 갈라 적어야** 하기
 * 때문이다. 서버 값을 올리면 여기도 함께 올린다.
 */
const MONSTER_CAP = 200
const HELD_CAP = 200
const ACTION_CAP = 50

/** 한 번에 펴 볼 줄 수. */
const PAGE = 20

/** 몬스터는 한 줄이 두 단(현황 + 고침 칸)이라 절반만 편다 — 같은 수로 펴면 두 배 길다. */
const MONSTER_PAGE = 10

/** 요약·콘텐츠는 길이가 고정이라 여기 닿지 않는다. 틀이 요구하는 자리를 채울 뿐이다. */
const NOTHING_TEXT = '적을 것이 없다'

/** 레벨 분포 한 줄. 서버 응답 모양에서 그대로 딴다. */
type LevelRow = AdminOverview['levelCounts'][number]

/**
 * 상한에 닿은 목록에 붙일 말.
 *
 * **잘린 것을 안 적으면 화면이 세계를 줄여 보여 준다.** 계정이 212인데 200줄만 오고,
 * 그 200이 전부인 것처럼 적히면 세계 현황을 보러 온 사람이 틀린 수를 들고 나간다 —
 * 그 순간 이 화면의 존재 이유가 사라진다.
 *
 * @param shown 실제로 온 줄 수.
 * @param cap 서버가 건 상한.
 * @param total 요약이 따로 세어 둔 전체 수. 모르면 undefined.
 * @returns 적을 말. 안 잘렸으면 undefined.
 */
function describeCap(
  shown: number,
  cap: number,
  total: number | undefined,
): string | undefined {
  if (shown < cap) {
    return undefined
  }
  if (total === undefined || total <= shown) {
    return `상한 ${String(cap)}줄에서 잘렸다 — 뒤는 여기서 못 본다`
  }
  return `상한 ${String(cap)}줄에서 잘렸다 — 전체 ${String(total)}줄`
}

/** 잘린 사실 한 줄이 받는 것. */
interface CapNoticeProps {
  readonly shown: number
  readonly cap: number
  /** 요약이 따로 세어 둔 전체 수. 아는 목록에만 준다. */
  readonly total?: number | undefined
}

/**
 * 잘린 사실을 한 줄로 그린다.
 *
 * @param props 온 줄 수와 상한.
 * @returns 렌더 트리. 안 잘렸으면 null.
 */
function CapNotice(props: CapNoticeProps): React.JSX.Element | null {
  const text = describeCap(props.shown, props.cap, props.total)
  if (text === undefined) {
    return null
  }
  // ⧅(수단 없음)다. ◈(위험)를 안 쓰는 이유는 이것이 고장이 아니라 설계된 상한이기
  // 때문이다 — 늘 켜지는 경보를 하나 더 만들면 진짜 경보가 배경이 된다.
  return <GlyphState state="blocked" size="sm" label={text} />
}

/**
 * 관리자 화면을 그린다.
 *
 * @param props 현황과 처리기.
 * @returns 패널 요소. 관리자가 아니면 null.
 */
export function AdminPanel(props: AdminPanelProps): React.JSX.Element | null {
  const { overview, detail } = props
  const link = props.link ?? 'online'
  const [draft, setDraft] = useState<Record<number, string>>({})

  if (overview === undefined) {
    // **현황이 없는 이유가 둘이다.** 붙어 있는데 없으면 404 — 관리자가 아니다. 그때는
    // 빈 패널조차 그리지 않는다(빈 패널이 관리자 경로의 존재를 알려 준다). 못 닿았거나
    // 아직 물어보는 중이면 관리자인지 아닌지 **아직 아무도 모른다** — 예전에는 그 둘까지
    // null 로 접어 「못 닿았다」조차 안 떴고, 화면은 조용히 비어 고장과 구별되지 않았다.
    if (link === 'online') {
      return null
    }
    return (
      <Panel title="관리자" tone="panel" padded>
        <LinkNoticeLine link={link} missing={MISSING_HINT} />
      </Panel>
    )
  }

  return (
    <Panel title="관리자" meta={overview.coreVersion} tone="panel" padded scroll>
      <div className="adm">
        <div className="adm__head">비각 현황</div>
        {/* 아홉 줄이 고정이다. 페이지도 거르기도 켜지 않는다 — 고정 길이 목록에 「더
            보기」가 서면 뒤에 뭔가 더 있다는 거짓말이 된다. */}
        <DataList
          items={SUMMARY_ROWS}
          rowKey={(row) => String(row.key)}
          renderRow={(row) => (
            <>
              <span className="adm__label">{row.label}</span>
              <ValueExpr text={String(overview[row.key])} size="sm" />
            </>
          )}
          emptyText={NOTHING_TEXT}
          listClass="adm__list"
          rowClass="adm__row"
        />

        <div className="adm__head">
          콘텐츠 · 읽기 전용 — 고치려면 resources 파일을 고쳐 배포한다
        </div>
        <DataList
          items={CONTENT_ROWS}
          rowKey={(row) => row.key}
          renderRow={(row) => (
            <>
              <span className="adm__label">{row.label}</span>
              <ValueExpr text={`${String(overview[row.key])}종`} size="sm" dim />
            </>
          )}
          emptyText={NOTHING_TEXT}
          listClass="adm__list"
          rowClass="adm__row"
        />

        <div className="adm__head">플레이어 레벨 분포</div>
        {/* **여기만 상한이 없다.** 서버가 레벨마다 한 줄씩 전부 실어 오므로 곡선이
            길어지는 만큼 줄도 는다 — 그래서 페이지를 켠다. 거르기는 안 켠다: 레벨은
            수라서 「3」을 치면 3·13·23·30…이 함께 걸린다. */}
        <DataList<LevelRow>
          items={overview.levelCounts}
          rowKey={(row) => String(row.level)}
          renderRow={(row) => (
            <>
              <span className="adm__label">레벨 {row.level}</span>
              <ValueExpr text={`${String(row.count)}명`} size="sm" />
            </>
          )}
          emptyText="아직 없다"
          listClass="adm__list"
          rowClass="adm__row"
          pageSize={PAGE}
          showCount
        />

        <div className="adm__head">지속 몬스터 · 장 / 레벨 / 보유</div>
        <DataList<AdminMonsterRow>
          items={overview.monsters}
          rowKey={(row) => String(row.recordId)}
          renderRow={(row) => (
            <>
              <div className="adm__row">
                <GlyphState
                  state={row.alive ? 'true' : 'blocked'}
                  size="sm"
                  label={`${row.catalogId} · ${row.tier}`}
                />
                <ValueExpr
                  text={`${String(row.zoneFloor)}장 · lv ${String(row.level)}/${String(row.levelCap)}`}
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
            </>
          )}
          emptyText="아직 비각에 지속 몬스터가 없다"
          listClass="adm__list"
          rowClass="adm__monster"
          pageSize={MONSTER_PAGE}
          showCount
          // 층과 이름으로 거른다. 「어느 층이 이상한가」가 이 표를 보는 이유이고,
          // 200줄에서 그것을 눈으로 세는 것은 브라우저 찾기와 다르지 않다.
          filterText={(row) => `${row.catalogId} ${String(row.zoneFloor)}장`}
          filterLabel="이름·층으로 거르기"
        />
        <CapNotice shown={overview.monsters.length} cap={MONSTER_CAP} />

        <div className="adm__head">몬스터가 들고 있는 것 · 원주인</div>
        <DataList<AdminHeldItem>
          items={overview.heldItems}
          rowKey={(row) => String(row.itemId)}
          // **무엇을 빼앗겼는지가 카탈로그 id 로만 적혀 있었다.** `sword_short` 는 읽어야
          // 알고, 스무 줄이 되면 아무도 안 읽는다 — 형태는 그림이 먼저 말하고 id 는 옆에
          // 남는다.
          //
          // **`hands` 가 이 응답에 없다.** `/admin/overview` 의 `held_items` 는
          // item_instance 에서 id·원주인·상태만 실어 오므로, 양손 협도가 직검 그림으로
          // 뜬다. 서버 필드라 다음 단계이며, 그때까지는 틀린 칼 한 자루가 글자만 있는
          // 줄보다 낫다. 몬스터가 드는 것은 장비뿐이라(`item_instance`) `useTag` 는
          // 애초에 볼 것이 없다.
          thumb={(row) => ({
            kind: 'EQUIPMENT',
            label: row.catalogId,
            art: findItemArt(row.catalogId),
          })}
          renderRow={(row) => (
            <>
              <span className="adm__label">{row.monsterId}</span>
              <ValueExpr
                text={`${row.catalogId}${row.takenFromHandle === '' ? '' : ` ← ${row.takenFromHandle}`}`}
                size="sm"
              />
              <Button
                size="sm"
                variant="ghost"
                glyph="✕"
                title="비각에서 거둔다. 되돌릴 수 없고 사유가 남는다"
                onClick={() => {
                  const reason = draft[-row.itemId] ?? ''
                  props.onIntervene('/admin/item/recall', row.itemId, reason)
                }}
              >
                회수
              </Button>
              <input
                className="adm__field adm__field--reason"
                type="text"
                placeholder="사유"
                value={draft[-row.itemId] ?? ''}
                onChange={(event) => {
                  setDraft((current) => ({ ...current, [-row.itemId]: event.target.value }))
                }}
              />
            </>
          )}
          emptyText="아직 빼앗긴 장비가 없다"
          listClass="adm__list"
          rowClass="adm__row"
          pageSize={PAGE}
          showCount
          // 원주인으로 거른다 — "내 장비를 누가 들고 있나" 가 회수 문의의 형태다.
          filterText={(row) => `${row.catalogId} ${row.takenFromHandle}`}
          filterLabel="이름·원주인으로 거르기"
        />
        {/* 여기만 전체 수를 안다 — 요약의 `몬스터 보유` 가 상한 없이 센 같은 모집단이다.
            몬스터 목록은 죽은 것까지 실어 오는데 요약은 살아 있는 것만 세므로 그쪽에는
            줄 수 있는 전체가 없다. */}
        <CapNotice
          shown={overview.heldItems.length}
          cap={HELD_CAP}
          total={overview.itemsHeldByMonsters}
        />

        {detail === '' ? null : <ValueExpr text={detail} size="sm" dim />}

        <div className="adm__head">최근 개입 · 손댄 것은 반드시 남는다</div>
        <DataList<AdminActionRow>
          items={overview.recentActions}
          // 시각과 대상이 같은 개입이 둘일 수 있다(같은 초에 두 번 눌린 회수). 값만으로
          // 키를 만들면 React 가 같은 줄로 보고 하나를 지운다.
          rowKey={(item, index) => `${item.createdAt}:${item.target}:${String(index)}`}
          renderRow={(item) => (
            <>
              <span className="adm__label">{item.handle}</span>
              <ValueExpr text={`${item.action} ${item.target} ${item.detail}`} size="sm" dim />
            </>
          )}
          emptyText="아직 손댄 기록이 없다"
          listClass="adm__list"
          rowClass="adm__row"
          pageSize={PAGE}
          showCount
        />
        <CapNotice shown={overview.recentActions.length} cap={ACTION_CAP} />
      </div>
    </Panel>
  )
}
