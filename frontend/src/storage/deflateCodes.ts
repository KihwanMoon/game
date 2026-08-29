/**
 * DEFLATE(RFC 1951)의 고정 표들. 굽는 쪽과 푸는 쪽이 같은 표를 봐야 한다.
 *
 * 표를 한 파일에 모은 이유는 사본이 갈라지는 것을 막기 위해서다. 길이 코드 하나가
 * 어긋나면 우리가 구운 코드를 파이썬 `gzip` 이 풀지 못하고, 그때 드러나는 증상은
 * "프리셋 공유가 가끔 깨진다" 라서 원인까지 도달하기 어렵다.
 */

/** 허프만 코드 길이의 상한 (RFC 1951 §3.2.7). */
export const MAX_CODE_BITS = 15

/** 블록 종결 심볼. 리터럴 256 번이다. */
export const END_OF_BLOCK = 256

/** 최소·최대 일치 길이. */
export const MIN_MATCH = 3
export const MAX_MATCH = 258

/** 되돌아볼 수 있는 최대 거리 — 32KB 창. */
export const MAX_DISTANCE = 32768

/** 길이 코드(257..285)의 기준 길이. */
export const LENGTH_BASE: readonly number[] = [
  3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131,
  163, 195, 227, 258,
]

/** 길이 코드마다 뒤따르는 추가 비트 수. */
export const LENGTH_EXTRA: readonly number[] = [
  0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0,
]

/** 거리 코드(0..29)의 기준 거리. */
export const DISTANCE_BASE: readonly number[] = [
  1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537, 2049,
  3073, 4097, 6145, 8193, 12289, 16385, 24577,
]

/** 거리 코드마다 뒤따르는 추가 비트 수. */
export const DISTANCE_EXTRA: readonly number[] = [
  0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13,
]

/** 동적 블록의 코드 길이 알파벳이 실려 오는 순서 (RFC 1951 §3.2.7). */
export const CODE_LENGTH_ORDER: readonly number[] = [
  16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15,
]

/**
 * 일치 길이를 담을 길이 코드의 자리를 찾는다.
 *
 * @param length 3..258 사이의 일치 길이.
 * @returns LENGTH_BASE 안의 자리.
 */
export function findLengthSlot(length: number): number {
  let slot = LENGTH_BASE.length - 1
  while (slot > 0 && (LENGTH_BASE[slot] ?? 0) > length) {
    slot -= 1
  }
  return slot
}

/**
 * 일치 거리를 담을 거리 코드의 자리를 찾는다.
 *
 * @param distance 1..32768 사이의 거리.
 * @returns DISTANCE_BASE 안의 자리.
 */
export function findDistanceSlot(distance: number): number {
  let slot = DISTANCE_BASE.length - 1
  while (slot > 0 && (DISTANCE_BASE[slot] ?? 0) > distance) {
    slot -= 1
  }
  return slot
}
