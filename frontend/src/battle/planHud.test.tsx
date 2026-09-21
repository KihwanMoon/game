/**
 * 도면 위 HUD — 상태를 보려고 탭을 옮기지 않아도 되는가 (2026-09-21 요청).
 *
 * **상태가 시트의 첫 탭이라 로그나 규칙표를 보는 동안 사라진다.** 그런데 체력·상태이상·
 * 소모품·쿨타임은 「지금 무엇을 할 수 있나」를 정하는 값이라 판이 도는 내내 보여야 한다.
 *
 * 전용 줄을 안 두고 겹치는 이유는 회계다 — 고정 줄 하나가 곧 시트를 그만큼 밀어내고,
 * 2026-09-08 에 상태 줄 44px 을 뺀 것이 그 판단이었다. 여기서 보는 것은 **그 규율을
 * 안 깼는가**와 **색만으로 말하지 않는가** 둘이다.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { buildPlanHud } from './planHud'
import { PlanHudLayer, countGaugeCells, readCooldownPercent } from './PlanHudLayer'
import type { VitalInput } from './vitalRows'

const INPUT: VitalInput = {
  hp: 18,
  hpMax: 100,
  potions: 2,
  potionsMax: 3,
  scrolls: 0,
  scrollsMax: 1,
  cpuUsed: 5,
  cpuBudget: 8,
  carried: new Map([
    ['POTION', 3],
    ['SCROLL', 1],
  ]),
  held: new Map([
    ['POTION', 2],
    ['SCROLL', 0],
  ]),
  statuses: new Map([
    ['POISON', 3],
    ['SLOW', 0],
  ]),
  skills: ['SKILL_1', 'SKILL_2'],
  cooldowns: new Map([
    ['SKILL_1', 0],
    ['SKILL_2', 2],
  ]),
  totals: new Map([
    ['SKILL_1', 6],
    ['SKILL_2', 4],
  ]),
}

describe('겹칠 값 고르기', () => {
  const hud = buildPlanHud(INPUT)

  it('★ 안 걸린 상태이상은 안 세운다 — 귀퉁이에서 빈 칸은 곧 가린 칸이다', () => {
    expect(hud.statuses.map((one) => one.label)).toEqual(['중독'])
  })

  it('★ 안 들고 온 소모품은 안 세운다 — 다섯 칸이 늘 서면 도면을 가린다', () => {
    expect(hud.items.map((one) => one.code)).toEqual(['PO', 'SC'])
  })

  it('★ 다 쓴 칸은 남는다 — 사라지면 「원래 없었다」로 읽힌다', () => {
    expect(hud.items.find((one) => one.code === 'SC')?.held).toBe(0)
  })

  it('★ 쓰는 재주는 쿨이 없어도 늘 선다 — 사라지면 「정보가 없어졌다」다', () => {
    expect(hud.skills).toHaveLength(2)
    expect(hud.skills[0]?.left).toBe(0)
  })

  it('경고 기준이 상태 탭과 같다', () => {
    expect(hud.isLow).toBe(true)
    expect(buildPlanHud({ ...INPUT, hp: 80 }).isLow).toBe(false)
  })
})

describe('그리는 법', () => {
  const html = renderToStaticMarkup(<PlanHudLayer hud={buildPlanHud(INPUT)} />)

  it('네 귀퉁이 중 셋에 선다 — 우상단은 비워 둔다', () => {
    expect(html).toContain('hud-pin--tl')
    expect(html).toContain('hud-pin--bl')
    expect(html).toContain('hud-pin--br')
  })

  it('★ 체력은 칸과 숫자로 함께 말한다 — 색이 유일한 채널이면 안 된다', () => {
    expect(html).toContain('hud-hp__bar')
    expect(html).toContain('18 / 100')
  })

  it('★ 남은 쿨을 숫자로도 적는다 — 그늘만이면 「거의 찼다」와 「막 썼다」가 같다', () => {
    expect(html).toContain('hud-skill__shade')
    expect(html).toMatch(/hud-skill__left">2</)
  })

  it('★ 보조 기술이 읽을 말이 있다 — 그늘과 코드는 눈으로만 보인다', () => {
    expect(html).toContain('준비됨')
    expect(html).toContain('2틱 남음')
    expect(html).toContain('탕약 2 / 3')
  })

  it('0 이 아니면 게이지가 최소 한 칸 — 죽은 것과 거의 죽은 것이 같으면 안 된다', () => {
    expect(countGaugeCells(1, 100)).toBe(1)
    expect(countGaugeCells(0, 100)).toBe(0)
    expect(countGaugeCells(50, 100)).toBe(5)
  })

  it('그늘 높이가 남은 쿨 비율이다', () => {
    expect(readCooldownPercent({ label: 'x', left: 2, total: 4 })).toBe(50)
    expect(readCooldownPercent({ label: 'x', left: 0, total: 6 })).toBe(0)
    // 쿨이 없는 재주는 덮지 않는다.
    expect(readCooldownPercent({ label: 'x', left: 3, total: 0 })).toBe(0)
  })
})

describe('높이를 안 먹는다', () => {
  it('★ 겹치는 층이다 — 전용 줄을 두면 시트가 그만큼 밀린다', () => {
    const css = readFileSync(fileURLToPath(new URL('./battle.css', import.meta.url)), 'utf8')
    const block = css.slice(css.indexOf('.hud-layer {'), css.indexOf('}', css.indexOf('.hud-layer {')))
    expect(block).toContain('position: absolute')
    // 도면의 칸을 가리면 고르는 일이 막힌다.
    expect(block).toContain('pointer-events: none')
  })
})
