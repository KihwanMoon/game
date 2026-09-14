/**
 * 「권」 탭 — 읽은 장을 다시 읽고, 이 권의 낱말을 본다.
 *
 * **막간은 흐르고 탭은 남는다.** 장 카드는 지날 때 한 번 뜨므로, 다시 읽을 자리가 없으면
 * 그 글은 사실상 없는 것과 같다.
 *
 * **안 내려간 장은 안 연다.** 표지(장 이름)는 보이고 본문은 잠긴다 — 목록이 통째로 비면
 * 「글이 없다」로 읽히고, 전부 열면 10장(빈 표지)이 1층에서 새어 나간다.
 *
 * 잠금 기준은 `meta.bestFloor` 다. 이 판의 층이 아니라 **지금까지 닿은 가장 깊은 층**이다
 * — 되풀이 관전에서 읽은 장이 다시 잠기면 그것은 진행이 아니라 벌이다.
 */
import { useState } from 'react'

import { ACT, CHAPTERS, GLOSSARY, PEOPLE, TABOOS } from '../content/story'
import { StoryNote } from '../content/StoryNote'
import { Button, Panel, ValueExpr } from '../ds'

export interface VolumePanelProps {
  /** 지금까지 닿은 가장 깊은 층. 0 이면 아직 한 장도 안 찍었다. */
  readonly bestFloor: number
}

/** 아직 안 찍은 장에 적는 말. **빈 칸을 두지 않는다** — 빈 칸은 결함처럼 보인다. */
const LOCKED_HINT = '아직 안 찍은 장이다'

/**
 * 그 장을 읽을 수 있는가.
 *
 * @param floor 장의 층.
 * @param bestFloor 지금까지 닿은 가장 깊은 층.
 * @returns 읽을 수 있으면 true.
 */
export function checkChapterOpen(floor: number, bestFloor: number): boolean {
  return floor <= bestFloor
}

/**
 * 「권」 탭을 그린다.
 *
 * @param props 도달 층.
 * @returns 패널들.
 */
export function VolumePanel(props: VolumePanelProps): React.JSX.Element {
  const [openFloor, setOpenFloor] = useState<number | undefined>(undefined)
  const read = CHAPTERS.filter((one) => checkChapterOpen(one.floor, props.bestFloor)).length

  return (
    <>
      <Panel title={ACT.labelKo} meta={`${String(read)} / ${String(CHAPTERS.length)}장`}>
        <p className="story-lede">{ACT.lineKo}</p>
        <ul className="story-list">
          {CHAPTERS.map((chapter) => {
            const isOpen = checkChapterOpen(chapter.floor, props.bestFloor)
            const isShown = isOpen && openFloor === chapter.floor
            return (
              <li className="story-list__item" key={chapter.floor}>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={!isOpen}
                  aria-expanded={isShown}
                  onClick={() => {
                    setOpenFloor(isShown ? undefined : chapter.floor)
                  }}
                >
                  <span className="story-list__ord">{String(chapter.floor)}장</span>
                  <span className="story-list__name">{isOpen ? chapter.titleKo : LOCKED_HINT}</span>
                </Button>
                {isShown ? <StoryNote note={chapter.noteKo} /> : null}
              </li>
            )
          })}
        </ul>
      </Panel>
      <Panel title="이 권의 낱말">
        <dl className="story-terms">
          {GLOSSARY.map((entry) => (
            <div className="story-terms__row" key={entry.termKo}>
              <dt className="story-terms__term">{entry.termKo}</dt>
              <dd className="story-terms__gloss">{entry.glossKo}</dd>
            </div>
          ))}
        </dl>
      </Panel>
      <Panel title="인물">
        <dl className="story-terms">
          {PEOPLE.map((person) => (
            <div className="story-terms__row" key={person.nameKo}>
              <dt className="story-terms__term">{person.nameKo}</dt>
              <dd className="story-terms__gloss">{person.lineKo}</dd>
            </div>
          ))}
        </dl>
      </Panel>
      <Panel title="금기 셋" meta="세계가 지키는 규율">
        <ul className="story-taboos">
          {TABOOS.map((taboo) => (
            <li className="story-taboos__item" key={taboo.lineKo}>
              <ValueExpr text={taboo.lineKo} size="sm" />
              <span className="story-taboos__gloss">{taboo.glossKo}</span>
            </li>
          ))}
        </ul>
      </Panel>
    </>
  )
}
