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
 * 읽을 자리는 「권」 탭이다.
 */
import { Button } from '../ds'
import { StoryNote } from '../content/StoryNote'

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
            다음 장으로
          </Button>
        </div>
      </div>
    </div>
  )
}
