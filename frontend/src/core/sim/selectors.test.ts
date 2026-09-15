/**
 * 셀렉터가 대상을 고르는 법 — 특히 **없을 때** 무엇을 하는가.
 *
 * 선호 대상이 없는 방에서 아무것도 안 하는 표가 벤치마크에 다섯 벌 있었고 전부 0% 였다
 * (2026-09-15 실측, 층 생성 120런). 「우선」 셀렉터 셋이 그 자리를 고친다.
 */
import { describe, expect, it } from 'vitest'

import { BALANCE, ROOM_TEMPLATES } from '../resources'
import { buildEngine, parseBalance, PLAYER_ENTITY_ID } from '../services/runBattle'
import {
  SELECTOR_NEAREST,
  SELECTOR_TYPE_SUMMONER,
  SELECTOR_TYPE_SUMMONER_FIRST,
  resolveTarget,
} from './selectors'

describe('「우선」 셀렉터 — 없으면 가장 가까운 것으로 (v15)', () => {
  /** 소환사가 없는 방 하나. 0% 짜리 표들이 죽던 자리다. */
  function buildNoSummoner() {
    const template = ROOM_TEMPLATES.find((one) => one.templateId === 'open_field')
    if (template === undefined) {
      throw new Error('open_field 가 없다')
    }
    const engine = buildEngine({ template, balance: parseBalance(BALANCE), seed: 3 })
    return engine
  }

  it('★ 선호 대상이 없으면 가장 가까운 것으로 떨어진다', () => {
    // **이 한 줄이 벤치마크 두 벌을 0% 에서 48%·30% 로 올렸다** (2026-09-15 실측).
    const engine = buildNoSummoner()
    const actor = engine.state.entities.get(PLAYER_ENTITY_ID)
    expect(actor).toBeDefined()
    if (actor === undefined) {
      return
    }
    const strict = resolveTarget(SELECTOR_TYPE_SUMMONER, actor, engine.state, engine.config.kindTypes)
    const lenient = resolveTarget(
      SELECTOR_TYPE_SUMMONER_FIRST,
      actor,
      engine.state,
      engine.config.kindTypes,
    )
    const nearest = resolveTarget(SELECTOR_NEAREST, actor, engine.state, engine.config.kindTypes)
    expect(strict, '이 방에는 소환사가 없다').toBeUndefined()
    expect(lenient).toBeDefined()
    expect(lenient?.entityId).toBe(nearest?.entityId)
  })

  it('★ 선호 대상이 있으면 그것을 고른다 — 「우선」이 「아무거나」가 되면 안 된다', () => {
    // 후보를 고르는 쪽에서 섞으면 소환사가 있을 때도 가까운 것이 후보에 들어간다.
    const engine = buildNoSummoner()
    const actor = engine.state.entities.get(PLAYER_ENTITY_ID)
    if (actor === undefined) {
      return
    }
    // 가장 가까운 적을 소환사로 바꿔 두면 둘이 같아야 한다.
    const nearest = resolveTarget(SELECTOR_NEAREST, actor, engine.state, engine.config.kindTypes)
    expect(nearest).toBeDefined()
    const kinds = new Map(engine.config.kindTypes)
    for (const [id] of kinds) {
      kinds.set(id, id === nearest?.kindId ? 'SUMMONER' : 'MELEE')
    }
    const picked = resolveTarget(SELECTOR_TYPE_SUMMONER_FIRST, actor, engine.state, kinds)
    expect(picked?.kindId).toBe(nearest?.kindId)
  })
})
