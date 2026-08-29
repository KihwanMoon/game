/**
 * 저장 층 검사 — **새로고침해도 짠 것이 남는가**.
 *
 * M3 의 정의가 "JSON 없이 플레이 가능" 이므로, 규칙 에디터로 짠 것이 탭을 닫는 순간
 * 사라지면 그 정의를 만족하지 못한다. 그래서 여기서 도는 것은 저장 형식의 단위 검사가
 * 아니라 **왕복**이다 — 저장소에 쓰고, 새 탭이 그러하듯 그 저장소만 들고 다시 세운다.
 *
 * 브라우저를 띄우지 않는다. `Storage` 를 인터페이스로 받아 두었으므로 대역 하나면 충분하고
 * (saveStore.ts), 그 덕에 저장이 막힌 브라우저·용량 초과 같은 갈래까지 여기서 돈다.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { G0_RULESETS } from '../core/resources'
import type { RuleSet } from '../core/schemas'
import { formatBase64Url, parseBase64Url } from './base64'
import { formatCanonicalJson } from './canonicalJson'
import {
  SAVE_FORMAT_TAG,
  SAVE_STORAGE_KEY,
  buildSaveText,
  getSaveVersion,
  parseSaveText,
  type EditorSave,
} from './editorSave'
import { buildGzip, parseGzip } from './gzip'
import { MAX_PRESET_SLOTS } from './presetPayload'
import { createSaveScheduler, readSave, removeSave, writeSave, type StorageLike } from './saveStore'

/** 대역 저장소. 실패를 흉내 낼 수 있어야 사파리 프라이빗 창 갈래가 검사된다. */
interface FakeStorage extends StorageLike {
  readonly entries: Map<string, string>
  failing: boolean
}

/**
 * 대역 저장소를 만든다.
 *
 * @returns 메모리에만 남는 저장소.
 */
function createFakeStorage(): FakeStorage {
  const entries = new Map<string, string>()
  return {
    entries,
    failing: false,
    getItem: (key: string) => entries.get(key) ?? null,
    setItem(key: string, value: string) {
      if (this.failing) {
        throw new Error('저장 용량을 넘겼다')
      }
      entries.set(key, value)
    },
    removeItem: (key: string) => {
      entries.delete(key)
    },
  }
}

/**
 * 바이트 하나를 뒤집은 사본을 만든다.
 *
 * @param data 원래 바이트.
 * @param at 뒤집을 자리.
 * @returns 그 자리만 다른 사본.
 */
function buildDamaged(data: Uint8Array, at: number): Uint8Array {
  const copy = Uint8Array.from(data)
  copy.set([(data[at] ?? 0) ^ 1], at)
  return copy
}

const PRESSURE = G0_RULESETS.get('g0_pressure') as RuleSet
const KITE = G0_RULESETS.get('g0_kite') as RuleSet

/**
 * 저장 한 벌을 만든다.
 *
 * @returns 규칙표·프리셋·판 조건이 채워진 저장.
 */
function buildSample(): EditorSave {
  return {
    ruleset: PRESSURE,
    presets: [
      { name: '근접 압박', ruleset: PRESSURE },
      { name: '원거리 견제', ruleset: KITE },
    ],
    roomId: 'pillars',
    seed: 42,
    lastResult: { outcome: 'PLAYER_LOSS', ticks: 37, playerHp: 0 },
  }
}

describe('저장 왕복', () => {
  it('쓰고 새 탭처럼 다시 읽으면 같은 것이 나온다', () => {
    const storage = createFakeStorage()
    const save = buildSample()
    expect(writeSave(storage, save)).toBe(true)

    // 새로고침. 남는 것은 저장소뿐이고 메모리의 상태는 사라진다.
    const restored = readSave(storage)
    expect(restored).toEqual(save)
  })

  it('규칙표는 규칙 한 줄까지 그대로 돌아온다', () => {
    const storage = createFakeStorage()
    writeSave(storage, buildSample())
    const restored = readSave(storage)
    expect(restored?.ruleset.rules).toEqual(PRESSURE.rules)
    expect(restored?.presets[1]?.ruleset.rules).toEqual(KITE.rules)
  })

  it('저장이 없으면 undefined 다 — 처음 여는 탭이다', () => {
    expect(readSave(createFakeStorage())).toBeUndefined()
  })

  it('지우면 그다음 탭은 처음부터 시작한다', () => {
    const storage = createFakeStorage()
    writeSave(storage, buildSample())
    removeSave(storage)
    expect(readSave(storage)).toBeUndefined()
  })
})

