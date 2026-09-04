/**
 * 관리 화면 — 게임 화면과 갈라진 페이지 (`/admin.html`).
 *
 * **관리자가 아니면 아무것도 안 그린다.** 관리 API 는 404 로 답하므로, 이 화면이 할 수
 * 있는 말은 "여기엔 아무것도 없다" 하나뿐이다 — 무엇이 없는지도 말하지 않는다.
 *
 * 발행 버튼이 편집과 갈라져 있다. **발행은 시즌을 가르는 행위**라 편집과 같은 버튼이면
 * 안 되고, 세대를 손으로 적어야 눌린다 (설계/4_아이템 §18).
 */
import { useEffect, useState } from 'react'

import { EnemyRuleEditor } from './EnemyRuleEditor'
import { RoomGrid } from './RoomGrid'
import { SkillTable } from './SkillTable'
import { ValueTree } from './ValueTree'
import { PublishBar } from './PublishBar'
import { readActivePack } from '../content/pack'
import { ALL_ITEM_TAGS, ALL_SKILL_IDS } from '../core/resources'
import { BENCHMARK_RULESETS, G0_RULESETS } from '../core/resources'
import { Button, GlyphState, Panel, ValueExpr } from '../ds'
import { BotDetailPanel } from './BotDetail'
import { DoppelPanel } from './DoppelPanel'
import { ReplayView } from './ReplayView'
import { BotPanel } from './BotPanel'
import { readInventory, type InventoryView } from '../storage'
import {
  applyBotGift,
  applyBotSettings,
  readBotAdmin,
  readBotBag,
  readBotDetail,
  readDoppelDetail,
  readReplay,
  readDoppelGear,
  type BotOverview,
} from '../storage/botAdmin'
import { CatalogAdminPanel, ContentAdminPanel } from '../editor'
import {
  applyCatalogAdmin,
  applyContentAdmin,
  ensureToken,
  getLocalStorage,
  readAdminItems,
  readContentAdmin,
  readContentAsset,
  type BotDetail,
  type DoppelDetail,
  type ReplayInput,
  type CatalogAdminView,
  type ContentAssetView,
  type ContentDraftView,
} from '../storage'

/** 사람 화면과 같은 밸런스를 본다 — 다른 값을 보면 캐릭터 탭이 다른 것을 그린다. */
const PLAYER_BASE = (readActivePack().balance as Record<string, unknown>).player as Record<
  string,
  number
>

type Tab = 'balance' | 'enemies' | 'skills' | 'rooms' | 'catalog' | 'bots' | 'doppel' | 'content'

const TABS: readonly { readonly id: Tab; readonly label: string }[] = [
  { id: 'balance', label: '밸런스' },
  { id: 'enemies', label: '적 규칙표' },
  { id: 'skills', label: '스킬' },
  { id: 'rooms', label: '룸' },
  { id: 'catalog', label: '아이템' },
  // 봇은 우리가 들인 것이라 우리가 봐야 한다 (T11). 표시만 하고 보는 자리가 없으면
  // 「몇 마리가 무엇을 하고 있는지」를 DB 로만 알 수 있고, 그러면 아무도 안 본다.
  { id: 'bots', label: '봇' },
  { id: 'doppel', label: '도플갱어' },
  // 원문은 마지막이다. 드물고 위험한 일에 쓰는 탈출구이지 기본 도구가 아니다.
  { id: 'content', label: '원문' },
]

const EMPTY_HINT = '여기엔 아무것도 없다'

/**
 * 봇에게 줄 수 있는 규칙표들.
 *
 * **자산에서 읽는다.** 목록을 손으로 적으면 규칙표를 늘렸을 때 관리 화면만 모르게 되고,
 * 없는 id 를 고르면 그 봇은 영영 안 논다.
 */
const RULESET_IDS: readonly string[] = [
  ...BENCHMARK_RULESETS.keys(),
  ...G0_RULESETS.keys(),
].sort()

/**
 * 연 자산의 절을 꺼낸다.
 *
 * **초안이 있으면 초안을 준다.** 지금 파일을 주면 방금 한 편집이 사라진다 — 콘텐츠
 * 편집기와 같은 규약이다.
 *
 * @param asset 서버가 준 자산 절.
 * @param wanted 지금 탭이 원하는 자산.
 * @returns 편집기에 넣을 절. 아직 안 읽었으면 undefined.
 */
function readAssetFile(
  asset: ContentAssetView | undefined,
  wanted: string,
): Record<string, unknown> | undefined {
  if (asset === undefined || asset.asset !== wanted) {
    return undefined
  }
  return (asset.draft ?? asset.current) as Record<string, unknown>
}

/**
 * 관리 화면을 그린다.
 *
 * @returns 화면 요소.
 */
