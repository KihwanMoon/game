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
import {
  TOKEN_STORAGE_KEY,
  ensureToken,
  readServerMeta,
  readToken,
  requestTicket,
} from './serverSync'
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

describe('티켓 — 지속 몬스터 스냅샷 (E4)', () => {
  const RAW = {
    ticket_id: 't1',
    seed: 42,
    room_id: 'corridor',
    floor: 1,
    mode: 'PRACTICE',
    core_version: 'b5.v2.e1',
    monster_snapshot: [
      {
        entity_id: 'goblin_archer_1',
        record_id: 2,
        kind_id: 'goblin_archer',
        tier: 'BOSS',
        level: 12,
        hp_max: 140,
        attack: 24,
        defense: 9,
        rule_slots: 6,
        cpu_budget: 10,
      },
      {
        entity_id: 'goblin_rusher_0',
        record_id: 1,
        kind_id: 'goblin_rusher',
        tier: 'ELITE',
        level: 7,
        hp_max: 96,
        attack: 17,
        defense: 5,
        rule_slots: 4,
        cpu_budget: 7,
      },
    ],
  }

  it('★ 티켓의 스냅샷을 읽는다', async () => {
    // **이 자리가 실제로 비어 있었다.** 서버는 스냅샷으로 재시뮬하는데 클라이언트가
    // 그것을 읽지 않아, 화면이 기본 적을 그리는 동안 서버는 엘리트를 상대할 뻔했다.
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(RAW) }),
    )
    const ticket = await requestTicket('token', 'corridor', 42)
    expect(ticket?.snapshots).toHaveLength(2)
    expect(ticket?.snapshots[0]?.hpMax).toBe(140)
  })

  it('entityId 순으로 정렬해서 준다 — 순서가 흔들리면 재현이 흔들린다', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(RAW) }),
    )
    const ticket = await requestTicket('token', 'corridor', 42)
    expect(ticket?.snapshots.map((item) => item.entityId)).toEqual([
      'goblin_archer_1',
      'goblin_rusher_0',
    ])
  })

  it('스냅샷 절이 없으면 빈 배열이다 — 로컬·구버전 서버가 이 경우다', async () => {
    const { monster_snapshot: _omitted, ...withoutSnapshot } = RAW
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(withoutSnapshot) }),
    )
    expect((await requestTicket('token', 'corridor', 42))?.snapshots).toEqual([])
  })
})

describe('티켓 — 로드아웃 (결정 #13)', () => {
  const RAW = {
    ticket_id: 't2',
    seed: 42,
    room_id: 'corridor',
    floor: 1,
    mode: 'PRACTICE',
    core_version: 'b5.v2.e1',
    loadout: {
      hp_max: 132,
      attack: 18,
      defense: 8,
      attack_range: 4,
      initiative: 56,
      cpu_budget: 11,
      rule_slots: 6,
      skills: ['SKILL_2', 'ATTACK'],
    },
  }

  it('★ 티켓의 로드아웃을 읽는다', async () => {
    // 스냅샷과 같은 자리다. 서버는 장비를 낀 캐릭터로 재시뮬하므로, 여기서 흘리면
    // 화면은 맨몸으로 싸우고 제출은 전부 불일치로 반려된다.
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(RAW) }),
    )
    const ticket = await requestTicket('token', 'corridor', 42)
    expect(ticket?.loadout?.attackRange).toBe(4)
    expect(ticket?.loadout?.hpMax).toBe(132)
  })

  it('스킬을 정렬해서 준다 — 순서가 흔들리면 「불가」 판정이 흔들린다', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(RAW) }),
    )
    const ticket = await requestTicket('token', 'corridor', 42)
    expect(ticket?.loadout?.skills).toEqual(['ATTACK', 'SKILL_2'])
  })

  it('로드아웃 절이 없으면 undefined 다 — 오프라인·구버전 서버가 이 경우다', async () => {
    const { loadout: _omitted, ...withoutLoadout } = RAW
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(withoutLoadout) }),
    )
    expect((await requestTicket('token', 'corridor', 42))?.loadout).toBeUndefined()
  })
})
