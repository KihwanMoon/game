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

import { renderToStaticMarkup as renderRow } from 'react-dom/server'

import { RuleRow, formatRuleIndex } from '../ds'
import { findUseTagArt } from '../content/itemArt'
import { buildPlanHud, readSkillMark } from './planHud'
import { findArmedPriority, type RuleRowView } from './ruleRows'
import {
  PlanHudLayer,
  countGaugeCells,
  readCooldownPercent,
  readSpentPercent,
} from './PlanHudLayer'
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
    ['BLINK', 2],
  ]),
  held: new Map([
    ['POTION', 2],
    ['SCROLL', 0],
    ['BLINK', 2],
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
    expect(hud.items.map((one) => one.tag)).toEqual(['POTION', 'SCROLL', 'BLINK'])
  })

  it('★ 그림은 **태그**로 찾는다 — 부적 넷이 같은 코드라 코드로는 칸이 안 갈린다', () => {
    // 숫자를 뗀 뒤로 그림이 유일한 신원이다. 셋이 같은 그림이면 셋이 같은 칸이 된다.
    const arts = hud.items.map((one) => one.art)
    expect(arts).toEqual([
      findUseTagArt('POTION'),
      findUseTagArt('SCROLL'),
      findUseTagArt('BLINK'),
    ])
    expect(new Set(arts).size).toBe(arts.length)
  })

  it('모르는 태그는 부적 그림으로 안 떨어진다 — 아는 척하면 그림이 거짓말을 한다', () => {
    expect(findUseTagArt('NOPE')).toBeUndefined()
  })

  it('★ 다 쓴 칸은 남는다 — 사라지면 「원래 없었다」로 읽힌다', () => {
    expect(hud.items.find((one) => one.code === 'SC')?.held).toBe(0)
  })

  it('★ 쓰는 재주는 쿨이 없어도 늘 선다 — 사라지면 「정보가 없어졌다」다', () => {
    expect(hud.skills).toHaveLength(2)
    expect(hud.skills[0]?.left).toBe(0)
  })

  it('★ 칸 표기는 네 글자까지이고, 온이름은 안 버린다', () => {
    // 띄어쓰기를 걷으면 지금 쓰는 재주는 전부 네 글자 안에 들어간다.
    expect(readSkillMark('유성 낙하')).toBe('유성낙하')
    expect(readSkillMark('연쇄 번개')).toBe('연쇄번개')
    expect(readSkillMark('돌려치기')).toBe('돌려치기')
    // 그보다 길면 앞쪽만 남는다 — 정본은 `label` 이다.
    expect(readSkillMark('아주 긴 재주 이름')).toBe('아주긴재')
    expect(hud.skills.every((one) => one.label.replace(/\s+/gu, '').startsWith(one.mark))).toBe(
      true,
    )
  })

  it('경고 기준이 상태 탭과 같다', () => {
    expect(hud.isLow).toBe(true)
    expect(buildPlanHud({ ...INPUT, hp: 80 }).isLow).toBe(false)
  })
})

/** 그 귀퉁이의 마크업만. 다른 귀퉁이의 글자가 섞이면 검사가 엉뚱한 것을 본다. */
function readPin(html: string, pin: string): string {
  const at = html.indexOf(`hud-pin--${pin}`)
  return html.slice(at, html.indexOf('hud-pin--', at + 1) === -1 ? undefined : html.indexOf('hud-pin--', at + 1))
}

/**
 * 눈에 보이는 글자만. 태그를 통째로 걷어 낸다 — `title`·보조 기술용 말·그림 주소는
 * 눈으로 읽는 채널이 아니고, 그림 주소(데이터 URI)에는 숫자가 잔뜩 들어 있다.
 */
