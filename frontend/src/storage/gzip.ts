/**
 * gzip 컨테이너 (RFC 1952). 파이썬 `gzip.compress` 와 서로 읽고 쓴다.
 *
 * **mtime 을 0 으로 박는다.** 파이썬 쪽(`game/schemas/preset_code.py`)이 같은 이유로 그렇게
 * 했다 — 머리에 시각이 들어가면 같은 규칙표가 1초 뒤에 다른 코드가 되고, 코드를 비교해
 * 규칙표가 같은지 보는 일이 불가능해진다 (R5). 시스템 시간을 읽지 않는다는 코어의 불변
 * 조건과 같은 규율이다.
 *
 * 머리의 XFL·OS 는 압축률과 만든 곳을 적는 자리이고 본문 해석에 쓰이지 않는다. OS 는
 * 255(모름)로 둔다 — 브라우저가 어느 운영체제인지는 프리셋의 내용이 아니다.
 */
import { deflateRaw } from './deflate'
import { inflateRaw } from './inflate'

const BYTE_BITS = 8
const BYTE_MASK = 0xff

/** gzip 머리 10바이트. */
const MAGIC_FIRST = 0x1f
const MAGIC_SECOND = 0x8b
const METHOD_DEFLATE = 8
const HEADER_BYTES = 10
const XFL_MAX_COMPRESSION = 2
const OS_UNKNOWN = 255

/** 시각을 넣지 않는다. 결정론을 위해 고정한다. */
const MTIME_ZERO = 0

/** 꼬리 8바이트 — CRC32 와 원래 길이. */
const FOOTER_BYTES = 8
const CRC_BYTES = 4

/** 머리의 FLG 비트 (RFC 1952 §2.3.1.2). 우리는 세우지 않지만 남이 세운 것은 읽어 넘긴다. */
const FLAG_TEXT = 1
const FLAG_CRC = 2
const FLAG_EXTRA = 4
const FLAG_NAME = 8
const FLAG_COMMENT = 16
const FLAG_CRC_BYTES = 2
const FLAG_EXTRA_LENGTH_BYTES = 2

/** 리틀엔디언 4바이트를 수로 되돌릴 때 쓰는 진법. 최상위 바이트를 `<<` 로 올리면
    부호 비트에 걸려 음수가 되므로 곱셈으로 쌓는다. */
const BYTE_RADIX = 256

/** CRC32 다항식(반전형)과 표. 표는 한 번 만들어 계속 쓴다. */
const CRC_POLYNOMIAL = 0xedb88320
const CRC_SEED = 0xffffffff
const CRC_TABLE_SIZE = 256

const CRC_TABLE: readonly number[] = Array.from({ length: CRC_TABLE_SIZE }, (_unused, index) => {
  let value = index
  for (let step = 0; step < BYTE_BITS; step += 1) {
    value = (value & 1) === 1 ? CRC_POLYNOMIAL ^ (value >>> 1) : value >>> 1
  }
  return value >>> 0
})

/**
 * 바이트열의 CRC32 를 계산한다.
 *
 * @param data 대상 바이트.
 * @returns 부호 없는 32비트 값.
 */
export function computeCrc32(data: Uint8Array): number {
  let crc = CRC_SEED
  for (const byte of data) {
    crc = (CRC_TABLE[(crc ^ byte) & BYTE_MASK] ?? 0) ^ (crc >>> BYTE_BITS)
  }
  return (crc ^ CRC_SEED) >>> 0
}

/**
 * 32비트 값을 리틀엔디언 4바이트로 적는다.
 *
 * @param target 적을 배열.
 * @param at 시작 자리.
 * @param value 적을 값.
 */
function writeUint32(target: Uint8Array, at: number, value: number): void {
  for (let step = 0; step < CRC_BYTES; step += 1) {
    target[at + step] = (value >>> (BYTE_BITS * step)) & BYTE_MASK
  }
}

/**
 * 리틀엔디언 4바이트를 읽는다.
 *
 * @param data 읽을 바이트.
 * @param at 시작 자리.
 * @returns 부호 없는 32비트 값.
 */
