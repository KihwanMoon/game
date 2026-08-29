/**
 * HUD 배럴 — 관전·진단 계층의 공개 경계.
 *
 * **`hud.css` 가 여기에 걸려 있다.** `ds/index.ts`·`battle/index.ts` 와 같은 규약이며
 * 이유도 같다 — 깊은 경로로 찌르면 스타일이 딸려오지 않아 토큰 없는 맨 마크업이 나온다.
 *
 * 여기 있는 것과 `src/battle` 에 있는 것의 경계는 **시간**이다. battle 은 지금 도는 판을
 * 앞으로 밀고, hud 는 끝난 판을 앞뒤로 걷는다. 판 조립·도면 렌더러·규칙표 서식은 battle
 * 것을 그대로 쓴다 — 여기서 다시 만들지 마라.
 */
import './hud.css'

export {
  DEFAULT_RULE_LABEL,
  PRE_MOVE_PHASES,
  SUSPICIOUS_WASTE_PCT,
  WASTE_MARKERS,
  buildDamageHeatmap,
  buildRuleStats,
  checkWasted,
  extractDamageHits,
  findHeatmapPeak,
  findHeatmapPeakCell,
  getWastePercent,
} from './analysis'
export type { DamageHit, HeatPeak, PositionTable, RuleStat } from './analysis'

export {
  HEAT_EMPTY_GLYPH,
  HEAT_LEVELS,
  describeRuleStat,
  formatHeatValue,
  formatOutcome,
  formatOutcomeNotice,
  formatTickLabel,
  getHeatLevel,
} from './analysisText'

export { readPositions, recordBattle, recordFrame } from './battleRecorder'
export type { BattleRecording, RecordedFrame } from './battleRecorder'

export {
  DEATH_REPLAY_TICKS,
  DEFAULT_WINDOW_ROWS,
  filterRecentEntries,
  findTickIndex,
  groupLogRows,
  selectLogWindow,
} from './logWindow'
export type { LogGroup, LogRun, LogWindow, WindowRequest } from './logWindow'

export { buildReplayTrace, findDecision } from './replayTrace'
export type { ReplayTraceRow } from './replayTrace'

export { DamageHeatmap } from './DamageHeatmap'
export type { DamageHeatmapProps } from './DamageHeatmap'

export { HudScreen } from './HudScreen'
export type { HudScreenProps } from './HudScreen'

export { HudCheck } from './HudCheck'

export { LogStream } from './LogStream'
export type { LogStreamProps } from './LogStream'

export { PostMortem, getReplayStartTick } from './PostMortem'
export type { PostMortemProps } from './PostMortem'

export { RuleStatsTable } from './RuleStatsTable'
export type { RuleStatsTableProps } from './RuleStatsTable'

export { TickScrubber } from './TickScrubber'
export type { TickScrubberProps } from './TickScrubber'

export { DEMO_CASES } from './demoCases'
export type { DemoCase } from './demoCases'

export { usePlanTheme } from './usePlanTheme'
export type { PlanThemeState } from './usePlanTheme'
