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

import { formatUseEffect } from '../../content/consumableEffects'

import { BALANCE, ROOM_TEMPLATES } from '../resources'
import { PLAYER_ENTITY_ID, buildEngine, parseBalance } from '../services/runBattle'
import { ITEM_POTION, ITEM_SCROLL } from './abilities'
import { SCROLL_RESOLVERS } from './actions'
import { buildSnapshot, readSnapshot } from './perception'

interface RawBlock {
  id: string
  param?: { values: string[] }
}

/** 카탈로그가 정한 파라미터 값들. 없으면 그 자체가 실패다 — 조용히 빈 목록이 되면 안 된다. */
function listCatalogValues(group: 'actions' | 'perceptions', blockId: string): readonly string[] {
  const blocks = (blocksRaw as unknown as Record<string, RawBlock[]>)[group] ?? []
  const found = blocks.find((one) => one.id === blockId)
  expect(found?.param?.values, `${blockId} 파라미터가 없다`).toBeDefined()
  return found?.param?.values ?? []
}

/** 인지 스냅샷 하나. 두 시험이 같은 값을 본다. */
function buildProbeSnapshot() {
  const template = ROOM_TEMPLATES.find((one) => one.templateId === 'open_field')
  if (template === undefined) {
    throw new Error('open_field 템플릿이 없다')
  }
  const engine = buildEngine({ template, balance: parseBalance(BALANCE), seed: 3 })
  const player = engine.state.entities.get(PLAYER_ENTITY_ID)
  if (player === undefined) {
    throw new Error('플레이어가 없다')
  }
  return buildSnapshot({
    state: engine.state,
    entity: player,
    kindTypes: engine.config.kindTypes,
  })
}

describe('스킬 인지 목록', () => {
  it('★ `USE_SKILL` 이 부를 수 있는 스킬은 전부 인지값을 갖는다', () => {
    const snapshot = buildProbeSnapshot()
    for (const skill of listCatalogValues('actions', 'USE_SKILL')) {
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

  it('★ `self_has_status` 가 묻는 상태는 전부 인지값을 갖는다', () => {
    // 스킬에서 겪은 것과 같은 자리다 (2026-09-11). 주문서 겹쳐 쓰기를 규칙표로 피하려면
    // `self_has_status[FOCUS]` 를 물을 수 있어야 하고, 키가 없으면 「없음」이 뜬다.
    const snapshot = buildProbeSnapshot()
    for (const status of listCatalogValues('perceptions', 'self_has_status')) {
      expect(
        readSnapshot(snapshot, 'self_has_status', status),
        `self_has_status[${status}]`,
      ).toBeDefined()
    }
  })
})

describe('소모품 태그 목록', () => {
  it('★ `USE_ITEM` 이 가리키는 태그는 전부 실행기가 안다', () => {
    // 고를 수 있는데 실행기가 모르면 「쓸 줄 모른다 — 틱 낭비」로 떨어진다. 규칙표를 짠
    // 사람에게 그것은 **참인데 아무 일도 안 일어나는 규칙**이다 (P1).
    const known = new Set([ITEM_POTION, ITEM_SCROLL, ...SCROLL_RESOLVERS.keys()])
    for (const tag of listCatalogValues('actions', 'USE_ITEM')) {
      expect(known.has(tag), `실행기가 모르는 태그다: ${tag}`).toBe(true)
    }
  })

  it('★ 그 태그들은 전부 **쓰면 무엇이 되는지** 적을 말이 있다', () => {
    // **안 적히면 고를 근거가 없다** (2026-09-11 요청: 「소모품들 설명 보충해줘」).
    // 이름과 등급만 보이면 「무엇을 들고 갈까」가 찍기가 된다.
    for (const tag of listCatalogValues('actions', 'USE_ITEM')) {
      expect(formatUseEffect(tag), `${tag} 의 사용 효과를 적을 말이 없다`).not.toBe('')
    }
  })
})
