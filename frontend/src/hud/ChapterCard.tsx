/**
 * 장 카드 — 장을 넘길 때 한 장이 찍혀 나온다.
 *
 * **새 화면을 안 만든다.** 방 사이에는 이미 창이 있다(자동 진행 몇 초). 그 창에 얹으면
 * 읽는 흐름이 곧 하강이 되고, 안 읽는 사람은 누르고 지나간다.
 *
 * **멈춰 세우지 않는다** — 닫기 전까지 다음 방으로 안 넘어가되, 전투를 되돌리거나 상태를
 * 바꾸지 않는다. 카드가 판정에 닿는 순간 글이 기계가 된다.
 *
 * 읽기는 **한 번 뜬다.** 같은 장을 다시 띄우면 되풀이 관전에서 매번 걸리적거린다 — 다시
 * 읽을 자리는 「기록」 탭이다. 「한 번」의 범위는 **계정이다**(2026-09-16) — 세션 안에서만
 * 기억하던 때는 새로고침하거나 다른 기기로 옮기면 1장 카드가 다시 떴다.
 */
import { useEffect, useRef, useState } from 'react'

import { StoryNote } from '../content/StoryNote'
import { Button } from '../ds'

/**
 * 저절로 닫히기까지의 초 (2026-09-16 요청).
 *
 * 카드가 떠 있는 동안 판이 멈추므로, 자리를 비운 사이에 뜨면 돌아올 때까지 판이 서 있다.
 * 열이면 수첩 한 장을 읽기에 넉넉하고, 안 읽는 사람을 오래 붙들지도 않는다.
 */
export const AUTO_CLOSE_SECONDS = 10

/** 초를 세는 간격. */
const ONE_SECOND_MS = 1000

export interface ChapterCardProps {
  /** 장 이름. */
  readonly title: string
  /** 수첩 원문. */
  readonly note: string
  /** 머리에 적을 자리 — 「3장」 또는 빈 문자열(층에 안 묶인 카드). */
  readonly ordinal: string
  readonly onClose: () => void
}

/**
 * 장 카드를 그린다.
 *
 * @param props 장 이름·본문·머리말·닫기.
 * @returns 카드 요소.
 */
export function ChapterCard(props: ChapterCardProps): React.JSX.Element {
  // **저절로 닫힌다** (2026-09-16 요청). 카드가 떠 있는 동안 판이 멈추므로, 자리를 비운
  // 사이에 뜨면 돌아올 때까지 판이 서 있다. 그렇다고 곧장 지우면 못 읽는다.
  //
  // **남은 초를 적는다.** 소리 없이 사라지면 「내가 뭘 눌렀나」가 되고, 그 다음부터는
  // 읽는 대신 사라지기 전에 닫게 된다 — 값을 병기하는 이 게임의 규율과 같은 자리다.
  const [left, setLeft] = useState(AUTO_CLOSE_SECONDS)
  // **최신 처리기를 참조로 든다.** 의존성에 넣으면 부모가 다시 그릴 때마다 초가 되감긴다.
  const onClose = useRef(props.onClose)
  onClose.current = props.onClose

  useEffect(() => {
    // **`Date.now` 를 안 읽는다.** 코어의 규율(R5)이 여기까지 오지는 않지만, 시계를 안
    // 보고도 되는 일에 시계를 끌어들일 이유가 없다 — 세는 것으로 족하다.
    const timer = setInterval(() => {
      setLeft((now) => {
        if (now <= 1) {
          clearInterval(timer)
          onClose.current()
          return 0
        }
        return now - 1
      })
    }, ONE_SECOND_MS)
    return () => {
      clearInterval(timer)
    }
  }, [])

  return (
    <div className="story-card" role="dialog" aria-label={`${props.ordinal} ${props.title}`}>
      <div className="story-card__sheet">
        <header className="story-card__head">
          {props.ordinal === '' ? null : <span className="ds-label">{props.ordinal}</span>}
          <h2 className="story-card__title">{props.title}</h2>
        </header>
        <StoryNote note={props.note} />
        <div className="story-card__foot">
          <Button size="sm" variant="secondary" glyph="→" onClick={props.onClose}>
            {left > 0 ? `다음 장으로 (${String(left)})` : '다음 장으로'}
          </Button>
        </div>
      </div>
    </div>
  )
}
