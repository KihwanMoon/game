/**
 * 무기 겉모습이 장비에서 온다 (설계/10_외형과_모션).
 *
 * **여기서 지키는 것은 C1·C2 다.** 겉모습은 시뮬 입력이 아니고(서버도 티켓도 안 거친다),
 * `core_version` 에도 안 낀다(그러면 스킨 하나에 시즌이 갈린다).
 */
import { describe, expect, it } from 'vitest'

import rawBalance from '@resources/balance/balance.json'
import rawLooks from '@resources/balance/looks.json'

import { PLAYER_ENTITY_ID } from '../core/services/runBattle'

import { DEFAULT_LOOK, buildLookOf, resolveActorLook, resolveWeaponLook } from './weaponLook'

const SOURCE = rawLooks as unknown as {
  looks: Record<string, { shape: string }>
  monsters: Record<string, { shape: string }>
}
const LOOKS = SOURCE.looks
const MONSTERS = SOURCE.monsters

/** 밸런스가 아는 적 전부. 표가 그것을 다 덮는지 여기서 대조한다. */
const ENEMIES = (
  rawBalance as unknown as { enemies: readonly { id: string; attack_range: number }[] }
).enemies

describe('resolveWeaponLook', () => {
  it('무기마다 다르게 휘두른다 — 자유도가 여기서 나온다', () => {
    expect(resolveWeaponLook('sword_saber')).toEqual({ shape: 'curved', motion: 'slash' })
    expect(resolveWeaponLook('axe_heavy')).toEqual({ shape: 'axe', motion: 'chop' })
    expect(resolveWeaponLook('sword_short')).toEqual({ shape: 'straight', motion: 'thrust' })
  })

  it('★ 활은 안 휘두른다 — 대신 화살이 난다', () => {
    // 사거리 넷 다섯에서 칼자국이 뜨면 거짓으로 읽히고, 아무것도 안 그리면 고리 하나만
    // 남아 무슨 일이 있었는지가 화면에 없다.
    expect(resolveWeaponLook('bow_long')).toEqual({ shape: 'arrow', motion: 'fly' })
    expect(resolveWeaponLook('bow_storm')).toEqual({ shape: 'arrow', motion: 'fly' })
  })

  it('★ 「아무것도 안 그림」은 여전히 표현할 수 있다', () => {
    // `none` 은 지우지 않았다 — 그릴 것이 정말 없는 자리가 나중에 생긴다. 다만 지금
    // 표에는 쓰는 무기가 없다: 활은 이제 화살을 날린다.
    const shapes = Object.values(LOOKS).map((one) => one.shape)
    expect(shapes).not.toContain('none')
  })

  it('★ 모르는 무기도 도면을 안 깬다', () => {
    // 새 아이템이 카탈로그에 들어와도 겉모습 표가 아직 모를 수 있다.
    expect(resolveWeaponLook('아직_없는_무기')).toEqual(DEFAULT_LOOK)
    expect(resolveWeaponLook('')).toEqual(DEFAULT_LOOK)
  })

  it('맨몸도 휘두른다 — 기본 꼴이 있다', () => {
    expect(DEFAULT_LOOK.shape).not.toBe('none')
  })
})

describe('겉모습이 코어에 안 낀다', () => {
  it('★ 겉모습 표에 버전 키가 없다 (계약 C2)', async () => {
    // 버전 키가 붙는 순간 `core_version` 의 축이 되고, 그러면 칼 모양을 고칠 때마다
    // 순위표 시즌이 갈리고 저장된 리플레이가 무효가 된다.
    const raw = (await import('@resources/balance/looks.json')) as unknown as {
      default: unknown
    }
    const keys = Object.keys(raw as Record<string, unknown>)
    expect(keys.some((key) => key.includes('version'))).toBe(false)
  })
})

