/**
 * 스냅샷은 제 층에만 얹힌다 — 파이썬 `test_snapshot_floor` 의 짝 (G3).
 *
 * 자리 이름이 층을 구분하지 않아 1층 방에 9층 개체가 서던 자리다. 두 코어가 같은 값을
 * 썼기 때문에 검증은 어긋나지 않았고, 그래서 조용했다 — 어긋난 것은 게임이었다.
 */
import { describe, expect, it } from 'vitest'

import type { MonsterSnapshot } from '../schemas/monsterSnapshot'
import { sortSnapshots } from '../schemas/monsterSnapshot'
import { buildFloorOverrides } from './runBattle'

/**
 * 같은 자리 이름을 가진 스냅샷 하나.
 *
 * @param zoneFloor 사는 층.
 * @param level 레벨.
 * @param recordId 개체 기록 id.
 * @returns 스냅샷.
 */
function build(zoneFloor: number, level: number, recordId = 0): MonsterSnapshot {
  return {
    entityId: 'goblin_rusher_0',
    recordId: recordId || zoneFloor,
    kindId: 'goblin_rusher',
    tier: 'NORMAL',
    level,
    hpMax: 10 * level,
    attack: level,
    defense: 0,
    attackRange: 0,
    skills: [],
    potions: -1,
    ruleSlots: 0,
    cpuBudget: 0,
    zoneFloor,
  }
}

describe('층별 스냅샷', () => {
  it('★ 1층 방에 9층 개체가 서지 않는다 — 버그 그 자체다', () => {
    const picked = buildFloorOverrides([build(1, 1), build(9, 9)], 1)
    expect(picked.get('goblin_rusher_0')?.level).toBe(1)
  })

  it('★ 층마다 제 것이 선다 — 한 티켓이 1층부터 10층까지 돈다', () => {
    const all = Array.from({ length: 10 }, (_unused, index) => build(index + 1, index + 1))
    for (let floor = 1; floor <= 10; floor += 1) {
      expect(buildFloorOverrides(all, floor).get('goblin_rusher_0')?.level).toBe(floor)
    }
  })

  it('얼려 둔 것이 없는 층은 템플릿 그대로 돈다', () => {
    expect(buildFloorOverrides([build(3, 3)], 1).size).toBe(0)
  })

  it('★ 층을 모르는 스냅샷(0)은 그대로 얹는다 — 옛 티켓이 예전처럼 돌아야 한다', () => {
    expect(buildFloorOverrides([build(0, 4)], 1).get('goblin_rusher_0')?.level).toBe(4)
    expect(buildFloorOverrides([build(0, 4)], 7).get('goblin_rusher_0')?.level).toBe(4)
  })

  it('★ 정렬이 전순서다 — 이름이 겹치면 들어온 순서가 남는다', () => {
    const first = sortSnapshots([build(9, 9), build(1, 1), build(3, 3)])
    const second = sortSnapshots([build(3, 3), build(9, 9), build(1, 1)])
    expect(first.map((item) => item.zoneFloor)).toEqual([1, 3, 9])
    expect(second.map((item) => item.zoneFloor)).toEqual([1, 3, 9])
  })

  it('같은 층에 같은 이름이 둘이면 레코드 id 가 순서를 정한다', () => {
    const rows = sortSnapshots([build(2, 2, 77), build(2, 2, 12)])
    expect(rows.map((item) => item.recordId)).toEqual([12, 77])
  })

  it('구버전 절에는 층이 없다 — 0 으로 읽어야 옛 티켓이 예전처럼 돈다', async () => {
    const { parseSnapshot } = await import('../schemas/monsterSnapshot')
    const raw = {
      entity_id: 'goblin_rusher_0',
      record_id: 1,
      kind_id: 'goblin_rusher',
      tier: 'NORMAL',
      level: 4,
      hp_max: 40,
      attack: 4,
      defense: 0,
      rule_slots: 0,
      cpu_budget: 0,
    }
    expect(parseSnapshot(raw).zoneFloor).toBe(0)
  })
})

