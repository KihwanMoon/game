/**
 * 도면 격자 판이 네 화면에서 같은 모양인가.
 *
 * **네 벌이던 것을 하나로 모았다** (가방·소모품·경매·스킬). 같은 것이 네 벌이면 한 곳을
 * 고쳐도 나머지 셋은 옛 모양으로 남고, 그때부터 사람은 같은 질문에 네 모양의 답을 받는다.
 * 여기서 보는 것은 「넷이 정말 같은 것을 그리는가」다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { CellFace } from './gridCell'
import { SlotBoard, SlotGrid } from './SlotBoard'
import { buildSkillCells } from './skillCells'

/**
 * 검사용 칸 하나.
 *
 * @param key 칸의 key.
 * @param label 칸 가운데 글자.
 * @returns 격자 칸.
 */
function buildCell(key: string, label: string): CellFace {
  return {
    key,
    code: '주',
    label,
    grade: 'COMMON',
    marks: [],
    countText: '',
    fact: '',
    isSealedSlot: false,
  }
}

const CELLS = [buildCell('a', '단검'), buildCell('b', '장궁')]

describe('SlotGrid — 제목 한 줄과 칸 격자', () => {
  it('모양이 클래스로 나간다 — 열 규칙은 CSS 가 안다', () => {
    for (const shape of ['equip', 'bag', 'free'] as const) {
      const html = renderToStaticMarkup(
        <SlotGrid
          title="장비"
          shape={shape}
          cells={CELLS}
          pickedKey=""
          onPick={() => undefined}
        />,
      )
      expect(html).toContain(`invg--${shape}`)
    }
  })

  it('★ 칸이 없고 할 말이 있으면 그 말을 적는다 — 빈 격자는 「불러오는 중」과 안 갈린다', () => {
    const html = renderToStaticMarkup(
      <SlotGrid
        title="매물"
        shape="free"
        cells={[]}
        pickedKey=""
        onPick={() => undefined}
        emptyText="걸린 매물이 없다"
      />,
    )
    expect(html).toContain('걸린 매물이 없다')
    expect(html).not.toContain('invg--free')
  })

  it('할 말이 없으면 빈 격자를 그대로 그린다 — 가방은 빈 칸이 곧 뜻이다', () => {
    const html = renderToStaticMarkup(
      <SlotGrid title="가방" shape="bag" cells={[]} pickedKey="" onPick={() => undefined} />,
    )
    expect(html).toContain('invg--bag')
  })

  it('★ 고른 칸이 세 채널로 적힌다 — 색·클래스·aria', () => {
    const html = renderToStaticMarkup(
      <SlotGrid title="장비" shape="equip" cells={CELLS} pickedKey="a" onPick={() => undefined} />,
    )
    expect(html).toContain('invg__cell--picked')
    expect(html).toContain('aria-pressed="true"')
  })
})

describe('SlotBoard — 격자와 고른 칸의 상세', () => {
  it('★ 아무것도 안 골랐으면 누를 것이 있다고 말한다', () => {
    const html = renderToStaticMarkup(
      <SlotBoard hint="칸을 고르면 여기에 상세가 뜬다">
        <SlotGrid title="장비" shape="equip" cells={CELLS} pickedKey="" onPick={() => undefined} />
      </SlotBoard>,
    )
    expect(html).toContain('칸을 고르면 여기에 상세가 뜬다')
  })

  it('고른 것이 있으면 안내 대신 상세가 선다', () => {
    const html = renderToStaticMarkup(
      <SlotBoard hint="칸을 고르면 여기에 상세가 뜬다" detail={<p>단검 상세</p>}>
        <SlotGrid title="장비" shape="equip" cells={CELLS} pickedKey="a" onPick={() => undefined} />
      </SlotBoard>,
    )
    expect(html).toContain('단검 상세')
    expect(html).not.toContain('칸을 고르면')
  })

  it('안내는 격자보다 앞에 선다 — 연결이 끊겼다는 말이 격자 아래 있으면 늦다', () => {
    const html = renderToStaticMarkup(
      <SlotBoard hint="…" notice={<p>런이 도는 중</p>}>
        <SlotGrid title="장비" shape="equip" cells={CELLS} pickedKey="" onPick={() => undefined} />
      </SlotBoard>,
    )
    expect(html.indexOf('런이 도는 중')).toBeLessThan(html.indexOf('invg'))
  })
})

describe('★ 스킬도 같은 겉면을 쓴다 — 여기만 손으로 그리고 있었다', () => {
  const VIEW = {
    rows: [
      { skillId: 'FIREBALL', isOn: true, isLocked: false },
      { skillId: 'HEAL', isOn: false, isLocked: false },
      { skillId: 'ATTACK', isOn: true, isLocked: true },
    ],
  }
  const cells = buildSkillCells(VIEW, (id) => id)

  it('key 가 곧 스킬 id 다 — 접두사를 붙이면 고른 칸에서 스킬을 되찾아야 한다', () => {
    expect(cells.map((cell) => cell.key)).toEqual(['FIREBALL', 'HEAL', 'ATTACK'])
  })

  it('★ 끈 것은 막힌 것과 다르다 — 이름이 남아야 다시 켤 것을 고른다', () => {
    const off = cells[1]
    expect(off?.isOff).toBe(true)
    expect(off?.isSealedSlot).toBe(false)
    expect(off?.label).toBe('HEAL')
    expect(off?.marks).toEqual(['끔'])
  })

  it('못 끄는 스킬은 자리 코드로 그 사실을 적는다 — 폴백이 기댄다', () => {
    expect(cells[2]?.code).toBe('기본')
    expect(cells[0]?.code).toBe('')
  })

  it('세팅이 없으면 빈 격자다 — 서버에 못 닿은 자리다', () => {
    expect(buildSkillCells(undefined, (id) => id)).toEqual([])
  })
})
