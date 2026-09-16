/**
 * 구글 로그인이 **두 번째 시도에서도 되는가**.
 *
 * 서버는 검증 전에 논스를 태운다(재생 공격을 막는 유일한 자리다). 그래서 시도 한 번이
 * 논스 하나를 태우는데, 한동안 화면이 새로 안 받았다 — 첫 시도가 어떤 이유로든 실패하면
 * 그 뒤로는 무엇을 눌러도 「로그인 요청이 만료됐다 — 다시 눌러 달라」만 떴고, **다시
 * 눌러도 같은 죽은 값을 보내므로** 새로고침 전까지 영영 안 됐다.
 *
 * 화면 검사로는 못 잡는 자리다 — 이 저장소의 렌더 검사는 정적이라 효과가 안 돌고,
 * 결함은 정확히 그 효과 안에 있었다. 그래서 회전을 부품으로 갈라 여기서 본다.
 */
import { describe, expect, it } from 'vitest'

import { type GoogleIdentity, buildNonceCycle } from './googleSession'

/** 구글 전역을 흉내 낸다. 초기화될 때마다 받은 논스를 적고, 콜백을 들고 있는다. */
function buildFakeGoogle(): {
  identity: GoogleIdentity
  seen: string[]
  fire: () => void
} {
  const seen: string[] = []
  let latest: ((response: { credential?: string }) => void) | undefined
  return {
    seen,
    fire: () => {
      latest?.({ credential: 'pretend.id.token' })
    },
    identity: {
      accounts: {
        id: {
          initialize: (options) => {
            seen.push(options.nonce)
            latest = options.callback
          },
          renderButton: () => undefined,
        },
      },
    },
  }
}

/** 부를 때마다 다른 논스를 내는 가짜 서버. */
function buildIssuer(): { readNonce: () => Promise<string>; count: () => number } {
  let issued = 0
  return {
    readNonce: () => {
      issued += 1
      return Promise.resolve(`nonce-${String(issued)}`)
    },
    count: () => issued,
  }
}

describe('논스 회전', () => {
  it('★ 한 번 쓴 논스를 두 번 안 보낸다 — 서버가 이미 태웠다', async () => {
    const google = buildFakeGoogle()
    const issuer = buildIssuer()
    const used: string[] = []
    const applyNonce = buildNonceCycle({
      clientId: 'cid',
      identity: google.identity,
      readNonce: issuer.readNonce,
      onCredential: (_credential, nonce) => {
        used.push(nonce)
      },
      checkLive: () => true,
    })

    expect(await applyNonce()).toBe(true)
    google.fire()
    // 콜백 안의 재초기화는 마이크로태스크 하나 뒤다.
    await Promise.resolve()
    await Promise.resolve()
    google.fire()

    expect(used[0]).toBe('nonce-1')
    // **여기가 결함이 살던 자리다.** 예전에는 둘 다 `nonce-1` 이었고, 서버는 두 번째를
    // 400 「만료됐다」로 돌려보냈다 — 그리고 그 안내가 시키는 「다시 누르기」도 같은 값을
    // 보내므로 새로고침 전까지 빠져나갈 수 없었다.
    expect(used[1]).toBe('nonce-2')
    expect(google.seen).toEqual(['nonce-1', 'nonce-2'])
  })

  it('★ 논스를 못 받으면 초기화하지 않는다 — 빈 값으로 초기화하면 눌러도 안 된다', async () => {
    const google = buildFakeGoogle()
    const applyNonce = buildNonceCycle({
      clientId: 'cid',
      identity: google.identity,
      readNonce: () => Promise.resolve(''),
      onCredential: () => undefined,
      checkLive: () => true,
    })
    expect(await applyNonce()).toBe(false)
    expect(google.seen).toEqual([])
  })

  it('★ 화면이 떠난 뒤에는 초기화하지 않는다 — 남의 화면을 건드린다', async () => {
    const google = buildFakeGoogle()
    const issuer = buildIssuer()
    const applyNonce = buildNonceCycle({
      clientId: 'cid',
      identity: google.identity,
      readNonce: issuer.readNonce,
      onCredential: () => undefined,
      checkLive: () => false,
    })
    expect(await applyNonce()).toBe(false)
    expect(google.seen).toEqual([])
    // 논스는 이미 받았다. 받고 나서 떠난 것을 알았을 뿐이라 한 장이 버려진다 —
    // 서버가 열 분 뒤 거둔다.
    expect(issuer.count()).toBe(1)
  })

  it('빈 신원 토큰은 안 보낸다 — 구글이 취소를 그렇게 알린다', async () => {
    const google = buildFakeGoogle()
    const issuer = buildIssuer()
    let calls = 0
    const applyNonce = buildNonceCycle({
      clientId: 'cid',
      identity: google.identity,
      readNonce: issuer.readNonce,
      onCredential: () => {
        calls += 1
      },
      checkLive: () => true,
    })
    await applyNonce()
    google.identity.accounts.id.initialize({
      client_id: 'cid',
      nonce: 'nonce-1',
      callback: () => undefined,
    })
    expect(calls).toBe(0)
  })
})
