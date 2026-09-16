/**
 * 구글 로그인의 논스 회전 — React 를 모른다.
 *
 * **서버는 검증 *전에* 논스를 태운다** (`google_auth.create_google_session`). 재생 공격을
 * 막는 유일한 자리라 그 순서가 맞다. 대신 **시도 한 번이 논스 하나를 태운다** — 성공했든
 * 실패했든.
 *
 * 그래서 화면은 쓸 때마다 새로 받아야 한다. 한동안 안 받았고, 그 결과 첫 시도가 어떤
 * 이유로든 실패하면 그 뒤로는 무엇을 눌러도 「로그인 요청이 만료됐다 — 다시 눌러 달라」만
 * 떴다. **다시 눌러도 같은 죽은 값을 보내므로** 새로고침 전까지 영영 안 됐다 — 안내가
 * 시키는 일이 되지 않는 상태였다.
 *
 * 부품으로 갈라 둔 이유는 검사 때문이다. 이 저장소의 화면 검사는 정적 렌더라 효과가 안
 * 도는데, **결함이 살던 자리가 바로 그 효과 안**이었다.
 */

/** 구글이 스크립트로 붙이는 전역. 쓰는 것만 적는다 — 전부 적으면 구글이 고칠 때 갈린다. */
export interface GoogleIdentity {
  accounts: {
    id: {
      initialize: (options: {
        client_id: string
        nonce: string
        callback: (response: { credential?: string }) => void
      }) => void
      renderButton: (parent: HTMLElement, options: Record<string, string | number>) => void
    }
  }
}

/** 논스 회전에 필요한 것들. 전부 밖에서 준다 — 그래야 검사가 들어올 수 있다. */
export interface SessionOptions {
  readonly clientId: string
  readonly identity: GoogleIdentity
  /** 서버에서 새 논스를 받는다. 못 받으면 빈 문자열. */
  readonly readNonce: () => Promise<string>
  /** 구글이 신원 토큰을 줬다. 그때 쓴 논스를 함께 넘긴다. */
  readonly onCredential: (credential: string, nonce: string) => void
  /** 화면이 아직 살아 있는가. 떠난 뒤에 초기화하면 남의 화면을 건드린다. */
  readonly checkLive: () => boolean
}

/**
 * 논스를 받아 구글을 초기화하고, 한 번 쓸 때마다 갈아 끼운다.
 *
 * @param options 클라이언트 id·구글 전역·논스 공급자·콜백.
 * @returns 초기화를 한 번 도는 함수. 처음 한 번은 부르는 쪽이 부른다.
 */
export function buildNonceCycle(options: SessionOptions): () => Promise<boolean> {
  async function applyNonce(): Promise<boolean> {
    const fresh = await options.readNonce()
    if (!options.checkLive() || fresh === '') {
      return false
    }
    options.identity.accounts.id.initialize({
      client_id: options.clientId,
      nonce: fresh,
      callback: (response) => {
        if (response.credential === undefined || response.credential === '') {
          return
        }
        // **쓴 값으로 보내고 곧바로 갈아 끼운다.** 이 시도가 성공하든 실패하든 서버는
        // 이미 이 논스를 태웠다 — 안 갈면 다음 누름이 무조건 「만료됐다」로 떨어진다.
        options.onCredential(response.credential, fresh)
        void applyNonce()
      },
    })
    return true
  }
  return applyNonce
}
