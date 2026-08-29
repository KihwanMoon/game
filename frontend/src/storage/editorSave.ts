/**
 * 브라우저에 남기는 에디터 저장 형식 (TDD §9, GDD §2.3).
 *
 * **첫 필드가 형식 태그(`v1`)다.** 태그를 먼저 읽어 처리 방법을 정하므로 본문 구조가
 * 바뀌어도 읽기 시작하는 지점은 그대로다 — `game/schemas/meta_save.py` 와 같은 규약이다.
 * 이 코어보다 새 태그는 거부한다. 모르는 필드를 무시하고 그대로 저장하면 그 필드가 다음
 * 저장에서 사라지고, 최신 탭에서 만든 프리셋이 옛 탭을 한 번 열었다는 이유로 없어진다.
 *
 * 담는 것은 **탭을 닫아도 남아야 하는 것**뿐이다 — 편집 중인 규칙표, 코드 라이브러리 8슬롯,
 * 방·시드, 직전 판 한 줄. 되돌리기 스택은 담지 않는다. 새로 연 탭에서 되돌릴 대상은
 * 이전 세션의 편집이 아니라 이번 세션의 편집이며, 스택까지 실으면 저장 용량이 편집
 * 횟수에 비례해 자란다.
 */
import type { RuleSet } from '../core/schemas'
import { formatCanonicalJson, parseJsonText, type JsonObject } from './canonicalJson'
import {
  MAX_PRESET_SLOTS,
  buildPresetPayload,
  buildRuleSetPayload,
  parsePresetPayload,
  parseRuleSetPayload,
  type RulePreset,
} from './presetPayload'

/** 형식 태그. 값이 아니라 접두어를 먼저 보는 것이 마이그레이션 판정의 방식이다. */
export const SAVE_FORMAT_PREFIX = 'v'
export const SAVE_FORMAT_VERSION = 1
export const SAVE_FORMAT_TAG = `${SAVE_FORMAT_PREFIX}${String(SAVE_FORMAT_VERSION)}`

/** localStorage 열쇠. 이름에 저장소 세대를 넣지 않는다 — 세대는 값 안의 태그가 말한다. */
export const SAVE_STORAGE_KEY = 'game.rule-editor'

/** 직전 판의 결과. 에디터로 돌아왔을 때 무엇을 고쳐야 하는지의 출발점이 된다. */
export interface RunResult {
  readonly outcome: string
  readonly ticks: number
  readonly playerHp: number
}

/** 저장되는 것 전부. */
export interface EditorSave {
  readonly ruleset: RuleSet
  readonly presets: readonly RulePreset[]
  readonly roomId: string
  readonly seed: number
  readonly lastResult: RunResult | undefined
}

/**
 * 형식 태그에서 버전 정수를 읽는다.
 *
 * @param tag `v1` 형태의 태그.
 * @returns 태그가 가리키는 버전 정수.
 * @throws 접두어가 없거나 뒤가 정수가 아닌 경우.
 */
export function getSaveVersion(tag: string): number {
  if (!tag.startsWith(SAVE_FORMAT_PREFIX)) {
    throw new Error(`형식 태그는 ${SAVE_FORMAT_PREFIX} 로 시작해야 한다: ${tag}`)
  }
  const body = tag.slice(SAVE_FORMAT_PREFIX.length)
  if (!/^\d+$/.test(body)) {
    throw new Error(`형식 태그의 버전이 정수가 아니다: ${tag}`)
  }
  return Number(body)
}

/**
 * 저장 내용을 JSON 절로 되돌린다.
 *
 * @param save 저장할 내용.
 * @returns 형식 태그가 붙은 절.
 */
export function buildSavePayload(save: EditorSave): JsonObject {
  const result = save.lastResult
  return {
    format: SAVE_FORMAT_TAG,
    ruleset: buildRuleSetPayload(save.ruleset),
    presets: save.presets.slice(0, MAX_PRESET_SLOTS).map(buildPresetPayload),
    room_id: save.roomId,
    seed: save.seed,
    last_result:
      result === undefined
        ? null
        : { outcome: result.outcome, ticks: result.ticks, player_hp: result.playerHp },
  }
}

/**
 * 저장 내용을 문자열로 굽는다.
 *
 * @param save 저장할 내용.
 * @returns localStorage 에 넣을 문자열.
 */
export function buildSaveText(save: EditorSave): string {
  return formatCanonicalJson(buildSavePayload(save))
}

/**
 * 직전 판 절을 읽는다.
 *
 * @param raw last_result 절. 없으면 null.
 * @returns 읽어 낸 결과. 절이 없으면 undefined.
 */
function parseRunResult(raw: unknown): RunResult | undefined {
  if (typeof raw !== 'object' || raw === null) {
    return undefined
  }
  const record = raw as Record<string, unknown>
  if (
    typeof record.outcome !== 'string' ||
    typeof record.ticks !== 'number' ||
    typeof record.player_hp !== 'number'
  ) {
    return undefined
  }
  return { outcome: record.outcome, ticks: record.ticks, playerHp: record.player_hp }
}

/**
 * 프리셋 목록을 읽는다. **읽히지 않는 슬롯은 버리고 나머지를 살린다.**
 *
 * 슬롯 하나가 깨졌다고 저장 전체를 버리면, 30분 짠 편집 중인 규칙표까지 함께 사라진다.
 * 세대가 갈린 경우는 여기 오기 전에 형식 태그가 잡으므로(parseSavePayload), 여기서
 * 걸리는 것은 손으로 고쳐 깨진 값이다.
 *
 * @param raw presets 배열. 없으면 빈 목록.
 * @returns 읽힌 슬롯만 모은 목록. 최대 8개.
 */
function parsePresets(raw: unknown): readonly RulePreset[] {
  if (!Array.isArray(raw)) {
    return []
  }
  const presets: RulePreset[] = []
  for (const item of raw.slice(0, MAX_PRESET_SLOTS)) {
    try {
      presets.push(parsePresetPayload(item))
    } catch {
      continue
    }
  }
  return presets
}

/**
 * JSON 절에서 저장 내용을 읽는다. 태그를 먼저 보고 판정한다.
 *
 * @param raw 저장 절 전체.
 * @returns 읽어 낸 저장 내용.
 * @throws 형식 태그가 없거나 이 코어보다 새 세대인 경우, 규칙표 절이 깨진 경우.
 */
export function parseSavePayload(raw: unknown): EditorSave {
  if (typeof raw !== 'object' || raw === null) {
    throw new Error('저장 절이 객체가 아니다')
  }
  const record = raw as Record<string, unknown>
  if (typeof record.format !== 'string') {
    throw new Error('저장에 형식 태그(format)가 없다')
  }
  const version = getSaveVersion(record.format)
  if (version > SAVE_FORMAT_VERSION) {
    throw new Error(`이 코어보다 새 저장이다: ${record.format} > ${SAVE_FORMAT_TAG}`)
  }
  return {
    ruleset: parseRuleSetPayload(record.ruleset),
    presets: parsePresets(record.presets),
    roomId: typeof record.room_id === 'string' ? record.room_id : '',
    seed: typeof record.seed === 'number' ? record.seed : 0,
    lastResult: parseRunResult(record.last_result),
  }
}

/**
 * 저장 문자열을 읽는다.
 *
 * @param text localStorage 에서 꺼낸 문자열.
 * @returns 읽어 낸 저장 내용.
 * @throws JSON 이 아니거나 절이 깨진 경우.
 */
export function parseSaveText(text: string): EditorSave {
  return parseSavePayload(parseJsonText(text))
}
