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
import { adoptServerMeta } from '../core/services/manageMeta'
import { readBestiary,
  TOKEN_STORAGE_KEY,
  readInventory,
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

describe('세이브 정본은 서버다', () => {
  const server = {
    ...createEmptyMeta(),
    bestFloor: 4,
    unlockedActions: ['ATTACK'],
    bestiary: [{ kindId: 'goblin_rusher', encounters: 5, defeats: 2 }],
  }
  const local = {
    ...createEmptyMeta(),
    bestFloor: 99,
    unlockedActions: ['RETREAT', 'SUMMON'],
    bestiary: [{ kindId: 'goblin_rusher', encounters: 300, defeats: 300 }],
  }

  it('★ 성취는 서버 것이 이긴다 — 기기 값이 더 커도 버린다', () => {
    // 기기 값은 오프라인 연습이 만든 낙관적 표시다. 합집합·최대값으로 두면 서버가
    // 뒷받침하지 않는 해금이 화면에 영영 남고, 그것이 순위에 안 잡힌다는 사실이
    // 나중에 드러난다.
    const adopted = adoptServerMeta(server, local)
    expect(adopted.bestFloor).toBe(4)
    expect(adopted.unlockedActions).toEqual(['ATTACK'])
    expect(adopted.bestiary[0]?.encounters).toBe(5)
  })

  it('★ 여러 번 받아들여도 같다 (멱등)', () => {
    const once = adoptServerMeta(server, local)
    expect(adoptServerMeta(server, once)).toEqual(once)
  })

  it('프리셋은 기기 것을 지킨다 — 편집 중인 것이 사라지면 안 된다', () => {
    const withPreset = { ...local, presets: [{ name: '내 것', ruleset: local.presets[0]?.ruleset }] }
    expect(adoptServerMeta(server, withPreset as typeof local).presets).toHaveLength(1)
  })

  it('기기에 프리셋이 없으면 서버 것을 받는다 — 새 기기가 이 경우다', () => {
    const withPreset = { ...server, presets: [{ name: '서버', ruleset: local.presets[0]?.ruleset }] }
    expect(adoptServerMeta(withPreset as typeof server, local).presets).toHaveLength(1)
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

describe('도감 — 규칙표를 그대로 읽는다', () => {
  const RAW = {
    entries: [
      {
        record_id: 3,
        catalog_id: 'goblin_rusher',
        label_ko: '사나운 고블린 돌격병',
        tier: 'ELITE',
        level: 3,
        level_cap: 5,
        zone_floor: 1,
        entity_slot: 'goblin_rusher_0',
        hp_max: 74,
        attack: 14,
        defense: 3,
        ruleset: {
          ruleset_id: 'ai_rusher',
          version: 1,
          rules: [
            {
              priority: 1,
              cpu_cost: 1,
              action: 'ATTACK',
              target: 'NEAREST',
              set_flag: null,
              conditions: {
                op: 'SINGLE',
                terms: [{ lhs: 'target_distance', lhs_param: 'NEAREST', cmp: '<=', rhs: 1 }],
              },
            },
          ],
        },
        affixes: [{ label_ko: '사나운' }],
        trophies: ['helm_iron'],
        holds_mine: true,
      },
    ],
  }

  it('★ **줄 수로 접지 않는다.**', async () => {
    // 서버는 처음부터 규칙표를 보내고 있었는데 파싱이 `rules.length` 로 접어 버렸다.
    // 도감이 표적 목록인 이유가 그 규칙표다 — 요약하면 카운터를 설계할 수 없다.
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(RAW) }),
    )
    const rows = await readBestiary('token')
    expect(rows?.[0]?.ruleset?.rules).toHaveLength(1)
    expect(rows?.[0]?.ruleset?.rules[0]?.action).toBe('ATTACK')
  })

  it('★ 스탯도 읽는다 — 규칙표만으로는 이길 수 있는지 알 수 없다', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(RAW) }),
    )
    const rows = await readBestiary('token')
    expect(rows?.[0]?.hpMax).toBe(74)
    expect(rows?.[0]?.attack).toBe(14)
  })

  it('규칙표가 없으면 undefined 다 — 구버전 서버가 이 경우다', async () => {
    const bare = { entries: [{ ...RAW.entries[0], ruleset: null }] }
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(bare) }),
    )
    expect((await readBestiary('token'))?.[0]?.ruleset).toBeUndefined()
  })
})


describe('가방을 읽을 때 서버가 붙인 표시를 잃지 않는다', () => {
  /**
   * 서버가 이런 칸 하나를 보냈다고 둔다.
   *
   * @param item 아이템 절에 덮어쓸 값.
   * @returns fetch 가 낼 응답.
   */
  function buildResponse(item: Record<string, unknown>) {
    return {
      ok: true,
      json: async () => ({
        slots: [
          {
            slot_index: 0,
            slot: null,
            is_sealed: false,
            item: {
              item_id: 1,
              catalog_id: 'helm_iron',
              label_ko: '철투구',
              kind: 'EQUIPMENT',
              slot: 'HEAD',
              hands: null,
              equipped_slot: null,
              is_broken: false,
              can_equip: true,
              requirements: [],
              ...item,
            },
          },
        ],
        equipment: [],
        balance: 0,
        repair_cost: 0,
      }),
    }
  }

  it('★ 되찾음 표시를 옮긴다 — 키 이름이 어긋나면 조용히 사라진다', async () => {
    // 이 계층은 snake_case 를 camelCase 로 옮기기만 한다. 그래서 오타 하나가 기능
    // 전체를 죽이면서 타입 검사도 통과한다 (`is_recovered` → 항상 false).
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(buildResponse({ is_recovered: true })))
    const view = await readInventory('t')
    expect(view?.slots[0]?.item?.isRecovered).toBe(true)
  })

  it('서버가 안 보내면 거짓이다 — 없는 것을 「되찾음」으로 칠하지 않는다', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(buildResponse({})))
    const view = await readInventory('t')
    expect(view?.slots[0]?.item?.isRecovered).toBe(false)
  })
})
