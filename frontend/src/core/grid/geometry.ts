/**
 * 격자 좌표 연산 — `game/app/grid/geometry.py` 의 이식 (Phase 0 F-5 결정).
 *
 * **이동은 4방향, 거리는 맨해튼이다.** 대각 이동을 허용하지 않는 이유는 P2(그리드는
 * 이유가 있어야 한다)에 있다 — 대각선으로 사선을 빠져나갈 수 있으면 통로 유인과 엄폐가
 * 동시에 약해져 방 설계가 전술을 만들지 못한다.
 *
 * GDD §3.2 의 포위도는 주변 8칸을 센다. 이동 4방향과 기준이 다른 것은 의도된 것이다.
 *
 * 좌표를 집합·대응표의 열쇠로 쓸 때는 반드시 `formatPositionKey` 를 거친다. 객체를
 * 그대로 `Set` 에 넣으면 동등성이 참조로 판정되어 같은 칸이 서로 다른 원소가 된다.
 */

import type { GridPosition } from '../schemas'

/** 격자 좌표. 스키마의 `GridPosition` 과 같은 것이며 이름만 파이썬 쪽에 맞췄다. */
export type Position = GridPosition

/**
 * 이동 가능한 방향. 순서를 고정한다 — 같은 비용의 경로가 여럿일 때 이 순서가 결과를
 * 가르므로, 바꾸면 저장된 리플레이가 재현되지 않는다 (R5).
 *
 * **`schemas/room` 의 동명 상수와 순서가 다르다.** 저쪽은 도달성 검사용(북·남·서·동)이고
 * 이쪽은 이동·길찾기용(북·동·남·서)이다. 파이썬도 두 상수를 따로 두고 있으므로 합치지
 * 않는다 — 합치는 순간 한쪽의 경로 선택이 조용히 바뀐다.
 */
export const STEP_OFFSETS: readonly (readonly [number, number])[] = [
  [0, -1],
  [1, 0],
  [0, 1],
  [-1, 0],
]

/** 포위 판정용 8방향. 이동에는 쓰지 않는다. */
export const NEIGHBOR_OFFSETS: readonly (readonly [number, number])[] = [
  [-1, -1],
  [0, -1],
  [1, -1],
  [-1, 0],
  [1, 0],
  [-1, 1],
  [0, 1],
  [1, 1],
]

/**
 * 두 좌표 사이의 맨해튼 거리를 잰다.
 *
 * @param origin 기준 좌표.
 * @param target 대상 좌표.
 * @returns 상하좌우로만 이동할 때의 최소 칸 수.
 */
export function getManhattanDistance(origin: Position, target: Position): number {
  return Math.abs(origin.x - target.x) + Math.abs(origin.y - target.y)
}

/**
 * 이동 가능한 이웃 4칸을 STEP_OFFSETS 순서로 돌려준다.
 *
 * @param origin 기준 좌표.
 * @returns 이웃 좌표 4개. 통행 가능 여부는 보지 않는다.
 */
export function iterSteps(origin: Position): readonly Position[] {
  return STEP_OFFSETS.map(([dx, dy]) => ({ x: origin.x + dx, y: origin.y + dy }))
}

/**
 * 포위 판정용 이웃 8칸을 돌려준다.
 *
 * @param origin 기준 좌표.
 * @returns 이웃 좌표 8개.
 */
export function iterNeighbors(origin: Position): readonly Position[] {
  return NEIGHBOR_OFFSETS.map(([dx, dy]) => ({ x: origin.x + dx, y: origin.y + dy }))
}

/**
 * 좌표를 집합·대응표의 열쇠로 만든다.
 *
 * @param position 바꿀 좌표.
 * @returns `"3,4"` 형태의 문자열.
 */
export function formatPositionKey(position: Position): string {
  return `${position.x},${position.y}`
}

/**
 * 열쇠 문자열을 좌표로 되돌린다. `formatPositionKey` 의 역이다.
 *
 * 거리장과 가시성 맵은 좌표를 열쇠로 눌러 담으므로, 그 안의 칸을 다시 좌표로 꺼내려면
 * 되돌리는 쪽도 한 곳에 있어야 한다. 손으로 `split(',')` 하는 자리가 늘면 형식이 갈린다.
 *
 * @param key `"3,4"` 형태의 열쇠.
 * @returns 되돌린 좌표.
 * @throws 두 정수로 나뉘지 않는 열쇠인 경우.
 */
export function parsePositionKey(key: string): Position {
  const parts = key.split(',')
  const x = Number(parts[0])
  const y = Number(parts[1])
  if (parts.length !== 2 || !Number.isInteger(x) || !Number.isInteger(y)) {
    throw new Error(`좌표 열쇠가 아니다: ${key}`)
  }
  return { x, y }
}

/**
 * 좌표를 로그 문구에 넣을 문자열로 만든다.
 *
 * 파이썬은 튜플을 `(3, 4)` 로 적는다. 골든 대조가 로그 줄을 그대로 비교하므로 쉼표
 * 뒤의 공백 하나까지 같아야 한다.
 *
 * @param position 적을 좌표.
 * @returns `"(3, 4)"` 형태의 문자열.
 */
export function formatPosition(position: Position): string {
  return `(${position.x}, ${position.y})`
}

/**
 * 두 좌표가 같은 칸인가.
 *
 * @param left 왼쪽 좌표.
 * @param right 오른쪽 좌표.
 * @returns 같으면 true.
 */
export function checkSamePosition(left: Position, right: Position): boolean {
  return left.x === right.x && left.y === right.y
}

/**
 * 파이썬 튜플 정렬과 같은 순서로 좌표를 비교한다 — x 를 먼저, 같으면 y 를 본다.
 *
 * @param left 왼쪽 좌표.
 * @param right 오른쪽 좌표.
 * @returns 왼쪽이 작으면 음수, 같으면 0, 크면 양수.
 */
export function comparePositions(left: Position, right: Position): number {
  return left.x === right.x ? left.y - right.y : left.x - right.x
}

/**
 * 좌표들을 중복 없이 파이썬 정렬 순서로 모은다. `sorted(set(...))` 에 대응한다.
 *
 * @param positions 모을 좌표들.
 * @returns 중복을 제거하고 (x, y) 오름차순으로 정렬한 좌표들.
 */
export function sortUniquePositions(positions: readonly Position[]): readonly Position[] {
  const unique = new Map<string, Position>()
  for (const position of positions) {
    unique.set(formatPositionKey(position), position)
  }
  return [...unique.values()].sort(comparePositions)
}
