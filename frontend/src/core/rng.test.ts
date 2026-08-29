/**
 * 결정론 난수원의 골든 테스트 (TDD §10, 게이트 G3).
 *
 * "난수가 그럴듯한가"가 아니라 "파이썬 코어와 같은 수열인가"를 본다. 기준값은
 * `scripts/export_rng_golden.py` 가 파이썬 코어에서 뽑아 둔 것이며, 여기서 값을 고쳐
 * 통과시키는 것은 검증을 지우는 것과 같다 — 기준을 바꾸려면 파이썬 쪽을 먼저 본다.
 */
import { describe, expect, it } from 'vitest'

import golden from './golden/rng_golden.json'
import { DeterministicRng, MASK_64, getLabelHash } from './rng'

// SplitMix64 참조 구현(Steele et al., 2014)의 공개 기준값. 0xE220A8397B1DCDAF.
const SEED_0_FIRST = 16294208416658607535n

function collectUint64(rng: DeterministicRng, count: number): string[] {
  return Array.from({ length: count }, () => rng.getUint64().toString())
}

describe('getUint64', () => {
  it('seed 0 의 첫 출력이 공개 기준값과 같다', () => {
    expect(new DeterministicRng(0).getUint64()).toBe(SEED_0_FIRST)
  })

  it.each(golden.uint64)('시드 $seed 의 수열이 파이썬과 같다', ({ seed, values }) => {
    const rng = new DeterministicRng(BigInt(seed))
    expect(collectUint64(rng, values.length)).toEqual(values)
  })

  it('출력이 64비트 범위를 벗어나지 않는다', () => {
    const rng = new DeterministicRng(31337)
    for (let i = 0; i < 200; i += 1) {
      const value = rng.getUint64()
      expect(value >= 0n && value <= MASK_64).toBe(true)
    }
  })

  it('같은 시드는 같은 수열을 낸다', () => {
    const first = new DeterministicRng(777)
    const second = new DeterministicRng(777)
    expect(collectUint64(first, 50)).toEqual(collectUint64(second, 50))
  })

  it('다른 시드는 갈라진다', () => {
    expect(new DeterministicRng(1).getUint64()).not.toBe(new DeterministicRng(2).getUint64())
  })
})

describe('seed', () => {
  it.each(golden.seed_mask)('시드 $input 이 파이썬과 같게 접힌다', ({ input, seed }) => {
    expect(new DeterministicRng(BigInt(input)).seed).toBe(BigInt(seed))
  })

  it('number 로 넘긴 안전 정수도 같은 시드가 된다', () => {
    expect(new DeterministicRng(12345).seed).toBe(new DeterministicRng(12345n).seed)
  })

  it('안전 정수가 아닌 number 시드는 거부한다', () => {
    expect(() => new DeterministicRng(2 ** 63)).toThrow(/안전 정수/)
  })
})

describe('reset', () => {
  it('상태를 시드 직후로 되돌린다', () => {
    const rng = new DeterministicRng(555)
    const before = collectUint64(rng, 5)
    rng.reset()
    expect(collectUint64(rng, 5)).toEqual(before)
  })
})

describe('getLabelHash', () => {
  it.each(golden.label_hash)('라벨 "$label" 의 해시가 파이썬과 같다', ({ label, value }) => {
    expect(getLabelHash(label)).toBe(BigInt(value))
  })
})

describe('getBelow', () => {
  it.each(golden.below)('시드 $seed / 상한 $bound 의 표집이 파이썬과 같다', (sample) => {
    const rng = new DeterministicRng(BigInt(sample.seed))
    const drawn = sample.values.map(() => rng.getBelow(sample.bound))
    expect(drawn).toEqual(sample.values)
  })

  it.each([0, -1, -100])('상한 %i 은 거부한다', (bound) => {
    expect(() => new DeterministicRng(0).getBelow(bound)).toThrow(/1 이상/)
  })

  it('정수가 아닌 상한은 거부한다', () => {
    expect(() => new DeterministicRng(0).getBelow(2.5)).toThrow(/안전 정수/)
  })

  it('마스크 후 버리는 방식이 특정 값을 영영 내지 못하지 않는다', () => {
    const rng = new DeterministicRng(9)
    const seen = new Set<number>()
    for (let i = 0; i < 400; i += 1) {
      seen.add(rng.getBelow(6))
    }
    expect([...seen].sort((a, b) => a - b)).toEqual([0, 1, 2, 3, 4, 5])
  })
})

describe('getRange', () => {
  it.each(golden.range)('시드 $seed 의 [$low, $high] 표집이 파이썬과 같다', (sample) => {
    const rng = new DeterministicRng(BigInt(sample.seed))
    const drawn = sample.values.map(() => rng.getRange(sample.low, sample.high))
    expect(drawn).toEqual(sample.values)
  })

  it('양끝을 모두 포함한다', () => {
    const rng = new DeterministicRng(2024)
    const seen = new Set<number>()
    for (let i = 0; i < 400; i += 1) {
      seen.add(rng.getRange(1, 6))
    }
    expect([...seen].sort((a, b) => a - b)).toEqual([1, 2, 3, 4, 5, 6])
  })

  it('뒤집힌 구간은 거부한다', () => {
    expect(() => new DeterministicRng(0).getRange(10, 3)).toThrow(/high 가 low 보다 작다/)
  })
})

describe('getChoice', () => {
  it.each(golden.choice)('시드 $seed 의 선택이 파이썬과 같다', (sample) => {
    const rng = new DeterministicRng(BigInt(sample.seed))
    const drawn = sample.values.map(() => rng.getChoice(sample.items))
    expect(drawn).toEqual(sample.values)
  })

  it('빈 시퀀스는 거부한다', () => {
    expect(() => new DeterministicRng(0).getChoice([])).toThrow(/빈 시퀀스/)
  })
})

describe('createStream', () => {
  it.each(golden.stream)('시드 $seed / 라벨 "$label" 스트림이 파이썬과 같다', (sample) => {
    const stream = new DeterministicRng(BigInt(sample.seed)).createStream(sample.label)
    expect(stream.seed).toBe(BigInt(sample.stream_seed))
    expect(collectUint64(stream, sample.values.length)).toEqual(sample.values)
  })

  it('부모 난수원을 진행시키지 않는다', () => {
    const parent = new DeterministicRng(42)
    parent.createStream('floor:2/node:5/loot')
    expect(parent.getUint64()).toBe(new DeterministicRng(42).getUint64())
  })

  it('라벨이 다르면 갈라진다', () => {
    const loot = new DeterministicRng(42).createStream('floor:2/node:5/loot')
    const rooms = new DeterministicRng(42).createStream('floor:2/node:5/rooms')
    expect(loot.getUint64()).not.toBe(rooms.getUint64())
  })
})
