/**
 * 정렬 열쇠 비교 — 파이썬 `sorted(key=...)` · `min(key=...)` · `max(key=...)` 의 대응물.
 *
 * 파이썬 코어는 동점을 튜플 열쇠로 가른다. 예: `(-initiative, entity_id)`. 그 의미를
 * 자바스크립트에서 손으로 다시 쓰면 항이 하나 빠지거나 순서가 뒤집혀도 대개 테스트가
 * 통과하고, 어긋난 결과는 수백 틱 뒤에야 드러난다. 그래서 튜플 비교를 한 곳에 두고
 * 호출자는 열쇠 배열만 만든다.
 *
 * **`min` 과 `max` 는 첫 번째 최적값을 돌려준다.** 파이썬이 그렇게 정의돼 있고, 그것이
 * 동점 처리의 마지막 방어선이다 — 마지막 값을 고르도록 쓰면 같은 시드가 다른 대상을
 * 골라 리플레이가 깨진다 (R5).
 */

/** 정렬 열쇠의 한 항. 파이썬 튜플의 원소 하나에 대응한다. */
export type SortKeyPart = number | string | bigint

/** 정렬 열쇠. 파이썬의 튜플 열쇠에 대응하며 앞쪽 항이 우선한다. */
export type SortKey = readonly SortKeyPart[]

/**
 * 문자열을 파이썬과 같은 순서로 비교한다.
 *
 * 파이썬은 코드 포인트로 비교하고 자바스크립트의 `<` 는 UTF-16 코드 단위로 비교한다.
 * 엔티티 id·스킬 id 는 전부 ASCII 라 두 순서가 같다. 한글이 섞이는 값을 이 함수로
 * 정렬해야 할 일이 생기면 그때는 코드 포인트 비교로 바꿔야 한다.
 *
 * @param left 왼쪽 값.
 * @param right 오른쪽 값.
 * @returns 왼쪽이 작으면 음수, 같으면 0, 크면 양수.
 */
export function compareText(left: string, right: string): number {
  if (left < right) {
    return -1
  }
  return left > right ? 1 : 0
}

/**
 * 열쇠 한 항을 비교한다.
 *
 * @param left 왼쪽 항.
 * @param right 오른쪽 항.
 * @returns 왼쪽이 작으면 음수, 같으면 0, 크면 양수.
 * @throws 두 항의 종류가 다른 경우. 파이썬이라면 TypeError 가 날 자리다.
 */
function comparePart(left: SortKeyPart, right: SortKeyPart): number {
  if (typeof left === 'string' && typeof right === 'string') {
    return compareText(left, right)
  }
  if (typeof left === 'bigint' && typeof right === 'bigint') {
    return left < right ? -1 : Number(left > right)
  }
  if (typeof left === 'number' && typeof right === 'number') {
    return left < right ? -1 : Number(left > right)
  }
  throw new TypeError(`열쇠 항의 종류가 다르다: ${typeof left} vs ${typeof right}`)
}

/**
 * 튜플 열쇠를 앞 항부터 비교한다.
 *
 * @param left 왼쪽 열쇠.
 * @param right 오른쪽 열쇠.
 * @returns 왼쪽이 작으면 음수, 같으면 0, 크면 양수.
 */
export function compareKeys(left: SortKey, right: SortKey): number {
  const shared = Math.min(left.length, right.length)
  for (let index = 0; index < shared; index += 1) {
    const decided = comparePart(left[index] as SortKeyPart, right[index] as SortKeyPart)
    if (decided !== 0) {
      return decided
    }
  }
  return left.length - right.length
}

/**
 * 열쇠 순으로 정렬한 새 배열을 만든다. 원본은 건드리지 않는다.
 *
 * @param items 정렬할 값들.
 * @param getKey 값에서 열쇠를 뽑는 함수.
 * @returns 정렬된 새 배열. 동점은 입력 순서를 지킨다(안정 정렬).
 */
export function sortByKey<ItemT>(
  items: readonly ItemT[],
  getKey: (item: ItemT) => SortKey,
): ItemT[] {
  return [...items].sort((left, right) => compareKeys(getKey(left), getKey(right)))
}

/**
 * 열쇠가 가장 작은 값을 고른다. 파이썬 `min(items, key=...)` 와 같다.
 *
 * @param items 고를 대상.
 * @param getKey 값에서 열쇠를 뽑는 함수.
 * @returns 첫 번째 최소값. 비어 있으면 undefined.
 */
export function findMinBy<ItemT>(
  items: readonly ItemT[],
  getKey: (item: ItemT) => SortKey,
): ItemT | undefined {
  let best: ItemT | undefined
  let bestKey: SortKey | undefined
  for (const item of items) {
    const key = getKey(item)
    if (bestKey === undefined || compareKeys(key, bestKey) < 0) {
      best = item
      bestKey = key
    }
  }
  return best
}

/**
 * 열쇠가 가장 큰 값을 고른다. 파이썬 `max(items, key=...)` 와 같다.
 *
 * @param items 고를 대상.
 * @param getKey 값에서 열쇠를 뽑는 함수.
 * @returns 첫 번째 최대값. 비어 있으면 undefined.
 */
export function findMaxBy<ItemT>(
  items: readonly ItemT[],
  getKey: (item: ItemT) => SortKey,
): ItemT | undefined {
  let best: ItemT | undefined
  let bestKey: SortKey | undefined
  for (const item of items) {
    const key = getKey(item)
    if (bestKey === undefined || compareKeys(key, bestKey) > 0) {
      best = item
      bestKey = key
    }
  }
  return best
}
