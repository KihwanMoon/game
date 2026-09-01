/**
 * 캐릭터 시트 검사 (결정 #13, #51).
 *
 * **이 화면이 없으면 규칙을 짤 수 없다.** 규칙이 `적거리 <= 사거리` 처럼 자기 스탯을
 * 참조하는데, 자기 사거리를 볼 데가 없으면 그 조건이 언제 참인지 모른 채 쓰게 된다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { BALANCE } from '../core/resources'
import { STATE_GLYPHS } from '../ds'
import type { ProgressView } from '../storage'
import { CharacterPanel, formatDelta, splitStatSources } from './CharacterPanel'

const BASE = BALANCE.player as unknown as Record<string, number>
const ITEMS = ['POTION', 'SCROLL']
const SKILLS = ['ATTACK', 'GUARD_BRACE', 'SKILL_1', 'SKILL_2']

const PROGRESS: ProgressView = {
  level: 9,
  totalXp: 0,
  remainingXp: 0,
  nextXp: 1,
  stats: { str: 10, dex: 0, int: 6 },
  statKeys: ['str', 'dex', 'int'],
  statPoints: 27,
  spentPoints: 16,
  bonusRuleSlots: 1,
  bonusCpu: 3,
  reachedFloor: 1,
  floorCap: 10,
  loadout: {
    hpMax: 160,
    attack: 25,
    defense: 7,
    attackRange: 4,
    initiative: 50,
    cpuBudget: 13,
    ruleSlots: 6,
    skillPowerPct: 112,
    consumables: [],
    skills: ['ATTACK', 'SKILL_1', 'SKILL_2'],
  },
}

function render(progress: ProgressView | undefined, isOnline = true) {
  return renderToStaticMarkup(
    <CharacterPanel
      progress={progress}
      baseStats={BASE}
      allSkills={SKILLS}
      allItems={ITEMS}
      isOnline={isOnline}
    />,
  )
}

describe('출처 쪼개기', () => {
  it('★ 세 몫의 합이 언제나 최종과 같다', () => {
    // 장비 몫을 빼서 구하므로 합이 안 맞으면 화면이 거짓말을 한다.
    const split = splitStatSources(160, 100, 40, 0)
    expect(split.base + split.gear + split.attributes + split.level).toBe(split.final)
    expect(split.gear).toBe(20)
  })

  it('장비가 없으면 장비 몫이 0 이다', () => {
    expect(splitStatSources(140, 100, 40, 0).gear).toBe(0)
  })

  it('0 은 가운뎃점으로 적는다 — 「+0」이 줄마다 늘어서면 읽히지 않는다', () => {
    expect(formatDelta(0)).toBe('·')
    expect(formatDelta(12)).toBe('+12')
    expect(formatDelta(-3)).toBe('-3')
    expect(formatDelta(12, '%')).toBe('+12%')
  })
})

describe('캐릭터 시트 화면', () => {
  it('★ 사거리가 보인다 — 이것 없이는 `적거리 <= 사거리` 를 쓸 수 없다', () => {
    const html = render(PROGRESS)
    expect(html).toContain('사거리')
    expect(html).toContain('= 4')
  })

  it('★ 값이 어디서 왔는지 함께 적는다', () => {
    // 「공격 25」만 적으면 장비 덕인지 능력치 덕인지 알 수 없고, 그러면 다음에 무엇을
    // 바꿔야 할지도 알 수 없다 (디자인 §8.2 와 같은 이유).
    const html = render(PROGRESS)
    expect(html).toContain('= 25')
    expect(html).toContain('+10')
  })

  it('★ 장착하지 않은 스킬을 「불가」로 보여준다', () => {
    // 규칙 에디터의 「불가」가 왜 떴는지는 여기서만 답할 수 있다.
    //
    // **글리프까지 본다.** 설명 문구만 검사하면 상태가 「참」으로 잘못 그려져도 통과한다 —
    // 이 게임은 참/거짓을 색·글리프·명도 셋으로 표기하므로 글리프가 곧 정보다.
    const html = render(PROGRESS)
    expect(html).toContain('GUARD_BRACE')
    expect(html).toContain('이 스킬을 여는 장비를 끼면 열린다')
    expect(html).toContain(STATE_GLYPHS.get('blocked'))
    expect(html).toContain(STATE_GLYPHS.get('true'))
  })

  it('★ 전부 갖췄으면 「불가」 글리프가 없다 — 붙으면 못 쓰는 것처럼 보인다', () => {
    // 스킬과 소모품 **둘 다** 갖춰야 한다. 하나라도 비면 그 줄이 불가로 남는다 —
    // 소모품이 그 목록에 들어온 뒤로 스킬만 채운 것으로는 부족해졌다 (#54).
    const full = {
      ...PROGRESS,
      loadout: {
        ...PROGRESS.loadout,
        skills: [...SKILLS],
        consumables: ITEMS.map((kind) => [kind, 1] as const),
      },
    } as ProgressView
    expect(render(full)).not.toContain(STATE_GLYPHS.get('blocked'))
  })

  it('★ 규칙 예산의 출처가 보인다 — 레벨과 지능이 각각 얼마를 줬는가', () => {
    const html = render(PROGRESS)
    expect(html).toContain('= 13')
    expect(html).toContain('= 6')
    expect(html).toContain('112%')
  })

  it('서버에 못 닿으면 그렇게 적는다 — 빈 표를 보여주면 스탯이 0 인 줄 안다', () => {
    expect(render(PROGRESS, false)).toContain('서버에 닿지 못했다')
    expect(render(undefined)).toContain('서버에 닿지 못했다')
  })
})

describe('소모품 (#54)', () => {
  it('★ 들고 있지 않은 소모품을 「불가」로 보여준다', () => {
    // `USE_ITEM[SCROLL]` 이 안 뜬 이유는 "주문서가 없다" 인데, 안 보여주면 그 답을
    // 어디서도 찾을 수 없다. 스킬 미장착과 같은 자리다.
    const html = render({
      ...PROGRESS,
      loadout: { ...PROGRESS.loadout, consumables: [['POTION', 2] as const] },
    } as ProgressView)
    expect(html).toContain('POTION')
    expect(html).toContain('SCROLL')
    expect(html).toContain('주우면 열린다')
  })

  it('★ 개수를 적는다 — 몇 번 쓸 수 있는지가 규칙 설계의 입력이다', () => {
    const html = render({
      ...PROGRESS,
      loadout: { ...PROGRESS.loadout, consumables: [['POTION', 3] as const] },
    } as ProgressView)
    expect(html).toContain('>3<')
  })
})
