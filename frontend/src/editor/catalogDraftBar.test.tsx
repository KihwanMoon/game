/**
 * 아이템 초안 바 검사 (설계/9_에이전트_운영 §3.2).
 *
 * **여기서 지키는 것은 발행 버튼이다.** 아이템 편집이 즉시 세계를 바꾸던 것을 초안으로
 * 돌렸고, 그 문을 사람이 연다 — 버튼이 아무 때나 눌리면 되돌린 것이 없어진다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { CatalogDraftBar, formatAction } from './CatalogDraftBar'
import type { CatalogDraftView } from '../storage/catalogDraft'

const CLEAN: CatalogDraftView = {
  drafts: [
    {
      catalogId: 'sword_probe',
      action: 'item',
      reason: '표본 무기를 들인다',
      handle: 'balance_agent',
      updatedAt: '2026-09-05 12:00',
      problem: '',
    },
  ],
  generation: 7,
  hint: '초안은 아직 아이템이 아니다',
}

const BLOCKED: CatalogDraftView = {
  ...CLEAN,
  drafts: [{ ...CLEAN.drafts[0]!, problem: '이미 있는 id 다' }],
}

function render(view: CatalogDraftView | undefined) {
  return renderToStaticMarkup(
    <CatalogDraftBar token="t" view={view} onDone={() => undefined} />,
  )
}

describe('formatAction', () => {
  it('서버가 주는 값을 사람이 읽는 말로 적는다', () => {
    expect(formatAction('item')).toBe('등록')
    expect(formatAction('retire')).toBe('폐기')
  })

  it('모르는 값은 그대로 둔다 — 지어내면 무엇이 일어날지 화면이 거짓말한다', () => {
    expect(formatAction('brand_new')).toBe('brand_new')
  })
})

describe('CatalogDraftBar', () => {
  it('쌓인 것이 없으면 그렇게 말한다 — 빈 화면은 고장으로 읽힌다', () => {
    expect(render({ drafts: [], generation: 7, hint: '' })).toContain('쌓인 아이템 초안이 없다')
  })

  it('★ 발행이 시즌을 가른다는 것을 먼저 말한다', () => {
    expect(render(CLEAN)).toContain('순위표 시즌이 갈린다')
  })

  it('누가 올렸는지 적는다 — 에이전트와 사람을 못 가르면 검토가 흐려진다', () => {
    const html = render(CLEAN)
    expect(html).toContain('balance_agent')
    expect(html).toContain('등록')
    expect(html).toContain('표본 무기를 들인다')
  })

  it('★ 못 나가는 줄은 누르기 전에 말한다', () => {
    // 눌러서 알게 하면 절반이 반영된 상태를 상상하게 된다.
    const html = render(BLOCKED)
    expect(html).toContain('이미 있는 id 다')
    expect(html).toContain('1건이 지금 카탈로그에 안 맞는다')
  })

  it('★ 처음에는 발행 버튼이 안 눌린다 — 세대와 사유를 적어야 한다', () => {
    expect(render(CLEAN)).toContain('disabled')
  })

  it('지금 세대를 자리표시로 보여 준다 — 손으로 적어야 하므로 알려는 줘야 한다', () => {
    expect(render(CLEAN)).toContain('지금 7')
  })

  it('아직 안 읽었을 때도 그린다', () => {
    expect(render(undefined)).toContain('쌓인 아이템 초안이 없다')
  })
})
