/**
 * 아이템 초안 바 — 쌓인 조작을 보이고, 사람이 한 번에 낸다 (설계/9_에이전트_운영 §3.2).
 *
 * **올리는 것과 내는 것이 다른 버튼이다.** 예전에는 등록·수정·폐기가 즉시 카탈로그를
 * 바꿨다 — 다른 다섯 자산은 사람이 발행을 눌러야 반영되는데 아이템만 열려 있었고, 그
 * 문으로 에이전트가 들어오면 검토가 사라진다.
 *
 * **세대를 손으로 적어야 눌린다.** 콘텐츠 발행과 같은 규율이다 — 자동으로 +1 하면
 * 관리자가 모르는 값으로 시즌이 갈린다.
 *
 * **못 나가는 줄을 먼저 말한다.** 눌러서 알게 하면 절반이 반영된 상태를 상상하게 된다.
 */
import { useState } from 'react'

import { Button, GlyphState, ValueExpr } from '../ds'
import {
  applyCatalogDiscard,
  applyCatalogPublish,
  type CatalogDraftRow,
  type CatalogDraftView,
} from '../storage/catalogDraft'

const DECIMAL_RADIX = 10

/** 사유의 최소 길이. 서버와 같은 값이다 — 짧으면 원장이 기록이 아니라 알리바이가 된다. */
const MIN_REASON = 4

/** 조작 이름을 사람이 읽는 말로. 서버가 주는 값 그대로를 화면에 적으면 안 읽힌다. */
const ACTION_LABEL: Readonly<Record<string, string>> = {
  item: '등록',
  edit: '수정',
  retire: '폐기',
  restore: '복구',
}

/**
 * 조작 이름을 적는다.
 *
 * @param action 서버가 준 값.
 * @returns 화면에 적을 말. 모르는 값이면 그대로 돌려준다.
 */
export function formatAction(action: string): string {
  return ACTION_LABEL[action] ?? action
}

export interface CatalogDraftBarProps {
  readonly token: string
  readonly view: CatalogDraftView | undefined
  /** 발행이나 버리기가 끝났을 때. 카탈로그와 초안을 함께 다시 읽으라는 신호다. */
  readonly onDone: (detail: string) => void
}

/**
 * 초안 한 줄을 그린다.
 *
 * @param row 그릴 줄.
 * @param onDiscard 버린다.
 * @returns 줄 요소.
 */
function renderRow(row: CatalogDraftRow, onDiscard: (catalogId: string) => void): React.JSX.Element {
  return (
    <div className="adminrow" key={row.catalogId}>
      <span className="adminrow__name">{row.catalogId}</span>
      <span className="adminrow__cell">{formatAction(row.action)}</span>
      <span className="adminrow__cell">{row.handle === '' ? '—' : row.handle}</span>
      <span className="adminrow__cell">{row.reason}</span>
      {/* 못 나가는 줄은 참/거짓을 색으로만 적지 않는다 — 글리프와 글자를 함께 쓴다. */}
      {row.problem === '' ? (
        <span className="adminrow__cell">{row.updatedAt}</span>
      ) : (
        <GlyphState state="danger" size="sm" label={row.problem} />
      )}
      <Button
        size="sm"
        variant="ghost"
        onClick={() => {
          onDiscard(row.catalogId)
        }}
      >
        버림
      </Button>
    </div>
  )
}

/**
 * 초안 바를 그린다.
 *
 * @param props 토큰·초안들·완료 콜백.
 * @returns 렌더 트리.
 */
export function CatalogDraftBar(props: CatalogDraftBarProps): React.JSX.Element {
  const [generation, setGeneration] = useState('')
  const [reason, setReason] = useState('')
  const drafts = props.view?.drafts ?? []
  const wanted = Number.parseInt(generation, DECIMAL_RADIX)
  const blocked = drafts.filter((row) => row.problem !== '').length
  const isReady =
    drafts.length > 0 &&
    blocked === 0 &&
    Number.isFinite(wanted) &&
    wanted === (props.view?.generation ?? -1) &&
    reason.length >= MIN_REASON

  if (drafts.length === 0) {
    return (
      <div className="adm__publish">
        <ValueExpr
          text={`쌓인 아이템 초안이 없다 · 지금 세대 ${String(props.view?.generation ?? 0)}`}
          size="sm"
          dim
        />
      </div>
    )
  }

  return (
    <div className="adm__publish">
      <GlyphState
        state={blocked > 0 ? 'danger' : 'true'}
        size="sm"
        label={
          blocked > 0
            ? `${String(blocked)}건이 지금 카탈로그에 안 맞는다 — 고치거나 버려야 낼 수 있다`
            : `초안 ${String(drafts.length)}건 · 발행하면 세대가 한 번 오르고 순위표 시즌이 갈린다`
        }
      />
      <div className="adminrow adminrow--head" aria-hidden="true">
        <span className="adminrow__name">아이템</span>
        <span className="adminrow__cell">조작</span>
        <span className="adminrow__cell">올린 이</span>
        <span className="adminrow__cell">사유</span>
        <span className="adminrow__cell">올린 때</span>
        <span className="adminrow__cell" />
      </div>
      {drafts.map((row) =>
        renderRow(row, (catalogId) => {
          void applyCatalogDiscard(props.token, catalogId).then((outcome) => {
            props.onDone(outcome.detail)
          })
        }),
      )}
      <div className="cat__row">
        <input
          className="cat__input"
          inputMode="numeric"
          value={generation}
          placeholder={`세대 (지금 ${String(props.view?.generation ?? 0)})`}
          aria-label="발행 세대"
          onChange={(event) => {
            setGeneration(event.target.value)
          }}
        />
        <input
          className="cat__input"
          value={reason}
          placeholder="무엇을 왜 내는가 (4자 이상)"
          aria-label="발행 사유"
          onChange={(event) => {
            setReason(event.target.value)
          }}
        />
        <Button
          size="sm"
          variant="primary"
          glyph="▲"
          disabled={!isReady}
          title="쌓인 아이템 초안을 한 번에 발행한다 — 세대가 한 번 오른다"
          onClick={() => {
            void applyCatalogPublish(props.token, wanted, reason).then((detail) => {
              setGeneration('')
              setReason('')
              props.onDone(detail)
            })
          }}
        >
          발행
        </Button>
      </div>
    </div>
  )
}
