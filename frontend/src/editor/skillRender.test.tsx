/**
 * 재주 세팅 패널 검사 (결정 #13 확장).
 *
 * **빼기만 한다.** 재주는 장비가 열고, 여기서는 연 것 중 안 들고 갈 것을 끈다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { findSkillArt } from '../content/skillArt'
import { readSkillName } from '../content/skills'

import type { SkillPrefView } from '../storage'

import { SkillPanel } from './SkillPanel'

const noop = (): undefined => undefined

/**
 * 칸에 실제로 걸린 그림 주소들. 마크업은 `'` 를 escape 하므로 되돌려 놓고 비교한다.
 *
 * @param html 정적 마크업.
 * @returns 주소들. 칸 순서 그대로.
 */
function listArt(html: string): string[] {
  return [...html.matchAll(/class="invg__art" src="([^"]*)"/gu)].map((hit) =>
    (hit[1] ?? '').replaceAll('&#x27;', "'"),
  )
}

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

describe('재주 세팅', () => {
  it('★ 한글 이름으로 적는다 — id 를 그대로 두면 그 줄만 다른 언어가 된다', () => {
    const html = render(VIEW)
    // **이름을 여기 적지 않는다.** `skills.json` 의 `label_ko` 가 정본이고, 적어 두면
    // 이름을 고칠 때 이 검사가 빨개진다 — 그러면 사람은 화면이 아니라 검사를 고치게
    // 되고, 그것이 사본을 만드는 첫걸음이다. 정본을 읽어 대조한다 (2026-09-19).
    for (const row of VIEW.rows) {
      expect(html).toContain(readSkillName(row.skillId))
    }
  })

  it('★ 칸마다 제 그림이 선다 (2026-09-21 요청) — 이름은 그림 아래에 남는다', () => {
    // **글자를 안 지운다.** 아직 안 그린 재주가 섞이면 그 칸만 글자가 되는데, 이름을
    // 지워 두면 그 칸이 빈 칸으로 보인다 (`gridCell.art` 가 적어 둔 규율).
    const html = render(VIEW)
    expect(listArt(html)).toEqual(VIEW.rows.map((row) => findSkillArt(row.skillId)))
    for (const row of VIEW.rows) {
      expect(html).toContain(readSkillName(row.skillId))
    }
    expect(html).toContain('invg__label--under')
  })

  it('★ 꺼진 칸이 격자에서 갈린다 — 색만이 아니라 「끔」 글자로도', () => {
    const html = render(VIEW)
    // **막힌 자리가 아니라 끈 것이다.** 막힌 자리(`--sealed`)는 그릴 이름이 없어 `▨` 가
    // 대신 서는데, 끈 재주는 이름이 남아야 무엇을 다시 켤지 고를 수 있다.
    expect(html).toContain('invg__cell--off')
    expect(html).not.toContain('invg__cell--sealed')
    expect(html).toContain('끔')
  })

  it('★ 끈 재주도 이름이 남는다 — 이름이 사라지면 다시 켤 것을 못 고른다', () => {
    expect(render(VIEW)).toContain('invg__label')
  })

  it('★ 누르면 수치가 뜬다 — 격자 자체에는 조작이 없다', async () => {
    const { listSkillFacts } = await import('./SkillPanel')
    const facts = listSkillFacts('AREA_ATTACK')
    expect(facts.join(' ')).toContain('계수')
    expect(facts.join(' ')).toContain('쿨타임')
    // 정본에 없는 재주는 그 사실을 말한다 — 조용한 빈칸이 아니다.
    expect(listSkillFacts('NOPE')[0]).toContain('정본에 없는')
  })

  it('★ 연쇄는 반경으로 안 적는다 — 「반경 2」면 한 번에 덮는 것으로 읽힌다', async () => {
    // 갈래마다 읽는 수가 다르다 (2026-09-17). 연쇄는 **튀는 거리와 횟수**가 둘 다
    // 있어야 무엇을 맞히는지가 정해진다.
    const { listSkillFacts } = await import('./SkillPanel')
    const facts = listSkillFacts('CHAIN_BOLT').join(' ')
    expect(facts).toContain('연쇄')
    expect(facts).toContain('2칸 안으로 3회 튄다')
    expect(facts).not.toContain('반경')
  })

  it('★ 얹는 상태를 적는다 — 없으면 서리 장판이 그냥 약한 광역기로 읽힌다', async () => {
    const { listSkillFacts } = await import('./SkillPanel')
    const facts = listSkillFacts('FROST_FIELD').join(' ')
    // 피해가 60% 뿐이라, 묶는다는 사실이 이 줄에 없으면 고를 이유가 안 보인다.
    expect(facts).toContain('이동불가 1틱')
    expect(facts).toContain('반경 3')
  })

  it('★ 서버에 못 닿으면 그 사실을 적는다', () => {
    // 화면에 나가는 말은 「재주」다 — 탭·제목과 같은 낱말이어야 한 화면에서 두 이름이
    // 되지 않는다 (2026-09-18).
    expect(render(undefined)).toContain('재주를 못 읽는다')
  })
})
