/**
 * 발행 바 — 쌓인 초안을 한 번에 낸다 (설계/4_아이템 §18).
 *
 * **편집과 갈라 둔다.** 발행은 순위표 시즌을 가르는 행위라, 편집과 같은 버튼이면 안 된다.
 *
 * **세대를 손으로 적어야 눌린다.** 자동으로 +1 하면 여러 자산을 한 번에 낼 때 세대가
 * 몇이 될지 관리자가 모르고, 모르는 값으로 시즌이 갈린다.
 */
import { useState } from 'react'

import { Button, GlyphState, ValueExpr } from '../ds'
import { applyContentPublish, type ContentDraftView } from '../storage'

export interface PublishBarProps {
  readonly token: string
  /** 쌓인 초안 수. 없으면 낼 것이 없다. */
  readonly drafts: number
  readonly onDone: (view: ContentDraftView | undefined, detail: string) => void
}

const DECIMAL_RADIX = 10

/**
 * 발행 바를 그린다.
 *
 * @param props 토큰·초안 수·완료 콜백.
 * @returns 렌더 트리.
 */
export function PublishBar(props: PublishBarProps): React.JSX.Element {
  const [generation, setGeneration] = useState('')
  const [note, setNote] = useState('')
  const wanted = Number.parseInt(generation, DECIMAL_RADIX)
  const isReady = props.drafts > 0 && Number.isFinite(wanted) && wanted > 0 && note.length >= 4

  return (
    <div className="adm__publish">
      <GlyphState
        state="danger"
        size="sm"
        label={`발행하면 코어 버전이 바뀐다 — 순위표 시즌이 갈린다 · 초안 ${String(props.drafts)}건`}
      />
      <div className="cat__row">
        <input
          className="cat__input"
          inputMode="numeric"
          value={generation}
          placeholder="세대"
          aria-label="발행 세대"
          onChange={(event) => {
            setGeneration(event.target.value)
          }}
        />
        <input
          className="cat__input"
          value={note}
          placeholder="무엇을 왜 내는가 (4자 이상)"
          aria-label="발행 사유"
          onChange={(event) => {
            setNote(event.target.value)
          }}
        />
        <Button
          size="sm"
          variant="primary"
          glyph="▲"
          disabled={!isReady}
          title="쌓인 초안을 한 번에 발행한다 — 서버가 곧바로 그 데이터로 돈다"
          onClick={() => {
            void applyContentPublish(props.token, wanted, note).then((outcome) => {
              props.onDone(outcome.view, outcome.detail)
              if (outcome.detail === '') {
                setGeneration('')
                setNote('')
              }
            })
          }}
        >
          발행
        </Button>
      </div>
      {props.drafts > 0 ? null : <ValueExpr text="낼 초안이 없다" size="sm" dim />}
    </div>
  )
}
