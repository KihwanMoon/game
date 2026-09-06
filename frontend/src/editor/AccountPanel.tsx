/**
 * 계정 패널 — 익명으로 놀다 가입하고, 다른 기기에서 불러온다.
 *
 * **가입은 승격이다.** 계정 id 가 바뀌지 않으므로 지금까지의 진행이 전부 따라온다.
 * 화면이 그것을 말해 주지 않으면 사람은 "가입하면 처음부터 다시" 라고 읽고 가입하지 않는다.
 *
 * 로그인은 **그 계정의 기록을 불러온다.** 이 기기에 남아 있던 익명 진행은 따라오지
 * 않으므로, 익명 상태에서 쌓은 것이 있으면 먼저 경고한다 — 되돌릴 수 없는 자리다.
 *
 * 모바일에서도 같은 부품을 쓴다. 자체 브레이크포인트를 두지 않고 토큰만 쓰며, 입력 칸과
 * 버튼 높이는 `--btn-tap-h` 가 정한다 (터치 레이아웃에서 44px).
 */
import { useState } from 'react'

import { Button, GlyphState, Panel, ValueExpr } from '../ds'
import type { AccountState } from '../storage'

import { checkLinked, describeLink, type LinkState } from './linkState'

export interface AccountPanelProps {
  readonly account: AccountState | undefined
  /** 서버에 닿지 못했으면 false. 그래도 게임은 돈다. */
  readonly link: LinkState
  /** 이 기기에 남아 있는 진행. 로그인 경고를 띄울지 판단한다. */
  readonly hasLocalProgress: boolean
  readonly onRegister: (loginId: string, password: string) => Promise<string>
  readonly onLogin: (loginId: string, password: string) => Promise<string>
  /**
   * 이 기기에서 로그아웃한다.
   *
   * **이 기기의 저장도 함께 지운다.** 토큰만 지우면 다음 사람이 이 기기를 열었을 때
   * 앞사람의 규칙표를 보게 된다.
   */
  readonly onLogout: () => void
  /**
   * 내 빌드가 남의 던전에 그림자로 서도 되는지 정한다 (설계/6_몬스터).
   *
   * **기본은 꺼져 있다.** 그림자는 내 규칙표로 싸우므로, 관전하며 행동을 보면 내 해답이
   * 어느 정도 역산된다 — 켜는 사람이 알고 켜야 하는 대가다.
   */
  readonly onDoppelOptIn?: (isOn: boolean) => void
}

type Mode = 'idle' | 'register' | 'login'

/** 못 닿았을 때 무엇이 어떻게 되는가. 앞머리는 linkState 가 든다. */
const MISSING_HINT = '진행은 이 기기에 남는다'
const ANONYMOUS_TEXT = '익명 — 이 기기에만 남는다'
const SINGLE_DEVICE_HINT =
  '한 계정은 한 기기다 — 다른 기기에서 로그인하면 이 기기는 로그아웃된다'

const PROMOTE_HINT = '가입해도 지금까지의 기록은 그대로 따라온다'
const LOGIN_WARNING = '로그인하면 이 기기의 익명 기록은 따라오지 않는다'

/**
 * 계정 패널을 그린다.
 *
 * @param props 계정 상태와 처리기.
 * @returns 패널 요소.
 */
