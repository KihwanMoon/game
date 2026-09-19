/**
 * 몬스터 도트 고르기 (2026-09-19).
 *
 * **아이템 쪽과 규약이 다르므로 지키는 것도 다르다.** 저쪽은 접두사가 형태를 말해서
 * 「이름을 규약 밖으로 지으면 그림이 조용히 안 뜬다」를 지킨다. 이쪽은 id 를 통째로
 * 쓰므로 물어볼 것이 하나다 — **적 전수에 그림이 다 있는가.**
 *
 * 그 실패는 조용하다: 그림이 없어도 칸은 코드 글자로 멀쩡히 그려지고, 한 종만 글자로
 * 남은 것은 도감을 끝까지 내려 본 사람만 본다.
 */
import balanceRaw from '@resources/balance/balance.json'
import { describe, expect, it } from 'vitest'

import { findMonsterArt, listMonsterArtIds } from './monsterArt'

interface RawEnemy {
  id: string
  label_ko: string
}

const ENEMIES = (balanceRaw as unknown as { enemies: RawEnemy[] }).enemies

describe('몬스터 도트', () => {
  it('★ 적 전수에 그림이 있다 — 한 종이라도 빠지면 그 칸만 글자로 남는다', () => {
    const missing = ENEMIES.filter((one) => findMonsterArt(one.id) === undefined).map(
      (one) => `${one.id}(${one.label_ko})`,
    )
    expect(missing).toEqual([])
  })

  it('★ 그림에 대응하는 적이 다 있다 — 종이 사라지면 그림도 지운다', () => {
    const known = new Set(ENEMIES.map((one) => one.id))
    expect(listMonsterArtIds().filter((id) => !known.has(id))).toEqual([])
  })

  it('★ 모르는 id 는 undefined 다 — 없는 그림을 지어내면 엉뚱한 종이 그려진다', () => {
    expect(findMonsterArt('goblin_rushr')).toBeUndefined()
    expect(findMonsterArt('')).toBeUndefined()
  })

  it('★ 아이템 표와 섞이지 않는다 — 접두사가 겹치는 날 도깨비 칸에 칼이 그려진다', () => {
    // `bestiaryCells.ts` 가 그림이 0장이던 시절부터 적어 둔 경고다. 표를 나눠 둔 것이
    // 그 답이고, 이 검사가 「나중에 하나로 합치자」를 막는다.
    const shared = listMonsterArtIds().filter((id) => id.startsWith('sword') || id.startsWith('bow'))
    expect(shared).toEqual([])
  })
})
