/**
 * DEFLATE 굽기 (RFC 1951) — 고정 허프만 블록 하나에 탐욕적 LZ77 을 실어 낸다.
 *
 * zlib 의 출력 바이트를 그대로 흉내 내지 않는다. 흉내 내려면 zlib 의 lazy 매칭·블록
 * 분할·트리 생성을 통째로 옮겨야 하고, 그렇게 옮긴 사본은 원본이 한 번 바뀌면 조용히
 * 갈라진다. 우리가 지켜야 하는 것은 **바이트가 같은 것이 아니라 형식이 같은 것**이다 —
 * 파이썬이 구운 코드를 우리가 풀고, 우리가 구운 코드를 파이썬이 푼다.
 *
 * 대신 **같은 입력이 언제나 같은 출력**이어야 한다는 조건은 지킨다. 시각도 난수도 보지
 * 않고 탐색 순서가 고정돼 있으므로, 같은 규칙표는 늘 같은 공유 코드가 된다 (R5). 그것이
 * 깨지면 "이 코드와 저 코드가 같은가" 로 규칙표를 비교할 수 없다.
 *
 * `CompressionStream` 을 쓰지 않은 이유는 그것이 비동기이고 브라우저마다 압축 수준이
 * 달라 같은 규칙표가 기기마다 다른 코드를 내기 때문이다.
 */
import {
  END_OF_BLOCK,
  LENGTH_BASE,
  LENGTH_EXTRA,
  MAX_DISTANCE,
  MAX_MATCH,
  MIN_MATCH,
  DISTANCE_BASE,
  DISTANCE_EXTRA,
  findDistanceSlot,
  findLengthSlot,
} from './deflateCodes'

const BYTE_BITS = 8
const BYTE_MASK = 0xff

/** 고정 허프만 표의 경계와 코드 (RFC 1951 §3.2.6). */
const LIT_8BIT_END = 144
const LIT_9BIT_END = 256
const LIT_7BIT_END = 280
const LIT_8BIT_CODE = 0x30
const LIT_9BIT_CODE = 0x190
const LIT_7BIT_CODE = 0
const LIT_HIGH_CODE = 0xc0
const LIT_8BIT_BITS = 8
const LIT_9BIT_BITS = 9
const LIT_7BIT_BITS = 7
const DISTANCE_CODE_BITS = 5

/** 마지막 블록임을 알리는 비트와 고정 허프만 블록 종류. */
const BFINAL = 1
const BTYPE_FIXED = 1
const BTYPE_BITS = 2

/** 해시 사슬의 크기와 한 자리에서 훑어볼 후보 수의 상한. */
const HASH_BITS = 15
const HASH_SIZE = 1 << HASH_BITS
const HASH_MASK = HASH_SIZE - 1
const HASH_SHIFT_FIRST = 10
const HASH_SHIFT_SECOND = 5
const MAX_CHAIN = 128

/** 사슬의 끝. */
const CHAIN_END = -1

/** 비트를 모아 바이트로 내보내는 버퍼. 바이트 안에서는 LSB 부터 채운다. */
interface BitWriter {
  readonly bytes: number[]
  buffer: number
  bits: number
}

/** 찾아낸 일치 하나. 길이가 MIN_MATCH 미만이면 쓰지 않는다. */
interface Match {
  readonly length: number
  readonly distance: number
}

const NO_MATCH: Match = { length: 0, distance: 0 }

/**
 * 비트 버퍼를 만든다.
 *
 * @returns 빈 버퍼.
 */
function createWriter(): BitWriter {
  return { bytes: [], buffer: 0, bits: 0 }
}

/**
 * 값을 낮은 자리부터 count 비트 쓴다. 길이·거리의 추가 비트가 이 순서다.
 *
 * @param writer 비트 버퍼.
 * @param value 쓸 값.
 * @param count 비트 수.
 */
function writeBits(writer: BitWriter, value: number, count: number): void {
  for (let step = 0; step < count; step += 1) {
    writer.buffer |= ((value >> step) & 1) << writer.bits
    writer.bits += 1
    if (writer.bits === BYTE_BITS) {
      writer.bytes.push(writer.buffer & BYTE_MASK)
      writer.buffer = 0
      writer.bits = 0
    }
  }
}

/**
 * 허프만 코드를 쓴다. **코드는 높은 자리부터** 나간다 (RFC 1951 §3.1.1).
 *
 * @param writer 비트 버퍼.
 * @param code 코드 값.
 * @param count 코드 길이.
 */
function writeCode(writer: BitWriter, code: number, count: number): void {
  for (let step = count - 1; step >= 0; step -= 1) {
    writeBits(writer, (code >> step) & 1, 1)
  }
}

/**
 * 남은 비트를 0 으로 채워 바이트를 맞추고 결과를 낸다.
 *
 * @param writer 비트 버퍼.
 * @returns 완성된 바이트.
 */
function buildBytes(writer: BitWriter): Uint8Array {
  if (writer.bits > 0) {
    writer.bytes.push(writer.buffer & BYTE_MASK)
    writer.buffer = 0
    writer.bits = 0
  }
  return Uint8Array.from(writer.bytes)
}

/**
 * 리터럴·길이 심볼 하나를 고정 표로 쓴다.
 *
 * @param writer 비트 버퍼.
 * @param symbol 0..287 사이의 심볼.
 */
