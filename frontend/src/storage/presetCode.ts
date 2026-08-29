/**
 * 프리셋 공유 코드 — `v2:` + gzip(JSON) + urlsafe base64.
 * `game/schemas/preset_code.py` 의 이식이며 **양쪽이 서로의 코드를 읽는다**.
 *
 * 형식이 갈리면 공유가 깨지므로 세 겹을 그대로 옮겼다. 각 겹의 이유도 파이썬 주석과 같다.
 *
 * - `v2:` 접두어 — 본문을 풀기 전에 마이그레이션 여부를 판정한다 (TDD §9). 풀어 보고서야
 *   버전을 알면, 형식이 바뀐 코드는 풀이 자체가 예외로 끝나 판정할 기회가 없다.
 * - gzip — 규칙표 JSON 은 키 이름이 반복돼 잘 줄어든다.
 * - urlsafe base64 — 채팅과 URL 에 그대로 붙는다.
 *
 * **압축 바이트까지 파이썬과 같지는 않다.** zlib 의 탐색 방식을 옮기지 않았기 때문이며
 * (deflate.ts), 그래서 같은 프리셋이라도 파이썬이 구운 코드와 브라우저가 구운 코드는
 * 글자가 다를 수 있다. 지켜지는 것은 **한쪽이 구운 것을 다른 쪽이 푼다**는 것과, 한 구현
 * 안에서는 같은 프리셋이 늘 같은 코드가 된다는 것이다.
 */
import { formatBase64Url, parseBase64Url } from './base64'
import { formatCanonicalJson, parseJsonText } from './canonicalJson'
import { buildGzip, parseGzip } from './gzip'
import { buildPresetPayload, parsePresetPayload, type RulePreset } from './presetPayload'

/** TDD §9 가 못박은 접두어. 값 2 는 규칙 DSL 의 세대다. */
export const PRESET_CODE_VERSION = 2
export const PRESET_CODE_SEPARATOR = ':'
export const PRESET_CODE_PREFIX = `v${String(PRESET_CODE_VERSION)}${PRESET_CODE_SEPARATOR}`

/** 접두어의 버전 자리를 읽는 꼴. `v12:` 처럼 두 자리도 받는다. */
const VERSION_PATTERN = /^v(\d+)$/

/**
 * 공유 코드의 버전을 본문을 풀지 않고 읽는다.
 *
 * @param code `v2:...` 형태의 공유 코드.
 * @returns 접두어가 가리키는 버전 정수.
 * @throws 접두어가 `v<정수>:` 형태가 아닌 경우.
 */
export function getCodeVersion(code: string): number {
  const [head, ...rest] = code.trim().split(PRESET_CODE_SEPARATOR)
  const matched = VERSION_PATTERN.exec(head ?? '')
  if (rest.length === 0 || matched === null) {
    throw new Error(`공유 코드는 v<버전>: 로 시작해야 한다: ${code.slice(0, 16)}`)
  }
  return Number(matched[1])
}

/**
 * 프리셋을 공유 코드 문자열로 만든다.
 *
 * @param preset 내보낼 프리셋.
 * @returns `v2:` 로 시작하는 공유 코드.
 */
export function exportPresetCode(preset: RulePreset): string {
  const raw = formatCanonicalJson(buildPresetPayload(preset))
  const packed = buildGzip(new TextEncoder().encode(raw))
  return PRESET_CODE_PREFIX + formatBase64Url(packed)
}

/**
 * 공유 코드를 프리셋으로 되돌린다. `exportPresetCode` 의 역방향이다.
 *
 * 깨진 코드는 층마다 다른 예외를 낸다 — base64·gzip·JSON·스키마가 각각 다른 것을 던진다.
 * 붙여넣다 잘린 코드 하나에 그 넷을 다 아는 호출자를 요구할 수 없으므로 여기서 한 종류로
 * 모은다. 파이썬 쪽도 같은 이유로 `ValueError` 하나로 모은다.
 *
 * @param code `v2:` 로 시작하는 공유 코드. 앞뒤 공백은 무시한다.
 * @returns 복원된 프리셋.
 * @throws 접두어가 없거나, 세대가 다르거나, 본문이 깨진 경우.
 */
export function parsePresetCode(code: string): RulePreset {
  const text = code.trim()
  const version = getCodeVersion(text)
  if (version !== PRESET_CODE_VERSION) {
    throw new Error(
      `이 코어가 읽을 수 없는 프리셋 세대다: v${String(version)} != v${String(PRESET_CODE_VERSION)}`,
    )
  }
  const body = text.slice(text.indexOf(PRESET_CODE_SEPARATOR) + 1)
  try {
    const raw = new TextDecoder().decode(parseGzip(parseBase64Url(body)))
    return parsePresetPayload(parseJsonText(raw))
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error)
    throw new Error(`프리셋 코드를 풀 수 없다: ${reason}`)
  }
}
