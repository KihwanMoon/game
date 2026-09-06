/**
 * 방 배치에 없는 개체를 방에 더한다 (설계/6_몬스터).
 *
 * **`game/app/services/room_extras.py` 의 이식이다.** 두 코어가 같은 시드에서 같은 판을
 * 내야 하므로(G3), 자리를 고르는 규칙이 글자 그대로 같아야 한다.
 *
 * **덮어쓰기로는 모든 방에 못 선다.** 스냅샷은 방 배치의 자리(`{종류}_{순번}`)를 덮어쓰는
 * 방식이라, 그 자리가 없는 방에는 설 자리 자체가 없다 — 실측으로 그림자가 층당 다섯 방
 * 중 두세 방에만 섰다.
 *
 * **무작위를 안 쓴다.** 자리를 굴려 뽑으면 흔들기 축의 호출 횟수가 바뀌어 같은 시드가
 * 다른 판을 낸다 (R5). 규칙은 「플레이어에게서 가장 먼 빈 칸, 같으면 위·왼쪽」 하나다.
 */
import { WALKABLE_TILES, getRoomTile } from '../schemas/room'
import type { RoomTemplate } from '../schemas/room'

/** 격자 위의 칸. */
export interface Spot {
  readonly x: number
  readonly y: number
}

/**
 * 멀수록 앞에 오는 정렬 키.
 *
 * **체비셰프 거리**를 쓴다 — 이 격자의 이동이 여덟 방향으로 열릴 수 있고, 그때 「몇
 * 걸음인가」가 곧 이 값이다. 같으면 위·왼쪽이 이긴다.
 *
 * @param spot 볼 칸.
 * @param origin 기준 칸. 플레이어가 선 자리다.
 * @returns 정렬 키 셋. 작을수록 앞이다.
 */
export function computeFarRank(spot: Spot, origin: Spot): readonly [number, number, number] {
  const far = Math.max(Math.abs(spot.x - origin.x), Math.abs(spot.y - origin.y))
  return [-far, spot.y, spot.x]
}

/**
 * 플레이어에게서 가장 먼 빈 칸.
 *
 * **가장 먼 칸이어야 한다.** 아무 빈 칸이나 주면 더해진 개체가 플레이어 코앞에 서고,
 * 그러면 규칙표가 손쓸 새 없이 첫 틱에 맞는다 — 더하는 것이 곧 처형이 된다.
 *
 * @param template 방 템플릿.
 * @param taken 이미 누가 선 칸들. `"x,y"` 꼴이다.
 * @param origin 기준 칸.
 * @returns 설 칸. 빈 칸이 없으면 undefined.
 */
export function findFarSpot(
  template: RoomTemplate,
  taken: ReadonlySet<string>,
  origin: Spot,
): Spot | undefined {
  let best: Spot | undefined
  let bestRank: readonly [number, number, number] | undefined
  for (let y = 0; y < template.height; y += 1) {
    for (let x = 0; x < template.width; x += 1) {
      if (taken.has(`${String(x)},${String(y)}`)) {
        continue
      }
      if (!WALKABLE_TILES.has(getRoomTile(template, x, y))) {
        continue
      }
      const rank = computeFarRank({ x, y }, origin)
      if (bestRank === undefined || isBefore(rank, bestRank)) {
        best = { x, y }
        bestRank = rank
      }
    }
  }
  return best
}

/**
 * 정렬 키 둘을 견준다.
 *
 * @param left 앞에 올 후보.
 * @param right 지금 가장 앞.
 * @returns left 가 앞이면 true.
 */
function isBefore(
  left: readonly [number, number, number],
  right: readonly [number, number, number],
): boolean {
  for (let index = 0; index < left.length; index += 1) {
    if (left[index] !== right[index]) {
      return (left[index] ?? 0) < (right[index] ?? 0)
    }
  }
  return false
}

/**
 * 방 배치가 안 쓴 스냅샷 자리들 — 이것이 더할 것이다.
 *
 * **정렬해서 낸다.** 순회 순서로 자리를 정하면 같은 티켓이 두 번 다른 판을 낸다 (R5).
 *
 * @param overrides 이 층의 스냅샷들. 자리 이름에서 스냅샷으로.
 * @param consumed 방 배치가 이미 쓴 자리 이름들.
 * @returns 더할 자리 이름들. 정렬돼 있다.
 */
export function listExtraSlots(
  overrides: ReadonlyMap<string, unknown>,
  consumed: ReadonlySet<string>,
): readonly string[] {
  return [...overrides.keys()].filter((slot) => !consumed.has(slot)).sort()
}
