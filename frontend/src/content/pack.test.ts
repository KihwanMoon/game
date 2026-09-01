/**
 * 콘텐츠 팩 (설계/4_아이템 §18).
 *
 * 여기서 지키는 것은 넷이다.
 *
 * 1. **번들이 폴백이다.** 서버에 못 닿아도 게임이 돈다.
 * 2. **받은 팩도 코어의 로더로 읽는다.** 깨진 절 하나가 화면을 통째로 죽이면 안 된다.
 * 3. **못 읽으면 번들로 떨어진다.** 콘텐츠 하나 잘못 발행했다고 아무도 못 들어오면 안 된다.
 * 4. **코어 버전은 서버가 준 것을 쓴다.** 브라우저가 다시 조립하면 두 곳이 갈린다.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  BUNDLED_PACK,
  applyContentPack,
  loadContentPack,
  parseContentPack,
  readActivePack,
} from './pack'
import balanceRaw from '@resources/balance/balance.json'
import blocksRaw from '@resources/balance/blocks.json'
import skillsRaw from '@resources/balance/skills.json'
import roomsRaw from '@resources/rooms/templates.json'
import enemiesRaw from '@resources/rulesets/enemies.json'

const RAW = {
  assets: {
    balance: balanceRaw,
    blocks: blocksRaw,
    skills: skillsRaw,
    rooms: roomsRaw,
    enemies: enemiesRaw,
  } as Record<string, unknown>,
  generation: 7,
  core_version: 'b6.v2.i1.s2.r1.a1.p7.e1',
}

afterEach(() => {
  vi.unstubAllGlobals()
  applyContentPack(BUNDLED_PACK)
})

describe('콘텐츠 팩', () => {
  it('★ 갈아 끼우기 전에는 번들이다 — 서버가 없어도 게임이 돈다', () => {
    expect(readActivePack()).toBe(BUNDLED_PACK)
    expect(BUNDLED_PACK.generation).toBe(0)
  })

  it('★ 서버가 준 팩을 코어의 로더로 읽는다', () => {
    const parsed = parseContentPack(RAW)
    expect(parsed).toBeDefined()
    expect(parsed?.rooms.length).toBeGreaterThan(0)
    expect(parsed?.enemies.size).toBeGreaterThan(0)
    expect(parsed?.catalog.actions.size).toBeGreaterThan(0)
  })

  it('★ 코어 버전은 서버가 준 것을 그대로 쓴다 — 다시 조립하면 두 곳이 갈린다', () => {
    expect(parseContentPack(RAW)?.coreVersion).toBe('b6.v2.i1.s2.r1.a1.p7.e1')
    expect(parseContentPack(RAW)?.generation).toBe(7)
  })

  it('★ 못 읽는 팩은 undefined 다 — 깨진 절 하나가 화면을 죽이면 안 된다', () => {
    const broken = { ...RAW, assets: { ...RAW.assets, rooms: { templates: [{ id: 'x' }] } } }
    expect(parseContentPack(broken)).toBeUndefined()
  })

  it('★ 서버에 못 닿으면 안 갈아 끼운다', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    expect(await loadContentPack()).toBe(false)
    expect(readActivePack()).toBe(BUNDLED_PACK)
  })

  it('★ 깨진 팩을 받아도 번들로 남는다 — 잘못 발행했다고 아무도 못 들어오면 안 된다', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ ...RAW, assets: { ...RAW.assets, blocks: {} } }),
      }),
    )
    expect(await loadContentPack()).toBe(false)
    expect(readActivePack()).toBe(BUNDLED_PACK)
  })

  it('받으면 갈아 끼운다', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => RAW }))
    expect(await loadContentPack()).toBe(true)
    expect(readActivePack().generation).toBe(7)
  })
})
