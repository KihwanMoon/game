/**
 * 서랍 검사.
 *
 * **탭 이름만 있고 내용이 안 그려지면 서랍은 장식이다.** 첫 화면 마크업에는 열려 있는
 * 칸만 있으므로, 나머지 칸이 실제로 뭔가를 내는지는 여기서 본다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { DrawerPanel, type DrawerTab } from './DrawerPanel'

const TABS: DrawerTab[] = [
  { id: 'me', label: '나', body: <p>캐릭터 시트</p> },
  { id: 'bag', label: '가방', body: <p>인벤토리</p> },
  { id: 'library', label: '서고', body: <p>코드 라이브러리</p> },
]

function render(tabs: DrawerTab[], initialId?: string) {
  return renderToStaticMarkup(
    <DrawerPanel tabs={tabs} {...(initialId === undefined ? {} : { initialId })} />,
  )
}

describe('서랍', () => {
  it('★ 탭이 전부 보인다 — 안 보이면 그 화면은 없는 것과 같다', () => {
    const html = render(TABS)
    for (const tab of TABS) {
      expect(html).toContain(`>${tab.label}<`)
    }
  })

  it('★ 한 번에 하나만 세운다 — 이것이 높이 문제를 푸는 방식이다', () => {
    // 아홉을 쌓으면 열 높이의 450% 를 요구해 아래쪽이 하단 바를 뚫고 나갔다.
    const html = render(TABS)
    expect(html).toContain('캐릭터 시트')
    expect(html).not.toContain('인벤토리')
    expect(html).not.toContain('코드 라이브러리')
  })

  it('★ 지정한 칸을 열 수 있다 — 열 수 없으면 첫 칸 말고는 못 본다', () => {
    const html = render(TABS, 'library')
    expect(html).toContain('코드 라이브러리')
    expect(html).not.toContain('캐릭터 시트')
  })

  it('★ 없는 칸을 지정하면 첫 칸으로 떨어진다', () => {
    // 관리자 권한을 잃으면 열려 있던 탭이 목록에서 사라진다. 그때 빈 화면이 되면
    // 고장으로 읽힌다.
    expect(render(TABS, 'admin')).toContain('캐릭터 시트')
  })

  it('탭이 없으면 아무것도 그리지 않는다 — 빈 서랍은 고장으로 읽힌다', () => {
    expect(render([])).toBe('')
  })

  it('열린 칸의 이름을 머리에 적는다 — 어느 서랍인지 모르면 탭이 있으나 마나다', () => {
    expect(render(TABS, 'bag')).toContain('가방')
  })
})
