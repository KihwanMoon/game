/**
 * 규칙 에디터 배럴 (W11~W12).
 *
 * 화면은 `RuleEditor` 하나이고, 나머지는 그 안쪽 조각이다. 텍스트 뷰의 직렬화
 * (`formatRuleText`·`parseRuleText`)만 밖으로 낸다 — 프리셋 공유 코드가 이것을 쓴다.
 */
export { RuleEditor } from './RuleEditor'
export type { RuleEditorProps } from './RuleEditor'
export { COMBAT_TAB_ID, checkWideTab } from './editorTabs'
export type { EditorTab } from './editorTabs'
export { AccountPanel } from './AccountPanel'
export type { AccountPanelProps } from './AccountPanel'
export { BestiaryPanel } from './BestiaryPanel'
export { TemplatePanel } from './TemplatePanel'
export { TemplateRow } from './TemplatePanel'
export type { TemplatePanelProps, TemplateRowProps } from './TemplatePanel'
export { formatRuleSentence, formatTermWord, ALWAYS_TEXT } from './ruleSentence'
export { CatalogAdminPanel } from './CatalogAdminPanel'
export { ContentAdminPanel, formatDraftText } from './ContentAdminPanel'
export type { ContentAdminPanelProps } from './ContentAdminPanel'
export type { CatalogAdminPanelProps } from './CatalogAdminPanel'
export { DiscoveryPanel, buildDiscoveryCells } from './DiscoveryPanel'
export {
  AUTO_ADVANCE_SECONDS,
  AutoAdvanceNotice,
  checkShouldAutoAdvance,
  readAutoAdvance,
  writeAutoAdvance,
} from './AutoAdvance'
export { EvictionNotice, EVICTION_TEXT } from './EvictionNotice'
export { GrowthPanel, formatAttributeEffect, STAT_LABELS } from './GrowthPanel'
export type { GrowthPanelProps } from './GrowthPanel'
export { buildRoomGroups, clipPurpose, PURPOSE_CLIP } from './roomChoices'
export type { RoomChoice, RoomGroup } from './roomChoices'
export { LinkNoticeLine } from './LinkNoticeLine'
export type { LinkNoticeLineProps } from './LinkNoticeLine'
export {
  checkLinked,
  describeGlobalLink,
  describeLink,
  LOADING_TEXT,
  OFFLINE_PREFIX,
  PROBING_TEXT,
} from './linkState'
export type { LinkState } from './linkState'
export type { DiscoveryPanelProps } from './DiscoveryPanel'
export { WorldPanel } from './WorldPanel'
export type { WorldPanelProps } from './WorldPanel'
export type { BestiaryPanelProps } from './BestiaryPanel'
export { ConsumablePanel, findFreeConsumableSlot } from './ConsumablePanel'
export type { ConsumablePanelProps } from './ConsumablePanel'
export {
  buildConsumableSlotCells,
  buildConsumableStockCells,
  formatCharges,
  formatClearLabel,
  formatRefillLabel,
  formatSlotCode,
  formatSlotName,
  USE_TAG_CODES,
  USE_TAG_LABELS,
} from './consumableCells'
export type { ConsumableCell } from './consumableCells'
export { ConsumableDetail } from './ConsumableDetail'
export { ConsumableGrid } from './ConsumableGrid'
export {
  buildChargeRow,
  compareToSlots,
  pickFromOption,
  pickFromSlot,
} from './compareConsumables'
export type { ComparePick, SlotCompare } from './compareConsumables'
export { AuctionPanel, AuctionDetail } from './AuctionPanel'
export type { AuctionPanelProps } from './AuctionPanel'
export { buildListingCells, findBuyBlocker, MINE_MARK } from './auctionCells'
export type { ListingCell } from './auctionCells'
export { CompareRows, CompareBlock } from './CompareRows'
export { renderCell } from './GridCellView'
export type { CellFace } from './gridCell'
export { InventoryPanel } from './InventoryPanel'
export { InventoryGrid } from './InventoryGrid'
export { MaintenanceEditor, MaintenancePalette, MaintenanceCheck } from './MaintenanceEditor'
export type { MaintenanceEditorProps } from './MaintenanceEditor'
export {
  checkBlocked,
  checkMaintenanceRows,
  createRow,
  DISCARD_GRADES,
  duplicateRow,
  findAction,
  formatGradeName,
  formatMaintenanceSentence,
  MAINTENANCE_ACTIONS,
  MAX_MAINTENANCE_ROWS,
  moveRow,
  replaceRow,
} from './maintenanceRules'
export type { MaintenanceAction, MaintenanceProblem } from './maintenanceRules'
export {
  buildMaintenancePreview,
  checkPreviewIdle,
  EMPTY_PREVIEW,
  formatMoneyDelta,
} from './maintenancePreview'
export type { MaintenancePreview, PreviewRow } from './maintenancePreview'
export { SkillPanel } from './SkillPanel'
export type { InventoryPanelProps } from './InventoryPanel'
export { MetaPanel } from './MetaPanel'
export type { MetaPanelProps } from './MetaPanel'
export { RuleLibrary } from './RuleLibrary'
export type { RuleLibraryProps } from './RuleLibrary'
export { writeClipboard } from './clipboard'
export {
  HISTORY_LIMIT,
  applyChange,
  applyRedo,
  applyUndo,
  TEXT_ENTRY_TAGS,
  checkCanRedo,
  checkCanUndo,
  checkTextEntry,
  createHistory,
  resolveHistoryCommand,
} from './history'
export type { EditHistory, HistoryCommand, KeyChord } from './history'
export { formatRuleText, formatRuleLine, formatTermText, parseRuleText, STAT_PREFIX } from './ruleText'
export type { RuleTextParse } from './ruleText'
export {
  addRule,
  addTerm,
  applyActionChoice,
  applyLhsChoice,
  calculateCpuCost,
  calculateTotalCpu,
  createRule,
  createTerm,
  duplicateRule,
  moveRule,
  removeRule,
  removeTerm,
  renumberRules,
  updateRule,
  updateTerm,
} from './draft'
export { RuleEditMobile } from './RuleEditMobile'
export type { EditLayout, RuleEditMobileProps } from './RuleEditMobile'
export { EditCard, EditField, EditNumber, EditSegments } from './EditParts'
export type {
  EditCardProps,
  EditFieldProps,
  EditNumberProps,
  EditOption,
  EditOptionGroup,
  EditSegmentsProps,
} from './EditParts'
export { ActionCard, ConditionCard, CpuCard, PRIORITY_NOTE, PriorityCard } from './RuleEditCards'
export type { ActionCardProps, ConditionCardProps, CpuCardProps, PriorityCardProps } from './RuleEditCards'
export {
  FLAG_FALSE,
  FLAG_NONE,
  FLAG_TRUE,
  buildSetFlag,
  getFlagName,
  getFlagValue,
} from './flagClause'
export {
  MEASURE_SOURCE,
  UNMEASURED,
  buildStatKey,
  buildTermKey,
  formatMeasuredCondition,
  formatMeasuredTerm,
  readLhsMeasure,
  readRhsMeasure,
  resolveMeasureState,
} from './termMeasure'
export type { TermReadings } from './termMeasure'
export { formatActionLabel } from './blockOptions'
export { TutorialPanel } from './TutorialPanel'
export type { TutorialPanelProps } from './TutorialPanel'
export { CharacterPanel } from './CharacterPanel'
export type { CharacterPanelProps } from './CharacterPanel'
export { AdminPanel } from './AdminPanel'
export type { AdminPanelProps } from './AdminPanel'
export { CatalogPanel, formatPeopleBar } from './CatalogPanel'
export type { CatalogPanelProps } from './CatalogPanel'
