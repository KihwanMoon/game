/**
 * 적 규칙표 편집기.
 *
 * 여기서 지키는 것은 넷이다.
 *
 * 1. **같은 편집기를 쓴다.** 적 규칙표는 플레이어 규칙표와 같은 형식이라, 새 편집기를
 *    만들면 규칙 표기가 둘이 되고 도감이 보여주는 것과 관리자가 고치는 것이 갈린다.
 * 2. **다른 규칙표는 손대지 않는다.** 파일을 통째로 다시 쓰면 안 연 규칙표의 주석·필드가
 *    사라지고, 그것은 편집이 아니라 소실이다.
 * 3. **저장은 초안이다.** 여기서 게임이 바뀌지 않는다.
 * 4. **고른 것이 색으로만 안 적힌다.** 벌이 열넷이라 어느 것을 열어 뒀는지가 화면에서
 *    유일하게 색으로 갈리면, 보조 기술도 밝기를 못 읽는 눈도 그것을 못 본다.
 *
 * **여기는 목록이 아니라 편집기다.** 공용 목록 틀로 옮기지 않는다 — 찾기·「더 보기」가
 * 끼면 고치던 규칙표가 화면에서 사라진다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { EnemyRuleEditor, buildEnemyFile, findEnemyRuleSet } from './EnemyRuleEditor'
import enemiesRaw from '@resources/rulesets/enemies.json'

const FILE = enemiesRaw as unknown as Record<string, unknown>
const noop = () => undefined

/**
 * 마크업에서 같은 말이 몇 번 나오는지 센다.
 *
 * @param markup 마크업.
 * @param needle 셀 말.
 * @returns 개수.
 */
function countOf(markup: string, needle: string): number {
  return markup.split(needle).length - 1
}

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

describe('적 규칙표 편집기 — 구조', () => {
  it('★ 규칙표 한 벌마다 단추가 하나씩 선다', () => {
    const markup = renderToStaticMarkup(<EnemyRuleEditor file={FILE} onSave={noop} />)
    const rows = FILE.rulesets as Record<string, unknown>[]
    expect(countOf(markup, 'aria-pressed=')).toBe(rows.length)
    expect(markup).toContain('ai_rusher')
  })

  it('★ 연 것을 색으로만 안 적는다 — aria-pressed 가 함께 나간다', () => {
    const markup = renderToStaticMarkup(<EnemyRuleEditor file={FILE} onSave={noop} />)
    // 아직 아무것도 안 열었으니 전부 거짓이다. 열면 그 하나가 참이 된다.
    expect(markup).toContain('aria-pressed="false"')
    expect(markup).not.toContain('aria-pressed="true"')
  })

  it('★ 아직 못 읽은 파일에는 단추가 서지 않는다 — 없는 id 를 열 수는 없다', () => {
    const markup = renderToStaticMarkup(<EnemyRuleEditor file={undefined} onSave={noop} />)
    expect(countOf(markup, 'aria-pressed=')).toBe(0)
    expect(markup).toContain('0벌')
  })

  it('★ 줄을 하나도 감추지 않는다 — 고치는 화면에서 「더 보기」는 고친 줄을 숨긴다', () => {
    const markup = renderToStaticMarkup(<EnemyRuleEditor file={FILE} onSave={noop} />)
    expect(markup).not.toContain('더 보기')
  })
})
