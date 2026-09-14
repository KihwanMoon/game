/**
 * 수첩 한 장을 그린다 — 장 카드와 「권」 탭이 함께 쓴다.
 *
 * **두 자리가 같은 글을 같은 꼴로 낸다.** 막간에서 본 문장을 탭에서 다시 찾을 때 모양이
 * 다르면 같은 글로 안 읽힌다.
 */
import { splitEmphasis, splitParagraphs } from './story'

export interface StoryNoteProps {
  /** 수첩 원문. 줄바꿈이 문단을 가르고 `**` 가 굵은 자리를 연다. */
  readonly note: string
}

/**
 * 수첩 글을 문단으로 그린다.
 *
 * @param props 원문.
 * @returns 문단들.
 */
export function StoryNote(props: StoryNoteProps): React.JSX.Element {
  return (
    // 문단과 조각에는 고유 id 가 없다. **순서가 곧 정체성이다** — 글은 다시 배열되지
    // 않으므로 자리를 열쇠로 써도 안 흔들린다.
    <div className="story-note">
      {splitParagraphs(props.note).map((line, lineIndex) => (
        <p className="story-note__line" key={`line-${String(lineIndex)}`}>
          {splitEmphasis(line).map((run, runIndex) =>
            run.isStrong ? (
              <strong className="story-note__strong" key={`run-${String(runIndex)}`}>
                {run.text}
              </strong>
            ) : (
              <span key={`run-${String(runIndex)}`}>{run.text}</span>
            ),
          )}
        </p>
      ))}
    </div>
  )
}
