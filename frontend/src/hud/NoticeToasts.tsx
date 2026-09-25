/**
 * 알림 토스트 · 알림 종 · 알림함 (2026-09-25).
 *
 * **화면을 밀지 않는다.** 판 결과가 출격 줄에 끼어들어 아래를 통째로 밀던 것을
 * (`battle/settlement.ts` 의 교훈) 화면 위에 띄운다. 토스트는 몇 초 뒤 사라지지만 알림은
 * 읽을 때까지 남고, 종에 안 읽은 수가 적힌다.
 *
 * **3중 표기.** 이김·짐·반려는 색만으로 안 가른다 — 글리프·왼쪽 세로바 색·보조 기술 이름을
 * 함께 단다. 황동은 안 쓴다(화면당 3곳 예산은 도면이 쓴다).
 */
import { useEffect, useRef, useState } from 'react'

import { Button } from '../ds'
import type { NoticeView } from '../storage'
import { formatUnreadBadge } from '../storage'

/** 토스트가 떠 있는 시간. 보상 한두 줄을 읽기에 넉넉하고, 다음 층이 오기 전에 비킨다. */
export const TOAST_MS = 5000

/** 한 번에 쌓는 토스트 수. 넘치면 「외 N건」으로 접는다 — 세 장을 넘으면 도면을 가린다. */
export const TOAST_LIMIT = 3

/** 알림 한 건의 표기. */
export interface NoticeTone {
  readonly glyph: string
  /** CSS 변형 이름. 왼쪽 세로바와 글리프의 색을 고른다. */
  readonly tone: 'win' | 'loss' | 'danger' | 'info'
  /** 보조 기술이 읽는 이름 — 색을 못 보는 경로의 마지막 채널이다. */
  readonly label: string
}

/**
 * 알림 종류를 글리프·색·이름 셋으로 옮긴다.
 *
 * @param notice 알림 한 건.
 * @returns 표기.
 */
export function describeNoticeTone(notice: NoticeView): NoticeTone {
  if (notice.kind === 'rejected') {
    return { glyph: '◈', tone: 'danger', label: '반려' }
  }
  if (notice.kind === 'floor') {
    return { glyph: '✓', tone: 'win', label: '돌파' }
  }
  if (notice.kind === 'run' || notice.kind === 'record') {
    // 제목이 서버가 확정한 승패를 말한다 — 여기서 다시 판정하지 않고 읽기만 한다.
    const isWon = notice.title.includes('이겼다')
    return isWon
      ? { glyph: '✓', tone: 'win', label: '이김' }
      : { glyph: '·', tone: 'loss', label: '짐' }
  }
  return { glyph: '◇', tone: 'info', label: '소식' }
}

/**
 * 반려는 저절로 안 닫는다. 서버가 판을 인정하지 않은 것은 보상이 안 들어온 까닭이고,
 * 5초 만에 사라지면 그 까닭이 조용히 묻힌다.
 *
 * @param notice 알림 한 건.
 * @returns 저절로 닫혀도 되면 참.
 */
export function checkAutoDismiss(notice: NoticeView): boolean {
  return notice.kind !== 'rejected'
}

interface ToastProps {
  readonly notice: NoticeView
  readonly onDismiss: (id: number) => void
}

function NoticeToast(props: ToastProps): React.JSX.Element {
  const tone = describeNoticeTone(props.notice)
  // **올려 두는 동안은 멈춘다.** 읽는 중에 사라지면 5초는 짧은 것이 아니라 틀린 것이다.
  const [isHeld, setHeld] = useState(false)
  const onDismiss = useRef(props.onDismiss)
  onDismiss.current = props.onDismiss
  const noticeId = props.notice.id
  const isAuto = checkAutoDismiss(props.notice)
  useEffect(() => {
    if (!isAuto || isHeld) {
      return undefined
    }
    const timer = setTimeout(() => {
      onDismiss.current(noticeId)
    }, TOAST_MS)
    return () => {
      clearTimeout(timer)
    }
  }, [isAuto, isHeld, noticeId])
  return (
    <li
      className={`notice-toast notice-toast--${tone.tone}`}
      onPointerEnter={() => {
        setHeld(true)
      }}
      onPointerLeave={() => {
        setHeld(false)
      }}
      onFocus={() => {
        setHeld(true)
      }}
      onBlur={() => {
        setHeld(false)
      }}
    >
      <span className="notice-toast__glyph" aria-hidden="true">
        {tone.glyph}
      </span>
      <div className="notice-toast__text">
        <strong className="notice-toast__title">
          <span className="ds-sr">{tone.label} — </span>
          {props.notice.title}
        </strong>
        {props.notice.lines.length === 0 ? null : (
          <span className="notice-toast__lines">{props.notice.lines.join(' · ')}</span>
        )}
      </div>
      <Button
        size="sm"
        variant="ghost"
        glyph="×"
        title="닫는다 — 알림함에는 남는다"
        onClick={() => {
          props.onDismiss(props.notice.id)
        }}
      >
        <span className="ds-sr">닫기</span>
      </Button>
    </li>
  )
}

export interface NoticeToastsProps {
  /** 띄울 것. 오래된 것부터. */
  readonly toasts: readonly NoticeView[]
  readonly onDismiss: (id: number) => void
  /** 「외 N건」을 누르면 알림함을 연다. */
  readonly onOpen: () => void
}

