/**
 * 스토리가 화면에 실렸는가 (2026-09-14 요청: 「게임에서 스토리를 볼 수 있게」).
 *
 * 지키는 것은 셋이다.
 *
 *     ① 안 내려간 장은 본문이 안 샌다 — 10장(빈 표지)이 1층에서 새면 끝을 먼저 읽는다
 *     ② 내려간 장은 열린다 — 잠금이 과하면 글이 없는 것과 같다
 *     ③ 글은 **문단으로** 선다 — `**` 가 글자로 보이면 화면이 원고를 그대로 흘린 것이다
 *
 * **황동은 안 쓴다.** 화면당 3곳 예산이고 글은 그 자리가 아니다 (design/README D-1).
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { CHAPTERS, SHADOW, splitEmphasis, splitParagraphs } from '../content/story'
import { StoryNote } from '../content/StoryNote'
import { ChapterCard } from '../hud/ChapterCard'
import { VolumePanel, checkChapterOpen } from './VolumePanel'

const noop = () => undefined

describe('권 탭', () => {
  it('★ 안 내려간 장은 본문이 안 샌다 — 끝을 먼저 읽게 두지 않는다', () => {
    const markup = renderToStaticMarkup(<VolumePanel bestFloor={1} />)
    const last = CHAPTERS[CHAPTERS.length - 1]
    expect(last).toBeDefined()
    expect(markup).not.toContain(last?.titleKo ?? '')
    // 첫 문장의 한 조각이라도 새면 안 된다.
    expect(markup).not.toContain('표지뿐이다')
  })

  it('★ 내려간 장은 목록에 이름이 선다', () => {
    const markup = renderToStaticMarkup(<VolumePanel bestFloor={10} />)
    for (const chapter of CHAPTERS) {
      expect(markup, `${String(chapter.floor)}장이 없다`).toContain(chapter.titleKo)
    }
  })

  it('한 장도 안 찍었어도 목록은 선다 — 빈 화면은 결함처럼 보인다', () => {
    const markup = renderToStaticMarkup(<VolumePanel bestFloor={0} />)
    expect(markup).toContain('아직 안 찍은 장이다')
    expect(markup).toContain('1장')
  })

  it('낱말·인물·금기가 함께 선다', () => {
    const markup = renderToStaticMarkup(<VolumePanel bestFloor={3} />)
    expect(markup).toContain('비각(祕閣)')
    expect(markup).toContain('하윤')
    expect(markup).toContain('몸은 안 들어간다')
  })

  it('황동을 안 쓴다 — 화면당 3곳 예산이고 글은 그 자리가 아니다', () => {
    const markup = renderToStaticMarkup(<VolumePanel bestFloor={10} />)
    expect(markup).not.toContain('brass')
  })

  it('잠금은 도달 층으로 가른다', () => {
    expect(checkChapterOpen(3, 3)).toBe(true)
    expect(checkChapterOpen(4, 3)).toBe(false)
    expect(checkChapterOpen(1, 0)).toBe(false)
  })
})

describe('장 카드', () => {
  it('★ 이름과 글이 함께 선다', () => {
    const first = CHAPTERS[0]
    expect(first).toBeDefined()
    const markup = renderToStaticMarkup(
      <ChapterCard
        title={first?.titleKo ?? ''}
        note={first?.noteKo ?? ''}
        ordinal="1장"
        onClose={noop}
      />,
    )
    expect(markup).toContain('1장')
    expect(markup).toContain(first?.titleKo ?? '')
    expect(markup).toContain('다음 장으로')
  })

  it('층에 안 묶인 카드는 머리에 장 번호를 안 적는다', () => {
    const markup = renderToStaticMarkup(
      <ChapterCard title={SHADOW.titleKo} note={SHADOW.noteKo} ordinal="" onClose={noop} />,
    )
    expect(markup).toContain(SHADOW.titleKo)
    expect(markup).not.toContain('ds-label')
  })
})

describe('수첩 글', () => {
  it('★ `**` 가 글자로 안 보인다 — 원고를 그대로 흘리면 화면이 초고가 된다', () => {
    const markup = renderToStaticMarkup(<StoryNote note="앞 **굵게** 뒤" />)
    expect(markup).not.toContain('**')
    expect(markup).toContain('<strong')
    expect(markup).toContain('굵게')
  })

  it('줄바꿈이 문단을 가른다', () => {
    expect(splitParagraphs('첫 줄\n둘째 줄\n\n셋째 줄')).toEqual(['첫 줄', '둘째 줄', '셋째 줄'])
  })

  it('여는 표시가 짝이 안 맞으면 가르지 않는다 — 반만 굵어지는 것보다 낫다', () => {
    expect(splitEmphasis('앞 **뒤')).toEqual([{ text: '앞 **뒤', isStrong: false }])
  })

  it('모든 장의 글이 문단으로 갈라진다 — 한 덩어리면 읽히지 않는다', () => {
    for (const chapter of CHAPTERS) {
      expect(splitParagraphs(chapter.noteKo).length, `${chapter.titleKo}`).toBeGreaterThan(1)
    }
  })
})