function readSeen(markup: string): string {
  return markup.replace(/<span class="ds-sr">[^<]*<\/span>/gu, '').replace(/<[^>]*>/gu, '')
}

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

  it('★ 소모품·재주는 한 칸씩 선다 — 종류가 늘어도 도면 한 열 안에 머문다', () => {
    expect(readPin(html, 'bl').match(/class="hud-cell hud-cell--/gu)).toHaveLength(3)
    expect(readPin(html, 'br').match(/class="hud-cell hud-cell--/gu)).toHaveLength(2)
  })

  it('★ 소모품도 재주도 그림으로 선다 — 34px 칸에 「유성 낙하」는 안 들어간다', () => {
    expect(readPin(html, 'bl')).toContain('hud-cell__art')
    expect(readPin(html, 'br')).toContain('hud-cell__art')
  })

  it('★ 그림이 없으면 글자로 떨어진다 — 빈 칸으로 두면 무엇을 쓰는지 사라진다', () => {
    // 정본에 없는 재주 id 는 그림도 이름도 없다. 그때 남는 것이 짧은 표기다.
    const odd = renderToStaticMarkup(
      <PlanHudLayer hud={buildPlanHud({ ...INPUT, skills: ['NO_SUCH_SKILL'] })} />,
    )
    expect(readPin(odd, 'br')).toContain('hud-cell__mark')
    expect(readPin(odd, 'br')).not.toContain('hud-cell__art')
  })

  it('★ 칸에 숫자를 안 적는다 (2026-09-21 요청) — 대신 그늘이 남은 만큼을 말한다', () => {
    // 부정 검사를 혼자 두지 않는다: 같은 값이 보조 기술용 말에는 **있다**.
    expect(readSeen(readPin(html, 'bl'))).not.toMatch(/\d/u)
    expect(readSeen(readPin(html, 'br'))).not.toMatch(/[0-9]틱/u)
    expect(html).toContain('탕약 2 / 3')
    expect(html).toContain('2틱 남음')
    expect(html).toContain('준비됨')
  })

  it('★ 못 쓰는 칸은 셋으로 말한다 — 그늘·괘선·글리프 (design/README D-1)', () => {
    // 다 쓴 부적과 도는 쿨 둘 다 ✕ 가 선다. 그늘만 남기면 「거의 찼다」와 못 쓰는
    // 것이 같은 그림이 된다 — 숫자를 뗀 뒤로 그 구분을 글리프가 맡는다.
    expect(readPin(html, 'bl').match(/hud-cell--out/gu)).toHaveLength(1)
    expect(readPin(html, 'br').match(/hud-cell--out/gu)).toHaveLength(1)
    expect(html).toContain('hud-cell__x')
    expect(html).toContain('hud-cell__shade')
  })

  it('다 안 쓴 칸에는 그늘이 아예 없다 — 0%% 를 그리면 밑동 괘선만 꼭대기에 남는다', () => {
    const full = renderToStaticMarkup(
      <PlanHudLayer hud={buildPlanHud({ ...INPUT, held: new Map([['POTION', 3]]), carried: new Map([['POTION', 3]]), skills: [] })} />,
    )
    expect(readPin(full, 'bl')).not.toContain('hud-cell__shade')
  })

  it('0 이 아니면 게이지가 최소 한 칸 — 죽은 것과 거의 죽은 것이 같으면 안 된다', () => {
    expect(countGaugeCells(1, 100)).toBe(1)
    expect(countGaugeCells(0, 100)).toBe(0)
    expect(countGaugeCells(50, 100)).toBe(5)
  })

  it('그늘 높이가 남은 쿨 비율이다', () => {
    expect(readCooldownPercent({ label: 'x', art: '', mark: 'x', left: 2, total: 4 })).toBe(50)
    expect(readCooldownPercent({ label: 'x', art: '', mark: 'x', left: 0, total: 6 })).toBe(0)
    // 쿨이 없는 재주는 덮지 않는다.
    expect(readCooldownPercent({ label: 'x', art: '', mark: 'x', left: 3, total: 0 })).toBe(0)
  })

  it('★ 소모품 그늘은 **쓴 만큼**이다 — 밝게 남은 것이 지금 들고 있는 수다', () => {
    const one = { tag: 'POTION', code: 'PO', label: '탕약', art: '' }
    expect(readSpentPercent({ ...one, held: 3, carried: 3 })).toBe(0)
    expect(readSpentPercent({ ...one, held: 2, carried: 3 })).toBe(33)
    expect(readSpentPercent({ ...one, held: 0, carried: 3 })).toBe(100)
    // 들고 온 적이 없는 칸은 애초에 안 선다 — 0 으로 나눠 NaN 을 그리지 않는다.
    expect(readSpentPercent({ ...one, held: 0, carried: 0 })).toBe(0)
  })
})

describe('발동한 내력 번호 — 없어진 지시선을 대신한다 (2026-09-21 요청)', () => {
  const hud = buildPlanHud(INPUT)

  it('★ 규칙 줄과 **같은 글자**로 적는다 — 한쪽이 `03` 이고 다른 쪽이 `3` 이면 안 이어진다', () => {
    const corner = renderToStaticMarkup(<PlanHudLayer armed={3} hud={hud} />)
    const row = renderRow(
      <RuleRow
        action="일격"
        armed
        condition="적거리(2) <= 사거리(3)"
        cpu={{ used: 2, budget: 8 }}
        index={3}
        state="true"
      />,
    )
    expect(formatRuleIndex(3)).toBe('03')
    expect(readPin(corner, 'tr')).toContain(formatRuleIndex(3))
    expect(row).toContain(formatRuleIndex(3))
  })

  it('★ 두 끝이 같은 광원이다 — 번호는 황동, 그 줄도 황동', () => {
    const css = readFileSync(fileURLToPath(new URL('./battle.css', import.meta.url)), 'utf8')
    // 이쪽 끝.
    expect(css).toContain('.hud-rule__num { color: var(--text-accent);')
    // 저쪽 끝은 ds 가 칠한다. 규칙 줄이 황동을 잃으면 이음의 한쪽이 없어진다.
    const ds = readFileSync(fileURLToPath(new URL('../ds/ds.css', import.meta.url)), 'utf8')
    expect(ds).toContain('.ds-rule-row--armed')
    expect(/\.ds-rule-row--armed[^}]*border-left-color: var\(--line-accent\)/.test(ds)).toBe(true)
  })

  it('★ 라벨은 안 칠한다 — 황동은 화면당 세 곳이고 한 곳이 두 곳이 되면 안 된다', () => {
    const css = readFileSync(fileURLToPath(new URL('./battle.css', import.meta.url)), 'utf8')
    expect(css).toContain('.hud-rule__tag { color: var(--text-dim); }')
  })

  it('★ 안 돌았으면 자리는 서되 불은 끈다 — 사라지면 귀퉁이가 틱마다 깜빡인다', () => {
    const idle = readPin(renderToStaticMarkup(<PlanHudLayer armed={null} hud={hud} />), 'tr')
    expect(idle).toContain('hud-rule--idle')
    expect(idle).toContain('이번 틱에는 발동한 내력이 없다')
  })

  it('★ 모르는 화면은 귀퉁이를 비운다 — 「모른다」를 「안 돌았다」로 그리지 않는다', () => {
    // 확인용 페이지처럼 추적 결과가 없는 화면이 있다.
    expect(renderToStaticMarkup(<PlanHudLayer hud={hud} />)).not.toContain('hud-pin--tr')
  })

  it('★ HUD 를 세우는 자리마다 번호도 함께 넘긴다 — 한 골격만 빠지면 그 배치에서만 없다', () => {
    // 2026-09-20 에 겪은 자리다. 로그 덧칠 함수는 멀쩡한데 **부르는 쪽이 안 불러서**
    // 사후 분석만 날것의 id 로 남았고, 그 함수를 보는 검사는 내내 초록이었다.
    //
    // 세는 방식은 `editor/itemArtWiring.test.ts` 와 같다: 넘기는 자리가 세우는 자리
    // 수만큼 있는가. 가로·세로 골격이 둘이라 하나만 빠지는 것이 실제 위험이다.
    for (const path of ['./BattleView.tsx', '../hud/HudScreen.tsx']) {
      const source = readFileSync(fileURLToPath(new URL(path, import.meta.url)), 'utf8')
      const huds = [...source.matchAll(/\bhud=\{/gu)].length
      const armed = [...source.matchAll(/\barmedRule=\{/gu)].length
      expect(huds, `${path}: HUD 를 세우는 자리`).toBeGreaterThan(0)
      expect(armed, `${path}: 번호를 안 넘기는 골격이 남았다`).toBe(huds)
      expect(source, path).toContain('findArmedPriority')
    }
  })

  it('발동한 줄 하나를 고른다 — 규칙표는 처음 참에서 멈추므로 둘일 수 없다', () => {
    const row = (priority: number, armed: boolean): RuleRowView => ({
      priority,
      state: armed ? 'true' : 'false',
      condition: '',
      action: '',
      cpu: { used: 1, budget: 8 },
      armed,
      enabled: true,
    })
    expect(findArmedPriority([row(1, false), row(2, true), row(3, false)])).toBe(2)
    expect(findArmedPriority([row(1, false)])).toBeNull()
    // **0 번도 실제 우선순위다.** `?? null` 이 아니라 `|| null` 이면 0 이 「없음」이 된다.
    expect(findArmedPriority([row(0, true)])).toBe(0)
  })
})

describe('높이를 안 먹는다', () => {
  const css = readFileSync(fileURLToPath(new URL('./battle.css', import.meta.url)), 'utf8')

  /**
   * 그 선택자의 선언 블록.
   *
   * @param selector 찾을 선택자.
   * @returns 중괄호 안.
   */
  function readBlock(selector: string): string {
    const at = css.indexOf(`${selector} {`)
    return css.slice(at, css.indexOf('}', at))
  }

  it('★ 겹치는 층이다 — 전용 줄을 두면 시트가 그만큼 밀린다', () => {
    const block = readBlock('.hud-layer')
    expect(block).toContain('position: absolute')
    // 도면의 칸을 가리면 고르는 일이 막힌다.
    expect(block).toContain('pointer-events: none')
  })

  it('★ 칸 하나가 도면의 한 칸이다 — 정사각이라 세로로 쌓아도 한 열만 먹는다', () => {
    const block = readBlock('.hud-cell')
    expect(block).toContain('inline-size: var(--plan-cell)')
    expect(block).toContain('block-size: var(--plan-cell)')
  })

  it('★ 아래 두 귀퉁이는 세로로 쌓는다 — 가로로 이으면 도면 폭을 가로지른다', () => {
    expect(readBlock('.hud-pin--bl,\n.hud-pin--br')).toContain('flex-direction: column-reverse')
  })
})
