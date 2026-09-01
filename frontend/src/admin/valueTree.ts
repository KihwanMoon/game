/**
 * 값 트리 편집 — 절의 **모양은 두고 값만 바꾼다**.
 *
 * 스키마를 화면이 정하지 않는다. 키를 더하거나 지울 수 있게 하면 로더가 못 읽는 절이
 * 만들어지는데, 그 절은 발행 시점에야 거절된다 — 그때는 이미 여러 자산을 고쳐 둔 뒤다.
 * **값만 바꾸면 절의 모양이 절대 안 깨진다.**
 *
 * 그래서 이 편집기가 못 하는 것이 있다: 몬스터를 새로 추가하거나 키를 지우는 일.
 * 그것은 원문(JSON) 편집기가 남아 있는 이유다 — 드물고 위험한 일에는 드물고 위험한
 * 도구를 쓴다.
 */

/** 절 안의 자리. 객체는 키, 배열은 인덱스다. */
export type ValuePath = readonly (string | number)[]

/** 편집기가 다루는 잎의 종류. */
export type LeafKind = 'number' | 'string' | 'boolean' | 'null'

/**
 * 값 하나의 종류를 본다.
 *
 * @param value 볼 값.
 * @returns 잎이면 그 종류, 가지면 undefined.
 */
export function readLeafKind(value: unknown): LeafKind | undefined {
  if (value === null) {
    return 'null'
  }
  if (typeof value === 'number') {
    return 'number'
  }
  if (typeof value === 'string') {
    return 'string'
  }
  if (typeof value === 'boolean') {
    return 'boolean'
  }
  return undefined
}

/**
 * 자리 하나의 값을 바꾼 새 절을 만든다.
 *
 * **원본을 안 건드린다.** 지나가는 길만 새로 만들고 나머지 가지는 원본 객체를 그대로
 * 재사용한다 — 통째로 복사하면 주석 같은 필드가 살아남는지 아무도 확신하지 못한다.
 *
 * @param root 절.
 * @param path 바꿀 자리.
 * @param value 새 값.
 * @returns 새 절. 자리가 없으면 원본 그대로.
 */
export function applyValueAt(root: unknown, path: ValuePath, value: unknown): unknown {
  if (path.length === 0) {
    return value
  }
  const [head, ...rest] = path
  if (Array.isArray(root)) {
    const index = Number(head)
    if (!Number.isInteger(index) || index < 0 || index >= root.length) {
      return root
    }
    const next = applyValueAt(root[index], rest, value)
    // **안 바뀌었으면 원본을 그대로 돌려준다.** 새 객체를 내면 아무것도 안 고친 편집이
    // "고쳤음" 으로 보이고, 저장 버튼이 열린다.
    if (next === root[index]) {
      return root
    }
    return root.map((item, at) => (at === index ? next : item))
  }
  if (typeof root === 'object' && root !== null) {
    const record = root as Record<string, unknown>
    const key = String(head)
    if (!(key in record)) {
      return root
    }
    const next = applyValueAt(record[key], rest, value)
    if (next === record[key]) {
      return root
    }
    return { ...record, [key]: next }
  }
  return root
}

/**
 * 화면이 친 글자를 그 잎의 종류에 맞는 값으로 되돌린다.
 *
 * **숫자 칸이 숫자가 아니면 안 바꾼다.** 반쯤 친 글자가 값을 지우면, 고치는 중에 절이
 * 잠깐 깨진 상태가 되고 그 상태로 저장될 수 있다.
 *
 * @param kind 잎의 종류.
 * @param text 친 글자.
 * @param current 지금 값.
 * @returns 새 값.
 */
export function parseLeafText(kind: LeafKind, text: string, current: unknown): unknown {
  if (kind === 'number') {
    const parsed = Number(text)
    return text.trim() === '' || Number.isNaN(parsed) ? current : parsed
  }
  if (kind === 'boolean') {
    return text === 'true'
  }
  if (kind === 'null') {
    // null 이던 자리는 숫자로 채울 수 있게 둔다 — `range: null` 을 3 으로 바꾸는 것이
    // 실제로 필요한 편집이다. 비우면 다시 null 이다.
    const parsed = Number(text)
    return text.trim() === '' ? null : Number.isNaN(parsed) ? text : parsed
  }
  return text
}

/**
 * 가지 이름을 사람이 읽는 이름으로.
 *
 * `_note`·`_comment` 는 사람이 적어 둔 것이다. 편집기에서 지우면 안 되지만 고칠 일도
 * 거의 없으므로, 이름으로 그 사실을 알린다.
 *
 * @param key 키.
 * @returns 화면에 적을 이름.
 */
export function formatKeyLabel(key: string): string {
  return key.startsWith('_') ? `${key} (설명)` : key
}
