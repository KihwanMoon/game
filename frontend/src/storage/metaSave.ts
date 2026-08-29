/**
 * 메타 세이브의 **파일 형식** — 파이썬 정본과 한 글자도 다르면 안 된다.
 *
 * 계약(무엇이 담기는가)은 `core/schemas/metaSave` 에 있고 여기는 그것을 JSON 으로
 * 옮기는 일만 한다. 파이썬은 `game/schemas/meta_save.py` 한 파일에 둘 다 있다 —
 * 그쪽은 표준 라이브러리가 JSON 을 대므로 층을 가를 이유가 없었다.
 *
 * **첫 필드가 형식 태그(`v1`)다.** 태그를 먼저 읽어 처리 방법을 정하므로 본문 구조가
 * 바뀌어도 읽기 시작하는 지점은 그대로다. 이 코어보다 새 태그는 거부한다 — 모르는 필드를
 * 무시하고 그대로 저장하면 그 필드가 다음 저장에서 사라지고, 최신 탭에서 얻은 해금이
 * 옛 탭을 한 번 열었다는 이유로 없어진다.
 *
 * 헤드리스 러너(`game/app/services/manage_meta.py`)가 쓴 `volume/meta_save.json` 을
 * 브라우저가 그대로 읽을 수 있어야 하므로, 키 이름은 스네이크 표기 그대로 둔다.
 */
import {
  META_FORMAT_VERSION,
  type BestiaryRecord,
  type MetaSave,
} from '../core/schemas/metaSave'
import { formatCanonicalJson, parseJsonText, type JsonObject, type JsonValue } from './canonicalJson'
import type { StorageLike } from './saveStore'
import { buildPresetPayload, parsePresetPayload } from './presetPayload'

/** 형식 태그. 값이 아니라 접두어를 먼저 보는 것이 마이그레이션 판정의 방식이다. */
export const META_FORMAT_PREFIX = 'v'
export const META_FORMAT_TAG = `${META_FORMAT_PREFIX}${String(META_FORMAT_VERSION)}`

/** localStorage 열쇠. 편집 세이브(`game.rule-editor`)와 갈라 둔다 — 수명이 다르다. */
export const META_STORAGE_KEY = 'game.meta-save'

/**
 * 형식 태그에서 버전 정수를 읽는다.
 *
 * @param tag `v1` 형태의 태그.
 * @returns 태그가 가리키는 버전 정수.
 * @throws 접두어가 없거나 뒤가 정수가 아닌 경우.
 */
export function getMetaVersion(tag: string): number {
  if (!tag.startsWith(META_FORMAT_PREFIX)) {
    throw new Error(`형식 태그는 ${META_FORMAT_PREFIX} 로 시작해야 한다: ${tag}`)
  }
  const body = tag.slice(META_FORMAT_PREFIX.length)
  if (body.length === 0 || !/^[0-9]+$/.test(body)) {
    throw new Error(`형식 태그의 버전이 정수가 아니다: ${tag}`)
  }
  return Number(body)
}

/**
 * 문자열 배열을 읽어 정렬한다. 배열이 아니면 빈 배열이다.
 *
 * 정렬하는 것은 R5 다. 집합을 그대로 직렬화하면 같은 세이브가 실행마다 다른 파일이 된다.
 *
 * @param raw 원시 값.
 * @returns 정렬된 문자열 배열.
 */
function readSortedStrings(raw: JsonValue | undefined): readonly string[] {
  if (!Array.isArray(raw)) {
    return []
  }
  return [...raw.filter((item): item is string => typeof item === 'string')].sort()
}

/**
 * 배열에서 객체 원소만 골라낸다.
 *
 * @param raw 원시 값.
 * @returns 객체만 남은 배열.
 */
function readObjects(raw: JsonValue | undefined): readonly JsonObject[] {
  if (!Array.isArray(raw)) {
    return []
  }
  return raw.filter(
    (item): item is JsonObject => typeof item === 'object' && item !== null && !Array.isArray(item),
  )
}

/**
 * 도감 한 줄을 읽는다.
 *
 * @param raw kind_id·encounters·defeats 를 가진 절.
 * @returns 만들어진 도감 기록.
 */
export function parseBestiaryPayload(raw: JsonObject): BestiaryRecord {
  return {
    kindId: String(raw.kind_id),
    encounters: typeof raw.encounters === 'number' ? raw.encounters : 0,
    defeats: typeof raw.defeats === 'number' ? raw.defeats : 0,
  }
}

