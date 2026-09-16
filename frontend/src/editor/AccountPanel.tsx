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

import { GoogleSignIn } from './GoogleSignIn'
import { checkLinked, describeLink, type LinkState } from './linkState'

export interface AccountPanelProps {
  readonly account: AccountState | undefined
  /** 서버에 닿지 못했으면 false. 그래도 게임은 돈다. */
  readonly link: LinkState
  /** 이 기기에 남아 있는 진행. 로그인 경고를 띄울지 판단한다. */
  readonly hasLocalProgress: boolean
  readonly onRegister: (loginId: string, password: string) => Promise<string>
  /** 구글이 준 신원 토큰으로 들어간다. 빈 문자열이면 성공이다. 없으면 버튼을 안 그린다. */
  readonly onGoogle?: (credential: string, nonce: string) => Promise<string>
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

/** 켜 둔 쪽에 적는 말. **무엇을 얻는지까지 적는다.** */
const DOPPEL_ON_HINT = '깊은 장에서 죽으면 내 내력이 남의 판에 둔갑으로 선다 — 그 둔갑이 이긴 만큼 활자가 들어온다'

/**
 * 꺼 둔 쪽에 적는 말.
 *
 * **놓치는 것을 적는다.** 예전에는 「내 둔갑은 안 선다」뿐이었고, 그 상태에서 동의한
 * 사람은 195명 중 1명이었다 — 화면이 대가만 말하고 얻는 것을 안 말했다.
 */
const DOPPEL_OFF_HINT = '내 둔갑은 안 선다 — 둔갑 순위표에도 안 서고 활자도 안 들어온다'

/** 켜고 끄는 단추의 설명. 대가와 얻는 것을 한 문장에 둔다. */
const DOPPEL_TRADE_HINT =
  '둔갑은 내 내력으로 싸운다 — 관전하는 사람이 내 해답을 어느 정도 읽게 되고, 대신 그 둔갑이 물러날 때 이긴 만큼 활자를 남긴다'

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
            알고 켜야 하는 대가라 기본은 꺼져 있다.

            **얻는 것도 함께 적는다** (2026-09-15). 꺼진 쪽에 「안 선다」만 적혀 있던
            동안 동의한 사람은 195명 중 1명이었다 — 대가만 보이고 무엇을 놓치는지는
            어디에도 없었다. 켜면 둔갑 순위표에 서고, 그 그림자가 이긴 만큼 활자가
            들어온다(봉인 옵션을 다시 찍는 재화). */}
        {isOnline && props.onDoppelOptIn !== undefined ? (
          <div className="account__actions">
            <GlyphState
              state={account?.doppelOptIn ? 'true' : 'false'}
              size="sm"
              label={
                account?.doppelOptIn ? DOPPEL_ON_HINT : DOPPEL_OFF_HINT
              }
            />
            <Button
              size="sm"
              variant="ghost"
              title={DOPPEL_TRADE_HINT}
              onClick={() => {
                props.onDoppelOptIn?.(!(account?.doppelOptIn ?? false))
              }}
            >
              {account?.doppelOptIn ? '둔갑 끄기' : '둔갑 켜기'}
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

        {/* **구글은 「또 하나의 가입 방법」이다.** 아이디·비밀번호를 없애지 않는다 —
            구글 계정이 없거나 쓰기 싫은 사람이 못 들어오게 되면, 편의를 더한 것이
            아니라 문을 하나로 줄인 것이다.

            **이미 가입한 계정에는 안 그린다.** 지금 이 화면의 구글 버튼은 「들어가기」라
            승격이거나 로그인인데, 이미 아이디가 붙은 계정에서 누르면 **다른 계정으로
            갈아타는 일**이 된다 — 그 길은 따로 「연결」로 두어야 뜻이 분명하다. */}
        {props.onGoogle !== undefined && account?.loginId == null ? (
          <div className="account__oauth">
            <GoogleSignIn
              onCredential={(credential, nonce) => {
                setBusy(true)
                setDetail('')
                void props.onGoogle?.(credential, nonce).then((message) => {
                  setBusy(false)
                  setDetail(message)
                })
              }}
            />
          </div>
        ) : null}

        {/* **방침으로 가는 길이 화면에 있어야 한다.** 구글 로그인 심사가 이 링크를
            확인하기도 하지만, 그 전에 **가입하는 자리**가 곧 무엇에 동의하는지 읽을
            자리다 — 문서를 만들어 두고 닿는 길을 안 두면 없는 것과 같다.

            `public/` 의 정적 페이지라 새 창이 아니라 그냥 이동해도 되지만, 가입 폼을
            채우던 중이면 적은 것이 날아간다. */}
        <div className="account__legal">
          <a href="/privacy.html" target="_blank" rel="noreferrer noopener">
            개인정보처리방침
          </a>
          <span aria-hidden="true">·</span>
          <a href="/terms.html" target="_blank" rel="noreferrer noopener">
            이용약관
          </a>
        </div>
      </div>
    </Panel>
  )
}
