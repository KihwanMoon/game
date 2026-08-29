/**
 * 전투 화면 배럴 (W13).
 *
 * `battle.css` 가 여기에 걸려 있다. ds 배럴과 같은 규약이며 이유도 같다 — 배럴이 공개
 * 경계이고, 깊은 경로로 찌르면 스타일 없는 마크업이 나온다.
 *
 * 밖으로 내는 것은 화면 하나(`BattleView`)와 그 화면을 특정하는 값(`BattleSetup`),
 * 그리고 도면 렌더러다. 렌더러를 따로 내는 이유는 사후 분석 리플레이(Phase 2 W8)가 같은
 * 도면을 다른 시간축으로 그리게 되기 때문이다 — 그때 화면째 복사하지 않으려면 렌더러가
 * 화면과 분리돼 있어야 한다.
 */
import './battle.css'

export { BattleView } from './BattleView'
export type { BattleViewProps } from './BattleView'

// 확인용 페이지도 배럴을 거친다. 컴포지션 루트가 깊은 경로로 찌르면 `battle.css` 가
// 딸려오지 않아 토큰 없는 맨 마크업이 나온다 (ds 배럴과 같은 규약).
export { BattleCheck } from './BattleCheck'

export { PlanCanvas, describeScene } from './PlanCanvas'
export type { PlanCanvasProps } from './PlanCanvas'

export {
  addExtraEnemies,
  buildBattleSession,
  checkOngoing,
  findRoomTemplate,
} from './battleSession'
export type { BattleSession, BattleSetup, ExtraEnemy } from './battleSession'

export {
  BATCH_INTERVAL_TICK_UNITS,
  SPEED_LABEL_BY_STEP,
  getStepTicksByStep,
  parseDurationMs,
  readBatchIntervalMs,
  useBattleClock,
} from './battleClock'
export type { BattleClockOptions } from './battleClock'

export {
  FALLBACK_ACTOR_KIND,
  KIND_BY_ENEMY_TYPE,
  SHORT_LABEL_BY_KIND_ID,
  resolveActorKind,
  resolveActorLabel,
} from './actorKind'

export { buildPlanScene } from './planScene'
export type { PlanActorView, PlanHazardView, PlanScene } from './planScene'

export { TILE_DRAWERS, getCellRect, renderPlan, resizePlanCanvas } from './planRenderer'
export type { CellRect, TileDrawer } from './planRenderer'

export {
  PLAN_COLOR_TOKENS,
  PLAN_FONT_TOKEN,
  PLAN_LENGTH_TOKENS,
  createTokenReader,
  readPlanTheme,
} from './planTheme'
export type { PlanTheme, TokenReader } from './planTheme'

export { LeaderLine, RING_RATIO, SHOULDER_MODULES, buildLeaderPath } from './leaderLine'
export type { LeaderPath, LeaderPoint } from './leaderLine'

export {
  NO_TARGET_NOTE,
  TracingRuleVm,
  buildRuleTrace,
  formatActionText,
  formatPendingCondition,
} from './ruleTrace'
export type { RuleTrace, RuleTraceRow } from './ruleTrace'