function writeSymbol(writer: BitWriter, symbol: number): void {
  if (symbol < LIT_8BIT_END) {
    writeCode(writer, LIT_8BIT_CODE + symbol, LIT_8BIT_BITS)
    return
  }
  if (symbol < LIT_9BIT_END) {
    writeCode(writer, LIT_9BIT_CODE + (symbol - LIT_8BIT_END), LIT_9BIT_BITS)
    return
  }
  if (symbol < LIT_7BIT_END) {
    writeCode(writer, LIT_7BIT_CODE + (symbol - LIT_9BIT_END), LIT_7BIT_BITS)
    return
  }
  writeCode(writer, LIT_HIGH_CODE + (symbol - LIT_7BIT_END), LIT_8BIT_BITS)
}

/**
 * 일치 하나를 길이 코드와 거리 코드로 쓴다.
 *
 * @param writer 비트 버퍼.
 * @param match 쓸 일치.
 */
function writeMatch(writer: BitWriter, match: Match): void {
  const lengthSlot = findLengthSlot(match.length)
  writeSymbol(writer, END_OF_BLOCK + 1 + lengthSlot)
  writeBits(writer, match.length - (LENGTH_BASE[lengthSlot] ?? 0), LENGTH_EXTRA[lengthSlot] ?? 0)
  const distanceSlot = findDistanceSlot(match.distance)
  writeCode(writer, distanceSlot, DISTANCE_CODE_BITS)
  writeBits(
    writer,
    match.distance - (DISTANCE_BASE[distanceSlot] ?? 0),
    DISTANCE_EXTRA[distanceSlot] ?? 0,
  )
}

/**
 * 세 바이트로 해시 자리를 만든다.
 *
 * @param data 입력 바이트.
 * @param at 시작 자리.
 * @returns 해시 자리.
 */
function computeHash(data: Uint8Array, at: number): number {
  const first = data[at] ?? 0
  const second = data[at + 1] ?? 0
  const third = data[at + 2] ?? 0
  return (
    ((first << HASH_SHIFT_FIRST) ^ (second << HASH_SHIFT_SECOND) ^ third) & HASH_MASK
  )
}

/**
 * 두 자리에서 시작하는 바이트열이 몇 개까지 같은지 센다.
 *
 * @param data 입력 바이트.
 * @param candidate 뒤쪽 자리(과거).
 * @param at 지금 자리.
 * @returns 일치 길이. 최대 MAX_MATCH.
 */
function countMatch(data: Uint8Array, candidate: number, at: number): number {
  let length = 0
  while (
    length < MAX_MATCH &&
    at + length < data.length &&
    data[candidate + length] === data[at + length]
  ) {
    length += 1
  }
  return length
}

/**
 * 지금 자리에서 가장 긴 일치를 찾는다. 같은 길이면 **가까운 것**을 고른다.
 *
 * @param data 입력 바이트.
 * @param head 해시 자리마다의 최근 위치.
 * @param prev 위치마다의 그 이전 위치.
 * @param at 지금 자리.
 * @returns 찾아낸 일치. 없으면 길이 0.
 */
function findMatch(data: Uint8Array, head: Int32Array, prev: Int32Array, at: number): Match {
  let candidate = head[computeHash(data, at)] ?? CHAIN_END
  let best = NO_MATCH
  let chain = MAX_CHAIN
  while (candidate !== CHAIN_END && chain > 0) {
    chain -= 1
    const distance = at - candidate
    if (distance > MAX_DISTANCE) {
      break
    }
    const length = countMatch(data, candidate, at)
    if (length > best.length) {
      best = { length, distance }
      if (length >= MAX_MATCH) {
        break
      }
    }
    candidate = prev[candidate] ?? CHAIN_END
  }
  return best
}

/**
 * 지금 자리를 해시 사슬에 넣는다.
 *
 * @param data 입력 바이트.
 * @param head 해시 자리마다의 최근 위치.
 * @param prev 위치마다의 그 이전 위치.
 * @param at 넣을 자리.
 */
function addToChain(data: Uint8Array, head: Int32Array, prev: Int32Array, at: number): void {
  if (at + MIN_MATCH > data.length) {
    return
  }
  const hash = computeHash(data, at)
  prev[at] = head[hash] ?? CHAIN_END
  head[hash] = at
}

/**
 * 바이트를 DEFLATE 본문으로 굽는다.
 *
 * @param data 원래 바이트.
 * @returns gzip 머리·꼬리가 붙지 않은 압축 본문.
 */
export function deflateRaw(data: Uint8Array): Uint8Array {
  const writer = createWriter()
  writeBits(writer, BFINAL, 1)
  writeBits(writer, BTYPE_FIXED, BTYPE_BITS)

  const head = new Int32Array(HASH_SIZE).fill(CHAIN_END)
  const prev = new Int32Array(Math.max(data.length, 1)).fill(CHAIN_END)
  let at = 0
  while (at < data.length) {
    const match = at + MIN_MATCH <= data.length ? findMatch(data, head, prev, at) : NO_MATCH
    if (match.length >= MIN_MATCH) {
      writeMatch(writer, match)
      for (let step = 0; step < match.length; step += 1) {
        addToChain(data, head, prev, at + step)
      }
      at += match.length
    } else {
      writeSymbol(writer, data[at] ?? 0)
      addToChain(data, head, prev, at)
      at += 1
    }
  }
  writeSymbol(writer, END_OF_BLOCK)
  return buildBytes(writer)
}
