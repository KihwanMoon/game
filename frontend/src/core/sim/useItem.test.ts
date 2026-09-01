/**
 * 소모품 사용의 갈래 — 두 코어가 같아야 하는 자리 (G3).
 *
 * **모르는 종류가 포션으로 떨어지던 자리다.** 문지기는 규칙이 가리킨 태그의 개수를 보고
 * (`ruleVm`), 실제로 빼는 것은 포션이었다(`abilities`) — 엉뚱한 소모품이 사라진다.
 * 지금은 블록 파라미터가 둘뿐이라 안 걸리지만, 소모품을 하나 늘리는 순간 걸린다.
 *
 * 파이썬 쪽 같은 검사는 `tests/test_use_tag.py` 다. 한쪽만 고치면 같은 시드가 다른 결과를
 * 내고, 그것이 G3 가 깨지는 실제 경로다.
 */
import { describe, expect, it } from 'vitest'

import { BALANCE, ROOM_TEMPLATES } from '../resources'
import { PLAYER_ENTITY_ID, buildEngine, parseBalance } from '../services/runBattle'
import { createPlannedAction } from './plan'
import { countItem } from './state'

const ITEM_POTION = 'POTION'
const UNKNOWN_KIND = 'BOMB'
const HELD = 2

/**
 * 플레이어 하나가 선 전투를 세운다.
 *
 * @returns 엔진과 플레이어.
 */
function buildProbe() {
  const template = ROOM_TEMPLATES[0]
  if (template === undefined) {
    throw new Error('룸 템플릿이 없다')
  }
  const engine = buildEngine({
    template,
    balance: parseBalance(BALANCE),
    seed: 12345n,
    maxTicks: 10,
    floor: 1,
    snapshots: [],
  })
  const player = engine.state.entities.get(PLAYER_ENTITY_ID)
  if (player === undefined) {
    throw new Error('플레이어가 없다')
  }
  player.consumables.set(ITEM_POTION, HELD)
  player.consumables.set(UNKNOWN_KIND, 1)
  return { engine, player }
}

describe('USE_ITEM 의 종류 갈래', () => {
  it('★ 모르는 종류는 아무것도 안 쓴다 — 포션이 대신 사라지면 안 된다', () => {
    const { engine, player } = buildProbe()
    engine.actions.applyItem(
      player,
      createPlannedAction({
        entityId: player.entityId,
        actionId: 'USE_ITEM',
        itemKind: UNKNOWN_KIND,
      }),
    )
    expect(countItem(player, ITEM_POTION)).toBe(HELD)
    expect(countItem(player, UNKNOWN_KIND)).toBe(1)
  })

  it('★ 아는 종류는 그대로 쓴다 — 문지기가 정상 사용까지 막으면 포션을 못 쓴다', () => {
    const { engine, player } = buildProbe()
    player.hp = 10
    engine.actions.applyItem(
      player,
      createPlannedAction({
        entityId: player.entityId,
        actionId: 'USE_ITEM',
        itemKind: ITEM_POTION,
      }),
    )
    expect(countItem(player, ITEM_POTION)).toBe(HELD - 1)
  })

  it('종류가 없으면 포션으로 본다 — `USE_POTION` 별칭과 저장된 규칙표가 그 길로 온다', () => {
    const { engine, player } = buildProbe()
    player.hp = 10
    engine.actions.applyItem(
      player,
      createPlannedAction({ entityId: player.entityId, actionId: 'USE_POTION' }),
    )
    expect(countItem(player, ITEM_POTION)).toBe(HELD - 1)
  })
})
