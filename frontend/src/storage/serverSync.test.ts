/**
 * 서버 동기화 검사 (B단계).
 *
 * 여기서 지키는 것은 둘이다.
 *
 * 1. **서버가 없어도 게임이 돈다.** 모든 실패 경로가 조용히 undefined/false 를 낸다.
 *    여기서 던지면 네트워크가 끊겼다는 이유로 화면이 안 뜬다.
 * 2. **합치기가 멱등이다.** 도감 횟수를 더하면 동기화를 두 번 할 때마다 숫자가 불어난다.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createEmptyMeta } from '../core/schemas'
import { mergeMeta } from '../core/services/manageMeta'
import { TOKEN_STORAGE_KEY, ensureToken, readServerMeta, readToken } from './serverSync'
import type { StorageLike } from './saveStore'

/**
 * 메모리 저장소를 만든다.
 *
 * @param seed 처음부터 들어 있을 값.
 * @returns 저장소.
 */
function createMemoryStorage(seed: Record<string, string> = {}): StorageLike {
  const table = new Map(Object.entries(seed))
  return {
    getItem: (key) => table.get(key) ?? null,
    setItem: (key, value) => {
      table.set(key, value)
    },
    removeItem: (key) => {
      table.delete(key)
    },
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('토큰', () => {
  it('저장돼 있으면 서버를 부르지 않는다', async () => {
    const fetchSpy = vi.fn()
    vi.stubGlobal('fetch', fetchSpy)
    const storage = createMemoryStorage({ [TOKEN_STORAGE_KEY]: 'kept' })
    expect(await ensureToken(storage)).toBe('kept')
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('★ 서버에 닿지 못하면 조용히 포기한다', async () => {
    // 던지면 네트워크가 끊겼다는 이유로 화면이 안 뜬다.
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    expect(await ensureToken(createMemoryStorage())).toBeUndefined()
  })

  it('서버가 거절하면 토큰을 만들지 않는다', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }))
    expect(await ensureToken(createMemoryStorage())).toBeUndefined()
  })

  it('받은 토큰을 저장한다', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ token: 'fresh' }) }),
    )
    const storage = createMemoryStorage()
    expect(await ensureToken(storage)).toBe('fresh')
    expect(readToken(storage)).toBe('fresh')
  })

  it('★ 저장하지 못하면 토큰을 돌려주지 않는다', async () => {
    // 토큰은 만들 때 한 번만 나온다. 저장에 실패한 계정은 영영 다시 못 쓴다.
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ token: 'lost' }) }),
    )
    const broken: StorageLike = {
      getItem: () => null,
      setItem: () => {
        throw new Error('quota')
      },
      removeItem: () => undefined,
    }
    expect(await ensureToken(broken)).toBeUndefined()
  })
})

describe('서버 세이브 읽기', () => {
  it('닿지 못하면 오프라인으로 보고한다', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    const outcome = await readServerMeta('t')
    expect(outcome.isOnline).toBe(false)
    expect(outcome.meta).toBeUndefined()
  })

  it('세이브가 없으면 접속은 성공으로 본다', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ payload: null }) }),
    )
    const outcome = await readServerMeta('t')
    expect(outcome.isOnline).toBe(true)
    expect(outcome.meta).toBeUndefined()
  })

  it('깨진 세이브는 없는 것과 같이 다룬다', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ payload: { a: 1 } }) }),
    )
    expect((await readServerMeta('t')).meta).toBeUndefined()
  })
})

describe('세이브 합치기', () => {
  const server = {
    ...createEmptyMeta(),
    bestFloor: 4,
    unlockedActions: ['ATTACK'],
    bestiary: [{ kindId: 'goblin_rusher', encounters: 5, defeats: 2 }],
  }
  const local = {
    ...createEmptyMeta(),
    bestFloor: 2,
    unlockedActions: ['RETREAT'],
    bestiary: [{ kindId: 'goblin_rusher', encounters: 3, defeats: 3 }],
  }

  it('최고 층은 최대값이다', () => {
    expect(mergeMeta(server, local).bestFloor).toBe(4)
  })

  it('해금은 합집합이고 정렬된다', () => {
    expect(mergeMeta(server, local).unlockedActions).toEqual(['ATTACK', 'RETREAT'])
  })

  it('★ 도감은 더하지 않고 최대값을 쓴다', () => {
    // 더하면 동기화를 두 번 할 때마다 숫자가 불어난다 — 양쪽이 같은 런을 이미 세었다.
    const merged = mergeMeta(server, local).bestiary[0]
    expect(merged).toEqual({ kindId: 'goblin_rusher', encounters: 5, defeats: 3 })
  })

  it('★ 여러 번 합쳐도 같다 (멱등)', () => {
    const once = mergeMeta(server, local)
    expect(mergeMeta(server, once)).toEqual(once)
    expect(mergeMeta(once, once)).toEqual(once)
  })

  it('프리셋은 기기 것을 지킨다 — 편집 중인 것이 사라지면 안 된다', () => {
    const withPreset = { ...local, presets: [{ name: '내 것', ruleset: local.presets[0]?.ruleset }] }
    expect(mergeMeta(server, withPreset as typeof local).presets).toHaveLength(1)
  })
})
