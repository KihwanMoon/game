/**
 * 스킬 세팅 패널 검사 (결정 #13 확장).
 *
 * **빼기만 한다.** 스킬은 장비가 열고, 여기서는 연 것 중 안 들고 갈 것을 끈다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { SkillPrefView } from '../storage'

import { SkillPanel } from './SkillPanel'

const noop = (): undefined => undefined

function render(view: SkillPrefView | undefined, detail = ''): string {
  return renderToStaticMarkup(
    <SkillPanel view={view} link="online" detail={detail} onChange={noop} />,
  )
}

const VIEW: SkillPrefView = {
  rows: [
    { skillId: 'ATTACK', isOn: true, isLocked: true },
    { skillId: 'SKILL_1', isOn: true, isLocked: false },
    { skillId: 'HEAL', isOn: false, isLocked: false },
  ],
}

describe('스킬 세팅', () => {
  it('★ 한글 이름으로 적는다 — id 를 그대로 두면 그 줄만 다른 언어가 된다', () => {
    const html = render(VIEW)
    expect(html).toContain('공격')
    expect(html).toContain('스킬 1')
    expect(html).toContain('치유')
  })

  it('★ 꺼진 칸이 격자에서 갈린다 — 색만이 아니라 「끔」 글자로도', () => {
    const html = render(VIEW)
    expect(html).toContain('invg__cell--sealed')
    expect(html).toContain('끔')
  })

  it('★ 누르면 수치가 뜬다 — 격자 자체에는 조작이 없다', async () => {
    const { listSkillFacts } = await import('./SkillPanel')
    const facts = listSkillFacts('AREA_ATTACK')
    expect(facts.join(' ')).toContain('계수')
    expect(facts.join(' ')).toContain('쿨타임')
    // 정본에 없는 스킬은 그 사실을 말한다 — 조용한 빈칸이 아니다.
    expect(listSkillFacts('NOPE')[0]).toContain('정본에 없는')
  })

  it('★ 서버에 못 닿으면 그 사실을 적는다', () => {
    expect(render(undefined)).toContain('스킬을 못 읽는다')
  })
})
