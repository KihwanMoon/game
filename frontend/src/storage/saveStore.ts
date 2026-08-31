/**
 * 저장소 접근과 디바운스 — "편집할 때마다 저장" 을 실제로 붙이는 자리.
 *
 * 저장소를 `Storage` 인터페이스로 받는 이유가 둘이다. 테스트가 브라우저 없이 저장→새로고침
 * 왕복을 돌릴 수 있고(vitest 는 node 환경에서 돈다), 저장이 막힌 브라우저에서 앱이 죽지
 * 않는다 — 사파리 프라이빗 창은 `setItem` 이 예외를 던지고, 쿠키를 막은 브라우저는
 * `localStorage` 접근 자체가 던진다. **저장 실패는 편집을 막지 않는다.**
 *
 * 키 입력마다 쓰지 않고 디바운스하는 이유는 값 하나를 고칠 때 규칙표 전체를 다시 찍기
 * 때문이다. 숫자 칸에 `12` 를 치면 저장이 두 번 도는데, 그 사이 값(`1`)은 아무도 필요로
 * 하지 않는다. 마지막 것 하나만 남기면 된다.
 */
import { SAVE_STORAGE_KEY, buildSaveText, parseSaveText, type EditorSave } from './editorSave'

/** 저장이 멈춘 뒤 실제로 쓰기까지의 간격(ms). 사람이 손을 뗀 것으로 볼 만한 길이다. */
export const SAVE_DELAY_MS = 400

/** `localStorage` 에서 우리가 쓰는 만큼만 뽑은 모양. */
export interface StorageLike {
  getItem: (key: string) => string | null
  setItem: (key: string, value: string) => void
  removeItem: (key: string) => void
}

/**
 * 저장 시도의 결과.
 *
 * `blocked` 는 브라우저가 막은 것이고(사파리 프라이빗 창, 쿠키 차단), `broken` 은 우리가
 * 못 만든 것이다. **화면이 둘을 다르게 말해야 한다** — 앞엣것은 쓰는 사람이 손쓸 수
 * 있고 뒤엣것은 우리가 고쳐야 한다.
 */
export type SaveOutcome = 'saved' | 'blocked' | 'broken'

/** 디바운스된 저장기. */
export interface SaveScheduler {
  /** 저장을 예약한다. 간격 안에 다시 부르면 앞의 예약은 버려진다. */
  readonly schedule: (save: EditorSave) => void
  /** 예약된 것이 있으면 지금 쓴다. */
  readonly flush: () => void
  /** 예약을 버린다. */
  readonly cancel: () => void
  /** 마지막 쓰기의 결과를 듣는다. 화면이 저장 상태를 말할 수 있어야 한다. */
  readonly listen: (watcher: (outcome: SaveOutcome) => void) => void
}

/**
 * 브라우저의 localStorage 를 집는다. 없거나 막혀 있으면 undefined 다.
 *
 * @returns 저장소. 쓸 수 없으면 undefined.
 */
export function getLocalStorage(): StorageLike | undefined {
  try {
    return globalThis.localStorage as StorageLike | undefined
  } catch {
    return undefined
  }
}

/**
 * 저장을 읽는다. **읽기 실패는 저장이 없는 것과 같이 다룬다.**
 *
 * 깨진 값 하나 때문에 화면이 뜨지 않으면 사람은 저장이 아니라 게임을 잃는다. 형식이
 * 갈렸거나(새 세대) 손으로 고쳐 깨진 값이면 처음 상태로 시작한다.
 *
 * @param storage 저장소.
 * @returns 읽어 낸 저장. 없거나 읽을 수 없으면 undefined.
 */
export function readSave(storage: StorageLike | undefined): EditorSave | undefined {
  if (storage === undefined) {
    return undefined
  }
  try {
    const text = storage.getItem(SAVE_STORAGE_KEY)
    return text === null ? undefined : parseSaveText(text)
  } catch {
    return undefined
  }
}

/**
 * 저장을 쓴다. 저장소가 막혀 있으면 조용히 넘어간다.
 *
 * @param storage 저장소.
 * @param save 저장할 내용.
 * @returns 실제로 썼으면 true.
 */
export function writeSave(storage: StorageLike | undefined, save: EditorSave): SaveOutcome {
  if (storage === undefined) {
    return 'blocked'
  }
  let text: string
  try {
    // **직렬화와 쓰기를 가른다.** 한 try 로 묶으면 "저장소가 막혔다" 와 "이 규칙표를
    // 문자열로 못 만든다" 가 같은 실패로 보이고, 뒤엣것은 코드 결함인데도 조용히
    // 넘어간다 — 쓰는 사람에게는 둘 다 "저장이 안 된다" 이지만 고칠 사람에게는 다르다.
    text = buildSaveText(save)
  } catch {
    return 'broken'
  }
  try {
    storage.setItem(SAVE_STORAGE_KEY, text)
    return 'saved'
  } catch {
    return 'blocked'
  }
}

/**
 * 저장을 지운다.
 *
 * @param storage 저장소.
 */
export function removeSave(storage: StorageLike | undefined): void {
  try {
    storage?.removeItem(SAVE_STORAGE_KEY)
  } catch {
    // 지우기 실패도 편집을 막지 않는다.
  }
}

/**
 * 디바운스된 저장기를 만든다.
 *
 * @param storage 저장소.
 * @param delayMs 손을 뗀 것으로 보는 간격.
 * @returns 예약·즉시 쓰기·취소를 가진 저장기.
 */
export function createSaveScheduler(
  storage: StorageLike | undefined,
  delayMs: number = SAVE_DELAY_MS,
): SaveScheduler {
  let timer: ReturnType<typeof setTimeout> | undefined = undefined
  let pending: EditorSave | undefined = undefined
  let watcher: ((outcome: SaveOutcome) => void) | undefined = undefined

  function cancel(): void {
    if (timer !== undefined) {
      clearTimeout(timer)
      timer = undefined
    }
    pending = undefined
  }

  function flush(): void {
    const save = pending
    if (timer !== undefined) {
      clearTimeout(timer)
      timer = undefined
    }
    pending = undefined
    if (save !== undefined) {
      // **결과를 먼저 계산한다.** `watcher?.(writeSave(...))` 로 쓰면 듣는 이가 없을 때
      // 옵셔널 호출이 인자까지 건너뛰어 저장 자체가 안 돈다 — 한 번 그렇게 썼고
      // 디바운스 검사가 잡았다.
      const outcome = writeSave(storage, save)
      watcher?.(outcome)
    }
  }

  function schedule(save: EditorSave): void {
    pending = save
    if (timer !== undefined) {
      clearTimeout(timer)
    }
    timer = setTimeout(flush, delayMs)
  }

  /**
   * 저장 결과를 들을 곳을 정한다.
   *
   * @param next 결과를 받을 함수.
   */
  function listen(next: (outcome: SaveOutcome) => void): void {
    watcher = next
  }

  return { schedule, flush, cancel, listen }
}
