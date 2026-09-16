/**
 * 카탈로그 화면 검사 (관리자, 읽기 전용).
 *
 * **이 화면의 목적은 「어디에 몰려 있는가」다.** 곡선만 보면 튜닝할 수 없다 — 사람들이
 * 실제로 어디서 멈추는지가 보여야 "이 구간이 너무 긴가" 를 물을 수 있다.
 *
 * 격자는 가방과 같은 것을 쓴다 (2026-09-16). 같은 아이템이 관리 화면에서만 다른 모양으로
 * 그려지면, 「무엇이 들어 있는가」를 답하려던 화면이 답을 틀리게 한다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { findItemArt } from '../content/itemArt'
import type { AdminCatalog } from '../storage'
import { CatalogPanel, EnemyDetail, ItemDetail, formatPeopleBar } from './CatalogPanel'
import { buildCatalogEnemyCells, buildCatalogItemCells } from './catalogCells'

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
      attackRange: 4,
      affixes: ['날카로움 +3'],
      requirements: ['attack >= 10'],
    },
    {
      // 손 수가 그림을 가르는 유일한 자리 — 같은 `sword_` 인데 양손은 협도다.
      catalogId: 'sword_great',
      labelKo: '대검',
      kind: 'EQUIPMENT',
      slot: 'WEAPON_MAIN',
      hands: 'TWO',
      grantsSkill: '',
      attackRange: 1,
      affixes: [],
      requirements: [],
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

/**
 * 마크업에 실제로 붙은 그림 주소들.
 *
 * **주소를 날것으로 찾으면 안 잡힌다.** 그림이 data URI 라 안에 작은따옴표가 들어 있고,
 * React 가 그것을 `&#x27;` 로 적는다 — 그래서 제대로 붙어 있어도 `toContain` 이 못 찾는다.
 */
function listArt(html: string): string[] {
  return [...html.matchAll(/class="invg__art" src="([^"]*)"/g)].map((hit) =>
    (hit[1] ?? '').replaceAll('&#x27;', "'"),
  )
}

/**
 * 칸에 실제로 그려진 이름들.
 *
 * **그냥 문자열을 찾으면 안 된다.** 칸의 `aria-label` 이 같은 이름을 담고 있어, 눈에
 * 보이는 이름을 지워도 통과한다 (실제로 그랬다).
 */
function listCellLabels(html: string): string[] {
  return [...html.matchAll(/class="invg__label[^"]*">([^<]*)</g)].map((hit) => hit[1] ?? '')
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
  it('★ 격자에 한 줄도 안 빠진다 — 못 찾는 것은 없는 것과 같다', () => {
    // 칸 이름은 두 글자로 자른다(도면 격자의 규약). 전체 이름은 고른 칸의 상세가 낸다.
    const cells = buildCatalogItemCells(CATALOG.items)
    expect(cells.map((cell) => cell.row.catalogId)).toEqual(
      CATALOG.items.map((row) => row.catalogId),
    )
    expect(listCellLabels(render(CATALOG))).toEqual(['장궁', '대검'])
  })

  it('★ 칸마다 그림이 붙는다 — 카탈로그는 「무엇이 들어 있는가」를 보는 곳이다', () => {
    // 주소까지, 그리고 칸 순서대로 못 박는다. 클래스 이름만 보면 아무 그림이나 붙어도
    // 통과하고, 개수만 보면 두 칸이 같은 그림이어도 통과한다.
    expect(listArt(render(CATALOG))).toEqual([
      findItemArt('bow_long', 'TWO'),
      findItemArt('sword_great', 'TWO'),
    ])
  })

  it('★ 손 수까지 넘긴다 — 안 넘기면 양손 협도가 직검으로 적힌다', () => {
    const glaive = findItemArt('sword_great', 'TWO')
    const sword = findItemArt('sword_great')
    // 두 값이 정말 다른 그림이라는 것부터 못 박는다. 같으면 아래 검사가 헐거워진다.
    expect(glaive).toBeDefined()
    expect(glaive).not.toBe(sword)
    expect(listArt(render(CATALOG))).not.toContain(sword)
  })

  it('★ 무엇을 해 주는가가 칸에 있다 — 여는 재주가 먼저다 (결정 #13)', () => {
    // 도면 격자로 옮기면서 얻은 줄이다. 예전 격자에는 이 자리가 없어, 「이게 뭘 해
    // 주지」를 알려면 칸을 하나씩 눌러야 했다.
    const cells = buildCatalogItemCells(CATALOG.items)
    expect(cells.map((cell) => cell.fact)).toEqual(['재주 AREA_ATTACK', ''])
  })

  it('★ 사거리는 근접(1)일 때 안 적는다 — 모든 칸에 같은 글자가 붙으면 아무 말도 안 한다', () => {
    const cells = buildCatalogItemCells(CATALOG.items)
    expect(cells.map((cell) => cell.countText)).toEqual(['사4', ''])
  })

  it('★ 고르면 접사·요구조건·여는 스킬이 함께 보인다', () => {
    // 격자는 이름과 자리까지만 담고 상세는 아래 한 곳에 편다. 정보가 사라진 것이
    // 아니라 자리를 옮긴 것이며, **옮긴 자리에 다 있는지**가 여기서 볼 것이다.
    const row = CATALOG.items.find((entry) => entry.labelKo === '장궁')
    if (row === undefined) {
      throw new Error('장궁이 픽스처에 없다')
    }
    const html = renderToStaticMarkup(<ItemDetail row={row} />)
    expect(html).toContain('날카로움 +3')
    expect(html).toContain('attack &gt;= 10')
    expect(html).toContain('AREA_ATTACK')
    // 사거리는 상세에만 전체 이름으로 적힌다 — 예전에는 패널 안에 상세가 한 벌 더
    // 적혀 있었고, 그 사본에서 이 줄이 빠져 있었다.
    expect(html).toContain('사거리 4')
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

  it('★ 적 칸은 유형 코드와 얼마나 아픈가를 낸다 — 그려 둔 몬스터 그림이 없다', () => {
    const cells = buildCatalogEnemyCells(CATALOG.enemies)
    expect(cells.map((cell) => [cell.code, cell.countText, cell.fact, cell.art])).toEqual([
      ['RA', 'hp30', '공6 사4', undefined],
    ])
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
