/**
 * 1막의 글 — 화면이 읽어 들이는 자리.
 *
 * **정본은 `game/resources/story/act1.json` 이고 여기서 복사하지 않는다.** 밸런스·토큰과
 * 같은 규율이다 (`@resources` 별칭). 사본을 두면 고친 날 한쪽만 옛말을 한다.
 *
 * **`core_version` 에는 안 들어간다.** 글은 판정에 닿지 않으므로 세대를 올리면 돌고 있는
 * 티켓만 무효가 된다 — 자산 여섯과 다른 축이다.
 *
 * **장은 층이 열고, 그림자는 만남이 연다.** 둔갑은 죽은 자리에 서므로 몇 층에 설지 아무도
 * 미리 못 정한다 (`game/app/bots/doppel.py` — 지금 프로덕션은 스무 마리가 전부 9층이다).
 * 층에 묶어 두면 「5장에서 만난다」가 대개 거짓이 된다.
 */
import raw from '@resources/story/act1.json'

/** 장 하나 — 층 하나에 대응한다. */
export interface Chapter {
  readonly floor: number
  readonly titleKo: string
  readonly noteKo: string
}

/** 층에 안 묶인 카드. 지금은 그림자 하나다. */
export interface StoryCard {
  readonly titleKo: string
  readonly noteKo: string
}

/** 낱말 하나. */
export interface GlossaryEntry {
  readonly termKo: string
  readonly glossKo: string
}

/** 인물 하나. */
export interface PersonEntry {
  readonly nameKo: string
  readonly lineKo: string
}

/** 금기 한 줄. */
export interface TabooEntry {
  readonly lineKo: string
  readonly glossKo: string
}

interface RawStory {
  readonly act: { readonly id: string; readonly label_ko: string; readonly line_ko: string }
  readonly chapters: readonly { floor: number; title_ko: string; note_ko: string }[]
  readonly shadow: { readonly title_ko: string; readonly note_ko: string }
  readonly glossary: readonly { term_ko: string; gloss_ko: string }[]
  readonly people: readonly { name_ko: string; line_ko: string }[]
  readonly taboos: readonly { line_ko: string; gloss_ko: string }[]
}

const STORY = raw as unknown as RawStory

/** 이 권의 이름과 한 줄. */
export const ACT = {
  id: STORY.act.id,
  labelKo: STORY.act.label_ko,
  lineKo: STORY.act.line_ko,
}

/** 장 전량. **층 순서로 선다** — 파일 순서에 기대면 장을 더할 때 목록이 조용히 뒤바뀐다. */
export const CHAPTERS: readonly Chapter[] = [...STORY.chapters]
  .sort((left, right) => left.floor - right.floor)
  .map((one) => ({ floor: one.floor, titleKo: one.title_ko, noteKo: one.note_ko }))

/** 둔갑을 만난 날의 카드. */
export const SHADOW: StoryCard = {
  titleKo: STORY.shadow.title_ko,
  noteKo: STORY.shadow.note_ko,
}

/** 낱말표. */
export const GLOSSARY: readonly GlossaryEntry[] = STORY.glossary.map((one) => ({
  termKo: one.term_ko,
  glossKo: one.gloss_ko,
}))

/** 인물. */
export const PEOPLE: readonly PersonEntry[] = STORY.people.map((one) => ({
  nameKo: one.name_ko,
  lineKo: one.line_ko,
}))

/** 금기 셋. */
export const TABOOS: readonly TabooEntry[] = STORY.taboos.map((one) => ({
  lineKo: one.line_ko,
  glossKo: one.gloss_ko,
}))

/**
 * 그 층의 장.
 *
 * @param floor 볼 층.
 * @returns 장. 그 층에 장이 없으면 undefined — **없는 층을 지어내지 않는다.** 액트가
 *   늘면 층도 느는데, 빈 카드를 띄우면 「글이 없다」가 「글이 비었다」로 보인다.
 */
export function findChapter(floor: number): Chapter | undefined {
  return CHAPTERS.find((one) => one.floor === floor)
}

/** 한 조각의 글. 굵은 자리인지 함께 담는다. */
export interface TextRun {
  readonly text: string
  readonly isStrong: boolean
}

/** 굵게 여는 표시. 문서와 같은 표기를 쓴다 — 글을 쓰는 사람이 두 문법을 외우지 않는다. */
const STRONG_MARK = '**'

/**
 * `**굵게**` 를 조각으로 가른다.
 *
 * **여는 표시가 짝이 안 맞으면 그대로 글자로 둔다.** 마크다운을 들이지 않고 이 한 가지만
 * 쓰는 이유는, 글에 필요한 강조가 하나뿐이고 파서가 커지면 글이 코드가 되기 때문이다.
 *
 * @param text 원문 한 문단.
 * @returns 조각들. 굵은 자리와 아닌 자리가 번갈아 선다.
 */
export function splitEmphasis(text: string): readonly TextRun[] {
  const parts = text.split(STRONG_MARK)
  // 짝이 안 맞으면(조각 수가 짝수) 가르지 않는다 — 반만 굵어지는 것보다 안 굵은 편이 낫다.
  if (parts.length % 2 === 0) {
    return [{ text, isStrong: false }]
  }
  return parts
    .map((part, index) => ({ text: part, isStrong: index % 2 === 1 }))
    .filter((run) => run.text !== '')
}

/**
 * 수첩 한 장을 문단으로 가른다.
 *
 * @param note 원문.
 * @returns 문단들. 빈 줄은 버린다.
 */
export function splitParagraphs(note: string): readonly string[] {
  return note.split('\n').filter((line) => line.trim() !== '')
}
