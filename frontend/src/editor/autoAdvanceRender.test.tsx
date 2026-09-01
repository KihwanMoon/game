/**
 * 자동 방 이동 검사.
 *
 * 지키는 것은 넷이다.
 *
 * 1. **이겼을 때만 넘어간다.** 진 판에서 넘어가면 왜 졌는지 볼 새가 없다.
 * 2. **곧장 넘어가지 않는다.** 방 사이는 규칙을 고치는 유일한 창이다 (GDD §2.2).
 * 3. **멈출 수 있고, 멈추기가 안내 옆에 있다.** 설정 화면에 있으면 지금 멈출 수 없다.
 * 4. **어디로 가는지 적는다.** 「곧 넘어감」만 적으면 멈출지를 정할 근거가 없다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import {
  AUTO_ADVANCE_KEY,
  AUTO_ADVANCE_SECONDS,
  AutoAdvanceNotice,
  checkShouldAutoAdvance,
  formatAutoAdvanceNote,
  readAutoAdvance,
  writeAutoAdvance,
} from './AutoAdvance'

const READY = { isFinished: true, hasNext: true, isEnabled: true, isStopped: false }

/**
 * 태그를 걷어내고 사람이 읽는 글자만 남긴다.
 *
 * @param html 렌더된 마크업.
 * @returns 글자만 남은 문자열.
 */
function stripTags(html: string): string {
  return html.replace(/<[^>]+>/g, '')
}

/** 기억만 하는 저장소. 기기 저장소 없이 읽고 쓰는 규칙만 본다. */
function buildStorage(seed: Record<string, string> = {}) {
  const box = new Map(Object.entries(seed))
  return {
    getItem: (key: string) => box.get(key) ?? null,
    setItem: (key: string, value: string) => {
      box.set(key, value)
    },
    removeItem: (key: string) => {
      box.delete(key)
    },
  }
}

describe('언제 넘어가는가', () => {
  it('★ 다음 방이 있고 켜져 있고 안 멈췄으면 넘어간다', () => {
    expect(checkShouldAutoAdvance(READY)).toBe(true)
  })

  it('★ 진 판에서는 안 넘어간다 — 다음 방이 아예 없다', () => {
    expect(checkShouldAutoAdvance({ ...READY, hasNext: false })).toBe(false)
  })

  it('★ 판이 안 끝났으면 안 넘어간다 — 싸우는 중에 넘기면 관전이 끊긴다', () => {
    expect(checkShouldAutoAdvance({ ...READY, isFinished: false })).toBe(false)
  })

  it('★ 멈췄으면 안 넘어간다 — 멈춤이 안 먹으면 규칙을 못 고친다', () => {
    expect(checkShouldAutoAdvance({ ...READY, isStopped: true })).toBe(false)
  })

  it('★ 꺼 두었으면 안 넘어간다', () => {
    expect(checkShouldAutoAdvance({ ...READY, isEnabled: false })).toBe(false)
  })
})

describe('설정을 기기에 남긴다', () => {
  it('★ 아무것도 안 적혀 있으면 켜진 것으로 본다 — 넣은 쪽이 기본이다', () => {
    expect(readAutoAdvance(buildStorage())).toBe(true)
  })

  it('★ 껐으면 다음에 들어와도 꺼져 있다 — 매번 다시 끄게 하면 안 쓴다', () => {
    const storage = buildStorage()
    writeAutoAdvance(storage, false)
    expect(readAutoAdvance(storage)).toBe(false)
  })

  it('다시 켜면 켜진다', () => {
    const storage = buildStorage({ [AUTO_ADVANCE_KEY]: 'off' })
    writeAutoAdvance(storage, true)
    expect(readAutoAdvance(storage)).toBe(true)
  })

  it('저장소가 없어도 앱이 안 죽는다 — 설정 하나 때문에 판을 멈출 이유가 없다', () => {
    expect(readAutoAdvance(undefined)).toBe(true)
    writeAutoAdvance(undefined, false)
  })
})

describe('안내', () => {
  it('★ 어디로 가는지 적는다 — 「곧 넘어감」만으로는 멈출지를 정할 수 없다', () => {
    expect(formatAutoAdvanceNote(2, 3, 5)).toBe('2초 뒤 다음 방(3/5)으로 간다')
  })

  it('★ 남은 초와 갈 방을 적는다 — 몇 초인지 모르면 멈출 겨를을 가늠할 수 없다', () => {
    const html = renderToStaticMarkup(
      <AutoAdvanceNotice
        secondsLeft={AUTO_ADVANCE_SECONDS}
        roomNumber={2}
        roomTotal={5}
        onStop={() => undefined}
      />,
    )
    // `ValueExpr` 가 값을 span 으로 쪼개므로 태그를 걷어내고 본다. 조각을 따로 찾으면
    // 문구가 흩어져도 통과한다.
    expect(stripTags(html)).toContain(formatAutoAdvanceNote(AUTO_ADVANCE_SECONDS, 2, 5))
  })

  it('★ 멈춤이 안내 옆에 붙어 있다 — 설정 화면에 있으면 지금 멈출 수 없다', () => {
    const html = renderToStaticMarkup(
      <AutoAdvanceNotice secondsLeft={3} roomNumber={2} roomTotal={5} onStop={() => undefined} />,
    )
    expect(html).toContain('멈춤')
  })

  it('★ 안 도는 중에는 아무것도 안 그린다 — 늘 떠 있으면 무엇이 도는지 알 수 없다', () => {
    const html = renderToStaticMarkup(
      <AutoAdvanceNotice
        secondsLeft={undefined}
        roomNumber={2}
        roomTotal={5}
        onStop={() => undefined}
      />,
    )
    expect(html).toBe('')
  })

  it('★ 곧장 넘기지 않는다 — 방 사이는 규칙을 고치는 유일한 창이다', () => {
    expect(AUTO_ADVANCE_SECONDS).toBeGreaterThan(0)
  })
})
