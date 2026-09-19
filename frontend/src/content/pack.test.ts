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
import { parseBalance } from '../core/services/runBattle'

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

describe('발행된 팩이 전투까지 간다 (2026-09-19)', () => {
  /**
   * **한 번도 발행한 적이 없어서 아무도 몰랐다.** 운영 DB 가 `published=0 · drafts=0`
   * 이라 이 경로가 한 번도 안 돌았고, 그동안 번들 쪽만 맞춰져 있었다.
   *
   * 어긋난 자리는 하나였다 — 번들은 `resources.BALANCE` 가 `{...balance.json, skills:
   * skills.json.skills}` 로 합쳐져 있는데 서버 팩은 두 자산을 **따로** 보내고,
   * `parseContentPack` 이 스킬에서 버전 숫자만 가져갔다. 그 팩이 `App.tsx` 의
   * `ACTIVE.balance` 로 그대로 가고 `parseBalance` 의 `readArray(raw, 'skills')` 가
   * 던진다 — 발행하는 순간 전투 화면이 죽는다.
   *
   * **위의 「코어의 로더로 읽는다」가 이것을 못 잡는다.** 그쪽은 팩이 만들어지는 것까지
   * 보고, 이쪽은 그 팩을 **전투가 받는 것**까지 본다.
   */
  it('★ 전투가 그 팩으로 돈다 — 발행하는 순간 화면이 죽으면 안 된다', () => {
    const pack = parseContentPack(RAW)
    expect(pack).toBeDefined()
    // `App.tsx` 가 하는 것과 같다: const BALANCE = ACTIVE.balance
    expect(() => parseBalance(pack!.balance)).not.toThrow()
  })

  it('★ 스킬 절이 밸런스에 합쳐진다 — 파이썬 `load_balance` 와 같은 규약', () => {
    const skills = parseBalance(parseContentPack(RAW)!.balance).skills
    expect(skills.length).toBe(skillsRaw.skills.length)
    // 버전만 가져가고 절을 빠뜨리면 여기서 빈 배열이 된다.
    expect(skills.some((one) => one.id === 'METEOR')).toBe(true)
  })

  it('★ 번들과 같은 스킬 수를 낸다 — 두 길이 다른 게임을 돌리면 안 된다', () => {
    expect(parseBalance(parseContentPack(RAW)!.balance).skills.length).toBe(
      parseBalance(BUNDLED_PACK.balance).skills.length,
    )
  })
})
