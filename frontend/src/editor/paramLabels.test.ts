/**
 * 화면에 뜨는 인자가 전부 한글인가.
 *
 * 블록 이름은 카탈로그가 `label_ko` 로 들고 있는데 **인자 값은 영문 id 그대로**였다.
 * 그래서 규칙표와 로그에 `대상 거리[NEAREST]`·`내 상태이상[POISON]` 처럼 **한 칸만 다른
 * 언어**로 뜨는 줄이 남았다 (2026-09-16 요청).
 *
 * 이 검사가 지키는 것은 **덮는 범위**다. 블록이 늘 때마다 인자도 느는데, 빠뜨린 것은
 * 화면에 뜨기 전까지 아무도 모른다 — 카탈로그가 정본이므로 카탈로그와 대조한다.
 *
 * **코어에서 바꾸지 않는 이유**는 따로 있다. 항 문구는 `core/rules/ruleVm` 의
 * `renderTerm` 이 만들고 그 문자열은 파이썬 코어와 비트 단위로 같아야 한다(게이트 G3).
 * 그래서 표시 계층에서 덧칠한다.
 */
import { describe, expect, it } from 'vitest'

import blocksRaw from '@resources/balance/blocks.json'

import { formatParamLabel, formatParamText } from './blockOptions'

interface RawBlock {
  id: string
  param?: { values: string[] }
}

/**
 * 카탈로그가 고를 수 있게 해 둔 인자 값 전부.
 *
 * @returns 값과 그것을 쓰는 블록 id 들.
 */
function listParamValues(): ReadonlyMap<string, string[]> {
  const found = new Map<string, string[]>()
  const raw = blocksRaw as unknown as Record<string, RawBlock[]>
  for (const group of ['perceptions', 'actions', 'selectors', 'stats']) {
    for (const block of raw[group] ?? []) {
      for (const value of block.param?.values ?? []) {
        found.set(value, [...(found.get(value) ?? []), block.id])
      }
    }
  }
  return found
}

/**
 * 한글로 안 옮기는 값들.
 *
 * 깃발 이름은 사람이 붙이는 꼬리표라 **뜻이 없다.** `A` 를 「가」로 옮기면 뜻이 생긴
 * 것처럼 보이지만 실제로는 아무 뜻도 없고, 규칙표를 짠 사람이 스스로 뜻을 붙이는 자리다.
 */
const KEPT = new Set(['A', 'B', 'C', 'D'])

describe('규칙 인자 표기', () => {
  const VALUES = listParamValues()

  it('★ 카탈로그가 고를 수 있게 한 인자가 전부 한글 이름을 갖는다', () => {
    // 하나도 못 찾았다면 훑기가 깨진 것이다. 0건은 「전부 통과」와 구별되지 않는다.
    expect(VALUES.size).toBeGreaterThan(30)
    const bare = [...VALUES.entries()]
      .filter(([value]) => !KEPT.has(value))
      .filter(([value]) => formatParamLabel(value) === value)
      .map(([value, blocks]) => `${value} (${blocks.join(', ')})`)
    expect(bare, '이름 없는 인자가 남았다').toEqual([])
  })

  it('★ 이미 만들어진 문구 안의 인자도 바뀐다 — 코어가 만든 줄이 그렇다', () => {
    expect(formatParamText('대상 거리[NEAREST](2) <= 3')).toBe('대상 거리[가장 가까운 적](2) <= 3')
    expect(formatParamText('내 상태이상[POISON] == 참')).toBe('내 상태이상[중독] == 참')
  })

  it('★ 모르는 값은 그대로 둔다 — 빈칸이 되면 무엇을 고른 건지 사라진다', () => {
    expect(formatParamText('내 깃발[ZZZ] == 참')).toBe('내 깃발[ZZZ] == 참')
    expect(formatParamLabel('ZZZ')).toBe('ZZZ')
  })

  it('깃발은 그대로 둔다 — 뜻이 없는 꼬리표다', () => {
    for (const flag of KEPT) {
      expect(formatParamLabel(flag)).toBe(flag)
    }
  })
})
