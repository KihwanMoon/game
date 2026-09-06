/**
 * 무기 겉모습이 장비에서 온다 (설계/10_외형과_모션).
 *
 * **여기서 지키는 것은 C1·C2 다.** 겉모습은 시뮬 입력이 아니고(서버도 티켓도 안 거친다),
 * `core_version` 에도 안 낀다(그러면 스킨 하나에 시즌이 갈린다).
 */
import { describe, expect, it } from 'vitest'

import rawLooks from '@resources/balance/item_looks.json'

import { PLAYER_ENTITY_ID } from '../core/services/runBattle'

import { DEFAULT_LOOK, buildLookOf, resolveWeaponLook } from './weaponLook'

const LOOKS = (rawLooks as unknown as { looks: Record<string, { shape: string }> }).looks

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
    const raw = (await import('@resources/balance/item_looks.json')) as unknown as {
      default: unknown
    }
    const keys = Object.keys(raw as Record<string, unknown>)
    expect(keys.some((key) => key.includes('version'))).toBe(false)
  })
})

describe('★ 화면 둘이 같은 표를 본다 — 리플레이만 기본 자국이었다 (실제 신고)', () => {
  it('플레이어는 낀 무기로, 나머지는 기본 자국으로 휘두른다', () => {
    const lookOf = buildLookOf('axe_heavy')
    expect(lookOf(PLAYER_ENTITY_ID)).toEqual(resolveWeaponLook('axe_heavy'))
    expect(lookOf('goblin_rusher_0')).toEqual(DEFAULT_LOOK)
  })

  it('맨몸은 기본 자국이다 — 안 넘긴 것과 맨몸은 같은 그림이되 다른 뜻이다', () => {
    expect(buildLookOf('')(PLAYER_ENTITY_ID)).toEqual(DEFAULT_LOOK)
  })

  it('★ 관전과 되감기가 같은 답을 낸다', () => {
    // 두 화면이 각자 표를 만들면 방금 본 판과 다른 칼이 되감기에 뜬다. 사후 분석이
    // 표를 아예 안 받아 실제로 그랬다 — 관전은 도끼, 되감기는 직검이었다.
    const watching = buildLookOf('sword_saber')
    const rewinding = buildLookOf('sword_saber')
    expect(rewinding(PLAYER_ENTITY_ID)).toEqual(watching(PLAYER_ENTITY_ID))
    expect(watching(PLAYER_ENTITY_ID)).not.toEqual(DEFAULT_LOOK)
  })
})
