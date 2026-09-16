/**
 * 구글 버튼 — 구글이 그리고, 우리는 자리만 내준다 (2026-09-16).
 *
 * **버튼을 직접 만들지 않는다.** 구글의 브랜드 규정이 모양·색·문구를 정해 두었고, 흉내
 * 내서 그리면 심사에서 되돌아온다. 그래서 이 게임의 도면 성격과 유일하게 안 맞는 부품이
 * 되는데, 그것은 규정이라 어쩔 수 없다 — 대신 **자리를 계정 패널 안에 두어** 화면 전체의
 * 황동 예산을 건드리지 않는다.
 *
 * **꺼져 있으면 아무것도 안 그린다.** 서버에 `GAME_GOOGLE_CLIENT_ID` 가 없으면 설정이
 * 꺼진 것이고, 그때 버튼만 떠 있으면 눌러도 안 되는 것을 눌러 보게 된다.
 *
 * **논스는 버튼을 그릴 때 받고, 한 번 쓰면 곧바로 새로 받는다.** 구글에 넘겨야 하는
 * 값이라 누르기 전에 있어야 하는데, 서버는 **검증 전에** 논스를 소진한다(재생 공격을
 * 막는 유일한 자리다). 그래서 한 번 시도한 뒤에는 들고 있던 값이 이미 죽어 있다.
 *
 * 한동안 새로 안 받았다. 그 결과 **첫 시도가 어떤 이유로든 실패하면 그 뒤로는 무엇을
 * 눌러도 「로그인 요청이 만료됐다 — 다시 눌러 달라」만 떴다** — 다시 눌러도 같은 죽은
 * 값을 보내므로 새로고침 전까지 영영 안 된다. 안내가 시키는 일이 되지 않는 상태였다.
 * 성공했든 실패했든 시도 뒤에는 새 논스로 다시 초기화한다.
 */
import { useEffect, useRef, useState } from 'react'

import { readGoogleConfig, readGoogleNonce } from '../storage'

import { type GoogleIdentity, buildNonceCycle } from './googleSession'

import { ValueExpr } from '../ds'

declare global {
  interface Window {
    google?: GoogleIdentity
  }
}

const SCRIPT_SRC = 'https://accounts.google.com/gsi/client'

/** 구글 스크립트를 한 번만 붙인다. 두 번 붙이면 `initialize` 가 두 번 돈다. */
function loadScript(): Promise<boolean> {
  if (window.google !== undefined) {
    return Promise.resolve(true)
  }
  const existing = document.querySelector(`script[src="${SCRIPT_SRC}"]`)
  if (existing !== null) {
    return new Promise((resolve) => {
      existing.addEventListener('load', () => {
        resolve(true)
      })
      existing.addEventListener('error', () => {
        resolve(false)
      })
    })
  }
  return new Promise((resolve) => {
    const tag = document.createElement('script')
    tag.src = SCRIPT_SRC
    tag.async = true
    tag.defer = true
    tag.addEventListener('load', () => {
      resolve(true)
    })
    tag.addEventListener('error', () => {
      resolve(false)
    })
    document.head.appendChild(tag)
  })
}

export interface GoogleSignInProps {
  /** 구글이 준 신원 토큰과 그때 쓴 논스를 넘긴다. */
  readonly onCredential: (credential: string, nonce: string) => void
}

/**
 * 구글 로그인 버튼을 그린다.
 *
 * @param props 콜백.
 * @returns 버튼 자리. 꺼져 있거나 못 닿으면 null.
 */
export function GoogleSignIn(props: GoogleSignInProps): React.JSX.Element | null {
  const slot = useRef<HTMLDivElement | null>(null)
  const [problem, setProblem] = useState('')
  const [isReady, setReady] = useState(false)
  // **최신 콜백을 참조로 든다.** 의존성에 넣으면 부모가 다시 그릴 때마다 구글 버튼을
  // 처음부터 다시 만들고, 그때마다 논스를 하나씩 더 받는다.
  const onCredential = useRef(props.onCredential)
  onCredential.current = props.onCredential
  const isLive = useRef(true)

  useEffect(() => {
    isLive.current = true

    void (async () => {
      const config = await readGoogleConfig()
      if (!isLive.current || !config.isEnabled) {
        return
      }
      const isLoaded = await loadScript()
      if (!isLive.current) {
        return
      }
      if (!isLoaded || window.google === undefined) {
        setProblem('구글에 닿지 못했다 — 아이디로 가입할 수 있다')
        return
      }
      const applyNonce = buildNonceCycle({
        clientId: config.clientId,
        identity: window.google,
        readNonce: readGoogleNonce,
        onCredential: (credential, used) => {
          onCredential.current(credential, used)
        },
        checkLive: () => isLive.current,
      })
      if (!(await applyNonce())) {
        if (isLive.current) {
          setProblem('서버에 닿지 못했다')
        }
        return
      }
      if (slot.current !== null) {
        window.google.accounts.id.renderButton(slot.current, {
          type: 'standard',
          theme: 'filled_black',
          size: 'medium',
          text: 'continue_with',
          shape: 'rectangular',
          locale: 'ko',
        })
      }
      setReady(true)
    })()
    return () => {
      isLive.current = false
    }
  }, [])

  if (problem !== '') {
    return <ValueExpr text={problem} size="sm" dim />
  }
  return (
    <div className="account__google" hidden={!isReady}>
      <div ref={slot} />
    </div>
  )
}
