/**
 * 저장 층의 공개 지점 (M3).
 *
 * 규칙표를 **브라우저에 남기고**(localStorage) **문자열로 주고받는**(공유 코드) 두 가지가
 * 여기 있다. 둘 다 형식에 버전 접두어가 있고(TDD §9), 파이썬 정본과 같은 형식이다 —
 * 저장은 `game/schemas/meta_save.py`, 공유 코드는 `game/schemas/preset_code.py`.
 *
 * gzip·base64·DEFLATE 구현도 이 층에 있다. 도메인을 모르는 코드지만 `core/` 에 두지
 * 않았다. `core/` 는 파이썬 코어의 이식이고 게이트 G3 이 그 동일성을 검사하는 자리인데,
 * 파이썬 쪽 대응물이 표준 라이브러리라 이식이라 부를 것이 없기 때문이다.
 */
export { formatBase64Url, parseBase64Url, BASE64_BLOCK } from './base64'
export { formatCanonicalJson, parseJsonText } from './canonicalJson'
export type { JsonObject, JsonValue } from './canonicalJson'
export { buildGzip, computeCrc32, parseGzip } from './gzip'
export { deflateRaw } from './deflate'
export { inflateRaw } from './inflate'
export {
  MAX_PRESET_SLOTS,
  buildPresetPayload,
  buildRuleSetPayload,
  parsePresetPayload,
  parseRuleSetPayload,
} from './presetPayload'
export type { RulePreset } from './presetPayload'
export {
  PRESET_CODE_PREFIX,
  PRESET_CODE_VERSION,
  exportPresetCode,
  getCodeVersion,
  parsePresetCode,
} from './presetCode'
export {
  SAVE_FORMAT_TAG,
  SAVE_FORMAT_VERSION,
  SAVE_STORAGE_KEY,
  buildSavePayload,
  buildSaveText,
  getSaveVersion,
  parseSavePayload,
  parseSaveText,
} from './editorSave'
export type { EditorSave, RunResult } from './editorSave'
export {
  SAVE_DELAY_MS,
  createSaveScheduler,
  getLocalStorage,
  readSave,
  removeSave,
  writeSave,
} from './saveStore'
export type { SaveScheduler, StorageLike } from './saveStore'
export {
  META_FORMAT_TAG,
  META_STORAGE_KEY,
  buildMetaPayload,
  buildMetaText,
  getMetaVersion,
  parseMetaPayload,
  parseMetaText,
  readMeta,
  writeMeta,
} from './metaSave'
export {
  API_ROOT,
  TOKEN_HEADER,
  TOKEN_STORAGE_KEY,
  createLogin,
  ensureToken,
  readAccount,
  readServerMeta,
  readToken,
  registerAccount,
  requestTicket,
  submitRun,
  writeServerMeta,
  writeToken,
} from './serverSync'
export type { AccountState, AuthOutcome, RunVerdict, ServerTicket, SyncOutcome } from './serverSync'
