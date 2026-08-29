/**
 * 시드 기반 결정론 난수원 — `game/app/core/rng.py` 의 TypeScript 이식 (TDD §1.1, 게이트 G3).
 *
 * 파이썬 코어가 정본이며 이 파일은 그것과 **비트 단위로 같은 수열**을 내야 한다.
 * 그래서 64비트 연산을 전부 BigInt 로 한다. Number 는 가수부가 53비트라 SplitMix64 의
 * 곱셈이 조용히 어긋난다 — 값이 비슷해 보여도 수열이 갈라지고, 저장된 리플레이가
 * 재현되지 않는다(R5).
 *
 * `Math.random` 과 `Date.now` 는 이 모듈은 물론 코어 어디에서도 쓰지 않는다.
 * 확률이 필요하면 정수 비교로 쓴다 — 30% 는 `rng.getBelow(100) < 30`.
 */

/** 64비트 마스크. 파이썬의 `MASK_64` 와 같다. */
export const MASK_64 = (1n << 64n) - 1n

// SplitMix64 상수 (Steele et al., 2014). 바꾸면 수열이 달라진다.
const GOLDEN_GAMMA = 0x9e3779b97f4a7c15n
const MIX_MULTIPLIER_A = 0xbf58476d1ce4e5b9n
const MIX_MULTIPLIER_B = 0x94d049bb133111ebn

// FNV-1a 64비트 상수. 자바스크립트에는 안정된 문자열 해시가 없으므로 명세가 고정된
// 것을 직접 구현한다.
const FNV_OFFSET_BASIS = 0xcbf29ce484222325n
const FNV_PRIME = 0x100000001b3n

const LABEL_ENCODER = new TextEncoder()

/**
 * 문자열 라벨을 64비트 정수로 접는다. 파이썬 `get_label_hash` 와 같은 값을 낸다.
 *
 * @param label 서브 시드를 파생시킬 라벨. 예: `"floor:2"`, `"node:5"`.
 * @returns 0 이상 2^64 미만의 정수.
 */
export function getLabelHash(label: string): bigint {
  let digest = FNV_OFFSET_BASIS
  for (const byte of LABEL_ENCODER.encode(label)) {
    digest = ((digest ^ BigInt(byte)) * FNV_PRIME) & MASK_64
  }
  return digest
}

/** SplitMix64 난수원. 같은 시드는 반드시 같은 수열을 낸다. */
export class DeterministicRng {
  private readonly _seed: bigint

  private _state: bigint

  /**
   * 난수원을 시드로 초기화한다.
   *
   * @param seed 시작 시드. 64비트로 잘라서 보관하므로 음수·초과값도 받는다.
   *   `number` 로 넘길 때는 안전 정수여야 한다 — 그 밖은 BigInt 로 넘긴다.
   */
  constructor(seed: bigint | number) {
    this._seed = toUint64(seed)
    this._state = this._seed
  }

  /** 이 난수원을 만든 시드. 리플레이 저장에 쓴다. */
  get seed(): bigint {
    return this._seed
  }

  /** 상태를 시드 직후로 되돌린다. 같은 수열이 처음부터 다시 나온다. */
  reset(): void {
    this._state = this._seed
  }

  /**
   * 다음 64비트 난수를 뽑는다.
   *
   * @returns 0 이상 2^64 미만의 정수.
   */
  getUint64(): bigint {
    this._state = (this._state + GOLDEN_GAMMA) & MASK_64
    let mixed = this._state
    mixed = ((mixed ^ (mixed >> 30n)) * MIX_MULTIPLIER_A) & MASK_64
    mixed = ((mixed ^ (mixed >> 27n)) * MIX_MULTIPLIER_B) & MASK_64
    return mixed ^ (mixed >> 31n)
  }

