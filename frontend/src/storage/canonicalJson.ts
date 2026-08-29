/**
 * 키를 정렬해 좁게 찍는 JSON. 파이썬
 * `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False)` 와 같은 글자를 낸다.
 *
 * 정렬이 필요한 이유는 **같은 규칙표가 늘 같은 문자열**이어야 하기 때문이다. 자바스크립트
 * 객체의 키 순서는 삽입 순서라, 편집 경로가 다르면 같은 내용이 다른 순서로 찍히고 그러면
 * 같은 프리셋이 다른 공유 코드가 된다. 코드가 같은지 보는 것으로 규칙표가 같은지 볼 수
 * 있어야 한다 (`game/schemas/preset_code.py`).
 *
 * 키는 전부 ASCII 다(`ruleset_id`·`cpu_cost` …). 그래서 자바스크립트의 UTF-16 코드 단위
 * 정렬과 파이썬의 코드 포인트 정렬이 같은 답을 낸다. 한글 키를 새로 들이면 이 전제가
 * 깨지므로 그러지 마라.
 */

/** JSON 으로 오갈 수 있는 값. 부동소수는 코어에 들어오지 않으므로 수는 전부 정수다. */
export type JsonValue = string | number | boolean | null | readonly JsonValue[] | JsonObject

/** JSON 객체. */
export interface JsonObject {
  readonly [key: string]: JsonValue
}

/**
 * 값을 정규 JSON 문자열로 찍는다.
 *
 * @param value 찍을 값.
 * @returns 키가 정렬되고 공백이 없는 JSON.
 */
export function formatCanonicalJson(value: JsonValue): string {
  if (Array.isArray(value)) {
    return `[${value.map(formatCanonicalJson).join(',')}]`
  }
  if (typeof value === 'object' && value !== null) {
    const record = value as JsonObject
    const parts = Object.keys(record)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${formatCanonicalJson(record[key] ?? null)}`)
    return `{${parts.join(',')}}`
  }
  return JSON.stringify(value)
}

/**
 * JSON 문자열을 읽는다. 형태 검사는 부르는 쪽이 한다.
 *
 * @param text 읽을 문자열.
 * @returns 읽어 낸 값.
 * @throws JSON 이 아닌 경우.
 */
export function parseJsonText(text: string): unknown {
  return JSON.parse(text) as unknown
}
