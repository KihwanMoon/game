/**
 * 정비 규칙 패널 검사 (설계/4_아이템 §5).
 *
 * 전투 규칙의 문장 결(「조건 → 행동」)을 그대로 쓴다 — 같은 게임 문법이라는 것이
 * 자리에서 보여야 한다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { MaintenanceView } from '../storage'

import { MaintenancePanel } from './MaintenancePanel'

const noop = (): undefined => undefined

function render(view: MaintenanceView | undefined, detail = ''): string {
  return renderToStaticMarkup(
    <MaintenancePanel view={view} isOnline detail={detail} onChange={noop} />,
  )
}

const ALL_ON: MaintenanceView = { isRefillOn: true, isRepairOn: true, discardGrade: 'COMMON' }
const ALL_OFF: MaintenanceView = { isRefillOn: false, isRepairOn: false, discardGrade: '' }

describe('정비 규칙', () => {
  it('★ 규칙 문장으로 적는다 — 「런이 끝나면 →」이 전투 규칙과 같은 문법이다', () => {
    const html = render(ALL_OFF)
    expect((html.match(/런이 끝나면/g) ?? []).length).toBe(3)
    expect(html).toContain('소모품을 잔액 안에서 보충한다')
    expect(html).toContain('파손된 착용 장비를 잔액 안에서 복구한다')
    expect(html).toContain('보통 등급 가방 장비를 버린다')
  })

  it('★ 언제 실행되는지 말한다 — 조용한 자동화는 「왜 돈이 줄었지」가 된다 (P1)', () => {
    expect(render(ALL_OFF)).toContain('티켓이 닫힐 때')
  })

  it('★ 켬·끔이 글자로도 갈린다 — 색만으로 가르지 않는다', () => {
    expect(render(ALL_ON)).toContain('켬')
    expect(render(ALL_OFF)).toContain('끔')
    expect(render(ALL_OFF)).toContain('mnt__what--off')
    expect(render(ALL_ON)).not.toContain('mnt__what--off')
  })

  it('★ 되찾은 것은 남긴다는 것을 버리기 줄이 말한다', () => {
    expect(render(ALL_OFF)).toContain('되찾은 것은 남긴다')
  })

  it('★ 저장 실패 사유를 그대로 띄운다 — 삼키면 껐다고 믿은 정비가 돈을 쓴다', () => {
    expect(render(ALL_OFF, '서버에 닿지 못했다')).toContain('서버에 닿지 못했다')
  })

  it('★ 서버에 못 닿으면 그 사실을 적는다', () => {
    expect(render(undefined)).toContain('정비 규칙을 못 읽는다')
  })
})
