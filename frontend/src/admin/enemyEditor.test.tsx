/**
 * 적 규칙표 편집기.
 *
 * 여기서 지키는 것은 셋이다.
 *
 * 1. **같은 편집기를 쓴다.** 적 규칙표는 플레이어 규칙표와 같은 형식이라, 새 편집기를
 *    만들면 규칙 표기가 둘이 되고 도감이 보여주는 것과 관리자가 고치는 것이 갈린다.
 * 2. **다른 규칙표는 손대지 않는다.** 파일을 통째로 다시 쓰면 안 연 규칙표의 주석·필드가
 *    사라지고, 그것은 편집이 아니라 소실이다.
 * 3. **저장은 초안이다.** 여기서 게임이 바뀌지 않는다.
 */
import { describe, expect, it } from 'vitest'

import { buildEnemyFile, findEnemyRuleSet } from './EnemyRuleEditor'
import enemiesRaw from '@resources/rulesets/enemies.json'

const FILE = enemiesRaw as unknown as Record<string, unknown>

describe('적 규칙표 편집기', () => {
  it('★ 파일에서 규칙표를 코어의 파서로 읽는다', () => {
    const found = findEnemyRuleSet(FILE, 'ai_rusher')
    expect(found).toBeDefined()
    expect(found?.rules.length).toBeGreaterThan(0)
  })

  it('없는 id 는 undefined 다 — 빈 편집기를 여는 것보다 낫다', () => {
    expect(findEnemyRuleSet(FILE, 'no_such_ruleset')).toBeUndefined()
  })

  it('★ 고친 규칙표만 바뀌고 나머지는 그대로다', () => {
    const before = (FILE.rulesets as Record<string, unknown>[]).length
    const found = findEnemyRuleSet(FILE, 'ai_rusher')
    if (found === undefined) {
      throw new Error('ai_rusher 가 없다')
    }
    const next = buildEnemyFile(FILE, { ...found, version: found.version + 1 })
    const rows = next.rulesets as Record<string, unknown>[]
    expect(rows).toHaveLength(before)
    expect(rows.find((row) => row.ruleset_id === 'ai_rusher')?.version).toBe(found.version + 1)
    // 다른 규칙표는 원본 객체 그대로다.
    const other = rows.find((row) => row.ruleset_id === 'ai_archer')
    const original = (FILE.rulesets as Record<string, unknown>[]).find(
      (row) => row.ruleset_id === 'ai_archer',
    )
    expect(other).toBe(original)
  })

  it('★ 고친 규칙표의 서술 필드가 살아남는다 — for_kind 를 잃으면 그 적이 규칙을 잃는다', () => {
    const found = findEnemyRuleSet(FILE, 'ai_rusher')
    if (found === undefined) {
      throw new Error('ai_rusher 가 없다')
    }
    const rows = buildEnemyFile(FILE, found).rulesets as Record<string, unknown>[]
    const edited = rows.find((row) => row.ruleset_id === 'ai_rusher')
    expect(edited?.for_kind).toBeDefined()
    expect(edited?.strategy_ko).toBeDefined()
  })
})