export function AdminScreen(): React.JSX.Element {
  const [token, setToken] = useState<string | undefined>(undefined)
  const [tab, setTab] = useState<Tab>('balance')
  const [content, setContent] = useState<ContentDraftView | undefined>(undefined)
  const [asset, setAsset] = useState<ContentAssetView | undefined>(undefined)
  const [catalog, setCatalog] = useState<CatalogAdminView | undefined>(undefined)
  const [detail, setDetail] = useState('')
  const [bots, setBots] = useState<BotOverview | undefined>(undefined)
  const [botBag, setBotBag] = useState<InventoryView | undefined>(undefined)
  // 고른 봇의 규칙표·성장·스킬·지나간 판. 가방과 따로인 것은 가방이 이미 사람 화면과
  // 같은 라우트를 쓰고 있어서다.
  const [botDetail, setBotDetail] = useState<BotDetail | undefined>(undefined)
  // 고른 도플갱어. **봇과 갈라 둔다** — 계정과 얼려 둔 개체 기록은 다른 것이다.
  const [doppelDetail, setDoppelDetail] = useState<DoppelDetail | undefined>(undefined)
  // 지금 다시 돌리고 있는 판. **입력이지 기록이 아니다** — 코어가 결정론이라 같은
  // 입력이면 같은 판이 나온다 (R5·G3).
  const [replay, setReplay] = useState<ReplayInput | undefined>(undefined)
  const [myBag, setMyBag] = useState<InventoryView | undefined>(undefined)
  const [doppelGear, setDoppelGear] = useState<InventoryView | undefined>(undefined)

  useEffect(() => {
    let isCurrent = true
    void (async () => {
      const found = await ensureToken(getLocalStorage())
      if (!isCurrent || found === undefined) {
        return
      }
      setToken(found)
      setContent(await readContentAdmin(found))
      setCatalog(await readAdminItems(found))
    })()
    return () => {
      isCurrent = false
    }
  }, [])

  if (token === undefined || (content === undefined && catalog === undefined)) {
    return (
      <div className="adm">
        <Panel title="관리" tone="panel" padded>
          <ValueExpr text={EMPTY_HINT} size="sm" dim />
        </Panel>
      </div>
    )
  }

  /**
   * 콘텐츠 초안을 저장하거나 버린다.
   *
   * @param path 라우트 경로.
   * @param name 자산 이름.
   * @param text 절의 JSON. 버리기는 빈 문자열.
   * @param note 사유.
   */
  function applyContent(path: string, name: string, text: string, note: string): void {
    if (token === undefined) {
      return
    }
    let payload: unknown = {}
    if (text !== '') {
      try {
        payload = JSON.parse(text)
      } catch (error) {
        setDetail(`JSON 이 아니다 — ${String(error)}`)
        return
      }
    }
    setDetail('')
    void applyContentAdmin(token, path, { asset: name, payload, note }).then((outcome) => {
      setDetail(outcome.detail)
      if (outcome.view !== undefined) {
        setContent(outcome.view)
        void readContentAsset(token, name).then(setAsset)
      }
    })
  }

  return (
    <div className="adm">
      {/* **재생은 화면을 덮는다.** 판 하나를 도는 동안 뒤의 표를 볼 이유가 없고, 전투
          화면은 제 높이를 다 써야 도면과 로그가 함께 선다. */}
      {replay === undefined ? null : (
        <ReplayView
          replay={replay}
          onClose={() => {
            setReplay(undefined)
          }}
        />
      )}
      <header className="adm__bar">
        <span className="adm__title">관리</span>
        <ValueExpr text={`코어 ${readActivePack().coreVersion}`} size="sm" dim />
        <div className="adm__tabs">
          {TABS.map((item) => (
            <Button
              key={item.id}
              size="sm"
              variant={item.id === tab ? 'primary' : 'ghost'}
              onClick={() => {
                setTab(item.id)
                // 탭을 열 때 그 자산을 읽어 둔다. 안 읽으면 편집기가 빈 채로 뜨고,
                // 그러면 "여기서 뭘 고치라는 거지" 가 된다.
                if (item.id === 'balance') {
                  void readContentAsset(token, 'balance').then(setAsset)
                } else if (item.id === 'enemies' || item.id === 'skills' || item.id === 'rooms') {
                  void readContentAsset(token, item.id).then(setAsset)
                } else if (item.id === 'bots') {
                  void readBotAdmin(token).then(setBots)
                  // 내 가방을 함께 읽는다. 넘길 것을 고르려면 무엇이 있는지 보여야 한다.
                  void readInventory(token).then(setMyBag)
                }
              }}
            >
              {item.label}
            </Button>
          ))}
        </div>
      </header>

      {detail === '' ? null : (
        <div className="adm__notice">
          <GlyphState state="danger" size="sm" label={detail} />
        </div>
      )}

      <PublishBar
        token={token}
        drafts={content?.drafts.length ?? 0}
        onDone={(next, said) => {
          setDetail(said)
          setContent(next)
        }}
      />

      <div className="adm__body">
        {tab === 'balance' ? (
          <ValueTree
            file={readAssetFile(asset, 'balance')}
            title="밸런스 · 몬스터 스탯"
            onSave={(text, note) => {
              applyContent('/admin/content/draft', 'balance', text, note)
            }}
          />
        ) : tab === 'skills' ? (
          <SkillTable
            file={readAssetFile(asset, 'skills')}
            onSave={(text, note) => {
              applyContent('/admin/content/draft', 'skills', text, note)
            }}
          />
        ) : tab === 'rooms' ? (
          <RoomGrid
            file={readAssetFile(asset, 'rooms')}
            onSave={(text, note) => {
              applyContent('/admin/content/draft', 'rooms', text, note)
            }}
          />
        ) : tab === 'enemies' ? (
          <EnemyRuleEditor
            file={readAssetFile(asset, 'enemies')}
            onSave={(text, note) => {
              applyContent('/admin/content/draft', 'enemies', text, note)
            }}
          />
        ) : tab === 'bots' ? (
          <BotPanel
            overview={bots}
            rulesetIds={RULESET_IDS}
            myBag={myBag}
            onPickBot={(accountId) => {
              setBotBag(undefined)
              setBotDetail(undefined)
              void readBotBag(token, accountId).then(setBotBag)
              void readBotDetail(token, accountId).then(setBotDetail)
            }}
            onGift={(accountId, itemId) => {
              void applyBotGift(token, accountId, itemId).then((updated) => {
                if (updated === undefined) {
                  setDetail('넘기지 못했다 — 내 가방에 없거나, 받는 쪽이 봇이 아니다')
                  return
                }
                setBots(updated)
                setDetail('넘겼다 — 그 아이템은 귀속되어 돌아오지 않는다')
                // 두 가방을 다시 읽는다. 안 읽으면 넘긴 물건이 양쪽에 그대로 보인다.
                void readBotBag(token, accountId).then(setBotBag)
                void readInventory(token).then(setMyBag)
              })
            }}
            onSave={(next) => {
              void applyBotSettings(token, next).then((updated) => {
                if (updated === undefined) {
                  setDetail('봇을 고치지 못했다 — 서버에 닿지 못했거나 없는 봇이다')
                  return
                }
                setBots(updated)
                setDetail('')
              })
            }}
            // **봇 하나를 사람 화면과 같은 눈으로 연다.** 표는 봇 떼를 다루고, 이것은
            // 고른 하나를 연다 — 규칙표 둘, 캐릭터, 가방, 스킬, 지나간 판. 자리는
            // 표 바로 아래다: 뒤에 두었더니 도플갱어와 두 가방에 묻혔다.
            detail={
              <BotDetailPanel
                detail={botDetail}
                bag={botBag}
                baseStats={PLAYER_BASE}
                allSkills={ALL_SKILL_IDS}
                allItems={ALL_ITEM_TAGS}
                onPlay={(submissionId) => {
                  setReplay(undefined)
                  void readReplay(token, submissionId).then(setReplay)
                }}
              />
            }
          />
        ) : tab === 'doppel' ? (
          <DoppelPanel
            overview={bots}
            detail={doppelDetail}
            gear={doppelGear}
            onPick={(recordId) => {
              setDoppelDetail(undefined)
              setDoppelGear(undefined)
              void readDoppelDetail(token, recordId).then(setDoppelDetail)
              void readDoppelGear(token, recordId).then(setDoppelGear)
            }}
          />
        ) : tab === 'content' ? (
          <ContentAdminPanel
              content={content}
              asset={asset}
              detail=""
              onOpen={(name) => {
                void readContentAsset(token, name).then(setAsset)
              }}
              onSave={(name, text, note) => {
                applyContent('/admin/content/draft', name, text, note)
              }}
              onDiscard={(name, note) => {
                applyContent('/admin/content/discard', name, '', note)
              }}
            />
        ) : (
          <CatalogAdminPanel
            catalog={catalog}
            detail=""
            onRetire={(catalogId, isRetired, reason) => {
              void applyCatalogAdmin(token, '/admin/catalog/retire', {
                catalog_id: catalogId,
                is_retired: isRetired,
                reason,
              }).then((outcome) => {
                setDetail(outcome.detail)
                if (outcome.view !== undefined) {
                  setCatalog(outcome.view)
                }
              })
            }}
            onEdit={(catalogId, patch, reason) => {
              // **고칠 수 있는 것만 보낸다.** 절에 분류·슬롯을 담을 자리가 없으므로
              // 소급 수정이 표현 불가능하다 (설계/4_아이템 §15.11).
              void applyCatalogAdmin(token, '/admin/catalog/edit', {
                catalog_id: catalogId,
                ...patch,
                reason,
              }).then((outcome) => {
                setDetail(outcome.detail)
                if (outcome.view !== undefined) {
                  setCatalog(outcome.view)
                }
              })
            }}
            onCreate={(payload, reason) => {
              // 접사는 폼이 이미 절로 만들어 준다 — JSON 을 손으로 치던 때는 따옴표
              // 하나가 틀리면 파서 이야기를 사유로 받았다.
              void applyCatalogAdmin(token, '/admin/catalog/item', {
                ...payload,
                reason,
              }).then((outcome) => {
                setDetail(outcome.detail)
                if (outcome.view !== undefined) {
                  setCatalog(outcome.view)
                }
              })
            }}
          />
        )}
      </div>
    </div>
  )
}