describe('★ 화면 둘이 같은 표를 본다 — 리플레이만 기본 자국이었다 (실제 신고)', () => {
  it('플레이어는 낀 무기로 휘두른다', () => {
    const lookOf = buildLookOf('axe_heavy')
    expect(lookOf(PLAYER_ENTITY_ID, PLAYER_ENTITY_ID, 1)).toEqual(resolveWeaponLook('axe_heavy'))
  })

  it('맨몸은 기본 자국이다 — 안 넘긴 것과 맨몸은 같은 그림이되 다른 뜻이다', () => {
    expect(buildLookOf('')(PLAYER_ENTITY_ID, PLAYER_ENTITY_ID, 1)).toEqual(DEFAULT_LOOK)
  })

  it('★ 관전과 되감기가 같은 답을 낸다', () => {
    // 두 화면이 각자 표를 만들면 방금 본 판과 다른 칼이 되감기에 뜬다. 사후 분석이
    // 표를 아예 안 받아 실제로 그랬다 — 관전은 도끼, 되감기는 직검이었다.
    const watching = buildLookOf('sword_saber')
    const rewinding = buildLookOf('sword_saber')
    const seen = watching(PLAYER_ENTITY_ID, PLAYER_ENTITY_ID, 1)
    expect(rewinding(PLAYER_ENTITY_ID, PLAYER_ENTITY_ID, 1)).toEqual(seen)
    expect(seen).not.toEqual(DEFAULT_LOOK)
  })

  it('★ 모르는 무기가 멀리 닿으면 날아간다 — 기본 직검으로 떨어지지 않는다', () => {
    const lookOf = buildLookOf('아직_없는_활')
    expect(lookOf(PLAYER_ENTITY_ID, PLAYER_ENTITY_ID, 5).motion).toBe('fly')
    expect(lookOf(PLAYER_ENTITY_ID, PLAYER_ENTITY_ID, 1)).toEqual(DEFAULT_LOOK)
  })
})

describe('★ 적도 제 무장으로 친다', () => {
  it('짐승은 물고 골렘은 후려치고 궁수는 쏜다', () => {
    expect(resolveActorLook('dire_wolf', 1).shape).toBe('fang')
    expect(resolveActorLook('shield_golem', 1).shape).toBe('fist')
    expect(resolveActorLook('goblin_archer', 4)).toEqual({ shape: 'arrow', motion: 'fly' })
    expect(resolveActorLook('arch_summoner', 4)).toEqual({ shape: 'bolt', motion: 'fly' })
  })

  it('★ 사거리 3 이상은 하나도 훑지 않는다 — 훑는 자국이 사거리를 거짓말한다', () => {
    const enemies = ENEMIES.filter((enemy) => enemy.attack_range >= 3)
    expect(enemies.length).toBeGreaterThan(0)
    for (const enemy of enemies) {
      expect(resolveActorLook(enemy.id, enemy.attack_range).motion).toBe('fly')
    }
  })

  it('★ 밸런스에 있는 적은 도플갱어만 빼고 전부 표에 있다', () => {
    // 표에 없는 적은 거리로 근사되는데, 그것은 안전망이지 답이 아니다.
    const missing = ENEMIES.map((enemy) => enemy.id).filter(
      (id) => id !== 'doppelganger' && MONSTERS[id] === undefined,
    )
    expect(missing).toEqual([])
  })

  it('★ 그림자는 일부러 표에 없다 — 무장이 종이 아니라 죽은 빌드의 것이다', () => {
    expect(MONSTERS['doppelganger']).toBeUndefined()
    // 장궁 든 그림자가 사거리 다섯에서 칼을 휘두르면 그것도 거짓이다.
    expect(resolveActorLook('doppelganger', 5).motion).toBe('fly')
    expect(resolveActorLook('doppelganger', 1)).toEqual(DEFAULT_LOOK)
  })

  it('새 적이 들어와도 도면이 안 깨진다', () => {
    expect(resolveActorLook('아직_없는_적', 1)).toEqual(DEFAULT_LOOK)
  })

  it('꼴은 닫힌 집합이다 (계약 C6)', () => {
    const known = new Set(['straight', 'curved', 'axe', 'arrow', 'fang', 'bolt', 'fist'])
    for (const id of Object.keys(MONSTERS)) {
      expect(known.has(resolveActorLook(id, 1).shape)).toBe(true)
    }
  })
})
