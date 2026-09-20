/**
 * 링크 만들기가 코드를 대신하지 않는가.
 *
 * **서버가 없어도 게임은 돈다** (CLAUDE.md). 그때 남에게 표를 건네는 수단은 공유
 * 코드뿐이고, 링크는 서버가 있을 때 더 나은 길이지 대체가 아니다 — 서버가 죽었을 때
 * 「링크를 못 만들었다」가 아니라 「코드는 그대로 쓸 수 있다」로 읽혀야 한다.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { RuleSet } from '../core/schemas'
import { SHARE_OFFLINE, createShareLink } from './shareLink'
import { TOKEN_STORAGE_KEY } from './serverSync'

const RULESET: RuleSet = {
  rulesetId: 'probe',
  version: 1,
  rules: [
    {
      priority: 1,
      conditions: { op: 'SINGLE', terms: [{ lhs: 'self_hp_percent', comparison: '<', rhs: 30, lhsParam: null }] },
      action: 'ATTACK',
      actionParam: null,
      target: 'NEAREST',
      setFlag: null,
      cpuCost: 1,
    },
  ],
}

function buildStorage(token: string | undefined) {
  const bag = new Map<string, string>()
  if (token !== undefined) {
    bag.set(TOKEN_STORAGE_KEY, token)
  }
  return {
    getItem: (key: string) => bag.get(key) ?? null,
    setItem: (key: string, value: string) => {
      bag.set(key, value)
    },
    removeItem: (key: string) => {
      bag.delete(key)
    },
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('짧은 주소 만들기', () => {
  it('★ 토큰이 없으면 코드를 그대로 쓰라고 말한다', async () => {
    const result = await createShareLink(RULESET, '표', buildStorage(undefined), 'https://x.test')
    expect(result.url).toBe('')
    expect(result.problem).toBe(SHARE_OFFLINE)
  })

  it('★ 서버에 못 닿아도 코드를 그대로 쓰라고 말한다 — 링크는 대체가 아니다', async () => {
    vi.stubGlobal('fetch', () => Promise.reject(new Error('끊김')))
    const result = await createShareLink(RULESET, '표', buildStorage('t'), 'https://x.test')
    expect(result.problem).toBe(SHARE_OFFLINE)
  })

  it('주소를 지금 열려 있는 곳으로 조립한다 — 서버는 경로만 안다', async () => {
    vi.stubGlobal('fetch', () =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ share_id: 'abc123', path: '/r/abc123' }),
      }),
    )
    const result = await createShareLink(RULESET, '표', buildStorage('t'), 'https://x.test')
    expect(result.url).toBe('https://x.test/r/abc123')
    expect(result.problem).toBe('')
  })

  it('★ 서버가 반려하면 사유를 그대로 보여 준다 — 「실패」만 적으면 고칠 곳을 못 찾는다', async () => {
    vi.stubGlobal('fetch', () =>
      Promise.resolve({
        ok: false,
        status: 422,
        json: () => Promise.resolve({ detail: '규칙표 위반: [1] USE_SKILL 의 재주 를 안 골랐다' }),
      }),
    )
    const result = await createShareLink(RULESET, '표', buildStorage('t'), 'https://x.test')
    expect(result.problem).toContain('재주 를 안 골랐다')
  })
})