export function AccountPanel(props: AccountPanelProps): React.JSX.Element {
  const { account, link, hasLocalProgress } = props
  const isOnline = checkLinked(link)
  const [mode, setMode] = useState<Mode>('idle')
  const [loginId, setLoginId] = useState('')
  const [password, setPassword] = useState('')
  const [detail, setDetail] = useState('')
  const [isBusy, setBusy] = useState(false)

  const isRegistered = account?.loginId !== undefined
  const canSubmit = loginId.trim() !== '' && password !== '' && !isBusy

  /**
   * 열린 서식을 닫고 입력을 비운다.
   */
  function resetForm(): void {
    setMode('idle')
    setLoginId('')
    setPassword('')
    setDetail('')
  }

  /**
   * 서식을 보낸다.
   *
   * `Button` 계약에 `type` 이 없으므로 제출은 이 함수가 직접 맡는다. `<form>` 을 그대로
   * 두는 이유는 모바일이다 — 자동완성과 키보드의 확인 키가 form 을 보고 붙는다.
   */
  function applySubmit(): void {
    if (!canSubmit) {
      return
    }
    setBusy(true)
    setDetail('')
    const run = mode === 'register' ? props.onRegister : props.onLogin
    void run(loginId.trim(), password).then((message) => {
      setBusy(false)
      if (message === '') {
        resetForm()
        return
      }
      setDetail(message)
    })
  }

  // **아직 물어보는 중이면 경보를 띄우지 않는다.** 첫 페인트마다 ◈ 가 뜨면 그 줄은
  // 곧 배경이 되고, 진짜로 서버가 죽은 날 아무도 안 읽는다.
  const status = !isOnline
    ? describeLink(link, MISSING_HINT)
    : isRegistered
      ? { state: 'true' as const, text: `${String(account?.loginId)} 로 로그인됨` }
      : { state: 'pending' as const, text: ANONYMOUS_TEXT }

  return (
    <Panel title="계정" meta={isRegistered ? '동기화됨' : '가입하면 지킬 수 있다'} tone="panel" padded>
      <div className="account">
        <div className="account__status">
          <GlyphState state={status.state} size="sm" label={status.text} />
        </div>

        {isRegistered || !isOnline ? null : (
          <ValueExpr text={PROMOTE_HINT} size="sm" dim />
        )}
        {/* **누르기 전에 알아야 한다.** 로그인하면 다른 기기가 튕기는데, 그 사실을
            튕긴 뒤에 알면 이미 그쪽에서 뭔가를 잃은 뒤다. */}
        {isOnline ? <ValueExpr text={SINGLE_DEVICE_HINT} size="sm" dim /> : null}

        {/* **내 그림자를 세울지는 내가 정한다** (설계/6_몬스터). 그림자는 내 규칙표로
            싸우므로 관전하며 행동을 보면 내 해답이 어느 정도 역산된다 — 켜는 사람이
            알고 켜야 하는 대가라 기본은 꺼져 있다. */}
        {isOnline && props.onDoppelOptIn !== undefined ? (
          <div className="account__actions">
            <GlyphState
              state={account?.doppelOptIn ? 'true' : 'false'}
              size="sm"
              label={
                account?.doppelOptIn
                  ? '깊은 층에서 죽으면 내 빌드가 남의 던전에 그림자로 선다'
                  : '내 그림자는 안 선다'
              }
            />
            <Button
              size="sm"
              variant="ghost"
              title="그림자는 내 규칙표로 싸운다 — 관전하는 사람이 내 해답을 어느 정도 읽게 된다"
              onClick={() => {
                props.onDoppelOptIn?.(!(account?.doppelOptIn ?? false))
              }}
            >
              {account?.doppelOptIn ? '그림자 끄기' : '그림자 켜기'}
            </Button>
          </div>
        ) : null}

        {mode === 'idle' ? (
          <div className="account__actions">
            {isRegistered ? (
              <>
                <ValueExpr text={`계정 #${String(account?.accountId ?? 0)}`} size="sm" dim />
                <Button
                  size="sm"
                  variant="ghost"
                  glyph="⏻"
                  title="이 기기에서 로그아웃한다 — 이 기기의 저장도 지워진다"
                  onClick={props.onLogout}
                >
                  로그아웃
                </Button>
              </>
            ) : (
              <Button
                size="sm"
                variant="primary"
                glyph="＋"
                disabled={!isOnline}
                onClick={() => {
                  setMode('register')
                }}
              >
                가입
              </Button>
            )}
            <Button
              size="sm"
              variant="ghost"
              glyph="↹"
              disabled={!isOnline}
              onClick={() => {
                setMode('login')
              }}
            >
              {isRegistered ? '다른 계정' : '로그인'}
            </Button>
          </div>
        ) : (
          <form
            className="account__form"
            onSubmit={(event) => {
              event.preventDefault()
              applySubmit()
            }}
          >
            {mode === 'login' && hasLocalProgress && !isRegistered ? (
              <div className="account__warn">
                <GlyphState state="danger" size="sm" label={LOGIN_WARNING} />
              </div>
            ) : null}

            <label className="account__label" htmlFor="account-id">
              아이디
            </label>
            <input
              id="account-id"
              className="account__field"
              type="text"
              autoComplete="username"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              inputMode="text"
              value={loginId}
              onChange={(event) => {
                setLoginId(event.target.value)
              }}
            />

            <label className="account__label" htmlFor="account-pw">
              비밀번호
            </label>
            <input
              id="account-pw"
              className="account__field"
              type="password"
              autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
              value={password}
              onChange={(event) => {
                setPassword(event.target.value)
              }}
            />

            {detail === '' ? null : (
              <div className="account__warn">
                <GlyphState state="danger" size="sm" label={detail} />
              </div>
            )}

            <div className="account__actions">
              <Button size="sm" variant="primary" disabled={!canSubmit} onClick={applySubmit}>
                {mode === 'register' ? '가입' : '로그인'}
              </Button>
              <Button size="sm" variant="ghost" onClick={resetForm}>
                취소
              </Button>
            </div>
          </form>
        )}
      </div>
    </Panel>
  )
}