  /**
   * 0 이상 bound 미만의 정수를 균등하게 뽑는다.
   *
   * 나머지 연산(`% bound`)을 쓰지 않는다. bound 가 2의 거듭제곱이 아닐 때 작은 값 쪽으로
   * 치우치며, 밸런싱을 데이터로 하는 이 프로젝트에서 그 편향은 그대로 수치 왜곡이 된다.
   * 파이썬과 마찬가지로 `bound.bit_length()` 폭의 마스크를 씌우고 범위 밖은 버린다 —
   * 마스크 폭이 다르면 버려지는 횟수가 달라져 두 코어의 수열이 갈라진다.
   *
   * @param bound 상한(미포함). 1 이상의 정수여야 한다.
   * @returns 0 이상 bound 미만의 정수.
   * @throws bound 가 1 미만이거나 정수가 아닌 경우.
   */
  getBelow(bound: number): number {
    if (!Number.isSafeInteger(bound)) {
      throw new RangeError(`bound 는 안전 정수여야 한다: ${bound}`)
    }
    if (bound < 1) {
      throw new RangeError(`bound 는 1 이상이어야 한다: ${bound}`)
    }
    const limit = BigInt(bound)
    const mask = (1n << BigInt(getBitLength(limit))) - 1n
    for (;;) {
      const candidate = this.getUint64() & mask
      if (candidate < limit) {
        return Number(candidate)
      }
    }
  }

  /**
   * low 이상 high 이하의 정수를 균등하게 뽑는다.
   *
   * @param low 하한(포함).
   * @param high 상한(포함).
   * @returns low 이상 high 이하의 정수.
   * @throws high 가 low 보다 작은 경우.
   */
  getRange(low: number, high: number): number {
    if (high < low) {
      throw new RangeError(`high 가 low 보다 작다: low=${low}, high=${high}`)
    }
    return low + this.getBelow(high - low + 1)
  }

  /**
   * 시퀀스에서 원소 하나를 균등하게 고른다.
   *
   * `Set` 이나 객체 키 목록을 그대로 넘기지 않는다 — 순회 순서가 보장되지 않아
   * 결정론이 깨진다(R5). 정렬된 배열로 바꿔서 넘긴다.
   *
   * @param items 고를 대상. 비어 있으면 안 된다.
   * @returns 고른 원소.
   * @throws items 가 비어 있는 경우.
   */
  getChoice<ItemT>(items: readonly ItemT[]): ItemT {
    if (items.length === 0) {
      throw new RangeError('빈 시퀀스에서는 고를 수 없다')
    }
    const picked = items[this.getBelow(items.length)]
    if (picked === undefined) {
      // 인덱스는 항상 범위 안이므로 도달하지 않는다. noUncheckedIndexedAccess 대응.
      throw new RangeError('시퀀스에 빈 자리가 있다')
    }
    return picked
  }

  /**
   * 라벨로 갈라진 독립 난수원을 만든다. 이 난수원의 상태는 바뀌지 않는다.
   *
   * 층·방·전리품처럼 서로 다른 축의 무작위성이 한 수열을 공유하면, 한쪽 호출 횟수가
   * 바뀔 때 다른 쪽 결과까지 흔들려 회귀 검증이 불가능해진다 (TDD §7.3).
   *
   * @param label 축을 구분하는 라벨. 예: `"floor:2/node:5/loot"`.
   * @returns 독립적으로 진행하는 새 난수원.
   */
  createStream(label: string): DeterministicRng {
    return new DeterministicRng(this._seed ^ getLabelHash(label))
  }
}

/**
 * 어떤 정수든 64비트 부호 없는 값으로 접는다. 파이썬의 `seed & MASK_64` 와 같다.
 *
 * @param value 접을 값.
 * @returns 0 이상 2^64 미만의 정수.
 * @throws number 로 넘어온 값이 안전 정수가 아닌 경우.
 */
function toUint64(value: bigint | number): bigint {
  if (typeof value === 'number' && !Number.isSafeInteger(value)) {
    throw new RangeError(`시드는 안전 정수이거나 BigInt 여야 한다: ${value}`)
  }
  return BigInt(value) & MASK_64
}

/**
 * 파이썬 `int.bit_length()` 와 같은 값을 낸다.
 *
 * @param value 0 이상의 정수.
 * @returns 값을 표현하는 데 필요한 비트 수. 0 이면 0.
 */
function getBitLength(value: bigint): number {
  return value === 0n ? 0 : value.toString(2).length
}
