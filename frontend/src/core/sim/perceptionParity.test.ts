/**
 * 스킬 인지 목록이 카탈로그와 갈리지 않는가 (게이트 G3).
 *
 * **갈리면 키째로 안 만들어진다.** 인지값이 없으면 참도 거짓도 아니라 화면에 「없음」이
 * 뜨고, 그 규칙은 영영 발동하지 않는다 — 실제 신고가 그것이었다 (2026-09-10):
 * `내 스킬 준비됨[CHAIN_BOLT](없음) == 참`. 쿨타임은 다 차 있었다.
 *
 * 파이썬에는 마법 셋이 들어왔는데 이쪽이 안 따라왔었다. **전투는 브라우저에서 돌고
 * 재시뮬은 파이썬이 하므로, 같은 판이 두 코어에서 다르게 돌고 있었다.** 골든이 이
 * 경로를 안 덮는다 — 골든 규칙표 중 마법 인지를 쓰는 것이 하나도 없다.
 *
 * 그래서 목록끼리 대조하지 않고 **양쪽이 같은 정본(`blocks.json`)과 대조한다.** 목록을
 * 서로 비교하면 둘 다 틀렸을 때 통과한다.
 */
import { describe, expect, it } from 'vitest'

import blocksRaw from '@resources/balance/blocks.json'

import { BALANCE, ROOM_TEMPLATES } from '../resources'
import { PLAYER_ENTITY_ID, buildEngine, parseBalance } from '../services/runBattle'
import { buildSnapshot, readSnapshot } from './perception'

/** `blocks.json` 이 정한 `USE_SKILL` 파라미터 — 인지가 만들어야 할 스킬 전량. */
function listCatalogSkills(): readonly string[] {
  const actions = (blocksRaw as { actions: { id: string; param?: { values: string[] } }[] }).actions
  const useSkill = actions.find((one) => one.id === 'USE_SKILL')
  expect(useSkill?.param?.values, 'USE_SKILL 파라미터가 없다').toBeDefined()
  return useSkill?.param?.values ?? []
}

describe('스킬 인지 목록', () => {
  it('★ `USE_SKILL` 이 부를 수 있는 스킬은 전부 인지값을 갖는다', () => {
    const template = ROOM_TEMPLATES.find((one) => one.templateId === 'open_field')
    if (template === undefined) {
      throw new Error('open_field 템플릿이 없다')
    }
    const engine = buildEngine({ template, balance: parseBalance(BALANCE), seed: 3 })
    const player = engine.state.entities.get(PLAYER_ENTITY_ID)
    if (player === undefined) {
      throw new Error('플레이어가 없다')
    }
    const snapshot = buildSnapshot({
      state: engine.state,
      entity: player,
      kindTypes: engine.config.kindTypes,
    })
    for (const skill of listCatalogSkills()) {
      // **`undefined` 가 아니어야 한다.** false 는 「지금은 못 쓴다」이고 `undefined` 는
      // 「그런 질문을 만들지도 않았다」다 — 화면이 「없음」이라 적는 쪽이다.
      expect(readSnapshot(snapshot, 'self_skill_ready', skill), `self_skill_ready[${skill}]`).toBeDefined()
      expect(
        readSnapshot(snapshot, 'self_cooldown_ready', skill),
        `self_cooldown_ready[${skill}]`,
      ).toBeDefined()
      expect(readSnapshot(snapshot, 'self_has_skill', skill), `self_has_skill[${skill}]`).toBeDefined()
    }
  })
})
