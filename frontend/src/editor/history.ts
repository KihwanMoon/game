/**
 * 되돌리기 스택 — 규칙표 한 벌을 통째로 쌓는다.
 *
 * `draft.ts` 가 전부 순수 함수라 편집 결과가 **새 규칙표 하나**로 나온다. 그래서 무엇이
 * 바뀌었는지 기록할 필요가 없고, 바뀌기 전 값을 그대로 밀어 넣기만 하면 된다. 편집 명령
 * 하나에 역명령 하나를 짝지어 두는 방식은 명령이 늘 때마다 짝을 빠뜨릴 수 있지만, 이
 * 방식은 새 편집이 생겨도 스택이 알아야 할 것이 없다.
 *
 * 규칙표 하나는 규칙 몇 줄짜리 객체라 50벌을 들고 있어도 부담이 없다. 상한을 두는 이유는
 * 용량이 아니라 **끝없이 자라는 자료구조를 남기지 않기 위해서**다.
 *
 * 새 편집이 들어오면 앞으로 갈 길(`future`)은 버린다. 되돌린 뒤 다른 편집을 하면 갈래가
 * 생기는데, 갈래를 남겨 두면 "다시 실행" 이 방금 한 편집과 무관한 규칙표를 꺼내 온다.
 */

/** 스택에 남기는 최대 단계 수. */
export const HISTORY_LIMIT = 50

/** 되돌리기 스택. `present` 가 지금 화면의 값이다. */
export interface EditHistory<T> {
  readonly past: readonly T[]
  readonly present: T
  readonly future: readonly T[]
}

/** 키 입력이 가리키는 되돌리기 명령. */
export type HistoryCommand = 'undo' | 'redo'

/** 되돌리기 판정에 필요한 만큼만 뽑은 키 입력. */
export interface KeyChord {
  readonly key: string
  readonly ctrlKey: boolean
  readonly metaKey: boolean
  readonly shiftKey: boolean
}

/**
 * 스택을 만든다.
 *
 * @param present 지금 값.
 * @returns 과거도 미래도 없는 스택.
 */
export function createHistory<T>(present: T): EditHistory<T> {
  return { past: [], present, future: [] }
}

/**
 * 편집 결과를 쌓는다. 같은 값이면 아무 일도 하지 않는다.
 *
 * @param history 지금 스택.
 * @param next 편집 결과.
 * @returns 새 스택.
 */
export function applyChange<T>(history: EditHistory<T>, next: T): EditHistory<T> {
  if (next === history.present) {
    return history
  }
  const past = [...history.past, history.present].slice(-HISTORY_LIMIT)
  return { past, present: next, future: [] }
}

/**
 * 한 단계 되돌린다.
 *
 * @param history 지금 스택.
 * @returns 되돌린 스택. 되돌릴 것이 없으면 그대로.
 */
export function applyUndo<T>(history: EditHistory<T>): EditHistory<T> {
  const previous = history.past[history.past.length - 1]
  if (previous === undefined) {
    return history
  }
  return {
    past: history.past.slice(0, -1),
    present: previous,
    future: [history.present, ...history.future],
  }
}

/**
 * 되돌린 것을 한 단계 다시 실행한다.
 *
 * @param history 지금 스택.
 * @returns 다시 실행한 스택. 갈 곳이 없으면 그대로.
 */
export function applyRedo<T>(history: EditHistory<T>): EditHistory<T> {
  const next = history.future[0]
  if (next === undefined) {
    return history
  }
  return {
    past: [...history.past, history.present],
    present: next,
    future: history.future.slice(1),
  }
}

/**
 * 되돌릴 것이 있는지 본다.
 *
 * @param history 지금 스택.
 * @returns 있으면 true.
 */
export function checkCanUndo<T>(history: EditHistory<T>): boolean {
  return history.past.length > 0
}

/**
 * 다시 실행할 것이 있는지 본다.
 *
 * @param history 지금 스택.
 * @returns 있으면 true.
 */
export function checkCanRedo<T>(history: EditHistory<T>): boolean {
  return history.future.length > 0
}

/**
 * 글자를 치는 칸의 태그 이름들. 여기 포커스가 있으면 되돌리기는 브라우저의 것이다.
 */
export const TEXT_ENTRY_TAGS: readonly string[] = ['INPUT', 'TEXTAREA']

/**
 * 지금 포커스가 글자를 치는 칸에 있는지 본다.
 *
 * 프리셋 이름이나 공유 코드를 치다 누른 `Ctrl+Z` 까지 규칙표를 되돌리면, 사람은 오타
 * 하나를 지우려다 규칙 한 줄을 잃는다. 그 칸의 되돌리기는 브라우저가 이미 갖고 있다.
 *
 * @param tagName 포커스가 있는 요소의 태그 이름.
 * @returns 글자 칸이면 true.
 */
export function checkTextEntry(tagName: string): boolean {
  return TEXT_ENTRY_TAGS.includes(tagName.toUpperCase())
}

/**
 * 키 입력이 되돌리기인지 판정한다.
 *
 * `Ctrl+Z`(맥은 `Cmd+Z`)가 되돌리기, `Ctrl+Shift+Z` 와 `Ctrl+Y` 가 다시 실행이다. 둘 다
 * 받는 이유는 관례가 플랫폼마다 갈리기 때문이며, 어느 쪽을 눌러도 되게 두는 편이 어느
 * 한쪽을 틀렸다고 하는 것보다 낫다.
 *
 * @param chord 키 입력.
 * @returns 명령. 되돌리기 키가 아니면 undefined.
 */
export function resolveHistoryCommand(chord: KeyChord): HistoryCommand | undefined {
  if (!chord.ctrlKey && !chord.metaKey) {
    return undefined
  }
  const key = chord.key.toLowerCase()
  if (key === 'y') {
    return 'redo'
  }
  if (key === 'z') {
    return chord.shiftKey ? 'redo' : 'undo'
  }
  return undefined
}
