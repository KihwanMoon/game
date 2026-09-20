/**
 * 도감 정적 페이지가 성립하는가.
 *
 * **이 페이지들이 이 사이트의 색인될 본문 전부다** (2026-09-20). 게임 본체는 SPA 라
 * 크롤러가 받아 가는 글자가 부트 화면 68자뿐이고, 구글은 JS 를 느리게나마 돌리지만
 * 네이버(Yeti)는 사실상 안 돌린다.
 *
 * 그래서 **글자가 실제로 들어 있는지**를 본다 — 껍데기만 굽고 속이 비면 아무 소용이
 * 없는데, 페이지가 41장 생기므로 눈으로는 안 보인다.
 */
import { describe, expect, it } from 'vitest'

import {
  type CodexInput,
  buildCodexPages,
  buildMonsterPath,
  buildSkillPath,
  buildSkillSentence,
  listRoomsOf,
  listRulesetSkills,
} from './codex'
import { attachParticle, checkHasFinal, escapeHtml, markStrong } from './codexPage'

const INPUT: CodexInput = {
  enemies: [
    {
      id: 'snare_boy',
      label_ko: '덫 동자',
      type: 'CASTER',
      tier: 'NORMAL',
      hp_max: 26,
      attack: 6,
      defense: 0,
      attack_range: 6,
      initiative: 60,
      cpu_budget: 4,
      rule_slots: 3,
      ruleset_id: 'ai_snare_boy',
      _note: '**피해를 안 준다.** 덫 굿은 계수 0 이다.',
    },
  ],
  skills: [
    { id: 'HEX_SNARE', label_ko: '덫 굿', actor: 'enemy', coef_pct: 0, cooldown: 6, telegraph: 1, hits: 'TILES' },
    { id: 'SKILL_1', label_ko: '일격', coef_pct: 160, cooldown: 6, hits: 'TARGET' },
  ],
  rulesets: [
    {
      ruleset_id: 'ai_snare_boy',
      strategy_ko: '먼저 묶는다.',
      rules: [{ action: 'USE_SKILL', action_param: 'HEX_SNARE' }, { action: 'SKILL_1' }],
    },
  ],
  rooms: [{ id: 'snare_grove', label_ko: '덫 숲', min_floor: 11, enemy_spawns: [{ kind: 'snare_boy' }] }],
  items: [{ id: 'sword_great', label_ko: '협도', grants_skill: 'SKILL_1' }],
  art: new Map([['snare_boy', '<svg viewBox="0 0 16 16"></svg>']]),
}

describe('도감 굽기', () => {
  const pages = buildCodexPages(INPUT)

  it('첫 장과 낱장이 모두 나온다', () => {
    expect(pages.map((one) => one.path)).toEqual([
      '/codex/',
      buildMonsterPath('snare_boy'),
      buildSkillPath('HEX_SNARE'),
      buildSkillPath('SKILL_1'),
    ])
  })

  it('★ 껍데기만 굽지 않는다 — 각 장에 읽을 글자가 있다', () => {
    for (const page of pages) {
      const body = page.html.slice(page.html.indexOf('<main'), page.html.indexOf('</main>'))
      const text = body.replace(/<svg[\s\S]*?<\/svg>/g, '').replace(/<[^>]+>/g, ' ')
      expect(text.replace(/\s+/g, ' ').trim().length, page.path).toBeGreaterThan(60)
    }
  })

  it('★ 낱장이 서로 이어진다 — 안 이어지면 크롤러에게 낱장 41개다', () => {
    const monster = pages.find((one) => one.path === buildMonsterPath('snare_boy'))
    expect(monster?.html).toContain(buildSkillPath('HEX_SNARE'))
    const skill = pages.find((one) => one.path === buildSkillPath('HEX_SNARE'))
    expect(skill?.html).toContain(buildMonsterPath('snare_boy'))
  })

  it('장마다 제목·설명·정식 주소가 다르다', () => {
    const titles = pages.map((one) => /<title>([^<]*)<\/title>/.exec(one.html)?.[1])
    expect(new Set(titles).size).toBe(pages.length)
    const canons = pages.map((one) => /rel="canonical" href="([^"]*)"/.exec(one.html)?.[1])
    expect(new Set(canons).size).toBe(pages.length)
  })

  it('그림은 막지 않고 그대로 싣는다 — 막으면 도트가 글자로 보인다', () => {
    const monster = pages.find((one) => one.path === buildMonsterPath('snare_boy'))
    expect(monster?.html).toContain('<svg viewBox="0 0 16 16"></svg>')
  })

  it('★ 여는 장비를 잇는다 — 설명문이 없는 기본 재주는 이것 말고 적을 것이 없다', () => {
    expect(pages.find((one) => one.path === buildSkillPath('SKILL_1'))?.html).toContain('협도')
  })

  it('적 전용은 그 사실을 적는다', () => {
    expect(pages.find((one) => one.path === buildSkillPath('HEX_SNARE'))?.html).toContain('적만 쓰는')
  })
})

describe('읽을거리 만들기', () => {
  it('규칙표가 쓰는 재주를 맨 행동과 인자꼴 양쪽에서 읽는다', () => {
    expect(listRulesetSkills(INPUT.rulesets[0]!)).toEqual(['HEX_SNARE', 'SKILL_1'])
  })

  it('그 종이 나오는 방을 찾는다', () => {
    expect(listRoomsOf(INPUT.rooms, 'snare_boy').map((one) => one.label_ko)).toEqual(['덫 숲'])
    expect(listRoomsOf(INPUT.rooms, 'goblin_rusher')).toEqual([])
  })

  it('★ 조사를 받침으로 가른다 — 틀리면 그 문장만 외국인이 쓴 것처럼 읽힌다', () => {
    expect(checkHasFinal('일격')).toBe(true)
    expect(checkHasFinal('유성 낙하')).toBe(false)
    expect(attachParticle('일격', '은', '는')).toBe('일격은')
    expect(attachParticle('유성 낙하', '은', '는')).toBe('유성 낙하는')
    expect(attachParticle('대상 하나', '을', '를')).toBe('대상 하나를')
  })

  it('수치에서 문장을 만든다', () => {
    expect(buildSkillSentence('일격', INPUT.skills[1]!, '대상 하나')).toBe(
      '일격은 대상 하나를 공격력의 160% 로 친다. 쓰는 그 틱에 나간다. 다시 쓰려면 6틱을 기다린다.',
    )
  })

  it('피해 0 인 재주는 「친다」고 말하지 않는다', () => {
    expect(buildSkillSentence('덫 굿', INPUT.skills[0]!, '예고한 칸')).toContain('예고한 칸에 걸린다')
  })

  it('★ 설명문의 강조를 옮기되 막은 뒤에 옮긴다 — 순서가 뒤집히면 우리 태그가 막힌다', () => {
    expect(markStrong(escapeHtml('**굵게** <b>아님</b>'))).toBe('<strong>굵게</strong> &lt;b&gt;아님&lt;/b&gt;')
  })
})
