/**
 * 주문서 셋이 하는 일 — `game/app/simulation/scrolls.py` 의 이식 (2026-09-11 결정).
 *
 * **주문서는 종류가 곧 태그다.** 칸은 하나(주문서 칸)이고 거기 무엇을 끼웠느냐가
 * `USE_ITEM[태그]` 를 정한다 — 순간이동을 끼우면 `USE_ITEM[BLINK]` 가 돌고
 * `USE_ITEM[SCROLL]` 은 「불가」가 된다. 그래서 「무엇을 들고 갈까」가 선택이 된다.
 *
 * **유지시간을 데이터가 아니라 여기 상수로 박는다** (실제 요청: 「유지시간이 명확해야
 * 규칙에 넣을 수 있다」). 규칙표를 짜는 사람이 몇 틱인지 알고 써야 하는 값이고, 그 값이
 * 아이템 등급마다 다르면 같은 규칙이 무엇을 끼웠느냐에 따라 다르게 돈다 — 등급이 바꾸는
 * 것은 **충전 수와 끼고 있는 동안의 접사**뿐이다.
 *
 * **저절로 터진다** (2026-09-11 개정). 주문서 한 줄은 규칙 슬롯 1 과 cpu 2 를 먹는데
 * 실측이 +3%p 였다 — 5칸이 꽉 찬 규칙표에서는 내줄 줄이 없어 「못 쓰는 것」이 맞았다.
 * 그래서 아이템마다 고정 트리거를 주고, 조건이 맞으면 규칙 줄 없이 발동·소비된다.
 * 확률이 아니라 **조건**이다 — 전투 판정에 난수를 들이지 않는다.
 *
 * **파이썬이 정본이다.** 여기 상수 하나가 어긋나면 브라우저에서 돈 판이 서버 재시뮬에서
 * 다르게 끝난다 (G3).
 */

import { divideFloor } from '../combat/damage'
import { getManhattanDistance } from '../grid/geometry'
import { WALKABLE_TILES } from '../schemas'
import { MELEE_REACH } from './plan'
import { PERCENT_BASE, type Entity, type WorldState } from './state'

/** 주문서 태그. 칸 계열은 전부 SCROLL 이다 (`storage` 의 SLOT_FAMILY). */
export const ITEM_BLINK = 'BLINK'
export const ITEM_FLAME = 'FLAME'
export const ITEM_FOCUS = 'FOCUS'

/**
 * 부릅이 거는 상태와 그 유지 틱. **규칙표가 읽는 값이라 한 자리에 박는다** —
 * `self_has_status[FOCUS]` 로 물어 겹쳐 쓰기를 피할 수 있다.
 */
export const STATUS_FOCUS = 'FOCUS'
export const FOCUS_TICKS = 4

/**
 * 부릅이 올리는 사거리. **한 칸이다.** `적거리 <= 사거리` 가 그 몇 틱만 참이 되는 것이
 * 이 주문서가 파는 것이고(P2), 두 칸을 주면 그 몇 틱이 다른 게임이 된다.
 */
export const FOCUS_RANGE_BONUS = 1

/** 순간이동이 물러나는 칸 수. 이동이 한 칸씩인 세계라 이것이 포위를 푸는 유일한 수단이다. */
export const BLINK_STEPS = 3

/**
 * 화염이 태우는 반경과 계수. **예고가 없다** — 마법은 전부 예고를 쓰므로(설계/5_스킬 §10)
 * 「예고 없는 광역」은 소모품만 할 수 있는 일이고, 대가는 충전 수다.
 */
export const FLAME_RADIUS = 1
export const FLAME_COEF_PCT = 120

/**
 * 적에게서 멀어지는 빈 칸을 찾는다.
 *
 * **가장 먼 칸이 아니라 가장 먼저 찾은 칸이다.** 후보를 정렬해 고르면 같은 판이 실행마다
 * 다른 칸을 고를 수 있고(R5), 무엇보다 「어디로 밀려나는가」가 규칙표가 답할 질문이
 * 아니다 — 답해야 하는 것은 「언제 쓸 것인가」다.
 *
 * @param state 세계 상태.
 * @param entity 쓰는 개체.
 * @returns 설 칸. 갈 곳이 없으면 null.
 */
