/**
 * 틱의 페이즈 이름과 승패 판정 이름 — `game/app/simulation/phases.py` 의 이식.
 *
 * 의존성이 없는 어휘만 둔다. 계획 타입(plan.ts)에 함께 두면 로그를 남길 뿐인 모듈까지
 * 인지 스냅샷을 끌어오게 되어 perception → telegraph → plan → perception 의 순환이 난다.
 */

export const PHASE_UPKEEP = 'UPKEEP'
export const PHASE_TELEGRAPH = 'TELEGRAPH'
export const PHASE_PERCEPTION = 'PERCEPTION'
export const PHASE_DECIDE = 'DECIDE'
export const PHASE_ACT = 'ACT'
export const PHASE_RESOLVE = 'RESOLVE'
export const PHASE_CLEANUP = 'CLEANUP'

/** 7페이즈의 고정 순서. 엔진은 이 순서를 벗어나지 않는다 (TDD §4.1). */
export const PHASE_ORDER: readonly string[] = [
  PHASE_UPKEEP,
  PHASE_TELEGRAPH,
  PHASE_PERCEPTION,
  PHASE_DECIDE,
  PHASE_ACT,
  PHASE_RESOLVE,
  PHASE_CLEANUP,
]

export const OUTCOME_ONGOING = 'ONGOING'
export const OUTCOME_PLAYER_WIN = 'PLAYER_WIN'
export const OUTCOME_PLAYER_LOSS = 'PLAYER_LOSS'
export const OUTCOME_TIMEOUT = 'TIMEOUT'
