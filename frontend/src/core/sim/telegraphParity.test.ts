/**
 * 스킬이 거는 예고가 두 코어에서 같이 도는가 (게이트 G3).
 *
 * **파이썬은 `skills.json` 의 `telegraph` 를 읽어 예고를 건다** (2026-09-09,
 * `blast_actions._build_skill_telegraph`). TS 는 아직 스킬 표를 안 들고 있어
 * (`EngineConfig` 가 속성마다 맵을 따로 갖는다) 그 경로가 없다 — 이식은
 * `설계/1_통합시스템설계` §6 의 H6 다.
 *
 * **지금은 두 코어가 같다.** 어느 스킬도 `telegraph > 0` 이 아니라 양쪽 다 개체 종류가
 * 정하는 예고(자폭형)만 탄다. 그래서 골든이 통과하는데, 그 통과는 **기능이 같아서가
 * 아니라 기능을 안 써서**다.
 *
 * 이 덫은 그 사실이 바뀌는 순간 운다. 마법 셋(H5)이 들어오면 여기서 먼저 걸리고,
 * 그때 TS 경로를 먼저 세워야 한다 — 안 그러면 브라우저에서 돌린 판과 서버가 재시뮬한
 * 판이 갈린다. 방어 태세가 정확히 그렇게 조용히 갈려 있었다.
 */
import { describe, expect, it } from 'vitest'

import skills from '@resources/balance/skills.json'

interface RawSkill {
  readonly id: string
  readonly telegraph?: number
}

describe('스킬 예고 이식', () => {
  it('예고를 쓰는 스킬이 생기면 TS 경로부터 세운다', () => {
    const casting = (skills.skills as RawSkill[])
      .filter((one) => (one.telegraph ?? 0) > 0)
      .map((one) => one.id)
    expect(
      casting,
      `이 스킬들이 예고를 쓴다: ${casting.join(', ')}. 파이썬은 걸고 TS 는 안 건다 — ` +
        'H6(TS 이식)을 먼저 하고 이 덫을 예고 대조로 바꿔라.',
    ).toEqual([])
  })
})
