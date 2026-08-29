/**
 * DEFLATE 풀기 (RFC 1951). 파이썬 `gzip.compress` 가 구운 본문을 브라우저에서 읽는다.
 *
 * 세 종류의 블록을 모두 받는다 — 저장(0)·고정 허프만(1)·동적 허프만(2). 파이썬 zlib 은
 * 압축률이 좋은 동적 블록을 주로 내므로 그 하나만 구현해도 대개 통하지만, 짧은 규칙표는
 * 저장 블록으로 나오고 우리 쪽 `deflateRaw` 는 고정 블록을 낸다. 셋 중 하나라도 빠지면
 * "어떤 프리셋은 열리고 어떤 프리셋은 안 열린다" 가 된다.
 *
 * 심볼 해독은 puff.c 의 방식이다 — 코드 길이별 개수와 심볼 목록만 들고 비트를 한 칸씩
 * 밀며 훑는다. 큰 조회표를 만들지 않는 대신 코드가 짧고, 다루는 양이 수 KB 라 속도가
 * 문제 되지 않는다.
 */
import {
  CODE_LENGTH_ORDER,
  DISTANCE_BASE,
  DISTANCE_EXTRA,
  END_OF_BLOCK,
  LENGTH_BASE,
  LENGTH_EXTRA,
  MAX_CODE_BITS,
} from './deflateCodes'

const BYTE_BITS = 8

/** 고정 허프만 표의 경계 (RFC 1951 §3.2.6). */
const FIXED_LIT_8BIT_END = 144
const FIXED_LIT_9BIT_END = 256
const FIXED_LIT_7BIT_END = 280
const FIXED_LIT_COUNT = 288
const FIXED_DIST_COUNT = 30
const FIXED_LIT_8BIT = 8
const FIXED_LIT_9BIT = 9
const FIXED_LIT_7BIT = 7
const FIXED_DIST_BITS = 5

/** 저장 블록 머리는 길이 2바이트와 그 보수 2바이트다. */
const STORED_HEADER_BYTES = 4
const STORED_LENGTH_MASK = 0xffff

/** 블록 종류. */
const BTYPE_STORED = 0
const BTYPE_FIXED = 1
const BTYPE_DYNAMIC = 2

/** 동적 블록 머리의 개수 필드. */
const HLIT_BASE = 257
const HDIST_BASE = 1
const HCLEN_BASE = 4
const HLIT_BITS = 5
const HDIST_BITS = 5
const HCLEN_BITS = 4
const CODE_LENGTH_BITS = 3

/** 코드 길이 알파벳의 반복 지시자 (16·17·18). */
const REPEAT_PREVIOUS = 16
const REPEAT_ZERO_SHORT = 17
const REPEAT_ZERO_LONG = 18
const REPEAT_PREVIOUS_BASE = 3
const REPEAT_PREVIOUS_BITS = 2
const REPEAT_ZERO_SHORT_BASE = 3
const REPEAT_ZERO_SHORT_BITS = 3
const REPEAT_ZERO_LONG_BASE = 11
const REPEAT_ZERO_LONG_BITS = 7

/** 비트 단위로 읽는 커서. 바이트 안에서는 LSB 부터 나간다. */
interface BitReader {
  readonly data: Uint8Array
  at: number
  buffer: number
  bits: number
}

/** 코드 길이별 개수와, 그 순서대로 늘어놓은 심볼. */
interface Huffman {
  readonly counts: readonly number[]
  readonly symbols: readonly number[]
}

/**
 * 비트 커서를 만든다.
 *
 * @param data 읽을 바이트.
 * @returns 처음 위치의 커서.
 */
function createReader(data: Uint8Array): BitReader {
  return { data, at: 0, buffer: 0, bits: 0 }
}

/**
 * 비트를 count 개 읽는다. 먼저 읽은 비트가 낮은 자리로 들어간다.
 *
 * @param reader 비트 커서.
 * @param count 읽을 비트 수.
 * @returns 읽은 값.
 * @throws 입력이 도중에 끝난 경우.
 */
function readBits(reader: BitReader, count: number): number {
  while (reader.bits < count) {
    const byte = reader.data[reader.at]
    if (byte === undefined) {
      throw new Error('압축 본문이 도중에 끝났다')
    }
    reader.at += 1
    reader.buffer |= byte << reader.bits
    reader.bits += BYTE_BITS
  }
  const value = reader.buffer & ((1 << count) - 1)
  reader.buffer >>>= count
  reader.bits -= count
  return value
}

