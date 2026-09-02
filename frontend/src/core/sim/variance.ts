/**
 * 판마다 달라지는 것 — 배치 흔들기와 정예 승격 (GDD §11 전략 공간).
 *
 * 파이썬 정본은 `game/app/simulation/variance.py` 이고 이 파일은 그 이식본이다. 두 코어가
 * 같은 순서로 같은 수를 뽑아야 하므로 상수 순서와 순회 순서를 절대 바꾸지 않는다 (G3).
 */
import type { RoomTemplate } from '../schemas'
import { WALKABLE_TILES, getRoomTile } from '../schemas'

import type { DeterministicRng } from '../rng'

/** 배치를 흔들 때 볼 이웃 칸. **순서가 계약이다** — 제자리를 맨 앞에 둔다. */
export const JITTER_OFFSETS: readonly (readonly [number, number])[] = [
  [0, 0],
  [1, 0],
  [-1, 0],
  [0, 1],
  [0, -1],
]

/** 층 1 의 정예 승격 확률(퍼센트)과 층마다 더할 몫. */
export const ELITE_BASE_PCT = 4
export const ELITE_PCT_PER_FLOOR = 3
const PERCENT_BASE = 100
const ELITE_CEILING_PCT = 50

/** 일반 종에서 같은 유형의 정예로. 닫힌 표다 — 파이썬과 같은 짝이어야 한다. */
export const ELITE_BY_KIND: ReadonlyMap<string, string> = new Map([
  ['goblin_rusher', 'veteran_rusher'],
  ['goblin_archer', 'longbow_archer'],
  ['goblin_summoner', 'arch_summoner'],
  ['mender_acolyte', 'plague_mender'],
  ['dire_wolf', 'veteran_rusher'],
])

/**
 * 이 층의 정예 승격 확률.
 *
 * @param floor 현재 층. 1 이 첫 층이다.
 * @returns 퍼센트. 절반을 넘지 않는다.
 */
export function resolveElitePct(floor: number): number {
  return Math.min(ELITE_CEILING_PCT, ELITE_BASE_PCT + ELITE_PCT_PER_FLOOR * Math.max(0, floor - 1))
}

/**
 * 이 적을 정예로 올릴지 정한다. **정수 비교다** (R5).
 *
 * @param kindId 원래 종.
 * @param floor 현재 층.
 * @param rng 변수 축 난수원.
 * @returns 바뀐 종. 짝이 없거나 굴림에서 떨어지면 원래 종 그대로다.
 */
export function resolveEliteKind(kindId: string, floor: number, rng: DeterministicRng): string {
  const elite = ELITE_BY_KIND.get(kindId)
  if (elite === undefined) {
    return kindId
  }
  return rng.getBelow(PERCENT_BASE) < resolveElitePct(floor) ? elite : kindId
}

/**
 * 적이 설 칸을 제 자리 둘레에서 고른다. 한 칸만 흔든다 — 방의 구조는 안 건드린다.
 *
 * @param template 방 템플릿.
 * @param spot 템플릿이 정한 자리.
 * @param taken 이미 누가 선 칸들 (`x,y` 문자열).
 * @param rng 변수 축 난수원.
 * @returns 설 칸. 후보가 없으면 제 자리 그대로다.
 */
export function resolveSpawnSpot(
  template: RoomTemplate,
  spot: { readonly x: number; readonly y: number },
  taken: ReadonlySet<string>,
  rng: DeterministicRng,
): { readonly x: number; readonly y: number } {
  const options = JITTER_OFFSETS.map(([dx, dy]) => ({ x: spot.x + dx, y: spot.y + dy })).filter(
    (spot2) =>
      !taken.has(`${String(spot2.x)},${String(spot2.y)}`) &&
      WALKABLE_TILES.has(getRoomTile(template, spot2.x, spot2.y)),
  )
  if (options.length === 0) {
    return spot
  }
  return options[rng.getBelow(options.length)] ?? spot
}