export function findBlinkSpot(state: WorldState, entity: Entity): { x: number; y: number } | null {
  const hostiles = state.listHostiles(entity)
  if (hostiles.length === 0) {
    return null
  }
  const taken = new Set(
    state
      .listActors()
      .filter((other) => other !== entity)
      .map((other) => `${String(other.position.x)},${String(other.position.y)}`),
  )
  const here = entity.position
  const gaps = (spot: { x: number; y: number }) =>
    Math.min(...hostiles.map((one) => getManhattanDistance(spot, one.position)))
  let best: { x: number; y: number } | null = null
  let bestGap = gaps(here)
  // 행 우선으로 훑는다. 순회 순서가 결과에 새어 나가면 안 된다 (R5).
  for (let y = 0; y < state.room.height; y += 1) {
    for (let x = 0; x < state.room.width; x += 1) {
      if (!WALKABLE_TILES.has(state.getTile(x, y)) || taken.has(`${String(x)},${String(y)}`)) {
        continue
      }
      const spot = { x, y }
      if (getManhattanDistance(here, spot) > BLINK_STEPS) {
        continue
      }
      const gap = gaps(spot)
      if (gap > bestGap) {
        bestGap = gap
        best = spot
      }
    }
  }
  return best
}

/**
 * 지금 이 개체가 닿는 거리.
 *
 * **한 자리에 모은 이유가 있다.** 사거리를 읽는 곳이 넷이다 — 규칙표의 `사거리` 값,
 * 폴백 정책, 시야 판정, 그리고 실제 타격. 부릅을 한 곳에만 반영하면 **규칙은 참인데
 * 공격이 안 닿거나**, 반대로 닿는데 규칙이 거짓이 된다 — 둘 다 「왜 안 때리지」로만 보인다.
 *
 * @param entity 볼 개체.
 * @returns 기본 사거리에 걸린 버프를 더한 값.
 */
export function readReach(entity: Entity): number {
  const bonus = (entity.statuses.get(STATUS_FOCUS) ?? 0) > 0 ? FOCUS_RANGE_BONUS : 0
  return entity.attackRange + bonus
}

/**
 * 포위로 치는 인접 적 수. 둘이면 이미 협공 보정이 붙는 자리다.
 */
export const SURROUNDED_COUNT = 2

/** 보호가 자세를 잡는 체력 문턱. 규칙표의 흔한 문턱(25~30%)과 같은 자리다. */
export const GUARD_HP_PCT = 30

/**
 * 태그에서 그것이 거는 상태로. **겹쳐 쓰기를 막는 자리다** (2026-09-11 실제 요청) —
 * 이미 걸려 있는데 또 쓰면 충전만 탄다. 즉발(순간이동·화염)은 여기 없다: 남는 상태가
 * 없으므로 겹칠 것도 없다.
 */
export const LASTING_STATUS: ReadonlyMap<string, string> = new Map([
  ['SCROLL', 'GUARD'],
  [ITEM_FOCUS, STATUS_FOCUS],
])

/**
 * 그 주문서가 거는 상태가 이미 걸려 있는가.
 *
 * @param entity 쓰려는 개체.
 * @param useTag 소모품 태그.
 * @returns 이미 걸려 있으면 true — 그때는 「불가」로 잡아 다음 규칙에 기회를 준다.
 */
export function checkAlreadyHeld(entity: Entity, useTag: string): boolean {
  const status = LASTING_STATUS.get(useTag)
  return status !== undefined && (entity.statuses.get(status) ?? 0) > 0
}

/**
 * 붙어 있는 적의 수.
 *
 * @param state 세계 상태.
 * @param entity 볼 개체.
 * @returns 인접(맨해튼 1) 적의 수.
 */
export function countAdjacentHostiles(state: WorldState, entity: Entity): number {
  return state
    .listHostiles(entity)
    .filter((other) => getManhattanDistance(entity.position, other.position) <= MELEE_REACH).length
}