/**
 * 토스트 더미를 그린다.
 *
 * @param props 띄울 것·닫기·알림함 열기.
 * @returns 더미. 띄울 것이 없으면 null.
 */
export function NoticeToasts(props: NoticeToastsProps): React.JSX.Element | null {
  if (props.toasts.length === 0) {
    return null
  }
  // **새것이 위에 오지 않는다.** 오래된 것부터 쌓아야 사라지는 자리가 늘 같다 — 새것을 위에
  // 얹으면 읽던 것이 아래로 밀린다.
  const shown = props.toasts.slice(0, TOAST_LIMIT)
  const rest = props.toasts.length - shown.length
  return (
    <ol className="notice-toasts" aria-live="polite" aria-label="알림">
      {shown.map((notice) => (
        <NoticeToast key={notice.id} notice={notice} onDismiss={props.onDismiss} />
      ))}
      {rest <= 0 ? null : (
        <li className="notice-toast notice-toast--info">
          <Button size="sm" variant="ghost" onClick={props.onOpen}>
            {`외 ${String(rest)}건 — 알림함에서 본다`}
          </Button>
        </li>
      )}
    </ol>
  )
}

export interface NoticeBellProps {
  readonly unread: number
  readonly onOpen: () => void
}

/**
 * 알림 종 — 안 읽은 수를 단다.
 *
 * **0 이면 숫자를 안 그린다.** 「0」을 늘 달아 두면 눈이 그 자리를 배경으로 익혀, 수가 생겨도
 * 안 본다.
 *
 * @param props 안 읽은 수·열기.
 * @returns 단추.
 */
export function NoticeBell(props: NoticeBellProps): React.JSX.Element {
  const badge = formatUnreadBadge(props.unread)
  return (
    <Button
      size="sm"
      variant="ghost"
      glyph="◔"
      title={badge === '' ? '알림함' : `알림함 — 안 읽은 알림 ${String(props.unread)}건`}
      onClick={props.onOpen}
    >
      {badge === '' ? <span className="ds-sr">알림함</span> : <span className="notice-badge">{badge}</span>}
    </Button>
  )
}

export interface NoticeInboxProps {
  readonly notices: readonly NoticeView[]
  /** 열었을 때 안 읽었던 id 들. 열자마자 읽음이 되므로 표시는 이 목록으로 한다. */
  readonly unreadIds: ReadonlySet<number>
  readonly onClose: () => void
}

/**
 * 알림 시각을 짧게 적는다 — 오늘이면 시:분, 아니면 월/일 시:분.
 *
 * @param iso 서버 시각.
 * @param now 지금. 검사가 고정한다.
 * @returns 표기.
 */
export function formatNoticeTime(iso: string, now: Date = new Date()): string {
  const at = new Date(iso)
  if (Number.isNaN(at.getTime())) {
    return ''
  }
  const hhmm = `${String(at.getHours()).padStart(2, '0')}:${String(at.getMinutes()).padStart(2, '0')}`
  const isToday = at.toDateString() === now.toDateString()
  return isToday ? hhmm : `${String(at.getMonth() + 1)}/${String(at.getDate())} ${hhmm}`
}

/**
 * 알림함을 그린다.
 *
 * @param props 알림·안 읽었던 id·닫기.
 * @returns 낱장.
 */
export function NoticeInbox(props: NoticeInboxProps): React.JSX.Element {
  return (
    <div className="story-card" role="dialog" aria-label="알림함">
      <div className="story-card__sheet">
        <header className="story-card__head">
          <span className="ds-label">알림함</span>
          <h2 className="story-card__title">판 결과와 없는 동안 생긴 일</h2>
        </header>
        {props.notices.length === 0 ? (
          <p className="notice-inbox__empty">아직 알림이 없다 — 층을 깨거나 판이 끝나면 여기 남는다</p>
        ) : (
          <ol className="notice-inbox">
            {props.notices.map((notice) => {
              const tone = describeNoticeTone(notice)
              const isNew = props.unreadIds.has(notice.id)
              return (
                <li
                  key={notice.id}
                  className={`notice-inbox__row notice-toast--${tone.tone}${isNew ? ' notice-inbox__row--new' : ''}`}
                >
                  <span className="notice-toast__glyph" aria-hidden="true">
                    {tone.glyph}
                  </span>
                  <div className="notice-toast__text">
                    <strong className="notice-toast__title">
                      <span className="ds-sr">
                        {tone.label}
                        {isNew ? ' · 새 알림' : ''} —{' '}
                      </span>
                      {notice.title}
                    </strong>
                    {notice.lines.length === 0 ? null : (
                      <span className="notice-toast__lines">{notice.lines.join(' · ')}</span>
                    )}
                  </div>
                  <span className="notice-inbox__time">
                    {isNew ? <span aria-hidden="true">● </span> : null}
                    {formatNoticeTime(notice.createdAt)}
                  </span>
                </li>
              )
            })}
          </ol>
        )}
        <div className="story-card__foot">
          <Button size="sm" variant="secondary" onClick={props.onClose}>
            닫기
          </Button>
        </div>
      </div>
    </div>
  )
}