/**
 * 코드 길이 목록으로 허프만 표를 만든다. 길이 0 인 심볼은 쓰이지 않는다.
 *
 * @param lengths 심볼마다의 코드 길이.
 * @returns 길이별 개수와 심볼 목록.
 */
function buildHuffman(lengths: readonly number[]): Huffman {
  const counts = Array.from({ length: MAX_CODE_BITS + 1 }, () => 0)
  for (const length of lengths) {
    counts[length] = (counts[length] ?? 0) + 1
  }
  counts[0] = 0
  const symbols: number[] = []
  for (let length = 1; length <= MAX_CODE_BITS; length += 1) {
    for (let symbol = 0; symbol < lengths.length; symbol += 1) {
      if (lengths[symbol] === length) {
        symbols.push(symbol)
      }
    }
  }
  return { counts, symbols }
}

/**
 * 심볼 하나를 해독한다.
 *
 * @param reader 비트 커서.
 * @param table 허프만 표.
 * @returns 해독된 심볼.
 * @throws 표에 없는 코드가 나온 경우.
 */
function readSymbol(reader: BitReader, table: Huffman): number {
  let code = 0
  let first = 0
  let index = 0
  for (let length = 1; length <= MAX_CODE_BITS; length += 1) {
    code |= readBits(reader, 1)
    const count = table.counts[length] ?? 0
    if (code - first < count) {
      return table.symbols[index + (code - first)] ?? 0
    }
    index += count
    first = (first + count) << 1
    code <<= 1
  }
  throw new Error('허프만 표에 없는 코드다')
}

/** 고정 허프만 표는 값이 정해져 있다. 한 번 만들어 두고 계속 쓴다. */
const FIXED_LITERALS: Huffman = buildHuffman(
  Array.from({ length: FIXED_LIT_COUNT }, (_unused, symbol) => {
    if (symbol < FIXED_LIT_8BIT_END) {
      return FIXED_LIT_8BIT
    }
    if (symbol < FIXED_LIT_9BIT_END) {
      return FIXED_LIT_9BIT
    }
    return symbol < FIXED_LIT_7BIT_END ? FIXED_LIT_7BIT : FIXED_LIT_8BIT
  }),
)

const FIXED_DISTANCES: Huffman = buildHuffman(
  Array.from({ length: FIXED_DIST_COUNT }, () => FIXED_DIST_BITS),
)

/**
 * 저장 블록을 그대로 옮긴다.
 *
 * @param reader 비트 커서.
 * @param out 출력 버퍼.
 * @throws 길이와 그 보수가 어긋나거나 입력이 짧은 경우.
 */
function readStoredBlock(reader: BitReader, out: number[]): void {
  reader.buffer = 0
  reader.bits = 0
  const low = reader.data[reader.at]
  const high = reader.data[reader.at + 1]
  const lowInverse = reader.data[reader.at + 2]
  const highInverse = reader.data[reader.at + 3]
  if (low === undefined || high === undefined || lowInverse === undefined || highInverse === undefined) {
    throw new Error('저장 블록의 길이 머리가 잘렸다')
  }
  const length = low | (high << BYTE_BITS)
  const inverse = lowInverse | (highInverse << BYTE_BITS)
  if ((length ^ STORED_LENGTH_MASK) !== inverse) {
    throw new Error('저장 블록의 길이와 보수가 어긋난다')
  }
  reader.at += STORED_HEADER_BYTES
  for (let step = 0; step < length; step += 1) {
    const byte = reader.data[reader.at + step]
    if (byte === undefined) {
      throw new Error('저장 블록의 본문이 잘렸다')
    }
    out.push(byte)
  }
  reader.at += length
}

/**
 * 동적 블록의 머리를 읽어 두 허프만 표를 만든다.
 *
 * @param reader 비트 커서.
 * @returns 리터럴·길이 표와 거리 표.
 */