describe('스냅샷이 종을 정한다', () => {
  it('★ 도플갱어가 방에 선다 — 파이썬 `test_doppel_spawn` 의 짝 (G3)', async () => {
    const { buildEngine, parseBalance } = await import('./runBattle')
    const { BALANCE, ROOM_TEMPLATES } = await import('../resources')
    const template = ROOM_TEMPLATES.find((room) => room.templateId === 'corridor')
    if (template === undefined) {
      throw new Error('corridor 가 없다')
    }
    const slot = `${template.enemySpawns[0]?.kind ?? ''}_0`
    const engine = buildEngine({
      template,
      balance: parseBalance(BALANCE),
      seed: 1,
      isVaried: false,
      snapshots: [{ ...build(1, 3), entityId: slot, kindId: 'doppelganger', hpMax: 140 }],
    })
    expect(engine.state.entities.get(slot)?.kindId).toBe('doppelganger')
  })
})

describe('★ 얼려 둔 키트가 전투에 도달한다 — 파이썬 `test_doppel_build` 의 짝 (G3)', () => {
  // 스탯만 대체하던 때는 **장궁 든 봇의 그림자가 사거리 1 근접**으로 싸웠다. 사거리는
  // 주무기가 정하고 그 주무기는 얼려 뒀는데, 나르는 칸이 없어서 버려지고 있었다.
  const buildRoom = async () => {
    const { buildEngine, parseBalance } = await import('./runBattle')
    const { BALANCE, ROOM_TEMPLATES } = await import('../resources')
    const template = ROOM_TEMPLATES.find((room) => room.templateId === 'corridor')
    if (template === undefined) {
      throw new Error('corridor 가 없다')
    }
    const slot = `${template.enemySpawns[0]?.kind ?? ''}_0`
    return { buildEngine, template, balance: parseBalance(BALANCE), slot }
  }

  it('사거리·스킬·물약이 종의 값을 덮는다', async () => {
    const { buildEngine, template, balance, slot } = await buildRoom()
    const engine = buildEngine({
      template,
      balance,
      seed: 1,
      isVaried: false,
      snapshots: [
        {
          ...build(1, 3),
          entityId: slot,
          kindId: 'doppelganger',
          attackRange: 4,
          skills: ['AIMED_SHOT', 'GUARD_BRACE'],
          potions: 3,
        },
      ],
    })
    const entity = engine.state.entities.get(slot)
    expect(entity?.attackRange).toBe(4)
    expect(entity?.skills).toEqual(['AIMED_SHOT', 'GUARD_BRACE'])
    expect(entity?.consumables.get('POTION')).toBe(3)
  })

  it('★ 안 실린 값은 종의 것으로 떨어진다 — 옛 티켓이 예전과 같아야 한다 (R5)', async () => {
    // 0·빈 것·-1 을 그대로 쓰면 이미 발급된 티켓의 재시뮬이 발급 당시와 달라지고,
    // 정상 제출이 반려된다.
    const { buildEngine, template, balance, slot } = await buildRoom()
    const kind = balance.enemies.find((one) => one.id === 'doppelganger')
    const engine = buildEngine({
      template,
      balance,
      seed: 1,
      isVaried: false,
      snapshots: [{ ...build(1, 3), entityId: slot, kindId: 'doppelganger' }],
    })
    const entity = engine.state.entities.get(slot)
    expect(entity?.attackRange).toBe(kind?.attack_range)
    // null 이 「장착 개념이 안 배선됨 = 전부 허용」이다. 빈 배열(아무것도 없음)과
    // 뜻이 반대라, 스냅샷의 빈 것을 그대로 넘기면 스킬이 통째로 막힌다.
    expect(entity?.skills).toBeNull()
    expect(entity?.consumables.get('POTION')).toBe(kind?.potions ?? 0)
  })
})
