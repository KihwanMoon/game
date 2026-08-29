/**
 * 확인용 페이지가 돌리는 조합들.
 *
 * `scripts/export_analysis_golden.py` 의 `ANALYSIS_CASES` 와 같은 값이다. 화면으로 보는
 * 판과 대조하는 판이 같아야, 눈으로 이상해 보이는 것을 그대로 테스트로 옮길 수 있다.
 * 값을 바꾸려면 파이썬 쪽을 먼저 고치고 기준을 재생성한다.
 *
 * 마지막 두 조합은 템플릿에 없는 적을 덧붙인다. 방 다섯 개의 스폰이 전부 고블린 3종이라
 * 이것이 없으면 예고(TELEGRAPH)·소환·치유가 한 번도 돌지 않아, 예고 배너도 소환물의
 * 로그도 화면에서 확인할 길이 없다.
 */

import type { BattleSetup } from '../battle'

/** 확인용 조합 하나. 화면 표기와 전투 설정을 함께 든다. */
export interface DemoCase {
  readonly caseId: string
  readonly setup: BattleSetup
}

/**
 * 조합 하나를 만든다.
 *
 * @param setup 방·규칙표·시드와 덧붙일 적.
 * @returns 조합. id 는 파이썬 기준 문서의 case_id 와 같은 규칙이다.
 */
function createCase(setup: BattleSetup): DemoCase {
  return {
    caseId: `${setup.roomId}__${setup.rulesetId}__${String(setup.seed)}`,
    setup,
  }
}

/** 파이썬 기준과 같은 여섯 조합. 순서까지 같다. */
export const DEMO_CASES: readonly DemoCase[] = [
  createCase({ roomId: 'open_field', rulesetId: 'g0_pressure', seed: 1 }),
  createCase({ roomId: 'corridor', rulesetId: 'g0_kite', seed: 12345 }),
  createCase({ roomId: 'hazard_field', rulesetId: 'g0_cover', seed: 99 }),
  createCase({ roomId: 'spring_bait', rulesetId: 'g0_pressure', seed: 2024 }),
  createCase({
    roomId: 'open_field',
    rulesetId: 'g0_kite',
    seed: 4242,
    extraEnemies: [
      { kind: 'bomb_slime', x: 5, y: 4 },
      { kind: 'mender_acolyte', x: 6, y: 2 },
    ],
  }),
  createCase({
    roomId: 'pillars',
    rulesetId: 'g0_cover',
    seed: 555,
    extraEnemies: [
      { kind: 'arch_summoner', x: 7, y: 4 },
      { kind: 'veteran_rusher', x: 4, y: 6 },
    ],
  }),
]