function readDynamicTables(reader: BitReader): { literals: Huffman; distances: Huffman } {
  const literalCount = readBits(reader, HLIT_BITS) + HLIT_BASE
  const distanceCount = readBits(reader, HDIST_BITS) + HDIST_BASE
  const codeCount = readBits(reader, HCLEN_BITS) + HCLEN_BASE

  const codeLengths = Array.from({ length: CODE_LENGTH_ORDER.length }, () => 0)
  for (let step = 0; step < codeCount; step += 1) {
    codeLengths[CODE_LENGTH_ORDER[step] ?? 0] = readBits(reader, CODE_LENGTH_BITS)
  }
  const codeTable = buildHuffman(codeLengths)

  const lengths: number[] = []
  while (lengths.length < literalCount + distanceCount) {
    const symbol = readSymbol(reader, codeTable)
    if (symbol < REPEAT_PREVIOUS) {
      lengths.push(symbol)
      continue
    }
    const previous = symbol === REPEAT_PREVIOUS ? (lengths[lengths.length - 1] ?? 0) : 0
    const repeat = readRepeatCount(reader, symbol)
    for (let step = 0; step < repeat; step += 1) {
      lengths.push(previous)
    }
  }
  return {
    literals: buildHuffman(lengths.slice(0, literalCount)),
    distances: buildHuffman(lengths.slice(literalCount)),
  }
}

/**
 * 코드 길이 알파벳의 반복 횟수를 읽는다.
 *
 * @param reader 비트 커서.
 * @param symbol 16·17·18 중 하나.
 * @returns 반복 횟수.
 */
function readRepeatCount(reader: BitReader, symbol: number): number {
  if (symbol === REPEAT_PREVIOUS) {
    return REPEAT_PREVIOUS_BASE + readBits(reader, REPEAT_PREVIOUS_BITS)
  }
  if (symbol === REPEAT_ZERO_SHORT) {
    return REPEAT_ZERO_SHORT_BASE + readBits(reader, REPEAT_ZERO_SHORT_BITS)
  }
  if (symbol !== REPEAT_ZERO_LONG) {
    throw new Error(`코드 길이 알파벳에 없는 심볼이다: ${String(symbol)}`)
  }
  return REPEAT_ZERO_LONG_BASE + readBits(reader, REPEAT_ZERO_LONG_BITS)
}

/**
 * 허프만 블록 하나를 푼다.
 *
 * @param reader 비트 커서.
 * @param out 출력 버퍼.
 * @param literals 리터럴·길이 표.
 * @param distances 거리 표.
 * @throws 알 수 없는 심볼이거나 거리가 출력 길이를 넘는 경우.
 */
function readHuffmanBlock(
  reader: BitReader,
  out: number[],
  literals: Huffman,
  distances: Huffman,
): void {
  for (;;) {
    const symbol = readSymbol(reader, literals)
    if (symbol === END_OF_BLOCK) {
      return
    }
    if (symbol < END_OF_BLOCK) {
      out.push(symbol)
      continue
    }
    const lengthSlot = symbol - END_OF_BLOCK - 1
    const base = LENGTH_BASE[lengthSlot]
    if (base === undefined) {
      throw new Error(`길이 코드가 범위를 벗어났다: ${String(symbol)}`)
    }
    const length = base + readBits(reader, LENGTH_EXTRA[lengthSlot] ?? 0)
    const distanceSlot = readSymbol(reader, distances)
    const distanceBase = DISTANCE_BASE[distanceSlot]
    if (distanceBase === undefined) {
      throw new Error(`거리 코드가 범위를 벗어났다: ${String(distanceSlot)}`)
    }
    const distance = distanceBase + readBits(reader, DISTANCE_EXTRA[distanceSlot] ?? 0)
    if (distance > out.length) {
      throw new Error('거리가 지금까지 푼 길이보다 멀다')
    }
    for (let step = 0; step < length; step += 1) {
      out.push(out[out.length - distance] ?? 0)
    }
  }
}

/**
 * DEFLATE 본문을 푼다.
 *
 * @param data gzip 머리와 꼬리를 뗀 압축 본문.
 * @returns 원래 바이트.
 * @throws 알 수 없는 블록 종류이거나 본문이 깨진 경우.
 */
export function inflateRaw(data: Uint8Array): Uint8Array {
  const reader = createReader(data)
  const out: number[] = []
  let last = false
  while (!last) {
    last = readBits(reader, 1) === 1
    const kind = readBits(reader, 2)
    if (kind === BTYPE_STORED) {
      readStoredBlock(reader, out)
    } else if (kind === BTYPE_FIXED) {
      readHuffmanBlock(reader, out, FIXED_LITERALS, FIXED_DISTANCES)
    } else if (kind === BTYPE_DYNAMIC) {
      const tables = readDynamicTables(reader)
      readHuffmanBlock(reader, out, tables.literals, tables.distances)
    } else {
      throw new Error('예약된 블록 종류다')
    }
  }
  return Uint8Array.from(out)
}
