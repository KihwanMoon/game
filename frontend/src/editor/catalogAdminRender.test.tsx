/**
 * 카탈로그 관리 화면.
 *
 * 여기서 지키는 것은 넷이다.
 *
 * 1. **삭제 버튼이 없다.** 지우면 과거 기록을 못 읽는다.
 * 2. **폐기된 것도 보인다.** 폐기는 「없다」가 아니라 「새로 안 나온다」다.
 * 3. **세대가 눈에 있다.** 고치면 순위표 시즌이 갈린다 — 누르기 전에 알아야 한다.
 * 4. **못 고치는 것을 못 고친다고 적는다.** 서버만 막으면 「왜 안 되지」가 된다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { CatalogAdminPanel, CatalogForm } from './CatalogAdminPanel'
import type { CatalogAdminView } from '../storage'

const VIEW: CatalogAdminView = {
  generation: 7,
  grades: ['COMMON', 'FINE', 'RELIC'],
  items: [
    {
      catalogId: 'helm_iron',
      kind: 'EQUIPMENT',
      labelKo: '철 투구',
      slot: 'HEAD',
      hands: '',
      grade: 'COMMON',
      minFloor: 1,
      isRetired: false,
      affixes: ['튼튼함 +8'],
      requirements: [],
      grantsSkill: '',
      dropWeight: 1,
    },
    {
      catalogId: 'old_blade',
      kind: 'EQUIPMENT',
      labelKo: '옛 검',
      slot: 'WEAPON_MAIN',
      hands: 'ONE',
      grade: 'FINE',
      minFloor: 3,
      isRetired: true,
      affixes: [],
      requirements: [],
      grantsSkill: '',
      dropWeight: 0,
    },
  ],
}

const noop = () => undefined
const MARKUP = renderToStaticMarkup(
  <CatalogAdminPanel catalog={VIEW} detail="" onRetire={noop} onRename={noop}
        onCreate={noop} />,
)

describe('카탈로그 관리', () => {
  it('★ 삭제 버튼이 없다 — 지우면 원장이 가리키는 id 가 사라진다', () => {
    expect(MARKUP).not.toContain('삭제')
  })

  it('★ 폐기된 것도 목록에 남는다 — 되살릴 수 있어야 한다', () => {
    expect(MARKUP).toContain('<span class="ds-cell__name">옛 검</span>')
    expect(MARKUP).toContain('폐기')
  })

  it('★ 세대가 머리에 있다 — 고치면 순위표 시즌이 갈린다', () => {
    expect(MARKUP).toContain('세대 7')
    expect(MARKUP).toContain('순위표 시즌이 갈린다')
  })

  it('★ 못 고치는 것을 못 고친다고 적는다 — 서버만 막으면 「왜 안 되지」가 된다', () => {
    // **고르기 전에 있어야 한다.** 상세 안에 두면 규칙을 아는 시점이 늦고, 그때는 이미
    // 거절을 한 번 겪은 뒤다.
    expect(MARKUP).toContain('새 id 로 등록하고 옛 id 를 폐기한다')
  })

  it('★ 서버가 없으면 그렇게 말한다 — 빈 카탈로그와 못 불러온 카탈로그는 다르다', () => {
    const html = renderToStaticMarkup(
      <CatalogAdminPanel catalog={undefined} detail="" onRetire={noop} onRename={noop}
        onCreate={noop} />,
    )
    expect(html).toContain('서버에 닿지 못했다')
  })

  it('★ 거절 사유를 그대로 적는다 — 서버가 답을 알고 있다', () => {
    const html = renderToStaticMarkup(
      <CatalogAdminPanel
        catalog={VIEW}
        detail="이미 나온 아이템이 소급해 바뀐다 — 새 id 로 등록한다"
        onRetire={noop}
        onRename={noop}
        onCreate={noop}
      />,
    )
    expect(html).toContain('새 id 로 등록한다')
  })
})

describe('신규 등록 폼', () => {
  it('★ 등록 길이 화면에 있다 — 수정이 막혀 있으니 등록이 유일한 변경 경로다', () => {
    expect(MARKUP).toContain('새 종류 등록')
    expect(MARKUP).toContain('등록')
  })

  it('★ 서버가 아는 슬롯 이름을 그대로 쓴다 — 화면이 새 이름을 지으면 서버가 못 읽는다', () => {
    for (const slot of ['WEAPON_MAIN', 'HEAD', 'BODY', 'FEET', 'HANDS']) {
      expect(MARKUP).toContain(slot)
    }
  })

  it('★ 등급을 서버가 준 목록에서 고른다 — 화면이 목록을 들고 있으면 갈린다', () => {
    for (const grade of VIEW.grades) {
      expect(MARKUP).toContain(grade)
    }
  })

  it('★ id 가 없으면 잠긴다 — 이름 없는 아이템은 원장만 더럽힌다', () => {
    const html = renderToStaticMarkup(
      <CatalogForm grades={VIEW.grades} onCreate={() => undefined} />,
    )
    expect(html).toContain('disabled')
  })

  it('★ 등록도 새 id 로 하라는 안내가 붙는다 — 수정이 막힌 이유가 여기서 이어진다', () => {
    expect(MARKUP).toContain('새로 등록하고 옛 id 를 폐기한다')
  })
})
