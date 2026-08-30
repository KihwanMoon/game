/**
 * 튜토리얼 스테이지 (로드맵 W20, 결정 #17).
 *
 * **파이썬 `game/schemas/tutorial.py` 와 같은 파일을 읽는다** — 사본을 두지 않는다.
 * 사본이 갈라지면 검사가 통과한 스테이지와 화면이 보여 주는 스테이지가 달라지고, 그러면
 * 「시작으로는 지고 해답으로는 이긴다」는 계약이 화면에서만 조용히 깨진다.
 */
import type { RawRule } from './ruleset'

/** 단계를 통과했다고 볼 조건. */
export interface StageGoal {
  readonly outcome: string
  /** 규칙표가 써도 되는 최대 CPU. 없으면 기본 예산만 본다. */
  readonly maxCpu?: number
  /** 통과에 요구하는 최소 잔여 HP. 무피해를 요구할 때 쓴다. */
  readonly minPlayerHp?: number
}

/** 단계 하나. */
export interface TutorialStage {
  readonly stageId: string
  readonly titleKo: string
  readonly teachesKo: string
  readonly briefKo: string
  readonly hintKo: string
  readonly roomId: string
  readonly seed: number
  readonly startRules: readonly RawRule[]
  readonly solutionRules: readonly RawRule[]
  readonly goal: StageGoal
}

/** 파이썬이 쓰는 절 그대로. */
export interface RawTutorialStage {
  readonly stage_id: string
  readonly title_ko: string
  readonly teaches_ko: string
  readonly brief_ko: string
  readonly hint_ko: string
  readonly room_id: string
  readonly seed: number
  readonly start_rules: readonly RawRule[]
  readonly solution_rules: readonly RawRule[]
  readonly goal: { outcome: string; max_cpu?: number | null; min_player_hp?: number | null }
}

/**
 * 스테이지 절을 읽는다.
 *
 * @param raw 스테이지 절.
 * @returns 만들어진 단계.
 */
export function parseTutorialStage(raw: RawTutorialStage): TutorialStage {
  return {
    stageId: raw.stage_id,
    titleKo: raw.title_ko,
    teachesKo: raw.teaches_ko,
    briefKo: raw.brief_ko,
    hintKo: raw.hint_ko,
    roomId: raw.room_id,
    seed: raw.seed,
    startRules: raw.start_rules,
    solutionRules: raw.solution_rules,
    goal: {
      outcome: raw.goal.outcome,
      ...(raw.goal.max_cpu == null ? {} : { maxCpu: raw.goal.max_cpu }),
      ...(raw.goal.min_player_hp == null ? {} : { minPlayerHp: raw.goal.min_player_hp }),
    },
  }
}

/**
 * 이 결과가 단계를 통과했는가.
 *
 * @param goal 통과 조건.
 * @param outcome 판정.
 * @param playerHp 남은 체력.
 * @returns 통과했으면 true.
 */
export function checkStageCleared(goal: StageGoal, outcome: string, playerHp: number): boolean {
  if (outcome !== goal.outcome) {
    return false
  }
  return goal.minPlayerHp === undefined || playerHp >= goal.minPlayerHp
}
