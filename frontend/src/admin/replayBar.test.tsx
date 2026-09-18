/**
 * 재생 머리줄 — **값과 조작이 갈려 있다** (폰 신고: 「머리줄이 길다」).
 *
 * 제목·방·시드·그때의 결과·버튼 셋이 낱개로 서 있던 때는, 좁은 화면에서 여덟 조각이
 * 제각기 접혀 **값과 버튼이 사이사이로 섞였다** — 무엇이 읽을 것이고 무엇이 누를 것인지
 * 줄만 봐서는 알 수 없었다. 묶음이 둘이면 통째로 아랫줄에 내려간다.
 *
 * 배치 자체는 검사가 못 본다. 여기서 재는 것은 **접힐 수 있는 구조인가**다 — 값 묶음이
 * 서 있는지, 조작이 그 뒤 한 묶음인지, 닫기가 그 안에 있는지.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { ReplayView } from './ReplayView'

const REPLAY = {
  submissionId: 1,
  ruleset: { rulesetId: 'r', version: 1, rules: [] } as never,
  roomId: 'corridor',
  seed: 42,
  floor: 1,
  roomsPerFloor: 5,
  roomIds: ['corridor', 'chapel', 'pillars'],
  loadout: undefined,
  snapshots: [],
  outcome: 'PLAYER_WIN',
  ticks: 10,
  playerHp: 5,
}

const renderBar = (): string =>
  renderToStaticMarkup(<ReplayView replay={REPLAY} onClose={() => undefined} />)

describe('★ 재생 머리줄은 값 묶음과 조작 묶음으로 접힌다', () => {
  it('값 셋이 한 묶음 안에 있다 — 낱개로 접히면 값 사이로 버튼이 끼어든다', () => {
    const html = renderBar()
    const meta = html.indexOf('replay__meta')
    const acts = html.indexOf('replay__acts')
    expect(meta).toBeGreaterThan(-1)
    // 조작 묶음은 값 묶음 뒤다. 값이 열리고 닫힌 뒤에야 버튼이 나온다.
    expect(acts).toBeGreaterThan(meta)
    for (const value of ['방 1 / 3', '시드 42', '그때:']) {
      expect(html.indexOf(value)).toBeGreaterThan(meta)
      expect(html.indexOf(value)).toBeLessThan(acts)
    }
  })

  it('닫기는 조작 묶음 안이다 — 밖에 두면 접힐 때 혼자 떨어져 나간다', () => {
    const html = renderBar()
    expect(html.indexOf('닫기')).toBeGreaterThan(html.indexOf('replay__acts'))
  })

  it('빈 칸을 세워 밀지 않는다 — 접히는 줄에서 빈 칸은 자리를 잡아먹는다', () => {
    // 오른쪽으로 미는 일은 조작 묶음이 맡는다. 빈 칸(`.replay__spacer`)이 남아 있으면
    // 머리줄을 격자로 바꿀 때 그 칸이 한 자리를 차지해 배치가 어긋난다.
    expect(renderBar()).not.toContain('replay__spacer')
  })
})