function readUint32(data: Uint8Array, at: number): number {
  let value = 0
  for (let step = 0; step < CRC_BYTES; step += 1) {
    value += (data[at + step] ?? 0) * BYTE_RADIX ** step
  }
  return value >>> 0
}

/**
 * 바이트를 gzip 스트림으로 굽는다.
 *
 * @param data 원래 바이트.
 * @returns 머리·본문·꼬리가 붙은 gzip 스트림.
 */
export function buildGzip(data: Uint8Array): Uint8Array {
  const body = deflateRaw(data)
  const out = new Uint8Array(HEADER_BYTES + body.length + FOOTER_BYTES)
  out[0] = MAGIC_FIRST
  out[1] = MAGIC_SECOND
  out[2] = METHOD_DEFLATE
  out[3] = 0
  writeUint32(out, CRC_BYTES, MTIME_ZERO)
  out[HEADER_BYTES - 2] = XFL_MAX_COMPRESSION
  out[HEADER_BYTES - 1] = OS_UNKNOWN
  out.set(body, HEADER_BYTES)
  writeUint32(out, HEADER_BYTES + body.length, computeCrc32(data))
  writeUint32(out, HEADER_BYTES + body.length + CRC_BYTES, data.length >>> 0)
  return out
}

/**
 * 머리의 선택 필드를 건너뛴 자리를 찾는다.
 *
 * @param data gzip 스트림.
 * @param flags 머리의 FLG 바이트.
 * @returns 압축 본문이 시작하는 자리.
 * @throws 선택 필드가 스트림 밖으로 나가는 경우.
 */
function findBodyStart(data: Uint8Array, flags: number): number {
  let at = HEADER_BYTES
  if ((flags & FLAG_EXTRA) !== 0) {
    const low = data[at] ?? 0
    const high = data[at + 1] ?? 0
    at += FLAG_EXTRA_LENGTH_BYTES + (low | (high << BYTE_BITS))
  }
  for (const flag of [FLAG_NAME, FLAG_COMMENT]) {
    if ((flags & flag) === 0) {
      continue
    }
    while ((data[at] ?? 0) !== 0) {
      at += 1
    }
    at += 1
  }
  if ((flags & FLAG_CRC) !== 0) {
    at += FLAG_CRC_BYTES
  }
  if (at >= data.length) {
    throw new Error('gzip 머리가 스트림보다 길다')
  }
  return at
}

/**
 * gzip 스트림을 푼다. 꼬리의 CRC32 와 길이까지 대조한다.
 *
 * @param data gzip 스트림.
 * @returns 원래 바이트.
 * @throws 매직·압축 방식이 다르거나 꼬리가 본문과 어긋나는 경우.
 */
export function parseGzip(data: Uint8Array): Uint8Array {
  if (data[0] !== MAGIC_FIRST || data[1] !== MAGIC_SECOND) {
    throw new Error('gzip 스트림이 아니다')
  }
  if (data[2] !== METHOD_DEFLATE) {
    throw new Error(`아는 압축 방식이 아니다: ${String(data[2])}`)
  }
  const flags = data[3] ?? 0
  if ((flags & ~(FLAG_TEXT | FLAG_CRC | FLAG_EXTRA | FLAG_NAME | FLAG_COMMENT)) !== 0) {
    throw new Error('gzip 머리에 모르는 플래그가 있다')
  }
  const body = data.subarray(findBodyStart(data, flags), data.length - FOOTER_BYTES)
  const out = inflateRaw(body)
  const expected = readUint32(data, data.length - FOOTER_BYTES)
  if (computeCrc32(out) !== expected) {
    throw new Error('gzip 꼬리의 CRC32 가 본문과 어긋난다')
  }
  if ((out.length >>> 0) !== readUint32(data, data.length - CRC_BYTES)) {
    throw new Error('gzip 꼬리의 길이가 본문과 어긋난다')
  }
  return out
}
