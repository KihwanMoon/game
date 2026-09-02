/**
 * 정비 규칙 패널 검사 (설계/4_아이템 §5).
 *
 * **전투 규칙표처럼 조립한다.** 행을 더하고 빼고 순서를 바꾼다 — 행 순서가 실행 순서다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { MaintenanceView } from '../storage'

import { MaintenancePanel, liftRow, replaceRow } from './MaintenancePanel'

const noop = (): undefined => undefined

function render(view: MaintenanceView | undefined, detail = ''): string {
  return renderToStaticMarkup(
    <MaintenancePanel view={view} isOnline detail={detail} onChange={noop} />,
  )
}

const ROWS: MaintenanceView = {
  rows: [
    { action: 'DISCARD', grade: 'COMMON' },
    { action: 'REPAIR', grade: '' },
    { action: 'REFILL', grade: '' },
  ],
}

describe('정비 규칙 조립', () => {
  it('★ 행마다 번호가 선다 — 순서가 실행 순서라는 것이 자리에서 보인다', () => {
    const html = render(ROWS)
    expect(html).toContain('1.')
    expect(html).toContain('3.')
    expect(html).toContain('위에서 아래로 실행')
  })

  it('★ 버리기 행에만 등급 고르개가 붙는다 — 다른 행동은 인자를 안 받는다', () => {
    expect((render(ROWS).match(/정비 \d 등급/g) ?? []).length).toBe(1)
  })

  it('★ 행 지우기는 그 자리 하나만 지운다', () => {
    expect(replaceRow(ROWS.rows, 1, undefined)).toEqual([
      { action: 'DISCARD', grade: 'COMMON' },
      { action: 'REFILL', grade: '' },
    ])
  })

  it('★ 올리기가 순서를 한 칸만 바꾼다 — 0번은 그대로다', () => {
    expect(liftRow(ROWS.rows, 2).map((row) => row.action)).toEqual([
      'DISCARD',
      'REFILL',
      'REPAIR',
    ])
    expect(liftRow(ROWS.rows, 0)).toBe(ROWS.rows)
  })

  it('★ 행동을 바꾸면 인자가 따라온다 — 버리기가 아니면 등급이 비고, 버리기면 기본이 찬다', () => {
    const toRepair = replaceRow(ROWS.rows, 0, { action: 'REPAIR', grade: '' })
    expect(toRepair[0]).toEqual({ action: 'REPAIR', grade: '' })
  })

  it('★ 저장 실패 사유를 그대로 띄운다 — 삼키면 켰다고 믿은 정비가 안 돈다', () => {
    expect(render(ROWS, '버릴 수 없는 등급이다: X')).toContain('버릴 수 없는 등급이다')
  })

  it('★ 서버에 못 닿으면 그 사실을 적는다', () => {
    expect(render(undefined)).toContain('정비 규칙을 못 읽는다')
  })

  it('★ 빈 목록에도 추가 버튼이 있다 — 시작할 길이 없으면 기능이 없는 것과 같다', () => {
    expect(render({ rows: [] })).toContain('규칙 추가')
  })
})
