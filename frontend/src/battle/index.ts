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
  resolveRoomFloor,
} from './battleSession'
export type { BattleSession, BattleSetup, ChainPosition, ExtraEnemy } from './battleSession'

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
  DOPPEL_KIND_ID,
  FALLBACK_ACTOR_KIND,
  KIND_BY_ENEMY_TYPE,
  SHORT_LABEL_BY_KIND_ID,
  checkDoppel,
  resolveActorKind,
  resolveActorLabel,
} from './actorKind'

export {
  OUTCOME_GLYPHS,
  OUTCOME_LABELS,
  OUTCOME_NOTICES,
  OUTCOME_TONES,
  formatOutcome,
  formatOutcomeNotice,
  resolveOutcomeTone,
} from './outcomeText'
export type { OutcomeTone } from './outcomeText'

// 세로 모바일(390x844). 화면 하나가 아니라 `BattleView` 가 배치에 따라 고르는 트리다 —
// 밖에서 직접 고르지 않는다. 배럴에 내는 것은 테스트와 확인용 페이지가 부품 하나만
// 세워 볼 수 있어야 하기 때문이다.
export { BattlePortrait } from './BattlePortrait'
export type { BattlePortraitProps } from './BattlePortrait'

// 가로 모바일(844x390). 세로와 같은 이유로 배럴에 낸다.
export { BattleLandscape } from './BattleLandscape'
export type { BattleLandscapeProps } from './BattleLandscape'

// 두 모바일 배치가 함께 쓰는 부품. 시트(탭+본문+하단)와 배속 박스다 — 세로와 가로가
// 다른 것은 치수와 배열뿐이고 그 둘은 토큰과 CSS 가 정하므로, 마크업은 한 벌이면 된다.
export { BattleSheet, RuleSheet, SheetFoot, SheetTabs } from './BattleSheet'
export type {
  BattleSheetProps,
  RuleSheetProps,
  SheetFootProps,
  SheetTabsProps,
} from './BattleSheet'

export { INSTANT_GLYPH, SpeedBox } from './SpeedBox'
export type { SpeedBoxProps } from './SpeedBox'

export {
  RULE_OFF_SUFFIX,
  SHEET_TABS,
  SHEET_TAB_LABELS,
  TICK_PAD_WIDTH,
  buildRunRulesets,
  checkRuleEnabled,
  formatLogTabCount,
  formatRuleCondition,
  formatRulesTabCount,
  formatTick,
  toggleRulePriority,
} from './portraitSheet'
export type { SheetTab } from './portraitSheet'

export { buildRuleRows } from './ruleRows'
export type { RuleRowView, RuleRowsInput } from './ruleRows'

export { buildPlanScene } from './planScene'
export type { PlanActorView, PlanHazardView, PlanScene } from './planScene'

export {
  TILE_DRAWERS,
  getCellRect,
  renderPlan,
  resizePlanCanvas,
  resolveActorColor,
  resolveTierColor,
} from './planRenderer'
export type { CellRect, TileDrawer } from './planRenderer'

export {
  PLAN_COLOR_TOKENS,
  PLAN_FONT_TOKEN,
  PLAN_LENGTH_TOKENS,
  checkPlanThemeSame,
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

export { SettlementPanel } from './SettlementPanel'
export type { SettlementPanelProps } from './SettlementPanel'
export {
  appendSettlement,
  formatSettlementTabCount,
  splitRewardNotes,
  type FloorSettlement,
} from './settlement'
