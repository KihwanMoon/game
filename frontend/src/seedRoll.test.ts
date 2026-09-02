/**
 * 시드 굴리기 검사.
 *
 * 무작위를 검사하는 것은 어렵지만 **틀리는 방식은 몇 가지 안 된다** — 범위를 벗어나거나,
 * 늘 같은 값이 나오거나, 정수가 아니거나. 셋 다 실제로 판을 망가뜨린다.
 */
import { describe, expect, it } from 'vitest'

import { MAX_SEED } from './core/schemas'
import { rollSeed } from './seedRoll'

/** 몇 번 굴려 볼 것인가. */
const ROLLS = 200

describe('rollSeed', () => {
  it('★ 이식 범위 안의 정수를 준다 — 벗어나면 TS 코어가 그 수를 못 담는다', () => {
    for (let index = 0; index < ROLLS; index += 1) {
      const seed = rollSeed()
      expect(Number.isSafeInteger(seed)).toBe(true)
      expect(seed).toBeGreaterThanOrEqual(0)
      expect(seed).toBeLessThanOrEqual(MAX_SEED)
    }
  })

  it('★ 굴릴 때마다 다른 값이 나온다 — 같으면 판마다 같은 던전이 나온다', () => {
    const seen = new Set<number>()
    for (let index = 0; index < ROLLS; index += 1) {
      seen.add(rollSeed())
    }
    // 2^53 에서 200개를 뽑아 겹칠 확률은 사실상 0 이다. 하나라도 겹치면 난수원이 아니다.
    expect(seen.size).toBe(ROLLS)
  })

  it('상위 워드가 자리를 차지한다 — 32비트만 쓰면 판의 종류가 40억으로 줄어든다', () => {
    const big = Array.from({ length: ROLLS }, () => rollSeed()).filter(
      (seed) => seed > 0x100000000,
    )
    expect(big.length).toBeGreaterThan(0)
  })
})
