/**
 * 도감 화면 검사 (E단계).
 *
 * **"내 아이템을 들고 있다" 가 화면에 없으면 사본을 만드는 뜻이 사라진다.** 되찾으러
 * 가는 동기가 도달하지 않으면 World Loop 이 서지 않는다 (docs/설계/6_몬스터 §8).
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { BestiaryPanel, listRuleLines } from './BestiaryPanel'
import type { BestiaryEntry } from '../storage'

const ENTRIES: readonly BestiaryEntry[] = [
  {
    recordId: 1,
    labelKo: '사나운 고블린 돌격병',
    tier: 'ELITE',
    level: 3,
    levelCap: 5,
    zoneFloor: 1,
    entitySlot: 'goblin_rusher_0',
    hpMax: 74,
    attack: 14,
    defense: 3,
    ruleset: {
      rulesetId: 'ai_rusher',
      version: 1,
      rules: [
        {
          priority: 1,
          cpuCost: 1,
          action: 'ATTACK',
          target: 'NEAREST',
          setFlag: null,
          actionParam: null,
          conditions: {
            op: 'SINGLE',
            terms: [
              { lhs: 'target_distance', lhsParam: 'NEAREST', comparison: '<=', rhs: 1 },
            ],
          },
        },
      ],
    },
    affixes: ['사나운'],
    trophies: ['helm_iron'],
    holdsMine: true,
  },
]

describe('도감 패널', () => {
  const markup = renderToStaticMarkup(<BestiaryPanel entries={ENTRIES} link="online" />)

  it('★ 내 장비를 들고 있다고 말한다 — 되찾기 동기', () => {
    expect(markup).toContain('내 장비 보유')
    expect(markup).toContain('helm_iron')
  })

  it('레벨과 상한을 함께 적는다 — 얼마나 더 클 수 있는지가 표적 판단에 든다', () => {
    expect(markup).toContain('lv 3/5')
  })

  it('★ 규칙표를 그대로 낸다 — 줄 수로 접으면 카운터를 설계할 수 없다', () => {
    // 서버는 처음부터 규칙표를 보내고 있었는데 화면이 `rules.length` 로 접어 버렸다.
    // 도감이 표적 목록인 이유가 바로 그 규칙표다 (`설계/6_몬스터` §8).
    expect(markup).toContain('규칙표 1줄')
    expect(listRuleLines(ENTRIES[0] as BestiaryEntry).join('\n')).toContain('ATTACK')
  })

  it('★ 얼마나 센지도 적는다 — 규칙표만으로는 이길 수 있는지 알 수 없다', () => {
    expect(markup).toContain('hp 74')
    expect(markup).toContain('공 14')
  })

  it('규칙표가 없으면 펼칠 것도 없다 — 카탈로그 기본표가 빈 경우다', () => {
    const bare = { ...(ENTRIES[0] as BestiaryEntry), ruleset: undefined }
    expect(listRuleLines(bare)).toEqual([])
  })

  it('접사가 붙은 이름으로 개체를 지목한다', () => {
    expect(markup).toContain('사나운 고블린 돌격병')
  })

  it('★ 등급을 색으로 칠하지 않는다 — 글자로 적는다', () => {
    expect(markup).toContain('ELITE')
    expect(markup).not.toContain('brass')
  })
})

describe('도감 패널 — 빈 경우', () => {
  it('서버 없음과 빈 세계를 구분해서 말한다', () => {
    const offline = renderToStaticMarkup(<BestiaryPanel entries={undefined} link="offline" />)
    const empty = renderToStaticMarkup(<BestiaryPanel entries={[]} link="online" />)
    expect(offline).toContain('서버에 닿지 못했다')
    expect(empty).toContain('아직 세계에 지속 몬스터가 없다')
  })
})

describe('도감 스타일', () => {
  const css = readFileSync(fileURLToPath(new URL('./editor.css', import.meta.url)), 'utf8')
  const block = css.slice(css.indexOf('/* ── 도감'))

  it('생 hex 색이 없다', () => {
    expect(block).not.toMatch(/#[0-9a-fA-F]{3,8}\b/)
  })

  it('자체 미디어쿼리를 두지 않는다', () => {
    expect(block).not.toContain('@media')
  })
})
