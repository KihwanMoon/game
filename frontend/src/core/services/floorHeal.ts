/**
 * 층을 깬 직후의 HP — `game/app/progression/floors.py` 의 이식.
 *
 * **이 회복이 브라우저에만 없었다** (2026-09-11). 파이썬 연쇄는 층을 넘을 때 최대체력의
 * 30% 를 돌려주는데 TS `ChainCursor` 는 인계 HP 를 그대로 썼다 — 같은 티켓이 브라우저
 * 에서는 더 아픈 판으로 돌았다는 뜻이고, 하강이 깊어질수록 벌어진다 (G3).
 *
 * **골든이 이 자리를 안 덮는다.** 골든 연쇄는 `rooms_per_floor` 가 0 이라 층 경계가 한
 * 번도 안 생긴다 — 층을 넘는 판은 골든에 없다.
 *
 * 회복이 있는 이유는 실측이다: 없을 때 18개 규칙표 중 **아무도 2층을 못 넘었다.**
 */

/** 백분율 기준. 정수 내림 나눗셈이라야 두 코어가 마지막 자리에서 안 갈린다 (R5). */
const PERCENT_BASE = 100

/**
 * 층을 깰 때 돌려주는 퍼센트를 읽는다.
 *
 * @param raw balance.json 의 floor_scale 절.
 * @returns 퍼센트. 안 적혀 있으면 0 — **모르면 안 준다.**
 */
export function readFloorHealPct(raw: { readonly floor_heal_pct?: number } | undefined): number {
  return Math.max(0, Math.trunc(Number(raw?.floor_heal_pct ?? 0)))
}

/**
 * 다음 층을 여는 HP.
 *
 * @param hp 층을 끝냈을 때의 HP.
 * @param hpMax 최대체력.
 * @param healPct 돌려줄 퍼센트.
 * @returns 다음 층을 여는 HP. 최대체력을 안 넘는다.
 */
export function resolveFloorHeal(hp: number, hpMax: number, healPct: number): number {
  return Math.min(hpMax, hp + Math.floor((hpMax * healPct) / PERCENT_BASE))
}
