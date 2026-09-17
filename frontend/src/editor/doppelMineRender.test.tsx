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

describe('둔갑 목록이 공용 틀을 쓴다', () => {
  // 손으로 짠 `ul` 이 셋이었고 빈 경우를 저마다 바깥에서 갈라 적고 있었다 — 한 곳을
  // 고쳐도 나머지 둘은 옛 모양으로 남는 자리다 (2026-09-17).
  const EMPTY: MyDoppelView = { ...VIEW, standing: [], retired: [], recent: [] }

  it('★ 세 목록이 빈 경우를 저마다 말한다 — 「없다」가 서로 다른 없음이다', () => {
    const markup = renderToStaticMarkup(<MyDoppelPanel view={EMPTY} link="online" />)
    expect(markup).toContain('지금 서 있는 둔갑이 없다')
    // 물러난 것과 최근 판의 문구는 상수로 갈라져 있다 — 셋이 한 문장이면 안 된다.
    expect(markup.match(/ds-expr--dim/g)?.length ?? 0).toBeGreaterThanOrEqual(3)
  })

  it('★ 줄이 있으면 빈 문구 대신 줄이 뜬다', () => {
    const markup = renderToStaticMarkup(<MyDoppelPanel view={VIEW} link="online" />)
    expect(markup).not.toContain('지금 서 있는 둔갑이 없다')
    expect(markup).toContain('doppel-mine__row')
  })

  it('★ 전적에는 찾기가 선다 — 한 계정이 236판을 치렀다', () => {
    // **10 이 데이터를 잘라내고 있었다** (2026-09-17 실측). 서버가 열 줄만 줘서 나머지
    // 226판이 아예 안 보였고, 찾기를 붙여도 볼 것이 없었다. 상한을 100 으로 올렸다.
    const withRetired: MyDoppelView = {
      ...VIEW,
      retired: [{ recordId: 3, floor: 5, won: 2, lost: 1, at: '2026-09-16T00:00:00Z' }],
    }
    const markup = renderToStaticMarkup(<MyDoppelPanel view={withRetired} link="online" />)
    expect(markup).toContain('상대·장으로 찾기')
    expect(markup).toContain('장·전적으로 찾기')
  })

  it('★ 빈 목록에는 찾기 칸이 안 선다 — 걸 것이 없다', () => {
    const markup = renderToStaticMarkup(
      <MyDoppelPanel view={{ ...VIEW, recent: [], retired: [] }} link="online" />,
    )
    expect(markup).not.toContain('dlist__find')
  })

  it('★ 서 있는 둔갑에는 안 선다 — 둘까지라 뒤에 더 있다는 거짓말이 된다', () => {
    const many: MyDoppelView = {
      ...VIEW,
      retired: [],
      recent: [],
    }
    const markup = renderToStaticMarkup(<MyDoppelPanel view={many} link="online" />)
    // 서 있는 목록만 남았을 때 찾기 칸이 하나도 없어야 한다.
    expect(markup).not.toContain('dlist__find')
  })

  it('★ 첫 화면은 예전만큼만 보인다 — 한 장이 열 줄이다', () => {
    // 상한을 올렸다고 백 줄이 쏟아지면 그것은 고친 것이 아니라 바꾼 것이다.
    const long: MyDoppelView = {
      ...VIEW,
      recent: Array.from({ length: 30 }, (_unused, at) => ({
        ...(VIEW.recent[0] as MyDoppelView['recent'][number]),
        at: `2026-09-17T0${String(at % 10)}:00:00Z`,
        floor: at + 1,
      })),
    }
    const markup = renderToStaticMarkup(<MyDoppelPanel view={long} link="online" />)
    expect(markup).toContain('더 보기')
    expect(markup).toContain('1장')
    expect(markup).not.toContain('30장')
  })
})
