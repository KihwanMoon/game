/**
 * 내 둔갑이 화면에 도는가 (2026-09-15 요청: 「둔갑을 양방향으로」).
 *
 * 지키는 것은 셋이다.
 *
 *     ① 이긴 쪽이 주어다 — 「3장에서 이겼다」는 누가 이겼는지를 안 말한다
 *     ② 꺼 둔 계정과 빈 계정을 가른다 — 둘 다 전적이 0이라 글이 같으면 켤 이유를 모른다
 *     ③ 못 닿았을 때 그 사실을 적는다
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { MyDoppelPanel, formatBout, formatRetired } from './MyDoppelPanel'
import type { MyDoppelView } from '../storage'

const VIEW: MyDoppelView = {
  standing: [{ recordId: 7, floor: 9, level: 12, lives: 3 }],
  met: 5,
  won: 2,
  recent: [
    { floor: 9, isDoppelWin: true, opponent: 'sinindra', at: '2026-09-15T00:00:00Z' },
    { floor: 4, isDoppelWin: false, opponent: 'bot1', at: '2026-09-14T00:00:00Z' },
  ],
  retired: [],
  isOptedIn: true,
}

describe('내 둔갑', () => {
  it('★ 이긴 쪽을 주어로 적는다', () => {
    expect(formatBout({ floor: 9, isDoppelWin: true, opponent: 'sinindra' })).toBe(
      '9장 · sinindra 를 이겼다',
    )
    expect(formatBout({ floor: 4, isDoppelWin: false, opponent: 'bot1' })).toBe(
      '4장 · bot1 에게 잡혔다',
    )
  })

  it('이름을 모르면 「누군가」로 적는다 — 빈 칸은 고장으로 읽힌다', () => {
    expect(formatBout({ floor: 2, isDoppelWin: true, opponent: '' })).toContain('누군가')
  })

  it('★ 전적과 서 있는 자리를 함께 낸다', () => {
    const markup = renderToStaticMarkup(<MyDoppelPanel view={VIEW} link="online" />)
    expect(markup).toContain('만난 판 5')
    expect(markup).toContain('이긴 판 2')
    expect(markup).toContain('9장')
    expect(markup).toContain('sinindra 를 이겼다')
    expect(markup).toContain('bot1 에게 잡혔다')
  })

  it('★ 꺼 둔 계정에는 켜면 생긴다고 적는다 — 빈 것과 끈 것은 다르다', () => {
    const off = { ...VIEW, standing: [], met: 0, won: 0, recent: [], isOptedIn: false }
    const markup = renderToStaticMarkup(<MyDoppelPanel view={off} link="online" />)
    expect(markup).toContain('안 세우는 중')
    expect(markup).not.toContain('아직 아무도')
  })

  it('켜 뒀는데 아무도 안 만났으면 그렇게 적는다', () => {
    const empty = { ...VIEW, standing: [], met: 0, won: 0, recent: [] }
    const markup = renderToStaticMarkup(<MyDoppelPanel view={empty} link="online" />)
    expect(markup).toContain('아직 아무도')
    expect(markup).toContain('서 있는 둔갑이 없다')
  })

  it('못 닿으면 그 사실을 적는다', () => {
    const markup = renderToStaticMarkup(<MyDoppelPanel view={undefined} link="offline" />)
    expect(markup).toContain('내 둔갑은 서버가 안다')
  })
})

describe('물러난 둔갑', () => {
  it('★ 이긴 만큼 활자가 들어왔음을 적는다 — 셈이 끝나는 자리가 안 보이면 틀린 것으로 읽힌다', () => {
    expect(formatRetired({ floor: 4, won: 3, lost: 4 })).toBe('4장 · 3승 4패 → 활자 +3')
  })

  it('★ 한 번도 못 이긴 둔갑은 「활자 없음」이다 — 0 을 더했다고 적으면 거짓말이다', () => {
    expect(formatRetired({ floor: 9, won: 0, lost: 3 })).toBe('9장 · 0승 3패 → 활자 없음')
  })
})