/** 조건 발동 한 건의 판정 — 참·거짓과 **실측값을 병기한 문장** (GDD §8.2). */
export type TriggerCheck = (state: WorldState, entity: Entity) => readonly [boolean, string]

/** 보호 — 체력이 문턱 아래로 내려가 있고 적이 붙어 있는가. */
export const checkGuardTrigger: TriggerCheck = (state, entity) => {
  const hpPct = divideFloor(entity.hp * PERCENT_BASE, Math.max(1, entity.hpMax))
  const near = countAdjacentHostiles(state, entity)
  const fired = hpPct < GUARD_HP_PCT && near > 0
  return [fired, `내 HP%(${String(hpPct)}) < ${String(GUARD_HP_PCT)} AND 인접 적(${String(near)}) > 0`]
}

/** 순간이동 — 포위됐는가. 인접 적 수는 **규칙표가 못 묻는 값이다.** */
export const checkBlinkTrigger: TriggerCheck = (state, entity) => {
  const near = countAdjacentHostiles(state, entity)
  return [near >= SURROUNDED_COUNT, `인접 적(${String(near)}) >= ${String(SURROUNDED_COUNT)}`]
}

/** 화염 — 포위됐는가. 순간이동과 같은 조건이고 답이 반대다. */
export const checkFlameTrigger: TriggerCheck = (state, entity) => {
  const near = countAdjacentHostiles(state, entity)
  return [near >= SURROUNDED_COUNT, `인접 적(${String(near)}) >= ${String(SURROUNDED_COUNT)}`]
}

/** 부릅 — 적이 있는데 한 칸 차이로 안 닿는가. 닿으면 안 터진다. */
export const checkFocusTrigger: TriggerCheck = (state, entity) => {
  const hostiles = state.listHostiles(entity)
  if (hostiles.length === 0) {
    return [false, '적 없음']
  }
  const reach = readReach(entity)
  const near = Math.min(
    ...hostiles.map((one) => getManhattanDistance(entity.position, one.position)),
  )
  const fired = near === reach + FOCUS_RANGE_BONUS
  return [
    fired,
    `적거리(${String(near)}) == 사거리(${String(reach)}) + ${String(FOCUS_RANGE_BONUS)}`,
  ]
}

/**
 * 태그에서 그것이 저절로 터지는 조건으로. 파이썬 `TRIGGERS` 와 **같은 순서**다 (G3).
 *
 * 여기 없는 태그는 규칙표로만 쓴다 — 물약이 그렇다: 언제 마실지는 이 게임이 파는 판단
 * 그 자체라 기본값을 두지 않는다.
 */
export const TRIGGERS: ReadonlyMap<string, TriggerCheck> = new Map([
  ['SCROLL', checkGuardTrigger],
  [ITEM_BLINK, checkBlinkTrigger],
  [ITEM_FLAME, checkFlameTrigger],
  [ITEM_FOCUS, checkFocusTrigger],
])

/**
 * 이번 틱에 저절로 터질 주문서들.
 *
 * **규칙표가 직접 다루는 태그는 뺀다.** 내가 적은 줄이 기본보다 세다 — 안 그러면 자동이
 * 먼저 태워서 「내 규칙이 영영 안 뜬다」가 된다.
 *
 * @param state 세계 상태.
 * @param entity 들고 있는 개체.
 * @param managed 규칙표가 직접 쓰는 태그들.
 * @returns [태그, 실측값을 병기한 문장] 들. 터질 것이 없으면 빈 배열.
 */
export function listAutoScrolls(
  state: WorldState,
  entity: Entity,
  managed: readonly string[],
): readonly (readonly [string, string])[] {
  const fired: (readonly [string, string])[] = []
  for (const [useTag, check] of TRIGGERS) {
    if (managed.includes(useTag) || (entity.consumables.get(useTag) ?? 0) <= 0) {
      continue
    }
    if (checkAlreadyHeld(entity, useTag)) {
      continue
    }
    const [ok, expr] = check(state, entity)
    if (ok) {
      fired.push([useTag, expr])
    }
  }
  return fired
}
