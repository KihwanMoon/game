/**
 * 텍스트 뷰 — 규칙표를 GDD §3.1 표기로 보고 직접 고치고 붙여넣는다 (GDD §8.1).
 *
 * 프리셋 공유가 이 화면으로 이뤄진다(GDD §10 A등급). 그래서 **읽을 때마다 즉시 파싱**하고,
 * 성공했을 때만 규칙표에 반영한다. 편집 도중의 반쯤 쓴 줄이 규칙표를 덮으면 마지막으로
 * 성립했던 상태가 사라져, 오타 하나에 규칙표 전체를 잃는다.
 *
 * 파싱 오류는 줄 번호와 함께 그 자리에 적는다. 어느 줄이 왜 안 읽히는지 모르면 붙여넣기가
 * 도박이 된다.
 */
import type { ChangeEvent } from 'react'

import { Button, GlyphState, Panel } from '../ds'

/** TextView 의 props. */
export interface TextViewProps {
  readonly text: string
  readonly errors: readonly string[]
  readonly ruleCount: number
  readonly onTextChange: (text: string) => void
  readonly onCopy: () => void
}

/**
 * 텍스트 뷰를 그린다.
 *
 * @param props 텍스트와 콜백들.
 * @returns 렌더 트리.
 */
export function TextView(props: TextViewProps): React.JSX.Element {
  const ok = props.errors.length === 0

  /**
   * 입력을 부모로 올린다.
   *
   * @param event 입력 변경 이벤트.
   */
  function handleChange(event: ChangeEvent<HTMLTextAreaElement>): void {
    props.onTextChange(event.target.value)
  }

  return (
    <Panel
      title="텍스트 뷰"
      meta={<Button variant="ghost" size="sm" glyph="⧉" onClick={props.onCopy}>전체 복사</Button>}
      padded={false}
    >
      <div className="textview">
        <textarea
          className="textview__area"
          spellCheck={false}
          value={props.text}
          aria-label="규칙표 텍스트"
          onChange={handleChange}
        />
        <div className="textview__status">
          {ok ? (
            <GlyphState state="true" size="sm" label={`읽힘 — 규칙 ${String(props.ruleCount)}개`} />
          ) : (
            <ul className="textview__errors">
              {props.errors.map((text) => (
                <li key={text}>
                  <GlyphState state="danger" size="sm" label={text} />
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </Panel>
  )
}
