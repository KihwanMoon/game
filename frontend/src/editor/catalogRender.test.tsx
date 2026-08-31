/**
 * 카탈로그 화면 검사 (관리자, 읽기 전용).
 *
 * **이 화면의 목적은 「어디에 몰려 있는가」다.** 곡선만 보면 튜닝할 수 없다 — 사람들이
 * 실제로 어디서 멈추는지가 보여야 "이 구간이 너무 긴가" 를 물을 수 있다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { AdminCatalog } from '../storage'
import { CatalogPanel, EnemyDetail, ItemDetail, formatPeopleBar } from './CatalogPanel'

const CATALOG: AdminCatalog = {
  coreVersion: 'b5.v2.e1',
  items: [
    {
      catalogId: 'bow_long',
      labelKo: '장궁',
      kind: 'EQUIPMENT',
      slot: 'WEAPON_MAIN',
      hands: 'TWO',
      grantsSkill: 'AREA_ATTACK',
      affixes: ['날카로움 +3'],
      requirements: ['attack >= 10'],
    },
  ],
  enemies: [
    {
      kindId: 'goblin_archer',
      labelKo: '고블린 궁수',
      type: 'RANGED',
      rulesetId: 'ai_archer',
      hpMax: 30,
      attack: 6,
      defense: 1,
      attackRange: 4,
    },
  ],
  levelCurve: [
    { level: 1, requiredXp: 120, totalXp: 0, bonusRuleSlots: 0, bonusCpu: 0, bonusFlags: 0, statPoints: 0, attackIfAllStr: 0, players: 50 },
    { level: 2, requiredXp: 141, totalXp: 120, bonusRuleSlots: 0, bonusCpu: 0, bonusFlags: 0, statPoints: 3, attackIfAllStr: 3, players: 4 },
    { level: 9, requiredXp: 900, totalXp: 3000, bonusRuleSlots: 1, bonusCpu: 2, bonusFlags: 1, statPoints: 24, attackIfAllStr: 24, players: 0 },
  ],
  caps: { maxBonusRuleSlots: 4, maxBonusCpu: 12, maxBonusFlags: 2 },
}

function render(catalog: AdminCatalog | undefined) {
  return renderToStaticMarkup(<CatalogPanel catalog={catalog} />)
}

describe('관리자가 아니면', () => {
  it('★ 아무것도 그리지 않는다', () => {
    expect(render(undefined)).toBe('')
  })
})

describe('읽기 전용이라고 화면이 말한다', () => {
  it('★ 여기서 고칠 수 없다는 것과 어디서 고치는지를 함께 적는다', () => {
    // 런타임에 바꾸면 이미 발급된 티켓이 다른 게임을 가리킨다 (결정 #06, R5).
    const html = render(CATALOG)
    expect(html).toContain('여기서 고칠 수 없다')
    expect(html).toContain('resources')
  })
})

describe('아이템 카탈로그', () => {
  it('★ 격자에 이름이 하나도 안 빠진다 — 못 찾는 것은 없는 것과 같다', () => {
    // **칸의 이름 자리**를 본다. 그냥 문자열을 찾으면 Thumb 의 aria-label 이 같은 이름을
    // 담고 있어, 눈에 보이는 이름을 지워도 검사가 통과한다 (실제로 그랬다).
    const html = render(CATALOG)
    for (const row of CATALOG.items) {
      expect(html).toContain(`<span class="ds-cell__name">${row.labelKo}</span>`)
    }
  })

  it('★ 고르면 접사·요구조건·여는 스킬이 함께 보인다', () => {
    // 격자는 이름과 분류까지만 담고 상세는 아래 한 곳에 편다. 정보가 사라진 것이
    // 아니라 자리를 옮긴 것이며, **옮긴 자리에 다 있는지**가 여기서 볼 것이다.
    const row = CATALOG.items.find((entry) => entry.labelKo === '장궁')
    if (row === undefined) {
      throw new Error('장궁이 픽스처에 없다')
    }
    const html = renderToStaticMarkup(<ItemDetail row={row} />)
    expect(html).toContain('날카로움 +3')
    expect(html).toContain('attack &gt;= 10')
    expect(html).toContain('AREA_ATTACK')
  })

  it('★ 적 상세에는 규칙표가 있다 — 몬스터의 정체는 스탯이 아니라 규칙표다', () => {
    const row = CATALOG.enemies[0]
    if (row === undefined) {
      throw new Error('적이 픽스처에 없다')
    }
    const html = renderToStaticMarkup(<EnemyDetail row={row} />)
    expect(html).toContain(row.rulesetId)
    expect(html).toContain(String(row.hpMax))
  })
})

describe('인원 막대', () => {
  it('★ 숫자만으로는 분포가 안 보인다', () => {
    expect(formatPeopleBar(50, 50)).toHaveLength(12)
    expect(formatPeopleBar(4, 50)).toBe('▮')
  })

  it('0명이면 막대를 그리지 않는다 — 빈 막대가 1명처럼 읽힌다', () => {
    expect(formatPeopleBar(0, 50)).toBe('')
    expect(formatPeopleBar(3, 0)).toBe('')
  })
})
