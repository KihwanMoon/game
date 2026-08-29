/**
 * urlsafe base64 — 바이트 배열과 문자열 사이를 오간다.
 *
 * 파이썬 `game/schemas/preset_code.py` 가 `base64.urlsafe_b64encode` 를 쓰므로 여기도
 * 같은 알파벳(`-` `_`)을 쓴다. 표준 base64 의 `+` `/` 는 채팅과 URL 에서 깨진다.
 *
 * `btoa`·`atob` 를 부르지 않는 이유는 그것이 latin1 문자열만 받기 때문이다. 바이트를
 * 문자열로 한 번 접었다 펴는 과정이 끼면 UTF-8 규칙표 이름에서 조용히 값이 바뀌고,
 * 노드와 브라우저의 구현 차이까지 함께 들어온다. 바이트 배열을 직접 다룬다.
 */

/** urlsafe 알파벳. 인덱스가 곧 6비트 값이다. */
const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'

/** base64 는 4글자가 3바이트다. 붙여넣다 패딩이 잘려 오는 일이 잦아 복원에 쓴다. */
export const BASE64_BLOCK = 4

/** 한 덩어리에 담기는 바이트 수. */
const BYTE_GROUP = 3

/** 한 글자가 담는 비트 수. */
const CHAR_BITS = 6

const BYTE_BITS = 8
const SIX_BIT_MASK = 0x3f
const BYTE_MASK = 0xff
const PAD = '='

/** 알파벳의 역방향 대응표. 표준 base64 의 `+` `/` 도 함께 받아 준다. */
const VALUE_BY_CHAR: ReadonlyMap<string, number> = new Map([
  ...[...ALPHABET].map((char, index): [string, number] => [char, index]),
  ['+', ALPHABET.indexOf('-')],
  ['/', ALPHABET.indexOf('_')],
])

/**
 * 바이트 배열을 urlsafe base64 문자열로 만든다. 패딩(`=`)을 붙인다.
 *
 * @param bytes 인코딩할 바이트.
 * @returns base64 문자열.
 */
export function formatBase64Url(bytes: Uint8Array): string {
  let text = ''
  for (let at = 0; at < bytes.length; at += BYTE_GROUP) {
    const first = bytes[at] ?? 0
    const second = bytes[at + 1] ?? 0
    const third = bytes[at + 2] ?? 0
    const packed = (first << (BYTE_BITS * 2)) | (second << BYTE_BITS) | third
    const remaining = bytes.length - at
    const chars = [
      ALPHABET[(packed >> (CHAR_BITS * 3)) & SIX_BIT_MASK] ?? PAD,
      ALPHABET[(packed >> (CHAR_BITS * 2)) & SIX_BIT_MASK] ?? PAD,
      remaining > 1 ? (ALPHABET[(packed >> CHAR_BITS) & SIX_BIT_MASK] ?? PAD) : PAD,
      remaining > 2 ? (ALPHABET[packed & SIX_BIT_MASK] ?? PAD) : PAD,
    ]
    text += chars.join('')
  }
  return text
}

/**
 * urlsafe base64 문자열을 바이트 배열로 되돌린다.
 *
 * 잘린 패딩은 복원하고, 공백과 줄바꿈은 버린다 — 코드를 채팅에서 긁어 오면 둘 다 섞인다.
 *
 * @param text base64 문자열.
 * @returns 디코딩된 바이트.
 * @throws 알파벳에 없는 글자가 있는 경우.
 */
export function parseBase64Url(text: string): Uint8Array {
  const body = text.replace(/\s+/g, '').replace(/=+$/, '')
  const bytes: number[] = []
  let buffer = 0
  let bits = 0
  for (const char of body) {
    const value = VALUE_BY_CHAR.get(char)
    if (value === undefined) {
      throw new Error(`base64 에 없는 글자다: ${char}`)
    }
    buffer = (buffer << CHAR_BITS) | value
    bits += CHAR_BITS
    if (bits >= BYTE_BITS) {
      bits -= BYTE_BITS
      bytes.push((buffer >> bits) & BYTE_MASK)
    }
  }
  return Uint8Array.from(bytes)
}
