/**
 * 무기 겉모습이 장비에서 온다 (설계/10_외형과_모션).
 *
 * **여기서 지키는 것은 C1·C2 다.** 겉모습은 시뮬 입력이 아니고(서버도 티켓도 안 거친다),
 * `core_version` 에도 안 낀다(그러면 스킨 하나에 시즌이 갈린다).
 */
import { describe, expect, it } from 'vitest'

import { DEFAULT_LOOK, resolveWeaponLook } from './weaponLook'

describe('resolveWeaponLook', () => {
  it('무기마다 다르게 휘두른다 — 자유도가 여기서 나온다', () => {
    expect(resolveWeaponLook('sword_saber')).toEqual({ shape: 'curved', motion: 'slash' })
    expect(resolveWeaponLook('axe_heavy')).toEqual({ shape: 'axe', motion: 'chop' })
    expect(resolveWeaponLook('sword_short')).toEqual({ shape: 'straight', motion: 'thrust' })
  })

  it('★ 활은 안 휘두른다', () => {
    // 사거리 넷 다섯에서 칼자국이 뜨면 무슨 일이 있었는지가 거짓으로 읽힌다.
    expect(resolveWeaponLook('bow_long').shape).toBe('none')
    expect(resolveWeaponLook('bow_storm').shape).toBe('none')
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