describe('형식 태그', () => {
  it('저장 문자열의 첫 필드가 형식 태그다', () => {
    const parsed = JSON.parse(buildSaveText(buildSample())) as Record<string, unknown>
    expect(parsed.format).toBe(SAVE_FORMAT_TAG)
  })

  it('태그에서 버전을 읽는다', () => {
    expect(getSaveVersion('v1')).toBe(1)
    expect(getSaveVersion('v12')).toBe(12)
    expect(() => getSaveVersion('1')).toThrow(/형식 태그/)
    expect(() => getSaveVersion('vx')).toThrow(/정수/)
  })

  it('이 코어보다 새 저장은 거절한다 — 모르는 필드를 지우고 저장하지 않는다', () => {
    const text = buildSaveText(buildSample()).replace(`"${SAVE_FORMAT_TAG}"`, '"v99"')
    expect(() => parseSaveText(text)).toThrow(/새 저장/)
  })

  it('키 순서가 늘 같다 — 같은 내용이면 같은 문자열이다', () => {
    expect(buildSaveText(buildSample())).toBe(buildSaveText(buildSample()))
    expect(formatCanonicalJson({ b: 1, a: [2, { d: 3, c: 4 }] })).toBe('{"a":[2,{"c":4,"d":3}],"b":1}')
  })

  it('프리셋은 8슬롯까지만 저장한다 (GDD §2.3)', () => {
    const many = Array.from({ length: MAX_PRESET_SLOTS + 3 }, (_unused, at) => ({
      name: `슬롯 ${String(at)}`,
      ruleset: PRESSURE,
    }))
    const storage = createFakeStorage()
    writeSave(storage, { ...buildSample(), presets: many })
    expect(readSave(storage)?.presets).toHaveLength(MAX_PRESET_SLOTS)
  })
})

describe('저장이 막힌 브라우저', () => {
  it('쓸 수 없으면 false 를 내고 편집을 막지 않는다', () => {
    const storage = createFakeStorage()
    storage.failing = true
    expect(writeSave(storage, buildSample())).toBe(false)
  })

  it('저장소가 아예 없어도 읽기·쓰기가 던지지 않는다', () => {
    expect(readSave(undefined)).toBeUndefined()
    expect(writeSave(undefined, buildSample())).toBe(false)
    expect(() => {
      removeSave(undefined)
    }).not.toThrow()
  })

  it('슬롯 하나가 깨져도 편집 중인 규칙표는 살린다', () => {
    const storage = createFakeStorage()
    writeSave(storage, buildSample())
    const damaged = (storage.entries.get(SAVE_STORAGE_KEY) ?? '').replace('"ruleset_id":"g0_kite"', '"ruleset_id":null')
    storage.entries.set(SAVE_STORAGE_KEY, damaged)
    const restored = readSave(storage)
    expect(restored?.ruleset.rules).toEqual(PRESSURE.rules)
    expect(restored?.presets.map((item) => item.name)).toEqual(['근접 압박'])
  })

  it('깨진 값은 저장이 없는 것과 같이 다룬다', () => {
    const storage = createFakeStorage()
    storage.entries.set(SAVE_STORAGE_KEY, '{"format":"v1","ruleset":')
    expect(readSave(storage)).toBeUndefined()
  })
})

describe('디바운스', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  it('연달아 고쳐도 마지막 것 하나만 쓴다', () => {
    const storage = createFakeStorage()
    const written: string[] = []
    const scheduler = createSaveScheduler(
      {
        ...storage,
        setItem: (key: string, value: string) => {
          written.push(value)
          storage.entries.set(key, value)
        },
      },
      100,
    )
    scheduler.schedule({ ...buildSample(), seed: 1 })
    scheduler.schedule({ ...buildSample(), seed: 2 })
    scheduler.schedule({ ...buildSample(), seed: 3 })
    expect(written).toHaveLength(0)

    vi.advanceTimersByTime(100)
    expect(written).toHaveLength(1)
    expect(readSave(storage)?.seed).toBe(3)
    vi.useRealTimers()
  })

  it('취소하면 쓰지 않는다 — 화면을 떠나며 예약을 버린다', () => {
    const storage = createFakeStorage()
    const scheduler = createSaveScheduler(storage, 100)
    scheduler.schedule(buildSample())
    scheduler.cancel()
    vi.advanceTimersByTime(100)
    expect(storage.entries.size).toBe(0)
    vi.useRealTimers()
  })

  it('flush 는 기다리지 않고 지금 쓴다', () => {
    const storage = createFakeStorage()
    const scheduler = createSaveScheduler(storage, 100)
    scheduler.schedule(buildSample())
    scheduler.flush()
    expect(readSave(storage)?.seed).toBe(42)
    vi.useRealTimers()
  })
})

describe('압축·인코딩', () => {
  it('gzip 왕복이 바이트를 그대로 돌려준다', () => {
    const samples = ['', 'a', '{}', '{"a":1}'.repeat(300), '규칙표 '.repeat(200)]
    for (const sample of samples) {
      const bytes = new TextEncoder().encode(sample)
      expect(new TextDecoder().decode(parseGzip(buildGzip(bytes)))).toBe(sample)
    }
  })

  it('gzip 머리에 시각을 넣지 않는다 — 같은 내용이면 같은 바이트다', () => {
    const bytes = new TextEncoder().encode('같은 내용')
    expect([...buildGzip(bytes)]).toEqual([...buildGzip(bytes)])
    expect([...buildGzip(bytes).slice(4, 8)]).toEqual([0, 0, 0, 0])
  })

  it('꼬리가 본문과 어긋나면 거절한다', () => {
    const packed = buildGzip(new TextEncoder().encode('내용'))
    expect(() => parseGzip(buildDamaged(packed, packed.length - 1))).toThrow(/길이/)
    expect(() => parseGzip(buildDamaged(packed, packed.length - 5))).toThrow(/CRC32/)
  })

  it('base64 는 urlsafe 알파벳을 쓰고 왕복한다', () => {
    const bytes = Uint8Array.from(Array.from({ length: 256 }, (_unused, at) => (at * 7) % 256))
    const text = formatBase64Url(bytes)
    expect(text).not.toMatch(/[+/]/)
    expect([...parseBase64Url(text)]).toEqual([...bytes])
  })
})
