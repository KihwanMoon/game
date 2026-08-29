/**
 * 공유 코드가 파이썬과 같은 형식인지 본다 (M3).
 *
 * 여기서 지키는 것은 **양방향**이다. 한쪽만 맞으면 코드는 주고받는 것이 아니라 내보내기만
 * 되는 기능이 된다.
 *
 * - 파이썬 → TS: `__golden__/preset_code.json` 이 파이썬 코어가 구운 코드다. 그것을 풀어
 *   절과 정규 JSON 까지 대조한다. 파일을 손으로 고치지 않는다. 재생성은
 *   `uv run python -m scripts.export_preset_code_golden`.
 * - TS → 파이썬: `__golden__/ts_preset_code.json` 이 이 구현이 구운 코드이며,
 *   `tests/test_preset_code_interop.py` 가 같은 파일을 파이썬으로 푼다. 두 테스트가 한
 *   파일을 보므로, TS 압축이 바뀌면 이쪽이 먼저 붉어지고 파이썬 쪽 검사가 뒤따라 도는
 *   순서가 된다. 다시 만들려면 `UPDATE_TS_PRESET_GOLDEN=1` 로 이 파일을 돌린 뒤
 *   파이썬 테스트를 돌려 파이썬이 그것을 풀 수 있는지 확인한다.
 */
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { formatCanonicalJson } from './canonicalJson'
import {
  PRESET_CODE_PREFIX,
  PRESET_CODE_VERSION,
  exportPresetCode,
  getCodeVersion,
  parsePresetCode,
} from './presetCode'
import { buildPresetPayload, parsePresetPayload, type RulePreset } from './presetPayload'

/** 파이썬이 내보낸 기준값 한 케이스. */
interface GoldenCase {
  readonly name: string
  readonly ruleset_id: string
  readonly payload: unknown
  readonly canonical_json: string
  readonly code: string
}

/** 기준값 파일 전체. */
interface GoldenFile {
  readonly prefix: string
  readonly cases: readonly GoldenCase[]
}

/**
 * `__golden__` 의 JSON 을 읽는다.
 *
 * @param name 파일 이름.
 * @returns 읽어 낸 값.
 */
function readGolden(name: string): unknown {
  const path = fileURLToPath(new URL(`__golden__/${name}`, import.meta.url))
  return JSON.parse(readFileSync(path, 'utf-8')) as unknown
}

const GOLDEN = readGolden('preset_code.json') as GoldenFile
const TS_GOLDEN_PATH = fileURLToPath(new URL('__golden__/ts_preset_code.json', import.meta.url))
const PRESETS: readonly RulePreset[] = GOLDEN.cases.map((item) => parsePresetPayload(item.payload))

// 기준을 다시 만드는 유일한 경로다. 평소에는 파일을 읽기만 한다 — 테스트가 자기 기준을
// 조용히 덮어쓰면 그 뒤로는 아무것도 검증하지 못한다.
if (process.env.UPDATE_TS_PRESET_GOLDEN === '1') {
  const regenerated = PRESETS.map((preset) => exportPresetCode(preset))
  writeFileSync(TS_GOLDEN_PATH, `${JSON.stringify(regenerated, null, 2)}\n`, 'utf-8')
}

const TS_CODES = JSON.parse(readFileSync(TS_GOLDEN_PATH, 'utf-8')) as readonly string[]

describe('파이썬이 구운 코드', () => {
  it('접두어가 같다', () => {
    expect(GOLDEN.prefix).toBe(PRESET_CODE_PREFIX)
    for (const item of GOLDEN.cases) {
      expect(item.code.startsWith(PRESET_CODE_PREFIX)).toBe(true)
      expect(getCodeVersion(item.code)).toBe(PRESET_CODE_VERSION)
    }
  })

  it('풀면 같은 프리셋이 나온다', () => {
    GOLDEN.cases.forEach((item, at) => {
      const preset = parsePresetCode(item.code)
      expect(preset.name).toBe(item.name)
      expect(preset.ruleset.rulesetId).toBe(item.ruleset_id)
      expect(preset).toEqual(PRESETS[at])
    })
  })

  it('절을 다시 찍으면 파이썬과 글자까지 같다 — 압축 이전 단계의 대조다', () => {
    GOLDEN.cases.forEach((item, at) => {
      const preset = PRESETS[at] as RulePreset
      expect(formatCanonicalJson(buildPresetPayload(preset))).toBe(item.canonical_json)
    })
  })
})

describe('왕복', () => {
  it('내보낸 코드를 다시 읽으면 같은 프리셋이다', () => {
    for (const preset of PRESETS) {
      expect(parsePresetCode(exportPresetCode(preset))).toEqual(preset)
    }
  })

  it('같은 프리셋은 언제나 같은 코드다 — 시각도 난수도 보지 않는다', () => {
    for (const preset of PRESETS) {
      expect(exportPresetCode(preset)).toBe(exportPresetCode(preset))
    }
  })

  it('파이썬이 푼 것으로 확인된 코드와 글자까지 같다', () => {
    expect(PRESETS.map((preset) => exportPresetCode(preset))).toEqual([...TS_CODES])
  })

  it('공백과 잘린 패딩이 섞여 들어와도 읽는다 — 채팅에서 긁어 온 코드다', () => {
    const preset = PRESETS[0] as RulePreset
    const code = exportPresetCode(preset)
    expect(parsePresetCode(`  ${code.replace(/=+$/, '')}\n`)).toEqual(preset)
  })
})

describe('접두어 판정', () => {
  it('버전을 본문을 풀지 않고 읽는다', () => {
    expect(getCodeVersion('v2:aaaa')).toBe(PRESET_CODE_VERSION)
    expect(getCodeVersion('v13:aaaa')).toBe(13)
  })

  it('세대가 다르면 풀기 전에 거절한다', () => {
    expect(() => parsePresetCode('v3:aaaa')).toThrow(/세대/)
  })

  it('접두어가 없으면 거절한다', () => {
    expect(() => parsePresetCode('그냥 문자열')).toThrow(/v<버전>/)
  })

  it('본문이 깨졌으면 한 종류의 오류로 모은다', () => {
    expect(() => parsePresetCode('v2:____')).toThrow(/프리셋 코드를 풀 수 없다/)
  })
})
