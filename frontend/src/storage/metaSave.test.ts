/**
 * 메타 세이브가 파이썬 정본과 같은 형식·같은 결산 규칙인지 본다 (GDD §2.3, TDD §9).
 *
 * 헤드리스 러너가 쓴 `volume/meta_save.json` 을 브라우저가 그대로 읽고 이어서 써야 한다.
 * **형식만 같고 결산 규칙이 다르면 더 나쁘다** — 파일은 열리는데 해금과 도감이 조용히
 * 갈린다.
 *
 * `__golden__/meta_save.json` 은 파이썬이 결산한 결과다. 손으로 고치지 않는다. 재생성은
 * `uv run python -m scripts.export_meta_golden`.
 *
 * 두 코어가 같은 값을 **다른 글자로** 쓴다는 점에 주의한다. 파이썬은 `indent=2`, TS 는
 * 정규 형식(좁게)이라 바이트 대조는 성립하지 않는다. 대조 대상은 언제나 절이다.
 */
import { describe, expect, it } from 'vitest'

import { BLOCK_CATALOG } from '../core/resources'
import { createEmptyMeta, MAX_SLOT_BONUS } from '../core/schemas'
import { applyRunSummary, getRuleSlotCap, getSlotBonus } from '../core/services/manageMeta'
import type { RunSummary } from '../core/services/manageMeta'
import golden from './__golden__/meta_save.json'
import {
  META_FORMAT_TAG,
  buildMetaPayload,
  buildMetaText,
  parseMetaPayload,
  parseMetaText,
} from './metaSave'

interface GoldenSummary {
  readonly floor_reached: number
  readonly is_cleared: boolean
  readonly seen_perceptions: readonly string[]
  readonly seen_actions: readonly string[]
  readonly encountered_kinds: readonly string[]
  readonly defeated_kinds: readonly string[]
}

/**
 * 골든의 스네이크 표기 결산 입력을 TS 형태로 옮긴다.
 *
 * @param raw 골든의 summary 절.
 * @returns 결산 입력.
 */
function readSummary(raw: GoldenSummary): RunSummary {
  return {
    floorReached: raw.floor_reached,
    isCleared: raw.is_cleared,
    seenPerceptions: raw.seen_perceptions,
    seenActions: raw.seen_actions,
    encounteredKinds: raw.encountered_kinds,
    defeatedKinds: raw.defeated_kinds,
  }
}

describe('메타 세이브 — 파이썬 정본 대조', () => {
  const cases = golden.cases as readonly {
    label: string
    before: Record<string, unknown>
    summary: GoldenSummary
    after: Record<string, unknown>
  }[]

  it('케이스가 비어 있지 않다', () => {
    // 파일을 못 읽어도 아래 each 가 조용히 0회 도는 것을 막는다.
    expect(cases.length).toBeGreaterThan(0)
  })

  it.each(cases.map((item) => [item.label, item] as const))(
    '%s',
    (_label, item) => {
      const before = parseMetaPayload(item.before)
      const after = applyRunSummary(before, readSummary(item.summary), BLOCK_CATALOG)
      expect(buildMetaPayload(after)).toEqual(item.after)
    },
  )

  it.each(cases.map((item) => [item.label, item] as const))(
    '%s — 읽고 다시 쓰면 같은 절이다',
    (_label, item) => {
      expect(buildMetaPayload(parseMetaPayload(item.after))).toEqual(item.after)
    },
  )
})

describe('메타 세이브 — 형식', () => {
  it('빈 세이브를 굽고 되읽으면 같다', () => {
    const empty = createEmptyMeta()
    expect(parseMetaText(buildMetaText(empty))).toEqual(empty)
  })

  it('형식 태그가 없으면 거부한다', () => {
    expect(() => parseMetaPayload({ best_floor: 1 })).toThrow('형식 태그')
  })

  it('이 코어보다 새 세대는 거부한다', () => {
    // 모르는 필드를 무시하고 저장하면 그 필드가 다음 저장에서 사라진다.
    expect(() => parseMetaPayload({ format: 'v99' })).toThrow('새 세이브')
  })

  it('객체가 아니면 거부한다', () => {
    expect(() => parseMetaPayload([1, 2])).toThrow('객체가 아니다')
  })

  it('굽는 절의 태그는 언제나 현재 값이다', () => {
    const payload = buildMetaPayload({ ...createEmptyMeta(), formatVersion: 1 })
    expect(payload.format).toBe(META_FORMAT_TAG)
  })

  it('해금 목록은 읽을 때 정렬된다', () => {
    // 정렬하지 않으면 같은 세이브가 실행마다 다른 파일이 된다 (R5).
    const meta = parseMetaPayload({
      format: META_FORMAT_TAG,
      unlocked_actions: ['RETREAT', 'ATTACK', 'HOLD'],
    })
    expect(meta.unlockedActions).toEqual(['ATTACK', 'HOLD', 'RETREAT'])
  })
})

describe('메타 세이브 — 슬롯 보너스', () => {
  it.each([
    [0, 0],
    [1, 0],
    [2, 1],
    [3, 2],
    [5, 4],
  ])('층 %i 는 보너스 %i', (floor, bonus) => {
    expect(getSlotBonus(floor)).toBe(bonus)
  })

  it('상한에서 멈춘다', () => {
    expect(getSlotBonus(100)).toBe(MAX_SLOT_BONUS)
  })

  it('슬롯 상한은 기본값에 보너스를 더한 값이다', () => {
    const meta = { ...createEmptyMeta(), bestFloor: 3 }
    expect(getRuleSlotCap(meta, 5)).toBe(7)
  })
})
