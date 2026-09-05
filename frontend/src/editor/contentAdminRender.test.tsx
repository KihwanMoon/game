/**
 * 콘텐츠 편집 화면 (설계/4_아이템 §16).
 *
 * 여기서 지키는 것은 넷이다.
 *
 * 1. **반영이 자동이 아니라는 것을 먼저 말한다.** 자동인 줄 알면 관리자가 순위표 시즌을
 *    모르게 가른다.
 * 2. **지금 파일에서 시작한다.** 백지에서 쓰게 하면 손으로 옮겨 적게 되고, 그 순간
 *    오타가 콘텐츠가 된다.
 * 3. **버전을 올려야 한다고 적는다.** 안 올리면 저장된 리플레이가 조용히 거짓이 된다.
 * 4. **거절 사유를 그대로 적는다.** 서버의 로더가 답을 알고 있다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { ContentAdminPanel, formatDraftText } from './ContentAdminPanel'
import type { ContentAssetView, ContentDraftView } from '../storage'

const VIEW: ContentDraftView = {
  drafts: [{ asset: 'skills', note: '계수 조정', updatedAt: '2026-08-31 12:00', currentVersion: 2 }],
  assets: ['balance', 'blocks', 'enemies', 'rooms', 'skills'],
  problem: '',
  openRuns: 0,
  publishHint: '초안은 게임에 반영되지 않는다. 커밋·배포해야 두 코어가 그것을 읽는다.',
}

const ASSET: ContentAssetView = {
  asset: 'skills',
  current: { skill_list_version: 2, skills: [{ id: 'ATTACK', coef_pct: 100 }] },
  draft: null,
  note: '',
  versionKey: 'skill_list_version',
}

const noop = () => undefined
const MARKUP = renderToStaticMarkup(
  <ContentAdminPanel
    content={VIEW}
    asset={ASSET}
    detail=""
    onOpen={noop}
    onSave={noop}
    onDiscard={noop}
  />,
)

describe('콘텐츠 편집', () => {
  it('★ 반영이 자동이 아니라는 것을 화면이 말한다', () => {
    expect(MARKUP).toContain('반영되지 않는다')
    expect(MARKUP).toContain('커밋')
  })

  it('★ 지금 파일 내용이 편집기에 들어 있다 — 백지면 손으로 옮겨 적게 된다', () => {
    expect(MARKUP).toContain('skill_list_version')
    expect(MARKUP).toContain('ATTACK')
  })

  it('★ 초안이 있으면 초안을 연다 — 지금 파일을 열면 방금 한 편집이 사라진다', () => {
    const html = renderToStaticMarkup(
      <ContentAdminPanel
        content={VIEW}
        asset={{ ...ASSET, draft: { skill_list_version: 9, skills: [] } }}
        detail=""
        onOpen={noop}
        onSave={noop}
        onDiscard={noop}
      />,
    )
    expect(html).toContain('&quot;skill_list_version&quot;: 9')
  })

  it('★ 버전을 올려야 한다고 적는다', () => {
    expect(MARKUP).toContain('올려야 저장된다')
  })

  it('★ 거절 사유를 그대로 적는다 — 서버의 로더가 답을 안다', () => {
    const html = renderToStaticMarkup(
      <ContentAdminPanel
        content={VIEW}
        asset={ASSET}
        detail="읽을 수 없다: 스킬에 id·coef_pct 가 없다"
        onOpen={noop}
        onSave={noop}
        onDiscard={noop}
      />,
    )
    expect(html).toContain('coef_pct 가 없다')
  })

  it('★ 서버가 없으면 그렇게 말한다', () => {
    const html = renderToStaticMarkup(
      <ContentAdminPanel
        content={undefined}
        asset={undefined}
        detail=""
        onOpen={noop}
        onSave={noop}
        onDiscard={noop}
      />,
    )
    expect(html).toContain('서버에 닿지 못했다')
  })

  it('빈 절은 빈 문자열이다 — "null" 을 편집기에 넣지 않는다', () => {
    expect(formatDraftText(null)).toBe('')
    expect(formatDraftText(undefined)).toBe('')
  })
})
