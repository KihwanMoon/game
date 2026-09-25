/**
 * 알림 토스트 · 종 · 알림함 (2026-09-25).
 *
 * 지키는 것: 처음 읽을 때 쏟지 않는다 · 반려는 저절로 안 닫는다 · 세 장을 넘으면 접는다 ·
 * 이김·짐·반려를 글리프와 보조 기술 이름으로도 가른다 · 0 은 숫자를 안 단다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { countNoticePages, formatUnreadBadge, pickFreshNotices, type NoticeView } from '../storage'
import { NoticeBell, NoticeInbox, NoticeToasts, checkAutoDismiss, describeNoticeTone } from './NoticeToasts'

function build(id: number, kind: NoticeView['kind'], title: string, isRead = false): NoticeView {
  return { id, kind, title, lines: ['푼 +40', '경험치 +160'], createdAt: '2026-09-25T10:00:00+09:00', isRead }
}

describe('새 알림 고르기', () => {
  const board = { unread: 2, total: 3, offset: 0, notices: [build(3, 'floor', '2장 돌파'), build(2, 'run', '1장에서 쓰러졌다'), build(1, 'floor', '1장 돌파', true)] }

  it('★ 처음 읽을 때는 아무것도 안 띄우고 기준만 세운다 — 쏟으면 토스트가 아니라 벽이다', () => {
    expect(pickFreshNotices(board, undefined)).toEqual({ fresh: [], seenId: 3 })
  })

  it('★ 지난번 뒤에 온 안 읽은 것만, 오래된 것부터', () => {
    expect(pickFreshNotices(board, 1).fresh.map((one) => one.id)).toEqual([2, 3])
  })

  it('★ 이미 읽은 것은 다시 안 띄운다', () => {
    const read = { unread: 0, total: 1, offset: 0, notices: [build(4, 'floor', '3장 돌파', true)] }
    expect(pickFreshNotices(read, 3).fresh).toEqual([])
  })
})

describe('안 읽은 수', () => {
  it('★ 0 은 안 달고, 아홉을 넘으면 접는다', () => {
    expect(formatUnreadBadge(0)).toBe('')
    expect(formatUnreadBadge(3)).toBe('3')
    expect(formatUnreadBadge(12)).toBe('9+')
  })

  it('★ 종은 0 일 때 숫자 없이 선다', () => {
    const quiet = renderToStaticMarkup(<NoticeBell unread={0} onOpen={() => undefined} />)
    expect(quiet).not.toContain('notice-badge')
    const loud = renderToStaticMarkup(<NoticeBell unread={2} onOpen={() => undefined} />)
    expect(loud).toContain('>2<')
  })
})

describe('표기', () => {
  it('★ 이김·짐·반려를 글리프와 이름으로 가른다 — 색만으로 안 가른다', () => {
    expect(describeNoticeTone(build(1, 'floor', '2장 돌파'))).toMatchObject({ glyph: '✓', label: '돌파' })
    expect(describeNoticeTone(build(1, 'run', '3장에서 쓰러졌다'))).toMatchObject({ glyph: '·', label: '짐' })
    expect(describeNoticeTone(build(1, 'rejected', '서버가 이 판을 인정하지 않았다'))).toMatchObject({ glyph: '◈', label: '반려' })
  })

  it('★ 반려는 저절로 안 닫는다 — 보상이 안 들어온 까닭이 5초 만에 묻힌다', () => {
    expect(checkAutoDismiss(build(1, 'rejected', 'x'))).toBe(false)
    expect(checkAutoDismiss(build(1, 'floor', 'x'))).toBe(true)
  })
})

describe('토스트 더미', () => {
  it('★ 세 장을 넘으면 「외 N건」으로 접는다', () => {
    const many = [1, 2, 3, 4, 5].map((id) => build(id, 'floor', `${String(id)}장 돌파`))
    const html = renderToStaticMarkup(<NoticeToasts toasts={many} onDismiss={() => undefined} onOpen={() => undefined} />)
    expect(html.match(/notice-toast--win/g)?.length).toBe(3)
    expect(html).toContain('외 2건')
  })

  it('★ 서버 본문을 항목 그대로 싣는다', () => {
    const html = renderToStaticMarkup(<NoticeToasts toasts={[build(1, 'floor', '1장 돌파')]} onDismiss={() => undefined} onOpen={() => undefined} />)
    expect(html).toContain('푼 +40 · 경험치 +160')
  })
})

describe('알림함', () => {
  const page = (from: number, count: number): NoticeView[] =>
    Array.from({ length: count }, (_, at) => build(from - at, 'floor', `${String(from - at)}장 돌파`))
  const draw = (notices: NoticeView[], at: number, pages: number, newCount: number): string =>
    renderToStaticMarkup(
      <NoticeInbox notices={notices} page={at} pageCount={pages} newCount={newCount} onPage={() => undefined} onClose={() => undefined} />,
    )

  it('★ 열 건이 한 쪽이다 — 쪽 수는 전체에서 센다, 없어도 한 쪽', () => {
    expect(countNoticePages(0)).toBe(1)
    expect(countNoticePages(10)).toBe(1)
    expect(countNoticePages(11)).toBe(2)
  })

  it('★ 열었을 때 안 읽었던 수만큼 가장 새 줄에 표시가 붙는다', () => {
    const html = draw(page(12, 10), 0, 2, 3)
    expect(html.match(/notice-inbox__row--new/g)?.length).toBe(3)
    expect(html).toContain('새 알림')
  })

  it('★ 뒷쪽에서도 자리로 새것을 안다 — 안 읽은 것은 늘 가장 새 N 건이다', () => {
    // 안 읽은 것 12건: 첫 쪽 10건 전부, 둘째 쪽 앞 2건.
    const html = draw(page(15, 5), 1, 2, 12)
    expect(html.match(/notice-inbox__row--new/g)?.length).toBe(2)
  })

  it('★ 쪽 넘김은 쪽이 둘 이상일 때만 서고, 끝에서는 그쪽 단추가 꺼진다', () => {
    expect(draw(page(3, 3), 0, 1, 0)).not.toContain('notice-inbox__pager')
    const first = draw(page(12, 10), 0, 2, 0)
    expect(first).toContain('1 / 2')
    expect(first).toMatch(/<button[^>]*disabled[^>]*>.*?더 새 것/)
  })

  it('★ 비어 있어도 무엇이 여기 올지 말한다', () => {
    expect(draw([], 0, 1, 0)).toContain('아직 알림이 없다')
  })
})
