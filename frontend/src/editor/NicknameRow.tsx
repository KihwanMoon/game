/**
 * 이름 짓기 한 줄 (2026-09-16).
 *
 * **화면마다 다른 이름이 뜨고 있었다.** 순위표는 아이디를, 둔갑 전적과 관리자 화면은
 * 자동 생성 별명(`user_3f9a…`)을 보여 줬다. 같은 사람이 화면을 옮길 때마다 다른 이름이
 * 되니 「누가 누구인지」가 끊겼다 — 내 둔갑이 남의 장에 서는 게임에서 그것은 기제의
 * 절반을 못 쓰게 만든다.
 *
 * **지금 뜨는 이름을 함께 보여 준다.** 안 정한 사람에게 「이름을 지어라」만 적으면 지금
 * 남들에게 무엇으로 보이는지를 모른 채 고르게 된다.
 */
import { useState } from 'react'

import { Button, GlyphState, ValueExpr } from '../ds'

import type { AccountState } from '../storage'

export interface NicknameRowProps {
  readonly account: AccountState | undefined
  /** 빈 문자열이면 성공이다. */
  readonly onSave: (nickname: string) => Promise<string>
}

/** 안 정했을 때 무엇으로 보이는가. */
const UNSET_HINT = '아직 이름을 안 지었다 — 남에게는 아래 이름으로 보인다'

/**
 * 이름을 보여 주고 고칠 수 있게 한다.
 *
 * @param props 계정과 저장 처리기.
 * @returns 한 줄. 계정을 모르면 null.
 */
export function NicknameRow(props: NicknameRowProps): React.JSX.Element | null {
  const { account } = props
  const [draft, setDraft] = useState('')
  const [isOpen, setOpen] = useState(false)
  const [detail, setDetail] = useState('')
  const [isBusy, setBusy] = useState(false)

  if (account === undefined) {
    return null
  }
  const hasName = account.nickname !== undefined

  function applySave(): void {
    const name = draft.trim()
    if (name === '' || isBusy) {
      return
    }
    setBusy(true)
    setDetail('')
    void props.onSave(name).then((message) => {
      setBusy(false)
      setDetail(message)
      if (message === '') {
        setOpen(false)
        setDraft('')
      }
    })
  }

  return (
    <div className="account__name">
      <GlyphState
        state={hasName ? 'true' : 'pending'}
        size="sm"
        label={hasName ? `이름 · ${account.displayName}` : UNSET_HINT}
      />
      {hasName ? null : <ValueExpr text={account.displayName} size="sm" dim />}
      {isOpen ? (
        <div className="account__name-edit">
          <input
            className="account__field"
            value={draft}
            maxLength={16}
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            placeholder="2~16자 · 한글·영문·숫자"
            aria-label="이름"
            onChange={(event) => {
              setDraft(event.target.value)
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault()
                applySave()
              }
            }}
          />
          <Button size="sm" variant="secondary" disabled={isBusy} onClick={applySave}>
            정하기
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setOpen(false)
              setDetail('')
            }}
          >
            취소
          </Button>
        </div>
      ) : (
        <Button
          size="sm"
          variant="ghost"
          glyph="✎"
          onClick={() => {
            setDraft(account.nickname ?? '')
            setOpen(true)
          }}
        >
          {hasName ? '이름 바꾸기' : '이름 짓기'}
        </Button>
      )}
      {detail === '' ? null : <GlyphState state="danger" size="sm" label={detail} />}
    </div>
  )
}
