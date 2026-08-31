/**
 * 콘텐츠 초안 편집 (설계/4_아이템 §16).
 *
 * **여기서 게임이 바뀌지 않는다.** 스킬·블록·밸런스·룸·적 규칙표는 두 코어가 함께 읽는
 * 실행 자산이고, 브라우저는 빌드 시점에 번들로 인라인한다. 저장은 초안일 뿐이고, 반영은
 * 운영자가 파일로 내보내 커밋·배포해야 끝난다 — 그 사실을 **화면이 먼저 말한다.**
 *
 * 편집은 **지금 파일에서 시작한다.** 백지에서 쓰게 하면 관리자가 손으로 옮겨 적게 되고,
 * 그 순간 오타가 콘텐츠가 된다.
 *
 * 절 편집기가 JSON 텍스트인 것은 임시 방편이 아니다. 이 자산들은 JSON 파일이고, 서버가
 * **코어의 로더로** 읽어 보고 사유를 그대로 돌려준다 — 화면이 따로 문법을 아는 것보다
 * 그쪽이 정확하다.
 */
import { useState } from 'react'

import { Button, GlyphState, Panel, ValueExpr } from '../ds'
import type { ContentAssetView, ContentDraftView } from '../storage'

export interface ContentAdminPanelProps {
  readonly content: ContentDraftView | undefined
  readonly asset: ContentAssetView | undefined
  readonly detail: string
  readonly onOpen: (asset: string) => void
  readonly onSave: (asset: string, text: string, note: string) => void
  readonly onDiscard: (asset: string, note: string) => void
}

const OFFLINE_HINT = '서버에 닿지 못했다 — 콘텐츠는 서버가 안다'

/**
 * 절을 사람이 읽는 JSON 으로 굽는다.
 *
 * @param value 절.
 * @returns 들여쓴 JSON. 없으면 빈 문자열.
 */
export function formatDraftText(value: unknown): string {
  return value === null || value === undefined ? '' : JSON.stringify(value, null, 2)
}

/**
 * 콘텐츠 편집 화면을 그린다.
 *
 * @param props 초안 목록·연 자산·콜백.
 * @returns 패널 요소.
 */
export function ContentAdminPanel(props: ContentAdminPanelProps): React.JSX.Element {
  const { content, asset } = props
  const [text, setText] = useState('')
  const [note, setNote] = useState('')
  const [openId, setOpenId] = useState('')

  if (content === undefined) {
    return (
      <Panel title="콘텐츠 편집" tone="panel" padded>
        <ValueExpr text={OFFLINE_HINT} size="sm" dim />
      </Panel>
    )
  }

  return (
    <Panel
      title="콘텐츠 편집"
      meta={`초안 ${String(content.drafts.length)}건`}
      tone="panel"
      padded
      scroll
    >
      <div className="cat">
        {/* **반영이 자동이 아니라는 것을 먼저 말한다.** 자동인 줄 알면 관리자가 시즌을
            모르게 가른다. */}
        <GlyphState state="danger" size="sm" label={content.publishHint} />
        {props.detail === '' ? null : <ValueExpr text={props.detail} size="sm" />}

        <div className="cat__tabs">
          {content.assets.map((name) => (
            <Button
              key={name}
              size="sm"
              variant={name === openId ? 'primary' : 'ghost'}
              onClick={() => {
                setOpenId(name)
                setText('')
                props.onOpen(name)
              }}
            >
              {name}
            </Button>
          ))}
        </div>

        <ul className="cat__list">
          {content.drafts.map((row) => (
            <li className="cat__entry" key={row.asset}>
              <div className="cat__row">
                <span className="cat__name">{row.asset}</span>
                <ValueExpr
                  text={`파일 세대 ${String(row.currentVersion)} · ${row.updatedAt}`}
                  size="sm"
                  dim
                />
              </div>
              <ValueExpr text={row.note} size="sm" />
              <Button
                size="sm"
                variant="ghost"
                title="초안을 버린다 — 파일은 안 건드린다"
                onClick={() => {
                  props.onDiscard(row.asset, note)
                }}
              >
                초안 버리기
              </Button>
            </li>
          ))}
        </ul>

        {asset === undefined ? null : (
          <div className="cat__detail">
            <span className="cat__name">{asset.asset}</span>
            <ValueExpr
              text={`${asset.versionKey} 를 올려야 저장된다 — 안 올리면 저장된 리플레이가 거짓이 된다`}
              size="sm"
              dim
            />
            <textarea
              className="cnt__editor"
              aria-label={`${asset.asset} 절`}
              value={text === '' ? formatDraftText(asset.draft ?? asset.current) : text}
              onChange={(event) => {
                setText(event.target.value)
              }}
            />
            <label className="cat__field">
              <span>사유</span>
              <input
                className="cat__input"
                value={note}
                placeholder="무엇을 왜 고치는가 (4자 이상)"
                onChange={(event) => {
                  setNote(event.target.value)
                }}
              />
            </label>
            <Button
              size="sm"
              variant="primary"
              title="초안으로 저장한다 — 게임에는 아직 반영되지 않는다"
              onClick={() => {
                props.onSave(
                  asset.asset,
                  text === '' ? formatDraftText(asset.draft ?? asset.current) : text,
                  note,
                )
              }}
            >
              초안 저장
            </Button>
          </div>
        )}
      </div>
    </Panel>
  )
}
