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
import { Button, GlyphState, Panel, ValueExpr } from '../ds'
import { CatalogAdminPanel, ContentAdminPanel } from '../editor'
import {
  applyCatalogAdmin,
  applyContentAdmin,
  ensureToken,
  getLocalStorage,
  readAdminItems,
  readContentAdmin,
  readContentAsset,
  type CatalogAdminView,
  type ContentAssetView,
  type ContentDraftView,
} from '../storage'

type Tab = 'balance' | 'enemies' | 'skills' | 'rooms' | 'catalog' | 'content'

const TABS: readonly { readonly id: Tab; readonly label: string }[] = [
  { id: 'balance', label: '밸런스' },
  { id: 'enemies', label: '적 규칙표' },
  { id: 'skills', label: '스킬' },
  { id: 'rooms', label: '룸' },
  { id: 'catalog', label: '아이템' },
  // 원문은 마지막이다. 드물고 위험한 일에 쓰는 탈출구이지 기본 도구가 아니다.
  { id: 'content', label: '원문' },
]

const EMPTY_HINT = '여기엔 아무것도 없다'

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