/**
 * 도감 한 줄을 JSON 으로 되돌린다.
 *
 * @param record 되돌릴 도감 기록.
 * @returns parseBestiaryPayload 가 다시 읽을 수 있는 절.
 */
export function buildBestiaryPayload(record: BestiaryRecord): JsonObject {
  return { kind_id: record.kindId, encounters: record.encounters, defeats: record.defeats }
}

/**
 * 메타 세이브 전체를 읽는다.
 *
 * @param raw 세이브 전체 절.
 * @returns 정렬 정규화까지 끝난 메타 세이브.
 * @throws 형식 태그가 없거나 이 코어보다 새 버전인 경우.
 */
export function parseMetaPayload(raw: unknown): MetaSave {
  if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) {
    throw new Error('세이브 절이 객체가 아니다')
  }
  const record = raw as JsonObject
  const tag = record.format
  if (typeof tag !== 'string') {
    throw new Error('세이브에 형식 태그(format)가 없다')
  }
  const version = getMetaVersion(tag)
  if (version > META_FORMAT_VERSION) {
    throw new Error(`이 코어보다 새 세이브다: ${tag} > ${META_FORMAT_TAG}`)
  }
  const records = readObjects(record.bestiary).map(parseBestiaryPayload)
  return {
    formatVersion: version,
    bestFloor: typeof record.best_floor === 'number' ? record.best_floor : 0,
    unlockedPerceptions: readSortedStrings(record.unlocked_perceptions),
    unlockedActions: readSortedStrings(record.unlocked_actions),
    bestiary: [...records].sort((left, right) => (left.kindId < right.kindId ? -1 : 1)),
    presets: readObjects(record.presets).map(parsePresetPayload),
  }
}

/**
 * 메타 세이브 전체를 JSON 절로 되돌린다. 형식 태그는 항상 현재 값이다.
 *
 * @param meta 되돌릴 세이브.
 * @returns parseMetaPayload 가 다시 읽을 수 있는 절.
 */
export function buildMetaPayload(meta: MetaSave): JsonObject {
  return {
    format: META_FORMAT_TAG,
    best_floor: meta.bestFloor,
    unlocked_perceptions: [...meta.unlockedPerceptions],
    unlocked_actions: [...meta.unlockedActions],
    bestiary: meta.bestiary.map(buildBestiaryPayload),
    presets: meta.presets.map(buildPresetPayload),
  }
}

/**
 * 메타 세이브를 문자열로 굽는다.
 *
 * @param meta 저장할 세이브.
 * @returns 정규 형식 JSON 문자열.
 */
export function buildMetaText(meta: MetaSave): string {
  return formatCanonicalJson(buildMetaPayload(meta))
}

/**
 * 문자열에서 메타 세이브를 읽는다.
 *
 * @param text 저장돼 있던 문자열.
 * @returns 읽어들인 세이브.
 * @throws JSON 이 아니거나 형식 태그가 맞지 않는 경우.
 */
export function parseMetaText(text: string): MetaSave {
  return parseMetaPayload(parseJsonText(text))
}

/**
 * 메타 세이브를 읽는다. **읽기 실패는 세이브가 없는 것과 같이 다룬다.**
 *
 * 깨진 값 하나 때문에 화면이 뜨지 않으면 사람은 세이브가 아니라 게임을 잃는다.
 * `readSave` 와 같은 판단이다.
 *
 * @param storage 저장소.
 * @returns 읽어 낸 세이브. 없거나 읽을 수 없으면 undefined.
 */
export function readMeta(storage: StorageLike | undefined): MetaSave | undefined {
  if (storage === undefined) {
    return undefined
  }
  try {
    const text = storage.getItem(META_STORAGE_KEY)
    return text === null ? undefined : parseMetaText(text)
  } catch {
    return undefined
  }
}

/**
 * 메타 세이브를 쓴다. 저장소가 막혀 있으면 조용히 넘어간다.
 *
 * @param storage 저장소.
 * @param meta 저장할 세이브.
 * @returns 실제로 썼으면 true.
 */
export function writeMeta(storage: StorageLike | undefined, meta: MetaSave): boolean {
  if (storage === undefined) {
    return false
  }
  try {
    storage.setItem(META_STORAGE_KEY, buildMetaText(meta))
    return true
  } catch {
    return false
  }
}
