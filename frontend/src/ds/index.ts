/**
 * 디자인 시스템 배럴. UI 담당들은 여기서만 가져간다.
 *
 * **`ds.css` 가 여기에 걸려 있다. 그래서 부품은 배럴에서만 가져간다** —
 * `import { Button } from '../ds'` 는 되지만 `from '../ds/Button'` 은 스타일이 딸려오지
 * 않아 토큰 없는 맨 마크업이 나온다. 스타일을 컴포넌트마다 import 해 두면 깊은 경로도
 * 살지만, 그러면 배럴이 공개 경계라는 사실이 흐려지고 계약에 없는 파일을 직접 찌르는
 * 코드가 늘어난다. 경계를 하나로 두는 쪽을 골랐다.
 *
 * 토큰(`@design/styles.css`)은 앱의 컴포지션 루트(main.tsx·galleryMain.tsx)가 먼저 싣는다.
 * 이 파일은 토큰을 **쓰기만** 하고 정의하지 않는다.
 *
 * 계약은 design/README.md 의 컴포넌트 표다. 선언되지 않은 표현 prop 을 늘리지 마라 —
 * 늘리는 순간 화면마다 다른 규칙이 생기고 디자인 시스템이 아니라 컴포넌트 더미가 된다.
 */
import './ds.css'

export { Button } from './Button'
export type { ButtonProps, ButtonSize, ButtonVariant } from './Button'

export { GlyphState, STATE_GLYPHS, STATE_NAMES } from './GlyphState'
export type { GlyphStateKind, GlyphStateProps } from './GlyphState'

export { HpGauge, LOW_HP_PERCENT, calculatePercent } from './HpGauge'
export type { HpGaugeProps } from './HpGauge'

export { LogPanel } from './LogPanel'
export type { LogPanelProps } from './LogPanel'

export { LogRow, formatDelta } from './LogRow'
export type { LogRowProps } from './LogRow'

export { Panel } from './Panel'
export type { PanelProps, PanelTone } from './Panel'

export { ACTOR_GLYPHS, ACTOR_NAMES, PlanActor } from './PlanActor'
export type { PlanActorKind, PlanActorProps } from './PlanActor'

export { PLAN_CELL_TOKEN, PlanGrid, buildCellStyle } from './PlanGrid'
export type { PlanGridProps } from './PlanGrid'

export { PIP_LIMIT, ResourceCount } from './ResourceCount'
export type { ResourceCountProps } from './ResourceCount'

export { RuleRow, checkCpuOver, formatCpu, resolveGlyphKind } from './RuleRow'
export type { CpuReadout, RuleCpu, RuleRowProps, RuleRowState } from './RuleRow'

export { RuleTable } from './RuleTable'
export type { RuleTableProps } from './RuleTable'

export { SEGMENT_LIMIT, SegmentedGauge, buildSegments } from './SegmentedGauge'
export type { GaugeTone, SegmentFill, SegmentedGaugeProps } from './SegmentedGauge'

export { SPEED_LABELS, SPEED_STEPS, SpeedControl } from './SpeedControl'
export type { SpeedControlProps } from './SpeedControl'

export { StatusBar } from './StatusBar'
export type { StatusBarProps } from './StatusBar'

export { ThreatNotice } from './ThreatNotice'
export type { ThreatNoticeProps } from './ThreatNotice'

export { TopBar } from './TopBar'
export type { TopBarProps } from './TopBar'

export { CellGrid } from './CellGrid'
export type { Cell, CellGridProps } from './CellGrid'
export { Thumb, THUMB_CODES } from './Thumb'
export type { ThumbProps, ThumbState } from './Thumb'
export { ValueExpr, splitExprSegments } from './ValueExpr'
export type { ExprSegment, ValueExprProps } from './ValueExpr'

export {
  DEFAULT_LAYOUT_MODE,
  LAYOUT_MODES,
  LAYOUT_MODE_TOKEN,
  readLayoutMode,
  useViewportMode,
  watchViewport,
} from './viewport'
export type { LayoutMode, TokenRead } from './viewport'
